from __future__ import annotations

import numpy as np

from cfpai.contracts.params import CFPAIParams


def adjusted_candidate_value(
    candidate_score: float,
    persistence_bonus: float = 0.0,
) -> float:
    """调整后的候选值 = 基础分 + 持仓延续性加分。"""
    return float(candidate_score + persistence_bonus)


def compute_node_utility(
    score: float,
    risk: float,
    lambda_risk: float = 0.4,
) -> float:
    """节点效用 = score - lambda_risk * risk。

    Tree Diagram 网格中每个节点的价值评估。
    """
    return float(score - lambda_risk * risk)


def rank_nodes(
    utilities: dict[str, float],
    max_assets: int = 3,
) -> list[tuple[str, float]]:
    """按效用排名，返回 top-N 节点。"""
    return sorted(utilities.items(), key=lambda kv: kv[1], reverse=True)[:max_assets]


def compute_grid_entropy(weights: dict[str, float]) -> float:
    """计算权重分布的熵（衡量分散程度）。

    高熵 = 均匀分散，低熵 = 集中。
    """
    vals = np.array([v for v in weights.values() if v > 0], dtype=float)
    if len(vals) == 0 or vals.sum() < 1e-12:
        return 0.0
    p = vals / vals.sum()
    return float(-np.sum(p * np.log2(p + 1e-12)))
