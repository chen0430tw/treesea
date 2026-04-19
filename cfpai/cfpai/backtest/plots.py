"""
CFPAI Backtest Plots — 回测可视化。

净值曲线（含回撤）、权重变化堆叠图、风险信号时间线。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def plot_equity_with_drawdown(
    result: pd.DataFrame,
    out_path: str | Path | None = None,
    title: str = "CFPAI Portfolio",
) -> None:
    """双轴图：净值曲线 + 回撤。"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7), height_ratios=[3, 1],
                                    sharex=True, gridspec_kw={"hspace": 0.05})

    dates = pd.to_datetime(result["Date"])
    equity = result["equity"]
    dd = equity / equity.cummax() - 1

    # 净值
    ax1.plot(dates, equity, color="#2196F3", linewidth=1.2, label="Portfolio NAV")
    ax1.set_ylabel("Net Asset Value")
    ax1.set_yscale("log")
    ax1.legend(loc="upper left")
    ax1.set_title(title)
    ax1.grid(True, alpha=0.3)

    # 风险声明水印
    fig.text(0.5, 0.005, "For research only. Past performance does not guarantee future results. See DISCLAIMER.md.",
             ha="center", fontsize=7, color="#999999", style="italic")

    # 回撤
    ax2.fill_between(dates, dd, 0, color="#F44336", alpha=0.4, label="Drawdown")
    ax2.set_ylabel("Drawdown")
    ax2.set_xlabel("Date")
    ax2.legend(loc="lower left")
    ax2.grid(True, alpha=0.3)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=45)

    plt.tight_layout()
    if out_path:
        plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()


def plot_weight_history(
    weights: pd.DataFrame,
    asset_prefixes: list[str],
    out_path: str | Path | None = None,
    title: str = "CFPAI Asset Weight History",
) -> None:
    """堆叠面积图：各资产权重随时间变化。"""
    fig, ax = plt.subplots(figsize=(12, 5))

    dates = pd.to_datetime(weights["Date"])
    bottom = np.zeros(len(weights))

    colors = plt.cm.Set2(np.linspace(0, 1, len(asset_prefixes)))

    for i, asset in enumerate(asset_prefixes):
        vals = weights[asset].values.astype(float)
        ax.fill_between(dates, bottom, bottom + vals, alpha=0.7,
                         color=colors[i], label=asset)
        bottom += vals

    # 现金区域
    ax.fill_between(dates, bottom, 1.0, alpha=0.3, color="#9E9E9E", label="Cash")

    ax.set_ylabel("Weight")
    ax.set_xlabel("Date")
    ax.set_title(title)
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper left", ncol=min(len(asset_prefixes) + 1, 4), fontsize=8)
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.xticks(rotation=45)

    fig.text(0.5, 0.005, "For research only. Not investment advice. See DISCLAIMER.md.",
             ha="center", fontsize=7, color="#999999", style="italic")
    plt.tight_layout()

    if out_path:
        plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()


def plot_risk_timeline(
    result: pd.DataFrame,
    weights: pd.DataFrame,
    asset_prefixes: list[str],
    out_path: str | Path | None = None,
    title: str = "CFPAI Risk Signal Timeline",
) -> None:
    """风险信号时间线：总仓位 + HHI 集中度 + 四灯信号。"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 5), sharex=True,
                                    gridspec_kw={"hspace": 0.05})

    dates = pd.to_datetime(weights["Date"])

    # 总仓位
    total_exposure = weights[asset_prefixes].sum(axis=1)
    ax1.plot(dates, total_exposure, color="#FF9800", linewidth=1, label="Total Exposure")
    ax1.axhline(y=0.90, color="#F44336", linestyle="--", alpha=0.5, label="Red line (90%)")
    ax1.axhline(y=0.70, color="#FFEB3B", linestyle="--", alpha=0.5, label="Yellow line (70%)")
    ax1.set_ylabel("Total Exposure")
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.set_title(title)

    # HHI 集中度
    hhi_series = []
    for i in range(len(weights)):
        w = weights.iloc[i][asset_prefixes].values.astype(float)
        total = w.sum()
        if total > 0:
            shares = w / total
            hhi = float(np.sum(shares ** 2))
        else:
            hhi = 0.0
        hhi_series.append(hhi)

    ax2.plot(dates, hhi_series, color="#9C27B0", linewidth=1, label="HHI Concentration")
    ax2.axhline(y=0.5, color="#F44336", linestyle="--", alpha=0.5)
    ax2.axhline(y=0.35, color="#FFEB3B", linestyle="--", alpha=0.5)
    ax2.set_ylabel("HHI")
    ax2.set_xlabel("Date")
    ax2.legend(loc="upper left", fontsize=8)
    ax2.grid(True, alpha=0.3)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.xticks(rotation=45)

    fig.text(0.5, 0.005, "For research only. Not investment advice. See DISCLAIMER.md.",
             ha="center", fontsize=7, color="#999999", style="italic")
    plt.tight_layout()

    if out_path:
        plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close()


def save_all_plots(
    result: pd.DataFrame,
    weights: pd.DataFrame,
    asset_prefixes: list[str],
    out_dir: str | Path,
    prefix: str = "cfpai",
) -> list[Path]:
    """一次生成所有图表。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    paths = []

    p = out / f"{prefix}_equity_drawdown.png"
    plot_equity_with_drawdown(result, p)
    paths.append(p)

    p = out / f"{prefix}_weight_history.png"
    plot_weight_history(weights, asset_prefixes, p)
    paths.append(p)

    p = out / f"{prefix}_risk_timeline.png"
    plot_risk_timeline(result, weights, asset_prefixes, p)
    paths.append(p)

    return paths
