"""2D parameter sweep: rotation range × wind-dir penalty weight.

For each (rot_max, weight) combo:
  1. Override DEFAULT_BRANCHES wind_rot_deg to span [-rot_max, +rot_max]
  2. Set ranking.WD_CENTER_PENALTY_WEIGHT to weight
  3. Run 30-day B-scheme fit → capture in-sample RMSE
  4. Run 5-day OOS → capture out-of-sample RMSE (incl. wind direction)
  5. Record metrics

Output: full JSON landscape + printed heatmap.
"""
from __future__ import annotations
import json
import math
import os
# Limit BLAS threads per process — with 16 workers × 64 OpenBLAS default threads
# we overflow RLIMIT_NPROC on the login node. 1 thread per worker is fine for
# 64×48 grids (multiprocessing already gives us real parallelism).
for _var in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS",
             "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
import sys
import time
from datetime import date
from multiprocessing import Pool
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tree_diagram.numerics import ensemble, ranking
from tree_diagram.numerics.forcing import GridConfig, build_grid, build_topography
from tree_diagram.numerics.weather_contract import WeatherCalibration
from td_taipei_forecast import build_taipei_state, ReferenceObs
from scipy import stats as sp_stats

# Reuse the fit/oos modules' internals without importing their main() side effects
from calibration.fit_calibration_b import (
    OBS_FILE, run_td_for_day, fit_two_param, fit_scale_through_origin,
    invert_q_to_rh_ratio,
)
from calibration.oos_validate import fetch_obs, predict_day, OOS_START, OOS_END


# multiprocessing worker: 30 days parallelize per combo.
# Cannot pass numpy arrays cheaply — each worker rebuilds its own grid_cache.
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


def _worker_run_day(task: tuple) -> dict:
    """task=(day_dict, branches_list, wd_weight). Worker updates module
    globals before running so that respawning the Pool per combo is avoided."""
    d, branches, wd_weight = task
    ensemble.DEFAULT_BRANCHES = branches
    ranking.WD_CENTER_PENALTY_WEIGHT = wd_weight
    obs_ref = ReferenceObs(T_avg_C=d["T_mean_C"], RH_pct=d["RH_mean_pct"],
                           P_hPa=d["P_mean_hPa"], ws_ms=d["ws_mean_ms"],
                           wd_deg=d["wd_vec_deg"])
    r = run_td_for_day(obs_ref, _WORKER_CFG, _WORKER_GRID)
    return {"obs": d, "td": r}


def _worker_predict_day(task: tuple) -> dict:
    d, cal_dict, branches, wd_weight = task
    ensemble.DEFAULT_BRANCHES = branches
    ranking.WD_CENTER_PENALTY_WEIGHT = wd_weight
    cal = WeatherCalibration(**cal_dict)
    return predict_day(d, cal, _WORKER_CFG, _WORKER_GRID)


ROT_MAX_VALUES = [30.0, 60.0, 90.0, 120.0, 150.0, 180.0]
WEIGHT_VALUES  = [0.10, 0.20, 0.40, 0.80]

OUT_FILE = Path(__file__).parent / "sweep_wind_params_localized.json"


