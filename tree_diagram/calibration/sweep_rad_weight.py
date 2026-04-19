"""2D sweep (GPU-enabled): weight × T_rad_cooling at fixed rotation ±180°.

New architecture:
  - 256×192 grid at DX=6km (finer physics than old 64×48/24km)
  - cupy path: convert state to GPU once, all branch_step runs on H100
  - Sequential (no multiprocessing): GPU kernel launches inside a single Python
    process. 2 H100s on nano5 login node; we use 1 — that's already fast enough.

For each combo:
  1. Set DEFAULT_BRANCHES wind_rot=linspace(-180,180,6), wind_nudge=1.5e-4
  2. Set WD_CENTER_PENALTY_WEIGHT + dynamics.T_RAD_COOL_K_PER_DAY
  3. Fit B-calibration (30-day obs) on GPU
  4. OOS 5 days
  5. 7-day free integration per family, weighted fusion via day-1 score
"""
from __future__ import annotations
import json
import math
import sys
import time
from datetime import date
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tree_diagram.numerics import ensemble, ranking, dynamics
from tree_diagram.numerics.forcing import GridConfig, build_grid, build_topography
from tree_diagram.numerics.weather_contract import WeatherCalibration
from tree_diagram.numerics.dynamics import branch_step
from tree_diagram.numerics.ensemble import _rotate_wind_inplace, DEFAULT_BRANCHES
from tree_diagram.numerics.ranking import score_state
from tree_diagram.numerics.weather_state import WeatherState
from tree_diagram.numerics._xp import has_cupy, to_numpy
from td_taipei_forecast import build_taipei_state, ReferenceObs
from scipy import stats as sp_stats

from calibration.fit_calibration_b import (
    OBS_FILE, fit_two_param, fit_scale_through_origin, invert_q_to_rh_ratio,
)
from calibration.oos_validate import fetch_obs, OOS_START, OOS_END


WEIGHTS     = [0.20, 0.40, 0.80]
RAD_RATES   = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0]
ROT_MAX_DEG = 180.0
USE_GPU     = True

OUT_FILE = Path(__file__).parent / "sweep_rad_weight.json"
TODAY = date(2026, 4, 19)
TAIPEI_OBS = ReferenceObs(T_avg_C=24.0, RH_pct=82.5, P_hPa=1009.0,
                           ws_ms=3.6, wd_deg=270.0)


def build_rotated_branches() -> list:
    rots = np.linspace(-ROT_MAX_DEG, +ROT_MAX_DEG, 6)
    templ = [
        {"name": "weak_mix",     "Kh": 240, "Kt": 120, "Kq":  95, "drag": 1.2e-5, "humid_couple": 0.80, "nudging": 0.00014, "pg_scale": 1.00, "wind_nudge": 1.5e-4},
        {"name": "balanced",     "Kh": 360, "Kt": 180, "Kq": 130, "drag": 1.5e-5, "humid_couple": 1.00, "nudging": 0.00016, "pg_scale": 1.00, "wind_nudge": 1.5e-4},
        {"name": "high_mix",     "Kh": 520, "Kt": 260, "Kq": 180, "drag": 1.8e-5, "humid_couple": 1.05, "nudging": 0.00017, "pg_scale": 1.00, "wind_nudge": 1.5e-4},
        {"name": "humid_bias",   "Kh": 340, "Kt": 175, "Kq": 220, "drag": 1.5e-5, "humid_couple": 1.24, "nudging": 0.00016, "pg_scale": 1.00, "wind_nudge": 1.5e-4},
        {"name": "strong_pg",    "Kh": 300, "Kt": 150, "Kq": 125, "drag": 1.2e-5, "humid_couple": 0.95, "nudging": 0.00015, "pg_scale": 1.18, "wind_nudge": 1.5e-4},
        {"name": "terrain_lock", "Kh": 330, "Kt": 170, "Kq": 135, "drag": 1.6e-5, "humid_couple": 1.02, "nudging": 0.00015, "pg_scale": 1.04, "wind_nudge": 1.5e-4},
    ]
    for i, b in enumerate(templ):
        b["wind_rot_deg"] = float(rots[i])
    return templ


def _maybe_gpu_state(s: WeatherState) -> WeatherState:
    return s.to_gpu() if USE_GPU and has_cupy() else s


def _maybe_gpu_topo(topo):
    if USE_GPU and has_cupy():
        import cupy as cp
        return cp.asarray(topo)
    return topo


