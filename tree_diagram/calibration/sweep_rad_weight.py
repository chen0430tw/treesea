"""2D sweep: weight × T_rad_cooling at fixed rotation ±180°.

For each combo:
  1. Set DEFAULT_BRANCHES wind_rot=linspace(-180,180,6), wind_nudge=1.5e-4
  2. Set WD_CENTER_PENALTY_WEIGHT
  3. Set dynamics.T_RAD_COOL_K_PER_DAY
  4. Run B-scheme fit (30 days) → calibration
  5. Run OOS (5 days) → nowcast metrics
  6. Run 7-day free integration → multi-day T trajectory
  7. Record: OOS T_RMSE, OOS wd_RMSE, week_T_day2 (spike), week_T_max,
             week_T_day7 (final), week_RH_day7

Finds new sweet spot under updated physics (wind_nudge + radiative cooling).
"""
from __future__ import annotations
import json
import math
import os
for _var in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS",
             "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
import sys
import time
from datetime import date, timedelta
from multiprocessing import get_context
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tree_diagram.numerics import ensemble, ranking, dynamics
from tree_diagram.numerics.forcing import GridConfig, build_grid, build_topography
from tree_diagram.numerics.weather_contract import WeatherCalibration
from tree_diagram.numerics.dynamics import branch_step
from tree_diagram.numerics.ensemble import _rotate_wind_inplace
from tree_diagram.numerics.weather_state import WeatherState
from td_taipei_forecast import build_taipei_state, ReferenceObs
from scipy import stats as sp_stats

from calibration.fit_calibration_b import (
    OBS_FILE, run_td_for_day, fit_two_param, fit_scale_through_origin,
    invert_q_to_rh_ratio,
)
from calibration.oos_validate import fetch_obs, predict_day, OOS_START, OOS_END


WEIGHTS     = [0.20, 0.40, 0.80]
RAD_RATES   = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0]    # K/day
ROT_MAX_DEG = 180.0                              # fixed from previous sweep

OUT_FILE = Path(__file__).parent / "sweep_rad_weight.json"
TODAY = date(2026, 4, 19)
TAIPEI_OBS = ReferenceObs(T_avg_C=24.0, RH_pct=82.5, P_hPa=1009.0,
                           ws_ms=3.6, wd_deg=270.0)


_WORKER_CFG = None
_WORKER_GRID = None


def _worker_init(cfg_dict: dict):
    global _WORKER_CFG, _WORKER_GRID
    _WORKER_CFG = GridConfig(**cfg_dict)
    XX, YY, _x, _y = build_grid(_WORKER_CFG)
    topo = build_topography(XX, YY)
    cy = int(np.argmin(np.abs(YY[:, 0])))
    cx = int(np.argmin(np.abs(XX[0, :])))
    _WORKER_GRID = {"XX": XX, "YY": YY, "topo": topo, "cy": cy, "cx": cx}


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


def _worker_fit_day(task: tuple) -> dict:
    d, branches, wd_w, rad = task
    ensemble.DEFAULT_BRANCHES = branches
    ranking.WD_CENTER_PENALTY_WEIGHT = wd_w
    dynamics.T_RAD_COOL_K_PER_DAY = rad
    obs_ref = ReferenceObs(T_avg_C=d["T_mean_C"], RH_pct=d["RH_mean_pct"],
                           P_hPa=d["P_mean_hPa"], ws_ms=d["ws_mean_ms"],
                           wd_deg=d["wd_vec_deg"])
    r = run_td_for_day(obs_ref, _WORKER_CFG, _WORKER_GRID)
    return {"obs": d, "td": r}


def _worker_oos_day(task: tuple) -> dict:
    d, cal_dict, branches, wd_w, rad = task
    ensemble.DEFAULT_BRANCHES = branches
    ranking.WD_CENTER_PENALTY_WEIGHT = wd_w
    dynamics.T_RAD_COOL_K_PER_DAY = rad
    cal = WeatherCalibration(**cal_dict)
    return predict_day(d, cal, _WORKER_CFG, _WORKER_GRID)


