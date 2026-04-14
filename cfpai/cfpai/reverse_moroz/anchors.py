from __future__ import annotations

import pandas as pd


def detect_anchor_assets(score_df: pd.DataFrame) -> pd.DataFrame:
    top1, top2 = [], []
    for i in range(len(score_df)):
        s = score_df.iloc[i].drop(labels=["Date"]).sort_values(ascending=False)
        a1 = s.index[0]
        a2 = s.index[1] if len(s) > 1 else a1
        top1.append(a1)
        top2.append(a2)
    return pd.DataFrame({"Date": score_df["Date"], "anchor_asset": top1, "secondary_asset": top2})
