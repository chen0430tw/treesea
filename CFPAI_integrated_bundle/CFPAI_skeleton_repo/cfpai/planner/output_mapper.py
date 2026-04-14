from __future__ import annotations

import pandas as pd


def build_planning_snapshot(path_df: pd.DataFrame, weights: pd.DataFrame) -> dict:
    if len(path_df) == 0 or len(weights) == 0:
        return {"market_label": "unknown", "selected_paths": [], "actions": {}, "risk_budget": None}
    latest_path = path_df.iloc[-1]
    latest_weights = weights.iloc[-1].to_dict()
    latest_weights.pop("Date", None)
    budget = 1.0 - max(latest_weights.values(), default=0.0)
    label = "risk_on" if sum(v for v in latest_weights.values()) > 0.6 else "neutral"
    return {
        "market_label": label,
        "selected_paths": [latest_path["path"]],
        "actions": latest_weights,
        "risk_budget": float(max(0.0, budget)),
    }