def run_family(init_state: WeatherState, obs_state: WeatherState, topo,
               cfg: GridConfig, fam: dict, steps: int,
               nudging_off_after_step: int | None = None) -> tuple:
    """Run one family for `steps` time-steps. If nudging_off_after_step is set,
    params.nudging and params.wind_nudge zeroed after that step index (for
    multi-day free integration after day 1)."""
    state = _rotate_wind_inplace(init_state, fam["wind_rot_deg"])
    budget = None
    params = dict(fam)
    nudge_orig = params.get("nudging", 0.0)
    wind_nudge_orig = params.get("wind_nudge", 0.0)
    for step_idx in range(steps):
        if nudging_off_after_step is not None and step_idx >= nudging_off_after_step:
            params["nudging"] = 0.0
            params["wind_nudge"] = 0.0
        else:
            params["nudging"] = nudge_orig
            params["wind_nudge"] = wind_nudge_orig
        state, budget = branch_step(state, params, obs_state, topo, cfg, budget)
    return state, budget


def run_ensemble_sequential(init_state, obs_state, topo, cfg, branches: list) -> list:
    """Run all families sequentially, each from fresh init, return ranked list."""
    results = []
    for fam in branches:
        state, _ = run_family(init_state, obs_state, topo, cfg, fam, cfg.STEPS)
        metric = score_state(state, obs_state, cfg)
        result = {"name": fam["name"], "state": state, **metric}
        results.append(result)
    # Sort by score desc
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def fit_b_scheme(obs_train, topo, cfg, branches, grid_center) -> tuple[WeatherCalibration, dict]:
    """30-day B-scheme fit. Returns (WeatherCalibration, diagnostics)."""
    cy, cx = grid_center
    T_int_list, T_real_list, q_int_list, h_ctr_list = [], [], [], []
    win_int_list, win_real_list, RH_real_list, P_real_list = [], [], [], []

    XX, YY, _x, _y = build_grid(cfg)

    for d in obs_train:
        obs_ref = ReferenceObs(T_avg_C=d["T_mean_C"], RH_pct=d["RH_mean_pct"],
                               P_hPa=d["P_mean_hPa"], ws_ms=d["ws_mean_ms"],
                               wd_deg=d["wd_vec_deg"])
        init_np = build_taipei_state(XX, YY, to_numpy(topo), cfg, perturbation=-1.0, obs_ref=obs_ref)
        obs_np = build_taipei_state(XX, YY, to_numpy(topo), cfg, perturbation=0.0, obs_ref=obs_ref)
        init = _maybe_gpu_state(init_np)
        obs_state = _maybe_gpu_state(obs_np)

        ranked = run_ensemble_sequential(init, obs_state, topo, cfg, branches)
        top = ranked[0]["state"]

        T_int_list.append(float(top.T[cy, cx]))
        h_ctr_list.append(float(top.h[cy, cx]))
        q_int_list.append(float(top.q[cy, cx]))
        win_int_list.append(math.sqrt(float(top.u[cy, cx])**2 + float(top.v[cy, cx])**2))

        T_real_list.append(d["T_mean_C"] + 273.15)
        win_real_list.append(d["ws_mean_ms"])
        RH_real_list.append(d["RH_mean_pct"])
        P_real_list.append(d["P_mean_hPa"])

    T_int = np.array(T_int_list); T_real = np.array(T_real_list)
    q_int = np.array(q_int_list); h_ctr = np.array(h_ctr_list)
    win_int = np.array(win_int_list); win_real = np.array(win_real_list)
    RH_real = np.array(RH_real_list); P_real = np.array(P_real_list)

    T_fit = fit_two_param(T_int, T_real)
    wind_fit = fit_scale_through_origin(win_int, win_real)
    T_2m_C_ts = T_fit["theilsen"]["slope"] * T_int + T_fit["theilsen"]["intercept"] - 273.15
    q_rh = float(np.median(invert_q_to_rh_ratio(q_int, T_2m_C_ts, RH_real)))
    dh = h_ctr - 5700.0
    mask = np.abs(dh) > 10.0
    h2p = float(np.median((1013 - P_real[mask]) / dh[mask])) if mask.sum() >= 3 else 0.02

    cal = WeatherCalibration(
        location_name="sweep-gpu", fitted_date="sweep-gpu",
        T_offset_K=T_fit["theilsen"]["intercept"], T_scale=T_fit["theilsen"]["slope"],
        h_to_pressure_k=h2p, q_to_rh_ratio=q_rh,
        wind_scale=wind_fit["theilsen_median"]["scale"],
    )
    return cal, {"n_days": len(obs_train)}