def build_rotated_branches(rot_max: float) -> list:
    """Spread the 6 family rotations linearly across [-rot_max, +rot_max]."""
    rots = np.linspace(-rot_max, +rot_max, 6)
    template = [
        {"name": "weak_mix",     "Kh": 240, "Kt": 120, "Kq":  95, "drag": 1.2e-5, "humid_couple": 0.80, "nudging": 0.00014, "pg_scale": 1.00, "wind_nudge": 1.5e-4},
        {"name": "balanced",     "Kh": 360, "Kt": 180, "Kq": 130, "drag": 1.5e-5, "humid_couple": 1.00, "nudging": 0.00016, "pg_scale": 1.00, "wind_nudge": 1.5e-4},
        {"name": "high_mix",     "Kh": 520, "Kt": 260, "Kq": 180, "drag": 1.8e-5, "humid_couple": 1.05, "nudging": 0.00017, "pg_scale": 1.00, "wind_nudge": 1.5e-4},
        {"name": "humid_bias",   "Kh": 340, "Kt": 175, "Kq": 220, "drag": 1.5e-5, "humid_couple": 1.24, "nudging": 0.00016, "pg_scale": 1.00, "wind_nudge": 1.5e-4},
        {"name": "strong_pg",    "Kh": 300, "Kt": 150, "Kq": 125, "drag": 1.2e-5, "humid_couple": 0.95, "nudging": 0.00015, "pg_scale": 1.18, "wind_nudge": 1.5e-4},
        {"name": "terrain_lock", "Kh": 330, "Kt": 170, "Kq": 135, "drag": 1.6e-5, "humid_couple": 1.02, "nudging": 0.00015, "pg_scale": 1.04, "wind_nudge": 1.5e-4},
    ]
    for i, b in enumerate(template):
        b["wind_rot_deg"] = float(rots[i])
    return template


def fit_and_oos(cfg, grid_cache, obs_train, obs_oos, pool: Pool,
                branches: list, wd_weight: float) -> dict:
    """Run 30-day fit + 5-day OOS. Pool parallelizes across days (30+5 tasks).
    branches+wd_weight are passed per-task so the pool can be reused across combos.
    """
    # Fit — 30 days in parallel
    rows = pool.map(_worker_run_day, [(d, branches, wd_weight) for d in obs_train])

    T_int_K = np.array([r["td"]["T_internal_K"] for r in rows])
    T_real_K = np.array([r["obs"]["T_mean_C"] + 273.15 for r in rows])
    q_int = np.array([r["td"]["q_internal"] for r in rows])
    h_ctr = np.array([r["td"]["h_center_m"] for r in rows])
    win_int = np.array([math.sqrt(r["td"]["u_center"]**2 + r["td"]["v_center"]**2) for r in rows])
    win_real = np.array([r["obs"]["ws_mean_ms"] for r in rows])
    RH_real = np.array([r["obs"]["RH_mean_pct"] for r in rows])
    P_real = np.array([r["obs"]["P_mean_hPa"] for r in rows])

    T_fit = fit_two_param(T_int_K, T_real_K)
    wind_fit = fit_scale_through_origin(win_int, win_real)
    T_2m_C_ts = T_fit["theilsen"]["slope"] * T_int_K + T_fit["theilsen"]["intercept"] - 273.15
    ratios = invert_q_to_rh_ratio(q_int, T_2m_C_ts, RH_real)
    q_rh_ts = float(np.median(ratios))
    dh = h_ctr - 5700.0
    mask = np.abs(dh) > 10.0
    h2p_ts = float(np.median((1013 - P_real[mask]) / dh[mask])) if mask.sum() >= 3 else 0.02

    cal = WeatherCalibration(
        location_name="sweep",
        fitted_date="sweep",
        T_offset_K=T_fit["theilsen"]["intercept"],
        T_scale=T_fit["theilsen"]["slope"],
        h_to_pressure_k=h2p_ts, q_to_rh_ratio=q_rh_ts,
        wind_scale=wind_fit["theilsen_median"]["scale"],
    )

    # In-sample RMSE
    T_pred_C = cal.T_scale * T_int_K + cal.T_offset_K - 273.15
    RH_pred = np.array([cal.map_humidity(q_int[i], T_pred_C[i]) for i in range(len(rows))])
    win_pred = cal.wind_scale * win_int
    P_pred = 1013 - cal.h_to_pressure_k * dh

    def rmse(a, b): return float(np.sqrt(np.mean((a - b)**2)))

    is_rmse = {
        "T_C":    rmse(T_pred_C, T_real_K - 273.15),
        "RH_pct": rmse(RH_pred, RH_real),
        "ws_ms":  rmse(win_pred, win_real),
        "P_hPa":  rmse(P_pred, P_real),
    }

    # OOS — 5 days in parallel
    def angle_diff(a: float, b: float) -> float:
        return (a - b + 540.0) % 360.0 - 180.0

    cal_dict = {
        "location_name": cal.location_name, "fitted_date": cal.fitted_date,
        "T_offset_K": cal.T_offset_K, "T_scale": cal.T_scale,
        "h_to_pressure_k": cal.h_to_pressure_k,
        "q_to_rh_ratio": cal.q_to_rh_ratio, "wind_scale": cal.wind_scale,
    }
    oos_preds = pool.map(_worker_predict_day,
                          [(d, cal_dict, branches, wd_weight) for d in obs_oos])
    errs_T, errs_RH, errs_ws, errs_P, errs_wd = [], [], [], [], []
    for d, p in zip(obs_oos, oos_preds):
        errs_T.append(p["T_C"] - d["T_mean_C"])
        errs_RH.append(p["RH_pct"] - d["RH_mean_pct"])
        errs_ws.append(p["ws_ms"] - d["ws_mean_ms"])
        errs_P.append(p["P_hPa"] - d["P_mean_hPa"])
        errs_wd.append(angle_diff(p["wd_deg"], d["wd_vec_deg"]))

    def rmse_arr(lst):
        a = np.array(lst); return float(np.sqrt(np.mean(a**2)))

    oos_rmse = {
        "T_C":    rmse_arr(errs_T),
        "RH_pct": rmse_arr(errs_RH),
        "ws_ms":  rmse_arr(errs_ws),
        "P_hPa":  rmse_arr(errs_P),
        "wd_deg": rmse_arr(errs_wd),
    }

    return {"in_sample": is_rmse, "out_of_sample": oos_rmse,
            "calibration": {"T_scale": cal.T_scale, "T_offset_K": cal.T_offset_K,
                            "q_to_rh_ratio": cal.q_to_rh_ratio,
                            "wind_scale": cal.wind_scale,
                            "h_to_pressure_k": cal.h_to_pressure_k}}