def _worker_week_family(task: tuple) -> dict:
    """Run one family for 7 days (DA day 1 + free days 2-7), return daily center values."""
    fam, obs_ref_dict, branches, wd_w, rad = task
    ensemble.DEFAULT_BRANCHES = branches
    ranking.WD_CENTER_PENALTY_WEIGHT = wd_w
    dynamics.T_RAD_COOL_K_PER_DAY = rad

    obs_ref = ReferenceObs(**obs_ref_dict)
    XX, YY, topo = _WORKER_GRID["XX"], _WORKER_GRID["YY"], _WORKER_GRID["topo"]
    cy, cx = _WORKER_GRID["cy"], _WORKER_GRID["cx"]

    cfg_day = GridConfig(NX=_WORKER_CFG.NX, NY=_WORKER_CFG.NY, DX=_WORKER_CFG.DX,
                         DY=_WORKER_CFG.DY, DT=_WORKER_CFG.DT, STEPS=1440)

    init = build_taipei_state(XX, YY, topo, cfg_day, perturbation=-1.0, obs_ref=obs_ref)
    obs_state = build_taipei_state(XX, YY, topo, cfg_day, perturbation=0.0, obs_ref=obs_ref)

    state = _rotate_wind_inplace(init, fam["wind_rot_deg"])
    budget = None
    daily = []
    for d_idx in range(7):
        params = dict(fam)
        if d_idx + 1 > 1:
            params["nudging"] = 0.0
            params["wind_nudge"] = 0.0
        for _ in range(1440):
            state, budget = branch_step(state, params, obs_state, topo, cfg_day, budget)
        daily.append({"T_K": float(state.T[cy, cx]),
                      "h": float(state.h[cy, cx]),
                      "q": float(state.q[cy, cx]),
                      "u": float(state.u[cy, cx]),
                      "v": float(state.v[cy, cx])})
    return {"family": fam["name"], "score": fam.get("_day1_score", 0.5),
            "daily": daily}


