from __future__ import annotations
from typing import Dict, List

from .worldline_kernel import EvaluationResult


def compress_to_main_branches(
    results: List[EvaluationResult],
    top_k: int = 12,
) -> List[EvaluationResult]:
    return sorted(results, key=lambda x: x.balanced_score, reverse=True)[:top_k]


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
