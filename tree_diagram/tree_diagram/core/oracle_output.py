from __future__ import annotations
from typing import Dict, List, Optional

from .problem_seed import ProblemSeed
from .background_inference import ProblemBackground
from .worldline_kernel import EvaluationResult
from .branch_ecology import branch_status_histogram


# ---------------------------------------------------------------------------
# Abstract oracle (from proto 1 oracle_summary)
# ---------------------------------------------------------------------------

def oracle_summary_abstract(
    seed: ProblemSeed,
    bg: ProblemBackground,
    field: Dict[str, float],
    top_results: List[EvaluationResult],
    hydro: dict,
) -> dict:
    best: Optional[EvaluationResult] = top_results[0] if top_results else None

    background_naturally_emerged = (
        len(bg.dominant_pressures) >= 2
        and bg.hidden_variables.get("latent_stress", 0.0) > 0.3
    )

    best_worldline: dict = {}
    if best is not None:
        best_worldline = {
            "family": best.family,
            "template": best.template,
            "params": best.params,
            "balanced_score": best.balanced_score,
            "feasibility": best.feasibility,
            "stability": best.stability,
            "field_fit": best.field_fit,
            "risk": best.risk,
            "nutrient_gain": best.nutrient_gain,
            "branch_status": best.branch_status,
        }

    branch_histogram = branch_status_histogram(top_results)

    return {
        "mode": "abstract",
        "seed_title": seed.title,
        "background_naturally_emerged": background_naturally_emerged,
        "core_contradiction": bg.core_contradiction,
        "inferred_goal_axis": bg.inferred_goal_axis,
        "dominant_pressures": bg.dominant_pressures,
        "field_snapshot": field,
        "best_worldline": best_worldline,
        "hydro_control_state": hydro,
        "branch_histogram": branch_histogram,
        "total_evaluated": len(top_results),
    }


# ---------------------------------------------------------------------------
# Numerical oracle (from proto 2 run_all summary)
# ---------------------------------------------------------------------------

def oracle_summary_numerical(
    metrics: List[dict],
    hydro: dict,
    best_name: str,
) -> dict:
    branch_histogram: Dict[str, int] = {}
    for m in metrics:
        status = m.get("status", "unknown")
        branch_histogram[status] = branch_histogram.get(status, 0) + 1

    best_metric: dict = {}
    for m in metrics:
        if m.get("name") == best_name:
            best_metric = dict(m)
            break

    return {
        "mode": "numerical",
        "best_branch_name": best_name,
        "best_branch_metric": best_metric,
        "hydro_control_state": hydro,
        "branch_histogram": branch_histogram,
        "total_branches": len(metrics),
        "all_metrics": metrics,
    }


# ---------------------------------------------------------------------------
# Merge abstract + numerical oracle
# ---------------------------------------------------------------------------

def merge_oracle(abstract_oracle: dict, numerical_oracle: dict) -> dict:
    merged = {
        "mode": "integrated",
        "seed_title": abstract_oracle.get("seed_title", ""),
        # Abstract fields
        "background_naturally_emerged": abstract_oracle.get("background_naturally_emerged"),
        "core_contradiction": abstract_oracle.get("core_contradiction", ""),
        "inferred_goal_axis": abstract_oracle.get("inferred_goal_axis", ""),
        "dominant_pressures": abstract_oracle.get("dominant_pressures", []),
        "field_snapshot": abstract_oracle.get("field_snapshot", {}),
        "best_worldline": abstract_oracle.get("best_worldline", {}),
        "abstract_hydro": abstract_oracle.get("hydro_control_state", {}),
        "abstract_branch_histogram": abstract_oracle.get("branch_histogram", {}),
        "total_worldlines_evaluated": abstract_oracle.get("total_evaluated", 0),
        # Numerical fields
        "best_weather_branch": numerical_oracle.get("best_branch_name", ""),
        "best_weather_metric": numerical_oracle.get("best_branch_metric", {}),
        "numerical_hydro": numerical_oracle.get("hydro_control_state", {}),
        "weather_branch_histogram": numerical_oracle.get("branch_histogram", {}),
        "total_weather_branches": numerical_oracle.get("total_branches", 0),
        "weather_metrics": numerical_oracle.get("all_metrics", []),
    }
    return merged
