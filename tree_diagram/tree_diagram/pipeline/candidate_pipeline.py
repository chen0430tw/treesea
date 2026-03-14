from __future__ import annotations
import multiprocessing
from typing import List, Optional, Tuple

from ..core.problem_seed import ProblemSeed, default_seed
from ..core.background_inference import ProblemBackground, infer_problem_background
from ..core.group_field import encode_group_field
from ..core.worldline_kernel import (
    CandidateWorldline,
    EvaluationResult,
    generate_worldlines,
    evaluate_worldline,
)
from ..core.branch_ecology import compress_to_main_branches
from ..core.balance_layer import hydro_adjust_abstract
from ..core.oracle_output import oracle_summary_abstract


def _eval_task(args: tuple) -> EvaluationResult:
    seed_dict, field, worldline = args
    seed = ProblemSeed.from_dict(seed_dict)
    return evaluate_worldline(seed, field, worldline)


class CandidatePipeline:
    def __init__(
        self,
        seed: Optional[ProblemSeed] = None,
        top_k: int = 12,
        n_workers: int = 1,
    ) -> None:
        self.seed = seed if seed is not None else default_seed()
        self.top_k = top_k
        self.n_workers = n_workers

    def run(self) -> Tuple[List[EvaluationResult], dict, dict]:
        seed = self.seed

        # Stage 1: background inference
        bg: ProblemBackground = infer_problem_background(seed)

        # Stage 2: encode group field
        field = encode_group_field(seed)

        # Stage 3: generate worldlines
        worldlines: List[CandidateWorldline] = generate_worldlines(seed, bg)

        # Stage 4: evaluate (parallel if n_workers > 1)
        seed_dict = seed.to_dict()
        tasks = [(seed_dict, field, w) for w in worldlines]

        if self.n_workers > 1:
            with multiprocessing.Pool(processes=self.n_workers) as pool:
                all_results: List[EvaluationResult] = pool.map(_eval_task, tasks)
        else:
            all_results = [_eval_task(t) for t in tasks]

        # Stage 5: compress to top-k
        top_results = compress_to_main_branches(all_results, top_k=self.top_k)

        # Stage 6: hydro adjustment
        abstract_hydro = hydro_adjust_abstract(top_results)

        # Stage 7: oracle summary
        abstract_oracle = oracle_summary_abstract(seed, bg, field, top_results, abstract_hydro)

        return top_results, abstract_hydro, abstract_oracle
