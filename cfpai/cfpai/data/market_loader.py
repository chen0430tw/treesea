"""
多源市场数据加载器。

优先级：pandas-datareader (Stooq) → yfinance → 失败报错
不需要 API key，全部免费。
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd


def download_market_data(
    symbols: Iterable[str],
    start: str | None = None,
    end: str | None = None,
    source: str = "auto",
) -> dict[str, pd.DataFrame]:
    """下载多资产市场数据。

    Parameters
    ----------
    symbols : list of str
        资产代码（如 "SPY", "QQQ.US"）
    start, end : str, optional
        日期范围
    source : str
        "auto" 自动选源 | "stooq" | "yahoo"

    Returns
    -------
    dict[str, DataFrame]
        每个资产一个 DataFrame，含 Date/Open/High/Low/Close/Volume
    """
    if source == "auto":
        # 先试 pandas-datareader (Stooq)，失败则 yfinance
        try:
            return _download_stooq(symbols, start, end)
        except Exception:
            pass
        try:
            return _download_yahoo(symbols, start, end)
        except Exception:
            pass
        raise RuntimeError("All data sources failed. Install pandas-datareader or yfinance.")

    if source == "stooq":
        return _download_stooq(symbols, start, end)
    if source == "yahoo":
        return _download_yahoo(symbols, start, end)
    raise ValueError(f"Unknown source: {source}")


def _download_stooq(
    symbols: Iterable[str],
    start: str | None,
    end: str | None,
) -> dict[str, pd.DataFrame]:
    """通过 pandas-datareader 从 Stooq 获取数据。"""
    import pandas_datareader.data as web

    out = {}
    for sym in symbols:
        # Stooq 用 .US 后缀，pandas-datareader 自动处理
        stooq_sym = sym.upper().replace(".US", "") if ".US" in sym.upper() else sym.upper()
        df = web.DataReader(stooq_sym, "stooq", start=start, end=end)
        df = df.reset_index().sort_values("Date").reset_index(drop=True)
        # 标准化列名
        clean_sym = sym.upper().replace(".US", "")
        out[clean_sym] = df
    return out


def _download_yahoo(
    symbols: Iterable[str],
    start: str | None,
    end: str | None,
) -> dict[str, pd.DataFrame]:
    """通过 yfinance 获取数据。"""
    import yfinance as yf

    out = {}
    for sym in symbols:
        ticker = sym.upper().replace(".US", "")
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        df = df.reset_index()
        # yfinance 可能返回 MultiIndex columns
        if isinstance(df.columns[0], tuple):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        clean_sym = ticker
        out[clean_sym] = df
    return out


def download_and_align(
    symbols: Iterable[str],
    start: str | None = None,
    end: str | None = None,
    source: str = "auto",
) -> pd.DataFrame:
    """下载并对齐为 CFPAI 标准格式（{SYM}_Close, {SYM}_Volume 等）。"""
    frames = download_market_data(symbols, start, end, source)

    merged = None
    for sym, df in frames.items():
        use = df[["Date"]].copy()
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                use[f"{sym}_{col}"] = df[col]
        merged = use if merged is None else merged.merge(use, on="Date", how="inner")

    if merged is None:
        raise ValueError("No data downloaded.")
    return merged.sort_values("Date").reset_index(drop=True)
