from __future__ import annotations

import pandas as pd

from cfpai.contracts.params import CFPAIParams
from .path_builder import build_path_table


def run_chain_search(candidate_df: pd.DataFrame, params: CFPAIParams) -> pd.DataFrame:
    return build_path_table(candidate_df, params)
