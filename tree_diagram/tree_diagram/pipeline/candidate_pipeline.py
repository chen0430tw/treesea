from __future__ import annotations
from dataclasses import asdict
from typing import List, Optional, Tuple

from ..core.problem_seed import ProblemSeed, default_seed
from ..core.background_inference import ProblemBackground, infer_problem_background
from ..core.group_field import encode_group_field
from ..core.worldline_kernel import EvaluationResult, run_tree_diagram
from ..core.oracle_output import oracle_summary_abstract
from ..core.seed_normalizer import normalize_seed
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
        # Seed-normalisation overrides (see tree_diagram/core/seed_normalizer.py)
        field_aliases: Optional[dict] = None,
        merge_policy: str = "mean",
        fill_missing_with_neutral: bool = False,
        neutral_value: float = 0.5,
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
        # Seed-normalisation knobs. field_aliases supplies explicit
        # {custom_name: (section, kernel_field)} when users don't want
        # to rely on semantic routing.
        self.field_aliases = field_aliases or {}
        self.merge_policy  = merge_policy
        self.fill_missing_with_neutral = fill_missing_with_neutral
        self.neutral_value = neutral_value

    def run(self) -> Tuple[List[EvaluationResult], dict, dict]:
        # Seed normalisation — map any custom subject/environment/resource
        # fields the user passed into the canonical kernel schema before
        # background inference. Without this, novel field names (e.g.
        # "cognitive_load" instead of "stress_level") are silently ignored.
        # Resolution order inside normalize_seed:
        #   1. passthrough if name is already canonical
        #   2. explicit alias from self.field_aliases
        #   3. semantic keyword routing (SEMANTIC_ROUTES)
        seed, seed_trace = normalize_seed(
            self.seed,
            field_aliases=self.field_aliases,
            merge_policy=self.merge_policy,
            fill_missing_with_neutral=self.fill_missing_with_neutral,
            neutral_value=self.neutral_value,
        )
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

        # Expose normalisation trace so callers can audit which custom
        # seed fields were routed / aliased / unmatched.
        hydro["seed_normalisation"] = {
            "preserved":  seed_trace.preserved,
            "aliased":    seed_trace.aliased,
            "routed":     seed_trace.routed,
            "unmatched":  seed_trace.unmatched,
        }

        # Add seed IPL to hydro (routing context for oracle/report consumers)
        hydro["ipl_seed"] = ipl_seed

        # ── IPL Layer (Layer 2): post-eval index over evaluated candidates ───
        # EvaluationResult now carries REAL breakdown components after the
        # worldline_kernel refactor (2026-04-20):
        #   r.feasibility = phase_final      ∈ [0,1] high=good
        #   r.stability   = repeatability    ∈ [0,1] high=good
        #   r.field_fit   = 1/(1+e_cons)     ∈ [0,1] high=good
        #   r.risk        = p_blow           ∈ [0,1] high=danger
        # classify_phase_zone expects "high = danger" in phase_final/phase_max,
        # so we invert the healthy metrics here (1 - feasibility etc.) and take
        # the max with p_blow to get a composite danger signal.
        td_list = [
            TDOutputs(
                riskfield=[r.risk],
                curve=[r.field_fit, r.feasibility],
                graph=[],
                samples={},
                meta={
                    "balanced_score": r.balanced_score,
                    "phase_final":    max(float(r.risk),
                                           1.0 - float(r.feasibility)),
                    "phase_max":      max(float(r.risk),
                                           1.0 - float(r.field_fit)),
                    "stability":      r.stability,
                    "p_blow":         r.risk,
                },
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
        # Same "high = danger" alignment as td_list. e_cons_mean now maps to
        # (1 - field_fit): field_fit = 1/(1+e_cons) so (1-field_fit) is a
        # monotone "high = bad-fit" signal bounded in [0, 1].
        cbf_metrics = [
            Metrics(
                e_cons_mean    = max(0.0, 1.0 - float(r.field_fit)),
                impact_peak    = r.nutrient_gain,
                variance_proxy = max(0.0, 1.0 - float(r.stability)),
                disagree_proxy = max(0.0, 1.0 - float(r.feasibility)),
                ood_proxy      = float(r.risk),
                p_blow_max     = float(r.risk),
                phase_max      = max(float(r.risk),
                                     1.0 - float(r.field_fit)),
                phase_final    = max(float(r.risk),
                                     1.0 - float(r.feasibility)),
                repeatability  = float(r.stability),
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
        # Previously called with only (top_results, step), so UTM internally
        # fell back to hydro_adjust_numerical([]) → default pb=1.0 and
        # utm_p_blow=0.0. That pinned UTM to FLOW + NORMAL regardless of
        # problem severity. Feed it real signals from this run.
        metrics_list_for_utm = [
            {"score": r.balanced_score,
             "instability": max(0.0, 1.0 - r.stability)}
            for r in top_results
        ]
        utm_p_blow_value = float(
            hydro.get("cbf_allocation", {}).get("mean_p_blow", 0.0)
        )
        utm_adj  = utm_ctrl.adjust(
            top_results,
            metrics_list=metrics_list_for_utm,
            utm_p_blow=utm_p_blow_value,
            step=self.steps,
        )
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
