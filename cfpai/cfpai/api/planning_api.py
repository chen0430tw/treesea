"""
CFPAI Planning API — 规划执行接口。

统一入口：run_planning → 返回权重、风险信号、路径。
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from cfpai.contracts.params import CFPAIParams
from cfpai.pipeline import run_multiasset_planning
from cfpai.data.market_loader import download_and_align
from cfpai.data.universe_builder import build_default_universe
from cfpai.features.feature_pipeline import build_feature_pipeline
from cfpai.reverse_moroz.scoring import score_assets
from cfpai.reverse_moroz.expansion import expand_dynamic_candidates
from cfpai.chain_search.path_builder import build_path_table
from cfpai.tree_diagram.grid_builder import build_weight_grid
from cfpai.planner.output_mapper import build_planning_snapshot
from cfpai.backtest.engine import backtest_weights
from cfpai.backtest.metrics import perf_stats


def plan(
    symbols: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    params: CFPAIParams | None = None,
    source: str = "auto",
) -> dict[str, Any]:
    """完整规划流水线：数据→特征→评分→展开→路径→网格→规划输出→回测。"""
    symbols = symbols or build_default_universe()
    params = params or CFPAIParams()
    aligned = download_and_align(symbols, start, end, source)
    clean_syms = [s.upper().replace(".US", "") for s in symbols]
    feat = build_feature_pipeline(aligned, clean_syms)

    scores = score_assets(feat, clean_syms, params, mode=params.scoring_mode)
    candidates = expand_dynamic_candidates(scores, feat, clean_syms, params)
    paths = build_path_table(candidates, params)
    weights = build_weight_grid(candidates, clean_syms, params)
    snapshot = build_planning_snapshot(paths, weights)

    # 附带回测绩效
    bt_result = backtest_weights(weights, feat, clean_syms)
    stats, equity = perf_stats(bt_result["portfolio_ret"])

    return {
        "symbols": clean_syms,
        "start": start,
        "end": end,
        "params": asdict(params),
        "planning": snapshot,
        "stats": stats,
        "latest_weights": weights.iloc[-1].drop(labels=["Date"]).to_dict() if len(weights) > 0 else {},
        "rows": len(feat),
    }


def plan_with_sentiment(
    symbols: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    params: CFPAIParams | None = None,
    sentiment_scores: dict[str, float] | None = None,
    source: str = "auto",
) -> dict[str, Any]:
    """带新闻情绪的规划（白皮书 n_t 输入）。

    sentiment_scores: {symbol: float}，-1（极度悲观）到 +1（极度乐观）
    情绪分数会调制 Maxwell Demon 的门控增益。
    """
    result = plan(symbols, start, end, params, source)

    if sentiment_scores and result.get("latest_weights"):
        # 情绪调制：正情绪放大正权重，负情绪压制
        adjusted_weights = {}
        for sym, w in result["latest_weights"].items():
            s = sentiment_scores.get(sym, 0.0)
            # 情绪增益：[-0.2, +0.2] 范围
            gain = 1.0 + 0.2 * s
            adjusted_weights[sym] = round(w * gain, 4)

        # 重新归一化
        total = sum(max(0, v) for v in adjusted_weights.values())
        scale = max(0.0, 1.0 - (params or CFPAIParams()).cash_floor)
        if total > 0:
            for sym in adjusted_weights:
                adjusted_weights[sym] = round(adjusted_weights[sym] / total * scale, 4)

        result["sentiment_adjusted_weights"] = adjusted_weights
        result["sentiment_scores"] = sentiment_scores

    return result
