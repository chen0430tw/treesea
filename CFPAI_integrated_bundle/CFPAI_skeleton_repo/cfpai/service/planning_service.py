from __future__ import annotations
from pathlib import Path

from cfpai.multiasset_stooq import CFPAIMultiAssetStooq

BASE_DIR = Path("/mnt/data")


def run_planning_service(symbols=None, start=None, end=None, out_folder=None) -> dict:
    symbols = symbols or ["SPY.US", "QQQ.US", "TLT.US", "GLD.US", "XLF.US", "XLK.US", "XLE.US"]
    run_dir = Path(out_folder) if out_folder else BASE_DIR / "runs" / "planning_latest"
    model = CFPAIMultiAssetStooq(symbols=symbols, start=start, end=end)
    result, stats, scores, anchors, candidates, paths, weights, planning = model.backtest()
    model.save_run(run_dir, result, stats, scores, anchors, candidates, paths, weights)
    return {"status": "ok", "run_dir": str(run_dir), "symbols": symbols, "start": start, "end": end, "stats": stats, "planning": planning}
