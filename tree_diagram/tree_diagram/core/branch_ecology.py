from __future__ import annotations
from typing import Dict, List, Tuple

from .worldline_kernel import EvaluationResult

_RESOURCE_WEIGHTS: Dict[str, float] = {
    "active": 1.00, "restricted": 0.60, "starved": 0.20, "withered": 0.00,
}


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


def prune_withered(
    results: List[EvaluationResult],
) -> Tuple[List[EvaluationResult], int]:
    """Remove withered branches from the pool.

    Returns (surviving_results, pruned_count).
    Withered branches have compute_weight=0 in the Angio model — they receive
    no further resources and are excluded from downstream oracle processing.
    """
    surviving = [r for r in results if r.branch_status != "withered"]
    pruned    = len(results) - len(surviving)
    return surviving, pruned


def reflow_summary(results: List[EvaluationResult]) -> Dict[str, float]:
    """Summarise fractional resource distribution across the branch pool.

    Returns per-status weight fraction (sums to 1.0).
    Useful for hydro pressure diagnostics.
    """
    total = sum(_RESOURCE_WEIGHTS.get(r.branch_status, 0.0) for r in results)
    if total < 1e-12:
        return {"active": 0.0, "restricted": 0.0, "starved": 0.0, "withered": 0.0}
    by_status: Dict[str, float] = {}
    for r in results:
        s = r.branch_status
        by_status[s] = by_status.get(s, 0.0) + _RESOURCE_WEIGHTS.get(s, 0.0)
    return {k: round(v / total, 4) for k, v in by_status.items()}


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
