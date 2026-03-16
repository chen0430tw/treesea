from __future__ import annotations
from typing import List, Optional, Tuple

from ..core.problem_seed import ProblemSeed, default_seed
from ..core.background_inference import ProblemBackground, infer_problem_background
from ..core.group_field import encode_group_field
from ..core.worldline_kernel import EvaluationResult, run_tree_diagram
from ..core.oracle_output import oracle_summary_abstract


class CandidatePipeline:
    def __init__(
        self,
        seed: Optional[ProblemSeed] = None,
        top_k: int = 12,
        n_workers: int = 1,
        NX: int = 28,
        NY: int = 21,
        steps: int = 20,
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
        seed = self.seed
        bg   = infer_problem_background(seed)
        field = encode_group_field(seed)

        top_results, hydro = run_tree_diagram(
            seed, bg,
            NX=self.NX, NY=self.NY,
            steps=self.steps, top_k=self.top_k, dt=self.dt,
            device=self.device,
        )

        abstract_oracle = oracle_summary_abstract(seed, bg, field, top_results, hydro)
        return top_results, hydro, abstract_oracle
