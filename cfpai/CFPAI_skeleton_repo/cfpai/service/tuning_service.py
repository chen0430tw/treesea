from __future__ import annotations
from pathlib import Path

from cfpai.multiasset_stooq_utm import tune_stooq_multiasset

BASE_DIR = Path("/mnt/data")


def run_tuning_service(symbols=None, start=None, end=None, generations=6, population=12, elite_k=4, seed=430, out_folder=None) -> dict:
    symbols = symbols or ["SPY.US", "QQQ.US", "TLT.US", "GLD.US", "XLF.US", "XLK.US", "XLE.US"]
    run_dir = Path(out_folder) if out_folder else BASE_DIR / "runs" / "tuning_latest"
    best_params, hist, result, payload = tune_stooq_multiasset(symbols=symbols, start=start, end=end, generations=generations, population=population, elite_k=elite_k, seed=seed)
    model = payload["model"]
    model.save_run(run_dir, result, payload["stats"], payload["scores"], payload["anchors"], payload["candidates"], payload["paths"], payload["weights"])
    hist.to_csv(run_dir / "utm_search_history.csv", index=False, encoding="utf-8-sig")
    return {"status": "ok", "run_dir": str(run_dir), "symbols": symbols, "start": start, "end": end, "generations": generations, "population": population, "elite_k": elite_k, "seed": seed, "best_params": best_params.__dict__, "stats": payload["stats"], "planning": payload["planning"]}
