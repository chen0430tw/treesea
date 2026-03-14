from __future__ import annotations
from typing import Dict, List, Optional
import numpy as np

from .forcing import GridConfig
from .weather_state import WeatherState


def score_state(
    state: WeatherState,
    obs: WeatherState,
    cfg: GridConfig,
) -> dict:
    NY, NX = state.h.shape
    n = float(NY * NX)

    # RMS errors normalized by observation RMS
    h_rms_obs = float(np.sqrt(np.mean(obs.h ** 2)))
    t_rms_obs = float(np.sqrt(np.mean((obs.T - 273.15) ** 2))) + 1.0
    q_rms_obs = float(np.sqrt(np.mean(obs.q ** 2))) + 1e-6

    h_err = float(np.sqrt(np.mean((state.h - obs.h) ** 2))) / (h_rms_obs + 1.0)
    t_err = float(np.sqrt(np.mean((state.T - obs.T) ** 2))) / t_rms_obs
    q_err = float(np.sqrt(np.mean((state.q - obs.q) ** 2))) / q_rms_obs

    # Wind error
    w_rms_obs = float(np.sqrt(np.mean(obs.u ** 2 + obs.v ** 2))) + 1.0
    w_err = float(np.sqrt(np.mean((state.u - obs.u) ** 2 + (state.v - obs.v) ** 2))) / w_rms_obs

    # Instability: variance of h anomaly relative to obs
    h_anom = state.h - obs.h
    instability = float(np.std(h_anom)) / (h_rms_obs + 1.0)

    # Composite score: lower error = higher score
    score = 1.0 / (1.0 + 0.30 * h_err + 0.25 * t_err + 0.25 * q_err + 0.20 * w_err)

    return {
        "h_err": h_err,
        "t_err": t_err,
        "q_err": q_err,
        "w_err": w_err,
        "instability": instability,
        "score": score,
    }


def classify_branch(
    metric: dict,
    best_score: Optional[float] = None,
    score_span: Optional[float] = None,
) -> str:
    score = metric.get("score", 0.0)
    instability = metric.get("instability", 0.0)

    if best_score is None or score_span is None:
        # Absolute classification fallback
        if score >= 0.75:
            return "active"
        elif score >= 0.55:
            return "restricted"
        elif score >= 0.35:
            return "starved"
        else:
            return "withered"

    # Adaptive relative classification
    if score_span < 1e-9:
        relative = 1.0
    else:
        relative = (score - (best_score - score_span)) / score_span

    if relative >= 0.80 and instability < 0.40:
        return "active"
    elif relative >= 0.50 and instability < 0.65:
        return "restricted"
    elif relative >= 0.20:
        return "starved"
    else:
        return "withered"


def rank_ensemble(results: List[dict]) -> List[dict]:
    if not results:
        return results

    scores = [r.get("score", 0.0) for r in results]
    best_score = max(scores)
    worst_score = min(scores)
    score_span = best_score - worst_score

    ranked = []
    for r in results:
        r2 = dict(r)
        r2["status"] = classify_branch(r2, best_score=best_score, score_span=score_span)
        ranked.append(r2)

    ranked.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return ranked
