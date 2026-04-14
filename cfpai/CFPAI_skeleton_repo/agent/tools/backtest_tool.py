from __future__ import annotations
from cfpai.service.backtest_service import run_backtest_service

def run_backtest(symbols=None, start=None, end=None, use_utm=False, config=None):
    config = config or {}
    return run_backtest_service(
        symbols=symbols,
        start=start,
        end=end,
        use_utm=use_utm,
        generations=config.get("generations", 6),
        population=config.get("population", 12),
        elite_k=config.get("elite_k", 4),
        seed=config.get("seed", 430),
        out_folder=config.get("out_folder"),
    )
