"""MOROZ-Core 指标计算辅助函数。"""
from __future__ import annotations

import math
from typing import Sequence

from .types import Candidate, SearchMetrics


def entropy(weights: Sequence[float]) -> float:
    """Shannon 熵。"""
    s = sum(weights)
    if s <= 0:
        return 0.0
    probs = [w / s for w in weights if w > 0]
    return -sum(p * math.log(p) for p in probs)


def top_q_coverage(weights: Sequence[float], q: int = 5) -> float:
    """Top-q 概率质量覆盖率。"""
    s = sum(weights)
    if s <= 0:
        return 0.0
    probs = sorted([w / s for w in weights], reverse=True)
    return sum(probs[:q])


def retention_ratio(metrics: SearchMetrics) -> float:
    """保留率 = accepted / total_seen。"""
    total = (
        metrics.expanded
        + metrics.reject_prefix
        + metrics.reject_full
        + metrics.reject_structure
        + metrics.reject_bound
        + metrics.accepted
    )
    return (metrics.accepted / total) if total > 0 else 0.0


def effective_throughput(metrics: SearchMetrics, elapsed: float) -> float:
    """有效吞吐 = accepted / elapsed_seconds。"""
    return (metrics.accepted / elapsed) if elapsed > 0 else 0.0