def run_oos(obs_oos, topo, cfg, branches, cal, grid_center) -> dict:
    cy, cx = grid_center
    XX, YY, _x, _y = build_grid(cfg)
    errs_T, errs_wd = [], []
    for d in obs_oos:
        obs_ref = ReferenceObs(T_avg_C=d["T_mean_C"], RH_pct=d["RH_mean_pct"],
                               P_hPa=d["P_mean_hPa"], ws_ms=d["ws_mean_ms"],
                               wd_deg=d["wd_vec_deg"])
        init_np = build_taipei_state(XX, YY, to_numpy(topo), cfg, perturbation=-1.0, obs_ref=obs_ref)
        obs_np = build_taipei_state(XX, YY, to_numpy(topo), cfg, perturbation=0.0, obs_ref=obs_ref)
        init = _maybe_gpu_state(init_np); obs_state = _maybe_gpu_state(obs_np)
        ranked = run_ensemble_sequential(init, obs_state, topo, cfg, branches)
        top = ranked[0]["state"]

        T_int_K = float(top.T[cy, cx])
        u = float(top.u[cy, cx]); v = float(top.v[cy, cx])
        T_pred = cal.T_scale * T_int_K + cal.T_offset_K - 273.15
        wd_pred = (math.degrees(math.atan2(-u, -v)) + 360.0) % 360.0

        errs_T.append(T_pred - d["T_mean_C"])
        errs_wd.append((wd_pred - d["wd_vec_deg"] + 540.0) % 360.0 - 180.0)

    return {"T_rmse": float(np.sqrt(np.mean(np.array(errs_T)**2))),
            "wd_rmse": float(np.sqrt(np.mean(np.array(errs_wd)**2)))}


def run_week(topo, cfg_day, branches, cal, grid_center) -> dict:
    cy, cx = grid_center
    XX, YY, _x, _y = build_grid(cfg_day)
    init_np = build_taipei_state(XX, YY, to_numpy(topo), cfg_day, perturbation=-1.0, obs_ref=TAIPEI_OBS)
    obs_np = build_taipei_state(XX, YY, to_numpy(topo), cfg_day, perturbation=0.0, obs_ref=TAIPEI_OBS)
    init = _maybe_gpu_state(init_np); obs_state = _maybe_gpu_state(obs_np)

    per_family = []
    for fam in branches:
        state = _rotate_wind_inplace(init, fam["wind_rot_deg"])
        budget = None
        daily = []
        day1_score = None
        for d_idx in range(7):
            params = dict(fam)
            if d_idx + 1 > 1:
                params["nudging"] = 0.0
                params["wind_nudge"] = 0.0
            for _ in range(cfg_day.STEPS):
                state, budget = branch_step(state, params, obs_state, topo, cfg_day, budget)
            if d_idx == 0:
                day1_score = float(score_state(state, obs_state, cfg_day)["score"])
            daily.append({
                "T_K": float(state.T[cy, cx]), "h": float(state.h[cy, cx]),
                "q": float(state.q[cy, cx]),
                "u": float(state.u[cy, cx]), "v": float(state.v[cy, cx]),
            })
        per_family.append({"name": fam["name"], "day1_score": day1_score, "daily": daily})

    # Weighted fusion via day-1 score (softmax-shifted)
    scores = np.array([f["day1_score"] for f in per_family])
    shifted = scores - scores.min() + 1e-6
    weights = shifted / shifted.sum()
    week_T_C = []
    for d_idx in range(7):
        T_ints = np.array([f["daily"][d_idx]["T_K"] for f in per_family])
        T_int = np.average(T_ints, weights=weights)
        week_T_C.append(cal.T_scale * T_int + cal.T_offset_K - 273.15)
    return {"T_day1": float(week_T_C[0]), "T_day2": float(week_T_C[1]),
            "T_day7": float(week_T_C[6]), "T_max": float(max(week_T_C)),
            "spike": float(max(week_T_C) - week_T_C[0]),
            "trajectory": [float(t) for t in week_T_C]}


