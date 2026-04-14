from __future__ import annotations

import numpy as np
import pandas as pd

from cfpai.contracts.params import CFPAIParams


def asset_score_from_row(row: pd.Series, asset: str, params: CFPAIParams) -> float:
    return float(
        params.w_mom * row[f"{asset}_mom_20"]
        + params.w_trend * row[f"{asset}_trend_gap"]
        - params.w_vol * row[f"{asset}_vol_20"]
        + params.w_volume * np.clip(row[f"{asset}_volume_z"], -3, 3)
        + params.w_dd * row[f"{asset}_drawdown_63"]
    )


def score_assets(df: pd.DataFrame, asset_prefixes: list[str], params: CFPAIParams) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        one = {"Date": row["Date"]}
        for a in asset_prefixes:
            one[a] = asset_score_from_row(row, a, params)
        rows.append(one)
    return pd.DataFrame(rows)
