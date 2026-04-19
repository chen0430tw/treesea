from __future__ import annotations
from typing import Dict, List, Optional
import numpy as np

from .forcing import GridConfig
from .weather_state import WeatherState
from ._xp import get_xp

# Module-level weight for the center-cell wind-direction micro-penalty.
# Exposed so parameter sweeps can tune it without editing source.
WD_CENTER_PENALTY_WEIGHT: float = 0.80


def score_state(
    state: WeatherState,
    obs: WeatherState,
    cfg: GridConfig,
) -> dict:
    NY, NX = state.h.shape
    n = float(NY * NX)
    xp = get_xp(state.h)

    # RMS errors normalized by observation RMS (xp ops, .item/float at exit)
    h_rms_obs = float(xp.sqrt(xp.mean(obs.h ** 2)))
    t_rms_obs = float(xp.sqrt(xp.mean((obs.T - 273.15) ** 2))) + 1.0
    q_rms_obs = float(xp.sqrt(xp.mean(obs.q ** 2))) + 1e-6

    h_err = float(xp.sqrt(xp.mean((state.h - obs.h) ** 2))) / (h_rms_obs + 1.0)
    t_err = float(xp.sqrt(xp.mean((state.T - obs.T) ** 2))) / t_rms_obs
    q_err = float(xp.sqrt(xp.mean((state.q - obs.q) ** 2))) / q_rms_obs

    w_rms_obs = float(xp.sqrt(xp.mean(obs.u ** 2 + obs.v ** 2))) + 1.0
    w_err = float(xp.sqrt(xp.mean((state.u - obs.u) ** 2 + (state.v - obs.v) ** 2))) / w_rms_obs

    cy, cx = NY // 2, NX // 2
    # Scalars via float() — work on both numpy and cupy
    wd_state = float(np.arctan2(float(state.u[cy, cx]), float(state.v[cy, cx])))
    wd_obs   = float(np.arctan2(float(obs.u[cy, cx]),   float(obs.v[cy, cx])))
    d_wd = abs(((wd_state - wd_obs) + np.pi) % (2 * np.pi) - np.pi)
    wd_center_penalty = d_wd / np.pi

    h_anom = state.h - obs.h
    instability = float(xp.std(h_anom)) / (h_rms_obs + 1.0)

    # Composite score: lower error = higher score. wd_center_penalty is additive
    # (mild, weight 0.05) — existing h/t/q/w weights unchanged.
    score = 1.0 / (
        1.0
        + 0.30 * h_err
        + 0.25 * t_err
        + 0.25 * q_err
        + 0.20 * w_err
        + WD_CENTER_PENALTY_WEIGHT * wd_center_penalty
    )

    return {
        "h_err": h_err,
        "t_err": t_err,
        "q_err": q_err,
        "w_err": w_err,
        "wd_center_penalty": wd_center_penalty,
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
