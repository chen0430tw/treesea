from __future__ import annotations
from dataclasses import asdict
from typing import List, Optional, Tuple

from ..core.problem_seed import ProblemSeed, default_seed
from ..core.background_inference import ProblemBackground, infer_problem_background
from ..core.group_field import encode_group_field
from ..core.worldline_kernel import EvaluationResult, run_tree_diagram
from ..core.oracle_output import oracle_summary_abstract
from ..core.umdst_kernel import Metrics, TDOutputs
from ..core.cbf_balancer import aggregate_cbf
from ..core.ipl_phase_indexer import (
    IPLPhaseIndexer, build_ipl_index,
    zone_summary, smoothed_gain_centroid, phase_spread,
)
from ..vein.tri_vein_kernel import compute_tri_vein_batch, pareto_front, tri_vein_stats
from ..vein.veinlet_experts import VeinletEnsemble
from ..vein.vein_backbone import VeinBackbone
from ..control.utm_hydrology_controller import UTMHydrologyController
from ..oracle.report_builder import ReportBuilder
from ..llm_bridge.explanation_layer import ExplanationLayer


class CandidatePipeline:
    def __init__(
        self,
        seed: Optional[ProblemSeed] = None,
        top_k: int = 12,
        n_workers: int = 1,
        NX: int = 128,
        NY: int = 96,
        steps: int = 300,
        dt: float = 45.0,
        device: Optional[str] = None,
        # Legacy params accepted but unused
        full_eval: bool = False,
        weather_cfg=None,
    ) -> None:
        self.seed     = seed if seed is not None else default_seed()
        self.top_k    = top_k
        self.n_workers = n_workers
        self.NX       = NX
        self.NY       = NY
        self.steps    = steps
        self.dt       = dt
        self.device   = device  # None = auto (cuda if available, else cpu)

    def run(self) -> Tuple[List[EvaluationResult], dict, dict]:
        seed  = self.seed
        bg    = infer_problem_background(seed)
        field = encode_group_field(seed)

        # ── IPL Layer (Layer 2): seed-level phase zone routing (pre-eval) ────
        ipl_seed = IPLPhaseIndexer(seed, bg).build_index()
        # ────────────────────────────────────────────────────────────────────

        top_results, hydro = run_tree_diagram(
            seed, bg,
            NX=self.NX, NY=self.NY,
            steps=self.steps, top_k=self.top_k, dt=self.dt,
            device=self.device,
        )

        # Add seed IPL to hydro (routing context for oracle/report consumers)
        hydro["ipl_seed"] = ipl_seed

        # ── IPL Layer (Layer 2): post-eval index over evaluated candidates ───
        td_list = [
            TDOutputs(
                riskfield=[r.risk],
                curve=[r.field_fit, r.feasibility],
                graph=[],
                samples={},
                meta={"phase_final": r.balanced_score, "phase_max": r.field_fit},
            )
            for r in top_results
        ]
        path_ids  = [f"{r.family}/{r.template}" for r in top_results]
        ipl_index = build_ipl_index(path_ids, td_list)
        zs        = zone_summary(ipl_index)
        hydro["ipl_index"] = {
            "zone_summary":            zs,
            "smoothed_gain_centroid":  smoothed_gain_centroid(ipl_index),
            "phase_spread":            phase_spread(ipl_index),
            "top_zone":                max(zs, key=zs.get) if zs else "stable",
        }
        # ────────────────────────────────────────────────────────────────────

        # ── CBF Balance Layer (Layer 5): zero-net-drive balance ──────────────
        cbf_metrics = [
            Metrics(
                e_cons_mean    = r.risk,
                impact_peak    = r.nutrient_gain,
                variance_proxy = max(0.0, 1.0 - r.stability),
                disagree_proxy = max(0.0, 1.0 - r.feasibility),
                ood_proxy      = r.risk,
                p_blow_max     = r.risk,
                phase_max      = r.field_fit,
                phase_final    = r.balanced_score,
                repeatability  = r.stability,
            )
            for r in top_results
        ]
        hydro["cbf_allocation"] = aggregate_cbf(cbf_metrics, {})
        # ────────────────────────────────────────────────────────────────────

        # ── Vein layer: tri-channel scoring + family-expert re-ranking ──────
        tri_scores    = compute_tri_vein_batch(top_results)
        ensemble      = VeinletEnsemble()
        expert_scores = ensemble.score_all(tri_scores)

        # Re-rank by expert-adjusted composite score
        paired = sorted(
            zip(top_results, expert_scores),
            key=lambda x: x[1].adjusted,
            reverse=True,
        )
        top_results = [r for r, _ in paired]

        # Write expert-adjusted score back into final_balanced_score
        for r, es in zip(top_results, [e for _, e in paired]):
            r.final_balanced_score = round(es.adjusted, 6)

        # Backbone: low-rank diversity-aware branch summary
        backbone = VeinBackbone.from_results(top_results, top_k=min(8, len(top_results)))
        hydro["vein_backbone"] = backbone.to_dict()
        hydro["vein_stats"]    = tri_vein_stats(tri_scores)
        hydro["vein_pareto_size"] = len(pareto_front(tri_scores))
        # ────────────────────────────────────────────────────────────────────

        # ── H-UTM Hydro Control Layer (Layer 8): main-channel stability ─────
        utm_ctrl = UTMHydrologyController()
        utm_adj  = utm_ctrl.adjust(top_results, step=self.steps)
        hydro["utm_hydro_state"]    = utm_adj.hydro_state
        hydro["utm_state"]          = utm_adj.utm_state
        hydro["utm_main_channel_k"] = len(utm_adj.main_channel_ids)
        hydro.update(utm_adj.merged_hydro)
        # ────────────────────────────────────────────────────────────────────

        abstract_oracle = oracle_summary_abstract(seed, bg, field, top_results, hydro)

        # ── LLM Bridge (Layer 10): explanation layer for outer loop ──────────
        report = ReportBuilder().build_from_dict(abstract_oracle)
        exp    = ExplanationLayer().explain(report)
        abstract_oracle["llm_explanation"] = asdict(exp)
        # ────────────────────────────────────────────────────────────────────

        return top_results, hydro, abstract_oracle
