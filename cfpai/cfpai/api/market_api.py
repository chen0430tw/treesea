"""
CFPAI Market API — 市场数据查询接口。

提供资产价格、特征、对齐数据的统一访问。
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pandas as pd

from cfpai.data.market_loader import download_market_data, download_and_align
from cfpai.data.universe_builder import build_default_universe
from cfpai.features.feature_pipeline import build_feature_pipeline


def get_market_data(
    symbols: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    source: str = "auto",
) -> dict[str, Any]:
    """下载并返回原始市场数据。"""
    symbols = symbols or build_default_universe()
    frames = download_market_data(symbols, start, end, source)
    summary = {}
    for sym, df in frames.items():
        summary[sym] = {
            "rows": len(df),
            "start": str(df["Date"].iloc[0]) if len(df) > 0 else None,
            "end": str(df["Date"].iloc[-1]) if len(df) > 0 else None,
            "latest_close": float(df["Close"].iloc[-1]) if len(df) > 0 else None,
        }
    return {"symbols": list(frames.keys()), "summary": summary}


def get_aligned_features(
    symbols: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    source: str = "auto",
) -> dict[str, Any]:
    """下载、对齐、构建特征，返回摘要。"""
    symbols = symbols or build_default_universe()
    aligned = download_and_align(symbols, start, end, source)
    clean_syms = [s.upper().replace(".US", "") for s in symbols]
    feat = build_feature_pipeline(aligned, clean_syms)

    latest = feat.iloc[-1] if len(feat) > 0 else pd.Series()
    snapshot = {}
    for sym in clean_syms:
        snapshot[sym] = {
            "mom_20": float(latest.get(f"{sym}_mom_20", 0)),
            "vol_20": float(latest.get(f"{sym}_vol_20", 0)),
            "upvol_20": float(latest.get(f"{sym}_upvol_20", 0)),
            "downvol_20": float(latest.get(f"{sym}_downvol_20", 0)),
            "trend_gap": float(latest.get(f"{sym}_trend_gap", 0)),
            "drawdown_63": float(latest.get(f"{sym}_drawdown_63", 0)),
            "rel_strength": float(latest.get(f"{sym}_rel_strength", 0)),
        }

    return {
        "symbols": clean_syms,
        "rows": len(feat),
        "date_range": [str(feat["Date"].iloc[0]), str(feat["Date"].iloc[-1])] if len(feat) > 0 else [],
        "latest_features": snapshot,
    }


def get_latest_prices(
    symbols: list[str] | None = None,
    source: str = "auto",
) -> dict[str, float]:
    """获取最新收盘价。"""
    symbols = symbols or build_default_universe()
    frames = download_market_data(symbols, source=source)
    prices = {}
    for sym, df in frames.items():
        if len(df) > 0:
            prices[sym] = float(df["Close"].iloc[-1])
    return prices
