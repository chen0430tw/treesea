"""
UTM Diagnostics — 调参过程诊断。

分析 UTM 收敛性、参数稳定性、过拟合风险。
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def diagnose_convergence(history_df: pd.DataFrame) -> dict[str, Any]:
    """诊断 UTM 搜索的收敛情况。

    Parameters
    ----------
    history_df : DataFrame
        tune_with_utm 返回的 history，含 generation, score, train_*, val_* 列

    Returns
    -------
    dict with convergence diagnostics
    """
    if len(history_df) == 0:
        return {"status": "no_data"}

    scores = history_df["score"].values
    gens = history_df["generation"].values

    # 收敛速度：最后两代的 score 变化率
    if len(scores) >= 2:
        delta = scores[-1] - scores[-2]
        rel_delta = delta / (abs(scores[-2]) + 1e-12)
    else:
        delta = 0.0
        rel_delta = 0.0

    # 过拟合检测：train vs val 的 Sharpe 差距
    train_sharpe = history_df.get("train_sharpe", pd.Series(dtype=float))
    val_sharpe = history_df.get("val_sharpe", pd.Series(dtype=float))

    overfit_gap = None
    overfit_warning = False
    if len(train_sharpe) > 0 and len(val_sharpe) > 0:
        ts = float(train_sharpe.iloc[-1]) if not np.isnan(train_sharpe.iloc[-1]) else 0.0
        vs = float(val_sharpe.iloc[-1]) if not np.isnan(val_sharpe.iloc[-1]) else 0.0
        overfit_gap = round(ts - vs, 4)
        overfit_warning = overfit_gap > 0.5  # Sharpe 差距 > 0.5 就警告

    # 收敛判定
    converged = abs(rel_delta) < 0.01  # 相对变化 < 1%

    return {
        "generations": int(gens[-1]) + 1,
        "best_score": round(float(scores[-1]), 4),
        "score_trajectory": [round(float(s), 4) for s in scores],
        "last_delta": round(float(delta), 4),
        "last_rel_delta": round(float(rel_delta), 4),
        "converged": converged,
        "overfit_gap": overfit_gap,
        "overfit_warning": overfit_warning,
        "recommendation": _recommend(converged, overfit_warning, rel_delta),
    }


def _recommend(converged: bool, overfit: bool, rel_delta: float) -> str:
    if overfit:
        return "过拟合风险：train/val Sharpe 差距过大。建议增加数据、减少参数自由度、或加正则化。"
    if not converged and rel_delta > 0.05:
        return "尚未收敛且仍在改善。建议增加 generations。"
    if not converged and rel_delta < -0.01:
        return "搜索质量下降。建议重置种群或调整搜索范围。"
    if converged:
        return "已收敛。当前参数可用于生产。"
    return "接近收敛。可再跑 2-3 代确认稳定性。"


def diagnose_param_stability(history_df: pd.DataFrame) -> dict[str, Any]:
    """分析参数在搜索过程中的稳定性。"""
    param_cols = ["w_mom", "w_trend", "w_vol", "w_volume", "w_dd",
                  "lambda_risk", "persistence_bonus", "max_assets"]

    stability = {}
    for col in param_cols:
        if col not in history_df.columns:
            continue
        values = history_df[col].values
        if len(values) < 2:
            stability[col] = {"stable": True, "cv": 0.0}
            continue

        mean = float(np.mean(values))
        std = float(np.std(values))
        cv = std / (abs(mean) + 1e-12)  # 变异系数

        # 最后半程 vs 前半程
        mid = len(values) // 2
        first_half = np.mean(values[:mid])
        second_half = np.mean(values[mid:])
        drift = float(second_half - first_half)

        stability[col] = {
            "mean": round(mean, 4),
            "std": round(std, 4),
            "cv": round(cv, 4),
            "drift": round(drift, 4),
            "stable": cv < 0.2,  # CV < 20% 视为稳定
        }

    unstable = [k for k, v in stability.items() if not v.get("stable", True)]

    return {
        "params": stability,
        "unstable_params": unstable,
        "overall_stable": len(unstable) == 0,
    }


def full_utm_report(history_df: pd.DataFrame) -> dict[str, Any]:
    """完整 UTM 诊断报告。"""
    convergence = diagnose_convergence(history_df)
    stability = diagnose_param_stability(history_df)

    return {
        "convergence": convergence,
        "stability": stability,
        "summary": _build_summary(convergence, stability),
    }


def _build_summary(convergence: dict, stability: dict) -> str:
    parts = []
    parts.append(f"搜索 {convergence['generations']} 代，最佳分数 {convergence['best_score']}")

    if convergence["converged"]:
        parts.append("已收敛")
    else:
        parts.append("未完全收敛")

    if convergence.get("overfit_warning"):
        parts.append(f"⚠ 过拟合风险（train/val gap = {convergence['overfit_gap']}）")

    if stability["overall_stable"]:
        parts.append("参数稳定")
    else:
        parts.append(f"不稳定参数：{', '.join(stability['unstable_params'])}")

    parts.append(convergence["recommendation"])
    return "。".join(parts)
