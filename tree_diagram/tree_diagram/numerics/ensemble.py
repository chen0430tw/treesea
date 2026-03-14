from __future__ import annotations
from typing import Dict, List, Optional
import multiprocessing

from .forcing import GridConfig
from .weather_state import WeatherState
from .dynamics import branch_step
from .ranking import score_state


DEFAULT_BRANCHES: List[dict] = [
    {
        "name": "weak_mix",
        "Kh": 240,
        "Kt": 120,
        "Kq": 95,
        "drag": 1.2e-5,
        "humid_couple": 0.80,
        "nudging": 0.00014,
        "pg_scale": 1.00,
    },
    {
        "name": "balanced",
        "Kh": 360,
        "Kt": 180,
        "Kq": 130,
        "drag": 1.5e-5,
        "humid_couple": 1.00,
        "nudging": 0.00016,
        "pg_scale": 1.00,
    },
    {
        "name": "high_mix",
        "Kh": 520,
        "Kt": 260,
        "Kq": 180,
        "drag": 1.8e-5,
        "humid_couple": 1.05,
        "nudging": 0.00017,
        "pg_scale": 1.00,
    },
    {
        "name": "humid_bias",
        "Kh": 340,
        "Kt": 175,
        "Kq": 220,
        "drag": 1.5e-5,
        "humid_couple": 1.24,
        "nudging": 0.00016,
        "pg_scale": 1.00,
    },
    {
        "name": "strong_pg",
        "Kh": 300,
        "Kt": 150,
        "Kq": 125,
        "drag": 1.2e-5,
        "humid_couple": 0.95,
        "nudging": 0.00015,
        "pg_scale": 1.18,
    },
    {
        "name": "terrain_lock",
        "Kh": 330,
        "Kt": 170,
        "Kq": 135,
        "drag": 1.6e-5,
        "humid_couple": 1.02,
        "nudging": 0.00015,
        "pg_scale": 1.04,
    },
]


def _run_one_task(args: tuple) -> dict:
    """Top-level function for multiprocessing (must be picklable)."""
    branch_params, initial_state_dict, obs_dict, topography, cfg, pressure_balance = args

    initial_state = WeatherState.from_dict(initial_state_dict)
    obs = WeatherState.from_dict(obs_dict)

    # Apply pressure_balance scaling to pressure gradient
    params = dict(branch_params)
    params["pg_scale"] = params.get("pg_scale", 1.0) * pressure_balance

    state = WeatherState.from_dict(initial_state.to_dict())
    for _ in range(cfg.STEPS):
        state = branch_step(state, params, obs, topography, cfg)

    metric = score_state(state, obs, cfg)
    result = {"name": branch_params["name"], "state": state.to_dict()}
    result.update(metric)
    return result


def run_one_branch(
    branch_params: dict,
    initial_state: WeatherState,
    obs: WeatherState,
    topography,
    cfg: GridConfig,
    pressure_balance: float = 1.0,
) -> dict:
    import numpy as np

    params = dict(branch_params)
    params["pg_scale"] = params.get("pg_scale", 1.0) * pressure_balance

    state = WeatherState.from_dict(initial_state.to_dict())
    for _ in range(cfg.STEPS):
        state = branch_step(state, params, obs, topography, cfg)

    metric = score_state(state, obs, cfg)
    result = {"name": branch_params["name"], "state": state.to_dict()}
    result.update(metric)
    return result


def run_ensemble(
    initial_state: WeatherState,
    obs: WeatherState,
    topography,
    cfg: GridConfig,
    pressure_balance: float = 1.0,
    branches: Optional[List[dict]] = None,
    n_workers: int = 1,
) -> List[dict]:
    if branches is None:
        branches = DEFAULT_BRANCHES

    tasks = [
        (bp, initial_state.to_dict(), obs.to_dict(), topography, cfg, pressure_balance)
        for bp in branches
    ]

    if n_workers > 1:
        with multiprocessing.Pool(processes=n_workers) as pool:
            results = pool.map(_run_one_task, tasks)
    else:
        results = [_run_one_task(t) for t in tasks]

    return results
