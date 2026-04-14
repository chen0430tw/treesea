from __future__ import annotations

import pandas as pd

from .tuner import tune_with_utm


def run_utm_pipeline(feat_df: pd.DataFrame, asset_prefixes: list[str], generations: int = 6, population: int = 12, elite_k: int = 4, seed: int = 430):
    return tune_with_utm(feat_df, asset_prefixes, generations=generations, population=population, elite_k=elite_k, seed=seed)
