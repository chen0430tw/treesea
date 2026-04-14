from __future__ import annotations

import pandas as pd

from .risk_budget import compute_budget_from_weights
from .allocator import action_map_from_weights
from .output_mapper import build_planning_snapshot


def run_planner(path_df: pd.DataFrame, weights: pd.DataFrame) -> dict:
    return build_planning_snapshot(path_df, weights)