def main():
    print("=" * 80)
    print(f"2D SWEEP: rotation ∈ {ROT_MAX_VALUES}° × weight ∈ {WEIGHT_VALUES}")
    print(f"Total combos: {len(ROT_MAX_VALUES) * len(WEIGHT_VALUES)}")
    print("=" * 80)

    # Load obs once
    obs_train = json.loads(OBS_FILE.read_text(encoding="utf-8"))["days"]
    print(f"Loaded {len(obs_train)} training days")
    obs_oos = fetch_obs(OOS_START, OOS_END)
    print(f"Fetched {len(obs_oos)} OOS days\n")

    # Grid cache
    cfg = GridConfig(NX=64, NY=48, DX=24000.0, DY=24000.0, DT=60.0, STEPS=120)
    XX, YY, _x, _y = build_grid(cfg)
    topo = build_topography(XX, YY)
    cy = int(np.argmin(np.abs(YY[:, 0])))
    cx = int(np.argmin(np.abs(XX[0, :])))
    grid_cache = {"XX": XX, "YY": YY, "topo": topo, "cy": cy, "cx": cx}

    # Multiprocessing: single Pool with spawn context (fork OOMs on login node).
    # Params are passed per-task so no respawn needed.
    n_workers = 8
    cfg_dict = {"NX": cfg.NX, "NY": cfg.NY, "DX": cfg.DX, "DY": cfg.DY,
                "DT": cfg.DT, "STEPS": cfg.STEPS}
    print(f"Using {n_workers} worker processes (spawn, persistent)")

    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    pool = ctx.Pool(processes=n_workers, initializer=_worker_init, initargs=(cfg_dict,))

    results = []
    t0 = time.time()
    try:
      for i, rot_max in enumerate(ROT_MAX_VALUES):
        branches = build_rotated_branches(rot_max)
        for j, weight in enumerate(WEIGHT_VALUES):
            k = i * len(WEIGHT_VALUES) + j + 1
            N = len(ROT_MAX_VALUES) * len(WEIGHT_VALUES)
            elapsed = time.time() - t0
            print(f"[{k:2d}/{N}] rot=±{rot_max:4.0f}°  w={weight:.2f}  ...", end=" ", flush=True)
            m = fit_and_oos(cfg, grid_cache, obs_train, obs_oos, pool, branches, weight)
            print(f"IS T={m['in_sample']['T_C']:.3f}°C  OOS T={m['out_of_sample']['T_C']:.3f}  "
                  f"wd={m['out_of_sample']['wd_deg']:.1f}°  ws={m['out_of_sample']['ws_ms']:.3f}  "
                  f"RH={m['out_of_sample']['RH_pct']:.2f}%  "
                  f"[{elapsed:.0f}s elapsed]")
            results.append({"rot_max_deg": rot_max, "weight": weight, **m})
    finally:
      pool.close()
      pool.join()

    # Build heatmap tables
    print("\n" + "=" * 80)
    print("OOS WIND DIRECTION RMSE (°) — lower is better")
    print("=" * 80)
    print(f"{'weight\\rot':<12s}", *[f"±{r:>5.0f}°" for r in ROT_MAX_VALUES])
    for j, w in enumerate(WEIGHT_VALUES):
        row = [r for r in results if abs(r["weight"]-w)<1e-9]
        row.sort(key=lambda r: r["rot_max_deg"])
        print(f"w={w:<8.2f}", *[f"{r['out_of_sample']['wd_deg']:>7.1f}" for r in row])

    print("\n" + "=" * 80)
    print("OOS TEMPERATURE RMSE (°C) — want stable (rotation shouldn't break T)")
    print("=" * 80)
    print(f"{'weight\\rot':<12s}", *[f"±{r:>5.0f}°" for r in ROT_MAX_VALUES])
    for j, w in enumerate(WEIGHT_VALUES):
        row = [r for r in results if abs(r["weight"]-w)<1e-9]
        row.sort(key=lambda r: r["rot_max_deg"])
        print(f"w={w:<8.2f}", *[f"{r['out_of_sample']['T_C']:>7.3f}" for r in row])

    print("\n" + "=" * 80)
    print("OOS WIND SPEED RMSE (m/s)")
    print("=" * 80)
    print(f"{'weight\\rot':<12s}", *[f"±{r:>5.0f}°" for r in ROT_MAX_VALUES])
    for j, w in enumerate(WEIGHT_VALUES):
        row = [r for r in results if abs(r["weight"]-w)<1e-9]
        row.sort(key=lambda r: r["rot_max_deg"])
        print(f"w={w:<8.2f}", *[f"{r['out_of_sample']['ws_ms']:>7.3f}" for r in row])

    # Find best combo by wd RMSE (with T not degraded too much — require T OOS < 0.5°C)
    viable = [r for r in results if r["out_of_sample"]["T_C"] < 0.5]
    if viable:
        best = min(viable, key=lambda r: r["out_of_sample"]["wd_deg"])
        print("\n" + "=" * 80)
        print(f"BEST COMBO (min wd, T OOS < 0.5°C):")
        print(f"  rot_max=±{best['rot_max_deg']:.0f}°  weight={best['weight']:.2f}")
        print(f"  OOS: T={best['out_of_sample']['T_C']:.3f}°C  wd={best['out_of_sample']['wd_deg']:.1f}°  "
              f"ws={best['out_of_sample']['ws_ms']:.3f} m/s  RH={best['out_of_sample']['RH_pct']:.2f}%")
        print("=" * 80)

    OUT_FILE.write_text(json.dumps({"sweep": results}, indent=2), encoding="utf-8")
    print(f"\nSaved → {OUT_FILE}")


if __name__ == "__main__":
    main()
