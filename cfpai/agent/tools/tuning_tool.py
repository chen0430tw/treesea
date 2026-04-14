from __future__ import annotations
from cfpai.service.tuning_service import run_tuning_service

def run_tuning(symbols=None, start=None, end=None, generations=6, population=12, elite_k=4, seed=430):
    return run_tuning_service(
        symbols=symbols,
        start=start,
        end=end,
        generations=generations,
        population=population,
        elite_k=elite_k,
        seed=seed,
    )
