from __future__ import annotations

import pandas as pd

from cfpai.contracts.params import CFPAIParams


def build_path_table(candidate_df: pd.DataFrame, params: CFPAIParams) -> pd.DataFrame:
    prev_top = None
    rows = []
    for i in range(len(candidate_df)):
        s = candidate_df.iloc[i].drop(labels=["Date"]).sort_values(ascending=False)
        a1 = s.index[0]
        a2 = s.index[1] if len(s) > 1 else a1
        score = float(s.iloc[0] + (params.persistence_bonus if prev_top == a1 else 0.0))
        path = f"{a1} -> {a1}" if prev_top == a1 else f"{a1} -> {a2}"
        rows.append({
            "Date": candidate_df.at[i, "Date"],
            "anchor_asset": a1,
            "secondary_asset": a2,
            "path": path,
            "path_score": score,
        })
        prev_top = a1
    return pd.DataFrame(rows)
