from __future__ import annotations

from cfpai.data.stooq_loader import download_many_stooq
from cfpai.data.aligner import align_on_date
from cfpai.features.feature_pipeline import build_feature_pipeline
from cfpai.utm.pipeline import run_utm_pipeline
from cfpai.multiasset_stooq import CFPAIMultiAssetStooq


def tune_stooq_multiasset(symbols: list[str], start: str | None = None, end: str | None = None, generations: int = 6, population: int = 12, elite_k: int = 4, seed: int = 430):
    frames = download_many_stooq(symbols, start=start, end=end)
    aligned = align_on_date(frames)
    feat = build_feature_pipeline(aligned, symbols)
    best_params, hist = run_utm_pipeline(feat, symbols, generations=generations, population=population, elite_k=elite_k, seed=seed)
    model = CFPAIMultiAssetStooq(symbols=symbols, start=start, end=end, params=best_params)
    result, stats, scores, anchors, candidates, paths, weights, planning = model.run_core(feat)
    payload = {
        "stats": stats,
        "scores": scores,
        "anchors": anchors,
        "candidates": candidates,
        "paths": paths,
        "weights": weights,
        "planning": planning,
        "model": model,
    }
    return best_params, hist, result, payload
