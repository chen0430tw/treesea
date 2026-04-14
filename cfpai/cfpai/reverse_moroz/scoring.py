from __future__ import annotations

import numpy as np
import pandas as pd

from cfpai.contracts.params import CFPAIParams


# ================================================================
# 评分模式（可选组件）
# ================================================================

SCORING_MODES = {
    "classic": "经典线性评分（纯 momentum + trend - vol + volume + drawdown）",
    "updown_vol": "上下行波动率拆分（只惩罚下行波动，奖励上行波动）",
    "maxwell_demon": "麦克斯韦妖（上下行波动率 + 非线性门控）",
}

# 预设：Maxwell Demon（最优 Sharpe 1.82）
DEFAULT_SCORING_MODE = "maxwell_demon"


# ================================================================
# 麦克斯韦妖
# ================================================================

def _maxwell_demon(momentum: float, upvol: float, downvol: float) -> float:
    """非线性门控：根据动量方向和波动率不对称性调节信号增益。

    好分子（momentum>0 且 upvol>downvol）：开门放大，增益 > 1
    坏分子（momentum<0 且 downvol>upvol）：关门压制，增益 < 1
    中性分子：增益 ≈ 1
    """
    total_vol = upvol + downvol
    if total_vol < 1e-8:
        return 1.0
    vol_ratio = upvol / total_vol
    mom_sign = 1.0 if momentum > 0 else -1.0 if momentum < 0 else 0.0
    alpha = 2.0
    demon = 1.0 + alpha * mom_sign * (vol_ratio - 0.5)
    return max(0.3, min(2.0, demon))


# ================================================================
# 三种评分函数
# ================================================================

def _score_classic(row: pd.Series, asset: str, params: CFPAIParams) -> float:
    """经典线性评分：波动率全额扣分。"""
    return float(
        params.w_mom * row[f"{asset}_mom_20"]
        + params.w_trend * row[f"{asset}_trend_gap"]
        - params.w_vol * row[f"{asset}_vol_20"]
        + params.w_volume * np.clip(row[f"{asset}_volume_z"], -3, 3)
        + params.w_dd * row[f"{asset}_drawdown_63"]
    )


def _score_updown_vol(row: pd.Series, asset: str, params: CFPAIParams) -> float:
    """上下行波动率拆分：只惩罚下行，奖励上行。"""
    upvol = row.get(f"{asset}_upvol_20", 0.0)
    downvol = row.get(f"{asset}_downvol_20", row.get(f"{asset}_vol_20", 0.0))
    vol_score = 0.3 * upvol - params.w_vol * downvol

    return float(
        params.w_mom * row[f"{asset}_mom_20"]
        + params.w_trend * row[f"{asset}_trend_gap"]
        + vol_score
        + params.w_volume * np.clip(row[f"{asset}_volume_z"], -3, 3)
        + params.w_dd * row[f"{asset}_drawdown_63"]
    )


def _score_maxwell_demon(row: pd.Series, asset: str, params: CFPAIParams) -> float:
    """麦克斯韦妖：上下行波动率 + 非线性门控。"""
    upvol = row.get(f"{asset}_upvol_20", 0.0)
    downvol = row.get(f"{asset}_downvol_20", row.get(f"{asset}_vol_20", 0.0))
    vol_score = 0.3 * upvol - params.w_vol * downvol

    mom = row[f"{asset}_mom_20"]
    demon = _maxwell_demon(mom, upvol, downvol)

    linear = (
        params.w_mom * mom
        + params.w_trend * row[f"{asset}_trend_gap"]
        + vol_score
        + params.w_volume * np.clip(row[f"{asset}_volume_z"], -3, 3)
        + params.w_dd * row[f"{asset}_drawdown_63"]
    )

    return float(linear * demon)


_SCORING_FNS = {
    "classic": _score_classic,
    "updown_vol": _score_updown_vol,
    "maxwell_demon": _score_maxwell_demon,
}


# ================================================================
# 公开 API
# ================================================================

def asset_score_from_row(
    row: pd.Series,
    asset: str,
    params: CFPAIParams,
    mode: str | None = None,
) -> float:
    """计算单个资产的评分。

    Parameters
    ----------
    mode : str, optional
        "classic", "updown_vol", "maxwell_demon"
        默认使用 DEFAULT_SCORING_MODE
    """
    mode = mode or DEFAULT_SCORING_MODE
    fn = _SCORING_FNS.get(mode, _score_maxwell_demon)
    return fn(row, asset, params)


def score_assets(
    df: pd.DataFrame,
    asset_prefixes: list[str],
    params: CFPAIParams,
    mode: str | None = None,
) -> pd.DataFrame:
    """对所有资产评分。"""
    mode = mode or DEFAULT_SCORING_MODE
    rows = []
    for _, row in df.iterrows():
        one = {"Date": row["Date"]}
        for a in asset_prefixes:
            one[a] = asset_score_from_row(row, a, params, mode)
        rows.append(one)
    return pd.DataFrame(rows)
