from __future__ import annotations
from typing import Dict, List

from .worldline_kernel import EvaluationResult


def compress_to_main_branches(
    results: List[EvaluationResult],
    top_k: int = 12,
) -> List[EvaluationResult]:
    """Return top-k worldlines, keeping at most one entry per (family, n) pair.

    Within each (family, n) group only the best-scoring representative survives.
    This prevents parameter sweeps over rho/A/sigma from flooding the ranking
    with variations of the same plan.
    """
    # Best representative per (family, n)
    best: Dict[tuple, EvaluationResult] = {}
    for r in results:
        key = (r.family, r.params.get("n"))
        if key not in best or r.balanced_score > best[key].balanced_score:
            best[key] = r
    return sorted(best.values(), key=lambda x: x.balanced_score, reverse=True)[:top_k]


def branch_status_histogram(results: List[EvaluationResult]) -> Dict[str, int]:
    histogram: Dict[str, int] = {
        "active": 0,
        "restricted": 0,
        "starved": 0,
        "withered": 0,
    }
    for r in results:
        status = r.branch_status
        if status in histogram:
            histogram[status] += 1
        else:
            histogram[status] = 1
    return histogram
