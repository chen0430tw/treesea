from __future__ import annotations

import pandas as pd

from .engines import evaluate_weight_grid


def run_tree_diagram(candidate_df: pd.DataFrame, asset_prefixes: list[str], params) -> pd.DataFrame:
    return evaluate_weight_grid(candidate_df, asset_prefixes, params)
