from __future__ import annotations
import time
from typing import Optional

from ..core.problem_seed import ProblemSeed, default_seed
from ..numerics.forcing import GridConfig
from ..core.oracle_output import oracle_summary_numerical
from ..io.oracle_schema import TreeOutputBundle
from ..pipeline.candidate_pipeline import CandidatePipeline


class TreeDiagramRunner:
    def __init__(
        self,
        cfg: Optional[GridConfig] = None,
        seed: Optional[ProblemSeed] = None,
        top_k: int = 12,
        n_workers: int = 1,
        mode: str = "integrated",
        device: Optional[str] = None,
    ) -> None:
        self.cfg      = cfg if cfg is not None else GridConfig()
        self.seed     = seed if seed is not None else default_seed()
        self.top_k    = top_k
        self.n_workers = n_workers
        self.mode     = mode
        self.device   = device  # None = auto (cuda if available, else cpu)

    def run(self) -> TreeOutputBundle:
        t0 = time.time()

        # Grid dimensions derived from cfg
        NX    = max(28, self.cfg.NX // 4)
        NY    = max(21, self.cfg.NY // 4)
        steps = max(20, self.cfg.STEPS // 6)
        dt    = float(self.cfg.DT)

        pipeline = CandidatePipeline(
            seed=self.seed,
            top_k=self.top_k,
            n_workers=self.n_workers,
            NX=NX, NY=NY, steps=steps, dt=dt,
            device=self.device,
        )
        top_results, hydro, abstract_oracle = pipeline.run()

        best_worldline = abstract_oracle.get("best_worldline", {})

        return TreeOutputBundle(
            seed_title=self.seed.title,
            mode="integrated",
            best_worldline=best_worldline,
            hydro_control=hydro,
            branch_histogram=abstract_oracle.get("branch_histogram", {}),
            oracle_details=abstract_oracle,
            elapsed_sec=time.time() - t0,
        )
