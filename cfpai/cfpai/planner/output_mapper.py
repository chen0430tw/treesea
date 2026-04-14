from __future__ import annotations

import numpy as np
import pandas as pd

from cfpai.planner.risk_budget import compute_budget_from_weights, compute_hhi


def build_planning_snapshot(path_df: pd.DataFrame, weights: pd.DataFrame) -> dict:
    if len(path_df) == 0 or len(weights) == 0:
        return {
            "market_label": "unknown",
            "risk_signal": _make_risk_signal("unknown", 0.0, 0.0, 0.0),
            "selected_paths": [],
            "actions": {},
            "risk_budget": None,
        }

    latest_path = path_df.iloc[-1]
    latest_weights = weights.iloc[-1].to_dict()
    latest_weights.pop("Date", None)

    budget = compute_budget_from_weights(latest_weights)
    hhi = compute_hhi(latest_weights)
    total_exposure = sum(v for v in latest_weights.values())

    label = _classify_market(total_exposure, hhi, budget)
    risk_signal = _make_risk_signal(label, total_exposure, hhi, budget)

    return {
        "market_label": label,
        "risk_signal": risk_signal,
        "selected_paths": [latest_path["path"]],
        "actions": latest_weights,
        "risk_budget": float(max(0.0, budget)),
    }


def _classify_market(
    total_exposure: float,
    hhi: float,
    budget: float,
) -> str:
    """
    市场风险分级（四灯制）：

      green  — 低风险：分散持仓，充足预算
      yellow — 中风险：适度集中或预算偏低
      red    — 高风险：高度集中或满仓
      purple — 极高风险/紧急：满仓+极度集中+零预算
               （伊朗开战、次贷危机、黑天鹅级别）
    """
    if total_exposure > 0.90 and hhi > 0.6 and budget < 0.05:
        return "purple"
    if total_exposure > 0.85 and hhi > 0.5:
        return "red"
    if total_exposure > 0.70 or hhi > 0.35:
        return "yellow"
    return "green"


def _make_risk_signal(
    label: str,
    total_exposure: float,
    hhi: float,
    budget: float,
) -> dict:
    """
    红绿黄紫灯 + 百分比风险信号。

      light: "green" / "yellow" / "red" / "purple"
      risk_pct: 0-100 风险百分比
      exposure_pct: 总仓位百分比
      concentration_pct: 集中度百分比 (HHI * 100)
      budget_pct: 剩余风险预算百分比
      description: 人可读描述
      action: 建议行动
    """
    risk_pct = min(100.0, total_exposure * 60 + hhi * 40)

    signals = {
        "green": {
            "description": "Low risk. Portfolio is diversified with adequate cash buffer.",
            "action": "Normal operation. Monitor regularly.",
        },
        "yellow": {
            "description": "Moderate risk. Position concentration or exposure approaching limits.",
            "action": "Review positions. Consider reducing concentration.",
        },
        "red": {
            "description": "High risk. Portfolio is heavily concentrated with minimal buffer.",
            "action": "Reduce exposure. Increase cash position. Tighten stop-losses.",
        },
        "purple": {
            "description": "CRITICAL. Extreme concentration with zero buffer. Black swan conditions (war, systemic crisis, market collapse).",
            "action": "EMERGENCY. Immediate risk reduction required. Liquidate concentrated positions. Move to cash/safe haven. Do not add new positions.",
        },
        "unknown": {
            "description": "No data available.",
            "action": "Collect data before making decisions.",
        },
    }

    info = signals.get(label, signals["unknown"])

    return {
        "light": label,
        "risk_pct": round(risk_pct, 1),
        "exposure_pct": round(total_exposure * 100, 1),
        "concentration_pct": round(hhi * 100, 1),
        "budget_pct": round(budget * 100, 1),
        "description": info["description"],
        "action": info["action"],
    }
