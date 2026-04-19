from __future__ import annotations
from typing import Dict, List

from .worldline_kernel import EvaluationResult


# ---------------------------------------------------------------------------
# Abstract hydro (from proto 1 hydro_adjust_top_candidates)
# ---------------------------------------------------------------------------

def hydro_adjust_abstract(results: List[EvaluationResult]) -> dict:
    if not results:
        return {
            "pressure_balance": 1.0,
            "wither_ratio": 0.0,
            "active_ratio": 0.0,
            "restricted_ratio": 0.0,
            "mean_balanced_score": 0.0,
            "mean_risk": 0.0,
        }

    n = len(results)
    wither_count = sum(1 for r in results if r.branch_status == "withered")
    active_count = sum(1 for r in results if r.branch_status == "active")
    restricted_count = sum(1 for r in results if r.branch_status == "restricted")

    wither_ratio = wither_count / n
    active_ratio = active_count / n
    restricted_ratio = restricted_count / n

    mean_balanced_score = sum(r.balanced_score for r in results) / n
    mean_risk = sum(r.risk for r in results) / n

    # pressure_balance: 1.0 = FLOW (healthy). Withered branches pull DROUGHT;
    # restricted-but-competing branches pull FLOOD. All-active = baseline 1.0.
    # Previous formula used active_ratio (anti-pattern: all-active → 2.0 FLOOD).
    pressure_balance = max(0.0, min(2.0, 1.0 + restricted_ratio - wither_ratio))

    return {
        "pressure_balance": pressure_balance,
        "wither_ratio": wither_ratio,
        "active_ratio": active_ratio,
        "restricted_ratio": restricted_ratio,
        "mean_balanced_score": mean_balanced_score,
        "mean_risk": mean_risk,
    }


# ---------------------------------------------------------------------------
# Numerical hydro (from proto 2 hydro_control)
# ---------------------------------------------------------------------------

def hydro_adjust_numerical(metrics: List[dict]) -> dict:
    if not metrics:
        return {
            "pressure_balance": 1.0,
            "top_margin": 0.0,
            "score_spread": 0.0,
            "mean_score": 0.0,
            "mean_instability": 0.0,
        }

    scores = [m.get("score", 0.0) for m in metrics]
    instabilities = [m.get("instability", 0.0) for m in metrics]

    mean_score = sum(scores) / len(scores)
    mean_instability = sum(instabilities) / len(instabilities)

    sorted_scores = sorted(scores, reverse=True)
    top_margin = (sorted_scores[0] - sorted_scores[1]) if len(sorted_scores) > 1 else 0.0
    score_spread = sorted_scores[0] - sorted_scores[-1] if sorted_scores else 0.0

    # pressure_balance: 1.0 baseline (FLOW), driven to DROUGHT by high
    # mean_instability and to FLOOD by high score_spread (excess competition).
    # Previous formula expanded to 1.2 - 0.7·mi, whose baseline (mi=0) was 1.2,
    # already above the FLOOD threshold (1.15) — so hydro=FLOOD was pinned on.
    pressure_balance = max(
        0.0,
        min(
            2.0,
            1.0
            - 0.4 * mean_instability       # instability pulls toward DROUGHT
            + 0.5 * score_spread           # competition pushes toward FLOOD
            - 0.3 * top_margin,            # clear dominance pulls toward DROUGHT
        ),
    )

    return {
        "pressure_balance": pressure_balance,
        "top_margin": top_margin,
        "score_spread": score_spread,
        "mean_score": mean_score,
        "mean_instability": mean_instability,
    }


# ---------------------------------------------------------------------------
# Merge both hydro dicts
# ---------------------------------------------------------------------------

def merge_hydro(abstract_hydro: dict, numerical_hydro: dict) -> dict:
    merged = {}

    # Collect all keys from both
    all_keys = set(abstract_hydro.keys()) | set(numerical_hydro.keys())

    for key in all_keys:
        in_abstract = key in abstract_hydro
        in_numerical = key in numerical_hydro

        if key == "pressure_balance":
            # Average the shared pressure_balance
            a_val = abstract_hydro.get("pressure_balance", 1.0)
            n_val = numerical_hydro.get("pressure_balance", 1.0)
            merged["pressure_balance"] = (a_val + n_val) / 2.0
        elif in_abstract and in_numerical:
            # Both have it: average numeric values if possible
            a_val = abstract_hydro[key]
            n_val = numerical_hydro[key]
            try:
                merged[key] = (a_val + n_val) / 2.0
            except TypeError:
                merged[key] = a_val
        elif in_abstract:
            merged[key] = abstract_hydro[key]
        else:
            merged[key] = numerical_hydro[key]

    return merged
