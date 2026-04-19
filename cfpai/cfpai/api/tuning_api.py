"""
CFPAI Tuning API — UTM 调参接口。

暴露调参启动、历史查询、最优参数加载。
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pandas as pd

from cfpai.contracts.params import CFPAIParams
from cfpai.data.market_loader import download_and_align
from cfpai.data.universe_builder import build_default_universe
from cfpai.features.feature_pipeline import build_feature_pipeline
from cfpai.utm.tuner import tune_with_utm
from cfpai.backtest.engine import backtest_weights
from cfpai.backtest.metrics import perf_stats
from cfpai.reverse_moroz.scoring import score_assets
from cfpai.reverse_moroz.expansion import expand_dynamic_candidates
from cfpai.chain_search.path_builder import build_path_table
from cfpai.tree_diagram.grid_builder import build_weight_grid


def tune(
    symbols: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    generations: int = 6,
    population: int = 12,
    elite_k: int = 4,
    seed: int = 430,
    source: str = "auto",
) -> dict[str, Any]:
    """执行 UTM 调参，返回最优参数和收缩历史。"""
    symbols = symbols or build_default_universe()
    aligned = download_and_align(symbols, start, end, source)
    clean_syms = [s.upper().replace(".US", "") for s in symbols]
    feat = build_feature_pipeline(aligned, clean_syms)

    best_params, history = tune_with_utm(
        feat, clean_syms,
        generations=generations,
        population=population,
        elite_k=elite_k,
        seed=seed,
    )

    # 用最优参数跑一次完整回测
    scores = score_assets(feat, clean_syms, best_params, mode=best_params.scoring_mode)
    candidates = expand_dynamic_candidates(scores, feat, clean_syms, best_params)
    weights = build_weight_grid(candidates, clean_syms, best_params)
    bt_result = backtest_weights(weights, feat, clean_syms)
    stats, _ = perf_stats(bt_result["portfolio_ret"])

    return {
        "symbols": clean_syms,
        "best_params": asdict(best_params),
        "stats": stats,
        "generations": generations,
        "population": population,
        "elite_k": elite_k,
        "history": history.to_dict(orient="records"),
    }


def compare_default_vs_tuned(
    symbols: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    source: str = "auto",
) -> dict[str, Any]:
    """对比默认参数 vs UTM 调参后的绩效。"""
    symbols = symbols or build_default_universe()
    aligned = download_and_align(symbols, start, end, source)
    clean_syms = [s.upper().replace(".US", "") for s in symbols]
    feat = build_feature_pipeline(aligned, clean_syms)

    # 默认参数
    default_params = CFPAIParams()
    d_scores = score_assets(feat, clean_syms, default_params)
    d_cands = expand_dynamic_candidates(d_scores, feat, clean_syms, default_params)
    d_weights = build_weight_grid(d_cands, clean_syms, default_params)
    d_bt = backtest_weights(d_weights, feat, clean_syms)
    d_stats, _ = perf_stats(d_bt["portfolio_ret"])

    # UTM 调参
    best_params, history = tune_with_utm(feat, clean_syms)
    t_scores = score_assets(feat, clean_syms, best_params)
    t_cands = expand_dynamic_candidates(t_scores, feat, clean_syms, best_params)
    t_weights = build_weight_grid(t_cands, clean_syms, best_params)
    t_bt = backtest_weights(t_weights, feat, clean_syms)
    t_stats, _ = perf_stats(t_bt["portfolio_ret"])

    return {
        "symbols": clean_syms,
        "default": {"params": asdict(default_params), "stats": d_stats},
        "tuned": {"params": asdict(best_params), "stats": t_stats},
        "improvement": {
            "sharpe_delta": t_stats["sharpe"] - d_stats["sharpe"],
            "return_delta": t_stats["ann_return"] - d_stats["ann_return"],
            "maxdd_delta": t_stats["max_dd"] - d_stats["max_dd"],
        },
    }