def fit_and_eval(cfg, obs_train, obs_oos, branches, wd_w, rad, pool) -> dict:
    # Fit (30-day parallel)
    rows = pool.map(_worker_fit_day, [(d, branches, wd_w, rad) for d in obs_train])

    T_int = np.array([r["td"]["T_internal_K"] for r in rows])
    T_real = np.array([r["obs"]["T_mean_C"] + 273.15 for r in rows])
    q_int = np.array([r["td"]["q_internal"] for r in rows])
    h_ctr = np.array([r["td"]["h_center_m"] for r in rows])
    win_int = np.array([math.sqrt(r["td"]["u_center"]**2 + r["td"]["v_center"]**2) for r in rows])
    win_real = np.array([r["obs"]["ws_mean_ms"] for r in rows])
    RH_real = np.array([r["obs"]["RH_mean_pct"] for r in rows])
    P_real = np.array([r["obs"]["P_mean_hPa"] for r in rows])

    T_fit = fit_two_param(T_int, T_real)
    wind_fit = fit_scale_through_origin(win_int, win_real)
    T_2m_C_ts = T_fit["theilsen"]["slope"] * T_int + T_fit["theilsen"]["intercept"] - 273.15
    q_rh = float(np.median(invert_q_to_rh_ratio(q_int, T_2m_C_ts, RH_real)))
    dh = h_ctr - 5700.0
    mask = np.abs(dh) > 10.0
    h2p = float(np.median((1013 - P_real[mask]) / dh[mask])) if mask.sum() >= 3 else 0.02

    cal = WeatherCalibration(
        location_name="sweep", fitted_date="sweep",
        T_offset_K=T_fit["theilsen"]["intercept"], T_scale=T_fit["theilsen"]["slope"],
        h_to_pressure_k=h2p, q_to_rh_ratio=q_rh,
        wind_scale=wind_fit["theilsen_median"]["scale"],
    )
    cal_dict = {"location_name": cal.location_name, "fitted_date": cal.fitted_date,
                "T_offset_K": cal.T_offset_K, "T_scale": cal.T_scale,
                "h_to_pressure_k": cal.h_to_pressure_k,
                "q_to_rh_ratio": cal.q_to_rh_ratio, "wind_scale": cal.wind_scale}

    # OOS (5-day parallel)
    preds = pool.map(_worker_oos_day, [(d, cal_dict, branches, wd_w, rad) for d in obs_oos])

    def angle_diff(a, b): return (a - b + 540.0) % 360.0 - 180.0
    errs_T = np.array([p["T_C"] - d["T_mean_C"] for p, d in zip(preds, obs_oos)])
    errs_wd = np.array([angle_diff(p["wd_deg"], d["wd_vec_deg"]) for p, d in zip(preds, obs_oos)])

    oos_T_rmse = float(np.sqrt(np.mean(errs_T**2)))
    oos_wd_rmse = float(np.sqrt(np.mean(errs_wd**2)))

    # 7-day forecast (6 families parallel)
    obs_ref_d = TAIPEI_OBS.__dict__
    fam_results = pool.map(_worker_week_family,
                            [(f, obs_ref_d, branches, wd_w, rad) for f in branches])

    # Use day-1 score as weights (uniform fallback)
    weights = np.ones(6) / 6
    # Weighted daily center
    week_T_C = []
    week_RH = []
    for d_idx in range(7):
        stack_T = np.array([fr["daily"][d_idx]["T_K"] for fr in fam_results])
        stack_q = np.array([fr["daily"][d_idx]["q"] for fr in fam_results])
        T_int_avg = np.average(stack_T, weights=weights)
        q_avg = np.average(stack_q, weights=weights)
        T_2m_C = cal.T_scale * T_int_avg + cal.T_offset_K - 273.15
        week_T_C.append(T_2m_C)
        week_RH.append(cal.map_humidity(q_avg, T_2m_C))

    return {
        "oos_T_rmse": oos_T_rmse,
        "oos_wd_rmse": oos_wd_rmse,
        "week_T_day1": float(week_T_C[0]),
        "week_T_day2": float(week_T_C[1]),
        "week_T_day7": float(week_T_C[6]),
        "week_T_max":  float(max(week_T_C)),
        "week_T_spike": float(max(week_T_C) - week_T_C[0]),
        "week_RH_day7": float(week_RH[6]),
        "week_trajectory_T_C": [float(t) for t in week_T_C],
        "calibration": cal_dict,
    }


