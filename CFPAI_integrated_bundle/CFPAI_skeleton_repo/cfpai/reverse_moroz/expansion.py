from __future__ import annotations

import pandas as pd

from cfpai.contracts.params import CFPAIParams


def expand_dynamic_candidates(score_df: pd.DataFrame, feat_df: pd.DataFrame, asset_prefixes: list[str], params: CFPAIParams) -> pd.DataFrame:
    rows = []
    for i in range(len(score_df)):
        row = {"Date": score_df.at[i, "Date"]}
        for a in asset_prefixes:
            risk_pen = params.lambda_risk * float(feat_df.at[i, f"{a}_vol_20"])
            row[a] = float(score_df.at[i, a] - risk_pen)
        rows.append(row)
    return pd.DataFrame(rows)
