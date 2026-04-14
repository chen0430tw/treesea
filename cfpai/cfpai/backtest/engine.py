from __future__ import annotations

import numpy as np
import pandas as pd


def backtest_weights(weights: pd.DataFrame, feat_df: pd.DataFrame, asset_prefixes: list[str]) -> pd.DataFrame:
    result = feat_df[["Date"]].copy()
    for a in asset_prefixes:
        result[f"{a}_weight"] = weights[a].values
        result[f"{a}_ret_1d"] = feat_df[f"{a}_ret_1d"].values

    pret = np.zeros(len(result))
    for a in asset_prefixes:
        pret += result[f"{a}_weight"].shift(1).fillna(0.0).to_numpy() * result[f"{a}_ret_1d"].fillna(0.0).to_numpy()

    result["portfolio_ret"] = pret
    result["equity"] = (1 + result["portfolio_ret"]).cumprod()
    return result
