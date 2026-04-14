from __future__ import annotations

import io
from typing import Iterable

import pandas as pd
import requests


def download_stooq_csv(symbol: str, start: str | None = None, end: str | None = None, session: requests.Session | None = None) -> pd.DataFrame:
    sess = session or requests.Session()
    url = "https://stooq.com/q/d/l/"
    params = {"s": symbol.lower(), "i": "d"}
    if start:
        params["d1"] = pd.to_datetime(start).strftime("%Y%m%d")
    if end:
        params["d2"] = pd.to_datetime(end).strftime("%Y%m%d")
    r = sess.get(url, params=params, timeout=30)
    r.raise_for_status()
    text = r.text.strip()
    if not text or text.lower().startswith("no data"):
        raise ValueError(f"No data returned for {symbol}")
    df = pd.read_csv(io.StringIO(text))
    if "Date" not in df.columns:
        raise ValueError(f"Unexpected Stooq format for {symbol}")
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)


def download_many_stooq(symbols: Iterable[str], start: str | None = None, end: str | None = None) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    with requests.Session() as sess:
        for s in symbols:
            out[s.upper()] = download_stooq_csv(s, start=start, end=end, session=sess)
    return out
