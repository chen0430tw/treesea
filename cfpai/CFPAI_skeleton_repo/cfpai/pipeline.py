from __future__ import annotations

from cfpai.contracts.params import CFPAIParams
from cfpai.data.stooq_loader import download_many_stooq
from cfpai.data.aligner import align_on_date
from cfpai.data.universe_builder import build_default_universe
from cfpai.features.feature_pipeline import build_feature_pipeline
from cfpai.reverse_moroz.scoring import score_assets
from cfpai.reverse_moroz.expansion import expand_dynamic_candidates
from cfpai.reverse_moroz.anchors import detect_anchor_assets
from cfpai.chain_search.path_builder import build_path_table
from cfpai.tree_diagram.grid_builder import build_weight_grid
from cfpai.planner.output_mapper import build_planning_snapshot


def run_multiasset_planning(symbols: list[str] | None = None, start: str | None = None, end: str | None = None, params: CFPAIParams | None = None) -> dict:
    symbols = symbols or build_default_universe()
    params = params or CFPAIParams()
    frames = download_many_stooq(symbols, start=start, end=end)
    aligned = align_on_date(frames)
    feat = build_feature_pipeline(aligned, symbols)
    scores = score_assets(feat, symbols, params)
    candidates = expand_dynamic_candidates(scores, feat, symbols, params)
    paths = build_path_table(candidates, params)
    weights = build_weight_grid(candidates, symbols, params)
    snapshot = build_planning_snapshot(paths, weights)
    snapshot["symbols"] = symbols
    snapshot["start"] = start
    snapshot["end"] = end
    return snapshot
