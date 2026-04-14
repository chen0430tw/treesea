from __future__ import annotations

import pandas as pd

from .grid_builder import build_weight_grid
from .propagation import apply_identity_like_propagation


def evaluate_weight_grid(candidate_df: pd.DataFrame, asset_prefixes: list[str], params) -> pd.DataFrame:
    weights = build_weight_grid(candidate_df, asset_prefixes, params)
    return apply_identity_like_propagation(weights)
