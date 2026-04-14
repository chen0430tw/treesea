from __future__ import annotations

import numpy as np
import pandas as pd


def build_feature_pipeline(df: pd.DataFrame, asset_prefixes: list[str]) -> pd.DataFrame:
    x = df.copy()
    for a in asset_prefixes:
        close = x[f"{a}_Close"]
        volm = x[f"{a}_Volume"]

        x[f"{a}_ret_1d"] = close.pct_change()
        x[f"{a}_mom_20"] = close.pct_change(20)
        x[f"{a}_ma_50"] = close.rolling(50).mean()
        x[f"{a}_ma_200"] = close.rolling(200).mean()
        x[f"{a}_trend_gap"] = x[f"{a}_ma_50"] / x[f"{a}_ma_200"] - 1

        x[f"{a}_vol_20"] = x[f"{a}_ret_1d"].rolling(20).std() * np.sqrt(252)
        x[f"{a}_roll_max_63"] = close.rolling(63).max()
        x[f"{a}_drawdown_63"] = close / x[f"{a}_roll_max_63"] - 1

        vol_mean = volm.rolling(20).mean()
        vol_std = volm.rolling(20).std()
        x[f"{a}_volume_z"] = (volm - vol_mean) / vol_std

    return x.dropna().reset_index(drop=True)
