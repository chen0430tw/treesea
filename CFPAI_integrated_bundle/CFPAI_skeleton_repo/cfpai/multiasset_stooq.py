from __future__ import annotations

from cfpai.contracts.params import CFPAIParams
from cfpai.data.stooq_loader import download_many_stooq
from cfpai.data.aligner import align_on_date
from cfpai.features.feature_pipeline import build_feature_pipeline
from cfpai.reverse_moroz.pipeline import run_reverse_moroz
from cfpai.chain_search.pipeline import run_chain_search
from cfpai.tree_diagram.pipeline import run_tree_diagram
from cfpai.planner.pipeline import run_planner
from cfpai.backtest.engine import backtest_weights
from cfpai.backtest.metrics import perf_stats
from cfpai.backtest.report import save_run


class CFPAIMultiAssetStooq:
    def __init__(self, symbols: list[str], start: str | None = None, end: str | None = None, params: CFPAIParams | None = None):
        self.symbols = [s.upper() for s in symbols]
        self.start = start
        self.end = end
        self.params = params or CFPAIParams()

    def build_features(self):
        frames = download_many_stooq(self.symbols, start=self.start, end=self.end)
        aligned = align_on_date(frames)
        return build_feature_pipeline(aligned, self.symbols)

    def run_core(self, feat_df):
        scores, anchors, candidates = run_reverse_moroz(feat_df, self.symbols, self.params)
        paths = run_chain_search(candidates, self.params)
        weights = run_tree_diagram(candidates, self.symbols, self.params)
        planning = run_planner(paths, weights)
        result = backtest_weights(weights, feat_df, self.symbols)
        stats, _ = perf_stats(result["portfolio_ret"])
        return result, stats, scores, anchors, candidates, paths, weights, planning

    def backtest(self):
        feat = self.build_features()
        return self.run_core(feat)

    def save_run(self, out_folder, result, stats, scores, anchors, candidates, paths, weights):
        return save_run(out_folder, self.symbols, self.params, result, stats, scores, candidates, paths, weights)
