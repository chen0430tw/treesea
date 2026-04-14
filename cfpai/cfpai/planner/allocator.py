from __future__ import annotations

from cfpai.contracts.params import CFPAIParams


def action_map_from_weights(weight_map: dict[str, float]) -> dict[str, float]:
    """将权重映射转换为行动指令。"""
    return {k: float(v) for k, v in weight_map.items()}


def allocate_from_scores(
    ranked_scores: dict[str, float],
    params: CFPAIParams,
) -> dict[str, float]:
    """从排名分数生成资产配置权重。

    选取 top-N 资产（N = params.max_assets），
    按分数归一化，乘以 (1 - cash_floor)。
    """
    sorted_assets = sorted(ranked_scores.items(), key=lambda kv: kv[1], reverse=True)
    chosen = sorted_assets[:params.max_assets]

    total = sum(max(v, 0.0) for _, v in chosen)
    if total < 1e-12:
        return {a: 0.0 for a, _ in chosen}

    scale = max(0.0, 1.0 - params.cash_floor)
    return {a: scale * max(v, 0.0) / total for a, v in chosen}


def compute_rebalance_trades(
    current_weights: dict[str, float],
    target_weights: dict[str, float],
) -> dict[str, float]:
    """计算从当前持仓到目标持仓的调仓量。"""
    all_assets = set(current_weights) | set(target_weights)
    return {
        a: target_weights.get(a, 0.0) - current_weights.get(a, 0.0)
        for a in all_assets
    }