def main():
    print("=" * 80)
    print(f"3D SWEEP: weight ∈ {WEIGHTS} × T_rad ∈ {RAD_RATES} K/day  (rot fixed ±{ROT_MAX_DEG}°)")
    print(f"Total combos: {len(WEIGHTS) * len(RAD_RATES)}")
    print("=" * 80)

    obs_train = json.loads(OBS_FILE.read_text(encoding="utf-8"))["days"]
    obs_oos = fetch_obs(OOS_START, OOS_END)
    print(f"Training: {len(obs_train)} days;  OOS: {len(obs_oos)} days")

    cfg = GridConfig(NX=64, NY=48, DX=24000.0, DY=24000.0, DT=60.0, STEPS=120)
    cfg_dict = dict(NX=cfg.NX, NY=cfg.NY, DX=cfg.DX, DY=cfg.DY, DT=cfg.DT, STEPS=cfg.STEPS)

    n_workers = 8
    print(f"Using {n_workers} worker processes (spawn)\n")

    ctx = get_context("spawn")
    pool = ctx.Pool(processes=n_workers, initializer=_worker_init, initargs=(cfg_dict,))

    results = []
    t0 = time.time()
    try:
        branches = build_rotated_branches()
        for j, wd_w in enumerate(WEIGHTS):
            for k, rad in enumerate(RAD_RATES):
                idx = j * len(RAD_RATES) + k + 1
                N = len(WEIGHTS) * len(RAD_RATES)
                elapsed = time.time() - t0
                print(f"[{idx:2d}/{N}] w={wd_w:.2f}  rad={rad:.1f} K/d  ...", end=" ", flush=True)
                m = fit_and_eval(cfg, obs_train, obs_oos, branches, wd_w, rad, pool)
                print(f"OOS T={m['oos_T_rmse']:.3f}  wd={m['oos_wd_rmse']:.1f}°  "
                      f"week T_d1={m['week_T_day1']:.1f} d2={m['week_T_day2']:.1f} "
                      f"max={m['week_T_max']:.1f} d7={m['week_T_day7']:.1f} "
                      f"RH_d7={m['week_RH_day7']:.0f}%  "
                      f"spike={m['week_T_spike']:+.1f}  [{elapsed:.0f}s]")
                results.append({"weight": wd_w, "rad_K_day": rad, **m})
    finally:
        pool.close()
        pool.join()

    # Landscape tables
    print()
    print("=" * 80)
    print("OOS T_RMSE (°C)")
    print("=" * 80)
    print(f"{'w\\rad':<8}", *[f"{r:>6.1f}" for r in RAD_RATES])
    for w in WEIGHTS:
        row = [r for r in results if abs(r["weight"]-w)<1e-9]
        row.sort(key=lambda x: x["rad_K_day"])
        print(f"{w:<8.2f}", *[f"{r['oos_T_rmse']:>6.3f}" for r in row])

    print()
    print("Week Day2 T_spike (°C above day-1)")
    print("=" * 80)
    print(f"{'w\\rad':<8}", *[f"{r:>6.1f}" for r in RAD_RATES])
    for w in WEIGHTS:
        row = [r for r in results if abs(r["weight"]-w)<1e-9]
        row.sort(key=lambda x: x["rad_K_day"])
        print(f"{w:<8.2f}", *[f"{r['week_T_spike']:>+6.2f}" for r in row])

    print()
    print("Week Day7 T (°C) — want ~climo 22°C")
    print("=" * 80)
    print(f"{'w\\rad':<8}", *[f"{r:>6.1f}" for r in RAD_RATES])
    for w in WEIGHTS:
        row = [r for r in results if abs(r["weight"]-w)<1e-9]
        row.sort(key=lambda x: x["rad_K_day"])
        print(f"{w:<8.2f}", *[f"{r['week_T_day7']:>6.2f}" for r in row])

    print()
    print("OOS wd_RMSE (°)")
    print("=" * 80)
    print(f"{'w\\rad':<8}", *[f"{r:>6.1f}" for r in RAD_RATES])
    for w in WEIGHTS:
        row = [r for r in results if abs(r["weight"]-w)<1e-9]
        row.sort(key=lambda x: x["rad_K_day"])
        print(f"{w:<8.2f}", *[f"{r['oos_wd_rmse']:>6.1f}" for r in row])

    # Best: minimize |week_T_spike| subject to OOS T_RMSE<0.5 AND wd_RMSE<80
    viable = [r for r in results if r["oos_T_rmse"] < 0.5 and r["oos_wd_rmse"] < 80]
    if viable:
        best_spike = min(viable, key=lambda r: abs(r["week_T_spike"]))
        best_day7 = min(viable, key=lambda r: abs(r["week_T_day7"] - 22.0))
        print()
        print("=" * 80)
        print(f"BEST by spike stability (min |week_T_day2 - day1|):")
        print(f"  w={best_spike['weight']:.2f}  rad={best_spike['rad_K_day']:.1f}  "
              f"OOS T={best_spike['oos_T_rmse']:.3f}  wd={best_spike['oos_wd_rmse']:.1f}  "
              f"spike={best_spike['week_T_spike']:+.2f}  day7={best_spike['week_T_day7']:.2f}")
        print(f"BEST by day7-climo match (|day7 - 22°C|):")
        print(f"  w={best_day7['weight']:.2f}  rad={best_day7['rad_K_day']:.1f}  "
              f"OOS T={best_day7['oos_T_rmse']:.3f}  wd={best_day7['oos_wd_rmse']:.1f}  "
              f"spike={best_day7['week_T_spike']:+.2f}  day7={best_day7['week_T_day7']:.2f}")

    OUT_FILE.write_text(json.dumps({
        "rotation_max_deg": ROT_MAX_DEG,
        "weights": WEIGHTS,
        "rad_rates": RAD_RATES,
        "results": results,
    }, indent=2), encoding="utf-8")
    print(f"\nSaved → {OUT_FILE}")


if __name__ == "__main__":
    main()
