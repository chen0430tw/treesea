from __future__ import annotations

import pandas as pd


def latest_weight_snapshot(weights: pd.DataFrame) -> dict[str, float]:
    if len(weights) == 0:
        return {}
    row = weights.iloc[-1].to_dict()
    row.pop("Date", None)
    return row
