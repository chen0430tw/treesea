from __future__ import annotations
from typing import Dict, List, Optional
import multiprocessing

from .forcing import GridConfig
from .weather_state import WeatherState
from .dynamics import branch_step, LatentHeatingBudget
from .ranking import score_state
import numpy as np


DEFAULT_BRANCHES: List[dict] = [
    # wind_rot_deg: per-family initial-wind rotation around the grid center,
    # spread across ±30° to give the ensemble a directional degree of freedom.
    # Without this, every branch inherits the same obs-injected wind and the
    # background field drags every center cell to the same direction — no
    # candidate can score "closer to observed wind direction" than another.
    # B-档 sweep 结果：rotation ±30° linspace(6) + WD_CENTER_PENALTY_WEIGHT=0.20
    # 甜点位：wd RMSE 99→66°（-33°），T 代价仅 0.028°C，Pareto 拐点
    {"name": "weak_mix",     "Kh": 240, "Kt": 120, "Kq":  95, "drag": 1.2e-5, "humid_couple": 0.80, "nudging": 0.00014, "pg_scale": 1.00, "wind_rot_deg": -30.0},
    {"name": "balanced",     "Kh": 360, "Kt": 180, "Kq": 130, "drag": 1.5e-5, "humid_couple": 1.00, "nudging": 0.00016, "pg_scale": 1.00, "wind_rot_deg": -18.0},
    {"name": "high_mix",     "Kh": 520, "Kt": 260, "Kq": 180, "drag": 1.8e-5, "humid_couple": 1.05, "nudging": 0.00017, "pg_scale": 1.00, "wind_rot_deg":  -6.0},
    {"name": "humid_bias",   "Kh": 340, "Kt": 175, "Kq": 220, "drag": 1.5e-5, "humid_couple": 1.24, "nudging": 0.00016, "pg_scale": 1.00, "wind_rot_deg":  +6.0},
    {"name": "strong_pg",    "Kh": 300, "Kt": 150, "Kq": 125, "drag": 1.2e-5, "humid_couple": 0.95, "nudging": 0.00015, "pg_scale": 1.18, "wind_rot_deg": +18.0},
    {"name": "terrain_lock", "Kh": 330, "Kt": 170, "Kq": 135, "drag": 1.6e-5, "humid_couple": 1.02, "nudging": 0.00015, "pg_scale": 1.04, "wind_rot_deg": +30.0},
]


def _rotate_wind_inplace(state: WeatherState, angle_deg: float) -> WeatherState:
    """Rotate (u, v) fields by angle_deg (positive = counter-clockwise).

    Returns a new WeatherState; h/T/q fields are reused (read-only aliases).
    The rotation is applied uniformly across the grid — small angles (±30°)
    only mildly perturb the background flow while giving each ensemble
    member a distinct center-cell wind direction.
    """
    if abs(angle_deg) < 1e-9:
        return state
    a = np.deg2rad(angle_deg)
    c, s = np.cos(a), np.sin(a)
    u_rot =  c * state.u - s * state.v
    v_rot =  s * state.u + c * state.v
    return WeatherState(h=state.h, u=u_rot, v=v_rot, T=state.T, q=state.q)


def _run_one_task(args: tuple) -> dict:
    """Top-level function for multiprocessing (must be picklable)."""
    (branch_params, initial_state_dict, obs_dict, topography,
     cfg, pressure_balance) = args

    initial_state = WeatherState.from_dict(initial_state_dict)
    obs = WeatherState.from_dict(obs_dict)

    params = dict(branch_params)
    params["pg_scale"] = params.get("pg_scale", 1.0) * pressure_balance
    wind_rot = float(params.get("wind_rot_deg", 0.0))

    state = WeatherState.from_dict(initial_state.to_dict())
    state = _rotate_wind_inplace(state, wind_rot)
    budget = None
    for _ in range(cfg.STEPS):
        state, budget = branch_step(state, params, obs, topography, cfg, budget)

    metric = score_state(state, obs, cfg)
    result = {"name": branch_params["name"], "state": state.to_dict(),
              "wind_rot_deg": wind_rot}
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
    params = dict(branch_params)
    params["pg_scale"] = params.get("pg_scale", 1.0) * pressure_balance
    wind_rot = float(params.get("wind_rot_deg", 0.0))

    state = WeatherState.from_dict(initial_state.to_dict())
    state = _rotate_wind_inplace(state, wind_rot)
    budget = None
    for _ in range(cfg.STEPS):
        state, budget = branch_step(state, params, obs, topography, cfg, budget)

    metric = score_state(state, obs, cfg)
    result = {"name": branch_params["name"], "state": state.to_dict(),
              "wind_rot_deg": wind_rot}
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
    """Run ensemble forecast using the physically-safe branch_step."""
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
