from __future__ import annotations

import pandas as pd


OHLCV_COLS = ["Date", "Open", "High", "Low", "Close", "Volume"]


def align_on_date(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    merged = None
    for symbol, df in frames.items():
        use = df[OHLCV_COLS].copy()
        use = use.rename(columns={c: f"{symbol}_{c}" for c in OHLCV_COLS if c != "Date"})
        merged = use if merged is None else merged.merge(use, on="Date", how="inner")
    if merged is None:
        raise ValueError("No frames provided to align_on_date.")
    return merged.sort_values("Date").reset_index(drop=True)
