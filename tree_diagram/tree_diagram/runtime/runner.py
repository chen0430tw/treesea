from __future__ import annotations
import time
from typing import Optional

from ..core.problem_seed import ProblemSeed, default_seed
from ..numerics.forcing import GridConfig
from ..core.balance_layer import merge_hydro
from ..core.oracle_output import merge_oracle, oracle_summary_numerical
from ..io.oracle_schema import TreeOutputBundle
from ..pipeline.candidate_pipeline import CandidatePipeline
from ..pipeline.oracle_pipeline import WeatherOraclePipeline


class TreeDiagramRunner:
    def __init__(
        self,
        cfg: Optional[GridConfig] = None,
        seed: Optional[ProblemSeed] = None,
        top_k: int = 12,
        n_workers: int = 1,
        mode: str = "integrated",
    ) -> None:
        self.cfg = cfg if cfg is not None else GridConfig()
        self.seed = seed if seed is not None else default_seed()
        self.top_k = top_k
        self.n_workers = n_workers
        self.mode = mode

    def run(self) -> TreeOutputBundle:
        t0 = time.time()

        if self.mode == "candidate":
            return self._run_candidate(t0)
        elif self.mode == "weather":
            return self._run_weather(t0)
        else:
            return self._run_integrated(t0)

    # ------------------------------------------------------------------
    def _run_candidate(self, t0: float) -> TreeOutputBundle:
        pipeline = CandidatePipeline(
            seed=self.seed,
            top_k=self.top_k,
            n_workers=self.n_workers,
        )
        top_results, abstract_hydro, abstract_oracle = pipeline.run()

        best_worldline = abstract_oracle.get("best_worldline", {})

        return TreeOutputBundle(
            seed_title=self.seed.title,
            mode="candidate",
            best_worldline=best_worldline,
            hydro_control=abstract_hydro,
            branch_histogram=abstract_oracle.get("branch_histogram", {}),
            oracle_details=abstract_oracle,
            elapsed_sec=time.time() - t0,
        )

    # ------------------------------------------------------------------
    def _run_weather(self, t0: float) -> TreeOutputBundle:
        pipeline = WeatherOraclePipeline(cfg=self.cfg, n_workers=self.n_workers)
        states, metrics, numerical_hydro = pipeline.run(pressure_balance=1.0)

        best_name = metrics[0]["name"] if metrics else ""
        numerical_oracle = oracle_summary_numerical(metrics, numerical_hydro, best_name)

        branch_histogram = numerical_oracle.get("branch_histogram", {})
        best_weather = numerical_oracle.get("best_branch_metric", {})

        return TreeOutputBundle(
            seed_title=self.seed.title,
            mode="weather",
            best_worldline=best_weather,
            hydro_control=numerical_hydro,
            branch_histogram=branch_histogram,
            oracle_details=numerical_oracle,
            elapsed_sec=time.time() - t0,
        )

    # ------------------------------------------------------------------
    def _run_integrated(self, t0: float) -> TreeOutputBundle:
        # Stage 1: candidate pipeline
        cand_pipeline = CandidatePipeline(
            seed=self.seed,
            top_k=self.top_k,
            n_workers=self.n_workers,
        )
        top_results, abstract_hydro, abstract_oracle = cand_pipeline.run()

        # Extract pressure_balance from abstract hydro to feed into weather stage
        pressure_balance = abstract_hydro.get("pressure_balance", 1.0)
        # Clamp to a reasonable range for numerical stability
        pressure_balance = max(0.5, min(1.5, pressure_balance))

        # Stage 2: weather oracle pipeline
        oracle_pipeline = WeatherOraclePipeline(cfg=self.cfg, n_workers=self.n_workers)
        states, metrics, numerical_hydro = oracle_pipeline.run(pressure_balance=pressure_balance)

        best_name = metrics[0]["name"] if metrics else ""
        numerical_oracle = oracle_summary_numerical(metrics, numerical_hydro, best_name)

        # Merge hydro
        merged_hydro = merge_hydro(abstract_hydro, numerical_hydro)

        # Merge oracle
        merged_oracle = merge_oracle(abstract_oracle, numerical_oracle)

        best_worldline = abstract_oracle.get("best_worldline", {})

        branch_histogram = merged_oracle.get("abstract_branch_histogram", {})
        weather_histogram = merged_oracle.get("weather_branch_histogram", {})
        combined_histogram = dict(branch_histogram)
        for k, v in weather_histogram.items():
            key = f"weather_{k}"
            combined_histogram[key] = v

        return TreeOutputBundle(
            seed_title=self.seed.title,
            mode="integrated",
            best_worldline=best_worldline,
            hydro_control=merged_hydro,
            branch_histogram=combined_histogram,
            oracle_details=merged_oracle,
            elapsed_sec=time.time() - t0,
        )
