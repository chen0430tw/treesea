from __future__ import annotations

import pandas as pd

from cfpai.contracts.params import CFPAIParams
from .scoring import score_assets
from .anchors import detect_anchor_assets
from .expansion import expand_dynamic_candidates
from .contracts import ReverseMorozSnapshot


def run_reverse_moroz(feat_df: pd.DataFrame, asset_prefixes: list[str], params: CFPAIParams) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    scores = score_assets(feat_df, asset_prefixes, params)
    anchors = detect_anchor_assets(scores)
    candidates = expand_dynamic_candidates(scores, feat_df, asset_prefixes, params)
    return scores, anchors, candidates
