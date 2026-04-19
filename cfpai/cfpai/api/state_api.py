"""
CFPAI State API — 市场状态查询接口。

将白皮书 Φ 层（状态表示）暴露为可查询 API。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from cfpai.contracts.state_types import MarketState
from cfpai.data.market_loader import download_and_align
from cfpai.data.universe_builder import build_default_universe
from cfpai.features.feature_pipeline import build_feature_pipeline


def get_current_state(
    symbols: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    source: str = "auto",
) -> MarketState:
    """构建当前市场状态（白皮书 z_t = (z_f, z_r, z_s, z_l)）。"""
    symbols = symbols or build_default_universe()
    aligned = download_and_align(symbols, start, end, source)
    clean_syms = [s.upper().replace(".US", "") for s in symbols]
    feat = build_feature_pipeline(aligned, clean_syms)

    if len(feat) == 0:
        return MarketState()

    latest = feat.iloc[-1]

    # z_f: 资本流状态 — 动量方向 + 成交量异动
    flow_state = {}
    for sym in clean_syms:
        mom = float(latest.get(f"{sym}_mom_20", 0))
        vol_z = float(latest.get(f"{sym}_volume_z", 0))
        flow_state[sym] = round(mom * 0.6 + np.clip(vol_z, -3, 3) * 0.4, 4)

    # z_r: 风险状态 — 波动率 + 回撤
    risk_state = {}
    for sym in clean_syms:
        vol = float(latest.get(f"{sym}_vol_20", 0))
        dd = float(latest.get(f"{sym}_drawdown_63", 0))
        risk_state[sym] = round(vol * 0.5 + abs(dd) * 0.5, 4)

    # z_s: 结构轮动状态 — 相对强度
    rotation_state = {}
    for sym in clean_syms:
        rel = float(latest.get(f"{sym}_rel_strength", 0))
        rotation_state[sym] = round(rel, 4)

    # z_l: 流动性状态 — 成交量 z-score
    liquidity_state = {}
    for sym in clean_syms:
        vol_z = float(latest.get(f"{sym}_volume_z", 0))
        liquidity_state[sym] = round(np.clip(vol_z, -3, 3), 4)

    # 潜在向量：拼接所有子状态
    latent = []
    for sym in clean_syms:
        latent.extend([flow_state[sym], risk_state[sym], rotation_state[sym], liquidity_state[sym]])

    return MarketState(
        timestamp=str(latest.get("Date", "")),
        flow_state=flow_state,
        risk_state=risk_state,
        rotation_state=rotation_state,
        liquidity_state=liquidity_state,
        latent_vector=latent,
        metadata={"symbols": clean_syms, "rows": len(feat)},
    )


def get_state_history(
    symbols: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    source: str = "auto",
    window: int = 20,
) -> list[dict[str, Any]]:
    """返回最近 window 天的状态序列。"""
    symbols = symbols or build_default_universe()
    aligned = download_and_align(symbols, start, end, source)
    clean_syms = [s.upper().replace(".US", "") for s in symbols]
    feat = build_feature_pipeline(aligned, clean_syms)

    if len(feat) == 0:
        return []

    tail = feat.tail(window)
    history = []
    for _, row in tail.iterrows():
        risk_avg = float(np.mean([row.get(f"{s}_vol_20", 0) for s in clean_syms]))
        mom_avg = float(np.mean([row.get(f"{s}_mom_20", 0) for s in clean_syms]))
        history.append({
            "date": str(row.get("Date", "")),
            "avg_momentum": round(mom_avg, 4),
            "avg_risk": round(risk_avg, 4),
        })

    return history
