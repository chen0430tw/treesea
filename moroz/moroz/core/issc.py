"""ISSC — In-Situ Semantic Collapse.

职责：原地生成、前缀过滤、上界评估、本地评分、局部丢弃、收缩监测。
不管候选从哪来。对位迁移自 archive/uploads/MOROZ代码.txt。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .types import Candidate, SearchMetrics


@dataclass
class ISSCStats:
    entropy: float          # H: 分布多样性
    top_q_coverage: float   # C_q: Top-q 概率质量
    retention_ratio: float  # R: accepted / total_seen
    theta_eff: float        # Theta_eff: accepted / elapsed_seconds


@dataclass
class ISSCResult:
    ranked: list[tuple[float, Candidate]]
    stats: ISSCStats


class ISSC:
    def __init__(self, q: int = 5) -> None:
        self.q = q

    def collapse(
        self,
        ranked: Sequence[tuple[float, Candidate]],
        metrics: SearchMetrics,
        elapsed_seconds: float,
    ) -> ISSCResult:
        """对 ranked 候选做收缩统计封装，输出 collapse stats。"""
        if not ranked:
            return ISSCResult(
                ranked=[],
                stats=ISSCStats(
                    entropy=0.0, top_q_coverage=0.0,
                    retention_ratio=0.0, theta_eff=0.0,
                ),
            )

        weights = [max(score, 0.0) for score, _ in ranked]
        s = sum(weights)
        probs = [w / s for w in weights] if s > 0 else [0.0] * len(weights)

        entropy = -sum(p * math.log(p) for p in probs if p > 0)
        top_q = sum(probs[: min(self.q, len(probs))])

        total_seen = (
            metrics.expanded
            + metrics.reject_prefix
            + metrics.reject_full
            + metrics.reject_structure
            + metrics.reject_bound
            + metrics.accepted
        )
        retention_ratio = (metrics.accepted / total_seen) if total_seen > 0 else 0.0
        theta_eff = (metrics.accepted / elapsed_seconds) if elapsed_seconds > 0 else 0.0

        return ISSCResult(
            ranked=list(ranked),
            stats=ISSCStats(
                entropy=entropy,
                top_q_coverage=top_q,
                retention_ratio=retention_ratio,
                theta_eff=theta_eff,
            ),
        )
