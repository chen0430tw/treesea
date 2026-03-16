from __future__ import annotations

"""runtime/multi_node_runner.py

Multi-node entry point for Tree Diagram (MPI dispatch).

Architecture position:
  runtime layer — wraps distributed/mpi_adapter.MPIEnsembleRunner for
  multi-node execution.  Partitions the candidate set across MPI ranks
  and gathers results back to rank 0.

For single-node execution, prefer single_node_runner.py.
"""

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..core.problem_seed import ProblemSeed, default_seed
from ..core.background_inference import infer_problem_background
from ..core.group_field import encode_group_field
from ..core.worldline_kernel import (
    EvaluationResult,
    generate_candidates,
    prepare_candidate_arrays,
    encode_initial_state,
    unified_rollout,
    score_candidates,
    classify_relative,
    td_hydro_control,
    DX,
    DY,
)
from ..core.oracle_output import oracle_summary_abstract
from ..distributed.mpi_adapter import MPIEnsembleRunner
from ..io.oracle_schema import TreeOutputBundle


@dataclass
class MultiNodeConfig:
    """Configuration for multi-node runs."""
    top_k:     int   = 12
    NX:        int   = 28
    NY:        int   = 21
    steps:     int   = 20
    dt:        float = 45.0
    n_workers: int   = 1     # fallback thread pool workers per node


class MultiNodeRunner:
    """Run Tree Diagram across multiple MPI nodes.

    On a single-node system (or without mpi4py), falls back to the
    multiprocessing pool or serial execution.

    Usage::

        runner = MultiNodeRunner(n_workers=8)
        bundle = runner.run()
    """

    def __init__(
        self,
        cfg:  Optional[MultiNodeConfig] = None,
        seed: Optional[ProblemSeed] = None,
        n_workers: int = 1,
    ) -> None:
        self.cfg       = cfg  if cfg  is not None else MultiNodeConfig(n_workers=n_workers)
        self.seed      = seed if seed is not None else default_seed()
        self._mpi      = MPIEnsembleRunner(n_workers=self.cfg.n_workers)

    def run(self) -> TreeOutputBundle:
        """Execute multi-node pipeline and return TreeOutputBundle."""
        t0  = time.time()
        c   = self.cfg
        seed = self.seed
        bg   = infer_problem_background(seed)
        field = encode_group_field(seed)

        # Generate full candidate list
        candidates = generate_candidates(seed, bg)

        # Distribute simulation across nodes via MPI
        def _simulate_batch(batch: List[Dict]) -> List[Dict]:
            """Simulate a batch of candidates and return scored results."""
            import numpy as np
            carr  = prepare_candidate_arrays(batch)
            state = encode_initial_state(seed, batch, c.NX, c.NY)
            final = unified_rollout(state, carr, c.dt, DX, DY, c.steps)
            scores = score_candidates(final, carr, seed)
            statuses = classify_relative(scores)
            results = []
            for i, cand in enumerate(batch):
                results.append({
                    "candidate": cand,
                    "score":     float(scores[i]),
                    "status":    statuses[i],
                    "phase":     float(final.phase[i]),
                    "stress":    float(final.stress[i]),
                    "instab":    float(final.instability[i]),
                })
            return results

        # Chunk candidates for MPI distribution
        chunk_size = max(1, len(candidates) // max(1, self._mpi.n_workers))
        chunks: List[List[Dict]] = []
        for i in range(0, len(candidates), chunk_size):
            chunks.append(candidates[i:i + chunk_size])

        all_chunk_results = self._mpi.run(chunks, _simulate_batch)

        # Flatten
        flat: List[Dict] = []
        for chunk_res in all_chunk_results:
            flat.extend(chunk_res)

        # Sort and build top_k EvaluationResult
        flat.sort(key=lambda x: x["score"], reverse=True)
        top_k = c.top_k
        scores_arr: List[float] = [x["score"] for x in flat]

        import numpy as np
        scores_np = np.array(scores_arr)
        hydro = td_hydro_control(scores_np)

        top_results: List[EvaluationResult] = []
        for item in flat[:top_k]:
            cand = item["candidate"]
            p    = cand["params"]
            ph   = item["phase"]
            st   = item["stress"]
            ins  = item["instab"]
            sc   = item["score"]
            A    = float(p.get("A", 0.7))
            rho  = float(p.get("rho", 0.7))
            sig  = float(p.get("sigma", 0.05))

            from ..core.worldline_kernel import EvaluationResult
            top_results.append(EvaluationResult(
                family=cand["family"],
                template=cand["template"],
                params={k: p[k] for k in ("n", "rho", "A", "sigma") if k in p},
                feasibility=float(np.clip(0.35 * ph + 0.25 * (1 - st) + 0.20 * A * (0.55 + 0.45 * rho) + 0.20 * (1 - sig * 10), 0, 1)),
                stability=float(np.clip(0.40 * (1 - ins) + 0.30 * (1 - st) + 0.30 * (1 - min(sig * 5, 1.0)), 0, 1)),
                field_fit=float(np.clip(0.40 * ph + 0.35 * sc + 0.25 * A, 0, 1)),
                risk=float(np.clip(0.45 * st + 0.35 * ins + 0.20 * min(sig * 5, 1.0), 0, 1)),
                balanced_score=sc,
                nutrient_gain=float(np.clip(A * rho * (1 - sig), 0, 1)),
                branch_status=item["status"],
                weather_score=sc,
                weather_alignment=ph,
                final_balanced_score=sc,
            ))

        abstract_oracle = oracle_summary_abstract(seed, bg, field, top_results, hydro)
        elapsed = time.time() - t0

        return TreeOutputBundle(
            seed_title=seed.title,
            mode="integrated",
            best_worldline=abstract_oracle.get("best_worldline", {}),
            hydro_control=hydro,
            branch_histogram=abstract_oracle.get("branch_histogram", {}),
            oracle_details=abstract_oracle,
            elapsed_sec=elapsed,
        )