def main():
    print("=" * 80)
    print(f"2D GPU SWEEP: weight ∈ {WEIGHTS} × T_rad ∈ {RAD_RATES} K/day")
    print(f"Grid 256×192 / DX=6km ; rot fixed ±{ROT_MAX_DEG}° ; USE_GPU={USE_GPU and has_cupy()}")
    print("=" * 80)

    obs_train = json.loads(OBS_FILE.read_text(encoding="utf-8"))["days"]
    obs_oos = fetch_obs(OOS_START, OOS_END)

    cfg_oos = GridConfig(NX=256, NY=192, DX=6000.0, DY=6000.0, DT=60.0, STEPS=120)
    cfg_day = GridConfig(NX=256, NY=192, DX=6000.0, DY=6000.0, DT=60.0, STEPS=1440)
    XX, YY, _x, _y = build_grid(cfg_oos)
    topo_np = build_topography(XX, YY)
    topo = _maybe_gpu_topo(topo_np)
    cy = int(np.argmin(np.abs(YY[:, 0])))
    cx = int(np.argmin(np.abs(XX[0, :])))
    grid_center = (cy, cx)

    branches = build_rotated_branches()

    results = []
    t0 = time.time()
    for j, wd_w in enumerate(WEIGHTS):
        for k, rad in enumerate(RAD_RATES):
            idx = j * len(RAD_RATES) + k + 1
            N = len(WEIGHTS) * len(RAD_RATES)
            ensemble.DEFAULT_BRANCHES = branches
            ranking.WD_CENTER_PENALTY_WEIGHT = wd_w
            dynamics.T_RAD_COOL_K_PER_DAY = rad
            elapsed = time.time() - t0
            print(f"[{idx:2d}/{N}] w={wd_w:.2f}  rad={rad:.1f}  ...", end=" ", flush=True)
            cal, _ = fit_b_scheme(obs_train, topo, cfg_oos, branches, grid_center)
            oos = run_oos(obs_oos, topo, cfg_oos, branches, cal, grid_center)
            week = run_week(topo, cfg_day, branches, cal, grid_center)
            print(f"OOS T={oos['T_rmse']:.3f}  wd={oos['wd_rmse']:.1f}  "
                  f"week d1={week['T_day1']:.1f} d2={week['T_day2']:.1f} "
                  f"d7={week['T_day7']:.1f} spike={week['spike']:+.2f}  "
                  f"[{elapsed:.0f}s]")
            results.append({"weight": wd_w, "rad_K_day": rad,
                            "oos": oos, "week": week,
                            "calibration": {
                                "T_offset_K": cal.T_offset_K, "T_scale": cal.T_scale,
                                "q_to_rh_ratio": cal.q_to_rh_ratio,
                                "wind_scale": cal.wind_scale,
                                "h_to_pressure_k": cal.h_to_pressure_k}})

    # Landscape
    print("\n" + "=" * 80)
    print("OOS T_RMSE")
    print(f"{'w\\rad':<8}", *[f"{r:>6.1f}" for r in RAD_RATES])
    for w in WEIGHTS:
        row = [r for r in results if abs(r["weight"]-w)<1e-9]; row.sort(key=lambda x: x["rad_K_day"])
        print(f"{w:<8.2f}", *[f"{r['oos']['T_rmse']:>6.3f}" for r in row])

    print("\nWeek Day7 T (°C)")
    print(f"{'w\\rad':<8}", *[f"{r:>6.1f}" for r in RAD_RATES])
    for w in WEIGHTS:
        row = [r for r in results if abs(r["weight"]-w)<1e-9]; row.sort(key=lambda x: x["rad_K_day"])
        print(f"{w:<8.2f}", *[f"{r['week']['T_day7']:>6.2f}" for r in row])

    viable = [r for r in results if r["oos"]["T_rmse"] < 0.5]
    if viable:
        best_day7 = min(viable, key=lambda r: abs(r["week"]["T_day7"] - 22.0))
        print("\n" + "=" * 80)
        print(f"BEST by day7 climo match:")
        print(f"  w={best_day7['weight']}  rad={best_day7['rad_K_day']}  "
              f"OOS T={best_day7['oos']['T_rmse']:.3f}  wd={best_day7['oos']['wd_rmse']:.1f}  "
              f"spike={best_day7['week']['spike']:+.2f}  day7={best_day7['week']['T_day7']:.2f}")

    OUT_FILE.write_text(json.dumps({"grid_256x192": True, "use_gpu": USE_GPU and has_cupy(),
                                     "results": results}, indent=2), encoding="utf-8")
    print(f"\nSaved → {OUT_FILE}")


if __name__ == "__main__":
    main()
