from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pandas as pd

from cfpai.contracts.params import CFPAIParams
from cfpai.reverse_moroz.scoring import score_assets
from cfpai.reverse_moroz.expansion import expand_dynamic_candidates
from cfpai.chain_search.path_builder import build_path_table
from cfpai.tree_diagram.grid_builder import build_weight_grid
from cfpai.backtest.engine import backtest_weights
from cfpai.backtest.metrics import perf_stats


def objective(stats: dict) -> float:
    sharpe = 0.0 if np.isnan(stats["sharpe"]) else stats["sharpe"]
    return stats["ann_return"] + 0.30 * sharpe - 0.50 * abs(stats["max_dd"])


def tune_with_utm(
    feat_df: pd.DataFrame,
    asset_prefixes: list[str],
    generations: int = 6,
    population: int = 12,
    elite_k: int = 4,
    seed: int = 430,
) -> tuple[CFPAIParams, pd.DataFrame]:
    split = int(len(feat_df) * 0.7)
    train_df = feat_df.iloc[:split].reset_index(drop=True)
    val_df = feat_df.iloc[split:].reset_index(drop=True)

    param_names = ["w_mom", "w_trend", "w_vol", "w_volume", "w_dd", "lambda_risk", "persistence_bonus", "max_assets", "cash_floor"]
    means = np.array([0.9, 0.2, 0.33, 0.12, 0.36, 0.42, 0.13, 3.0, 0.0], dtype=float)
    scales = np.array([0.45, 0.18, 0.18, 0.08, 0.18, 0.20, 0.08, 0.9, 0.2], dtype=float)
    lower = np.array([0.1, -0.2, 0.01, -0.2, 0.01, 0.01, 0.0, 1.0, 0.0], dtype=float)
    upper = np.array([2.5, 1.2, 1.0, 0.5, 1.5, 1.5, 0.4, 5.0, 0.6], dtype=float)

    rng = np.random.default_rng(seed)
    history = []
    best = None

    for gen in range(generations):
        candidates = []
        for _ in range(population):
            vec = np.clip(rng.normal(means, scales), lower, upper)
            d = {k: float(v) for k, v in zip(param_names, vec)}
            d["max_assets"] = int(round(d["max_assets"]))
            params = CFPAIParams(**d)

            # train
            tr_scores = score_assets(train_df, asset_prefixes, params)
            tr_cands = expand_dynamic_candidates(tr_scores, train_df, asset_prefixes, params)
            tr_paths = build_path_table(tr_cands, params)
            tr_weights = build_weight_grid(tr_cands, asset_prefixes, params)
            tr_result = backtest_weights(tr_weights, train_df, asset_prefixes)
            tr_stats, _ = perf_stats(tr_result["portfolio_ret"])

            # val
            va_scores = score_assets(val_df, asset_prefixes, params)
            va_cands = expand_dynamic_candidates(va_scores, val_df, asset_prefixes, params)
            va_paths = build_path_table(va_cands, params)
            va_weights = build_weight_grid(va_cands, asset_prefixes, params)
            va_result = backtest_weights(va_weights, val_df, asset_prefixes)
            va_stats, _ = perf_stats(va_result["portfolio_ret"])

            score = 0.4 * objective(tr_stats) + 0.6 * objective(va_stats)
            row = {"generation": gen, "score": score, **asdict(params)}
            row.update({f"train_{k}": v for k, v in tr_stats.items()})
            row.update({f"val_{k}": v for k, v in va_stats.items()})
            candidates.append((score, vec, row, params))

        candidates.sort(key=lambda x: x[0], reverse=True)
        elites = candidates[:elite_k]
        elite_vecs = np.array([v for _, v, _, _ in elites])

        means = elite_vecs.mean(axis=0)
        elite_std = elite_vecs.std(axis=0)
        scales = np.maximum(0.03 * (upper - lower), 0.85 * elite_std + 0.15 * scales)

        best_score, _, best_row, best_params = elites[0]
        history.append(best_row)
        if best is None or best_score > best[0]:
            best = (best_score, best_params)

    return best[1], pd.DataFrame(history)
