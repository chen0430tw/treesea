from __future__ import annotations

import numpy as np


def compute_budget_from_weights(weight_map: dict[str, float]) -> float:
    """计算剩余风险预算。

    risk_budget = 1 - max_single_weight
    越集中在单一资产，风险预算越低。
    """
    if not weight_map:
        return 1.0
    return float(max(0.0, 1.0 - max(weight_map.values(), default=0.0)))


def compute_hhi(weight_map: dict[str, float]) -> float:
    """计算 Herfindahl-Hirschman Index（集中度指标）。

    HHI = sum(w_i^2)
    范围 [1/N, 1]，越高越集中。
    """
    weights = [v for v in weight_map.values() if v > 0]
    if not weights:
        return 0.0
    return float(sum(w ** 2 for w in weights))


def compute_risk_parity_target(
    vol_map: dict[str, float],
    total_risk: float = 1.0,
) -> dict[str, float]:
    """简单风险平价：按波动率倒数分配权重。

    每个资产承担相等的风险贡献。
    """
    if not vol_map:
        return {}
    inv_vols = {a: 1.0 / max(v, 1e-8) for a, v in vol_map.items()}
    total = sum(inv_vols.values())
    return {a: total_risk * iv / total for a, iv in inv_vols.items()}
