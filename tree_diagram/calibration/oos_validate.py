"""Out-of-sample validation for Taipei B-calibration.

Training set : 2026-03-15 .. 2026-04-13  (30 days, used for fit)
Held-out set : 2026-04-14 .. 2026-04-18  (5 days, never seen by fit)

For each held-out day:
  1. Fetch real obs from Open-Meteo ERA5 archive
  2. Feed obs into build_taipei_state → run TD → apply B-calibration
  3. Compare calibrated forecast vs same-day observation
  4. Aggregate RMSE per variable, compare to in-sample RMSE
"""
from __future__ import annotations
import json
import math
import sys
import urllib.request
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tree_diagram.numerics.forcing import GridConfig, build_grid, build_topography
from tree_diagram.numerics.ensemble import run_ensemble
from tree_diagram.numerics.ranking import rank_ensemble
from tree_diagram.numerics.weather_contract import WeatherCalibration
from td_taipei_forecast import build_taipei_state, ReferenceObs

TAIPEI_LAT = 25.0478
TAIPEI_LON = 121.5319

OOS_START = date(2026, 4, 14)
OOS_END   = date(2026, 4, 18)

CAL_FILE = Path(__file__).parent / "taipei_calibration_b.json"
OUT_FILE = Path(__file__).parent / "taipei_oos_validation.json"


def fetch_obs(start: date, end: date) -> list[dict]:
    # Prefer cached file if present — compute nodes may lack internet
    cache = Path(__file__).parent / "taipei_obs_oos_cache.json"
    if cache.exists():
        d = json.loads(cache.read_text(encoding="utf-8"))
        if d.get("start") == start.isoformat() and d.get("end") == end.isoformat():
            print(f"Loaded cached {start} .. {end} ({len(d['days'])} days)")
            return d["days"]

    hourly_vars = ",".join([
        "temperature_2m", "relative_humidity_2m", "surface_pressure",
        "wind_speed_10m", "wind_direction_10m",
    ])
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={TAIPEI_LAT}&longitude={TAIPEI_LON}"
        f"&start_date={start.isoformat()}&end_date={end.isoformat()}"
        f"&hourly={hourly_vars}&timezone=Asia/Taipei"
    )
    print(f"Fetching {start} .. {end}")
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.loads(r.read())
    h = data["hourly"]
    times = h["time"]

    bucket: dict = defaultdict(list)
    for i, t in enumerate(times):
        d = t.split("T")[0]
        if h["temperature_2m"][i] is None:   # ERA5 may lag; skip incomplete rows
            continue
        bucket[d].append({
            "T_C":   h["temperature_2m"][i],
            "RH":    h["relative_humidity_2m"][i],
            "P":     h["surface_pressure"][i],
            "ws":    h["wind_speed_10m"][i] / 3.6,
            "wd":    h["wind_direction_10m"][i],
        })

    daily = []
    for d in sorted(bucket):
        rows = bucket[d]
        if len(rows) < 18:   # need ~full day; skip partial
            print(f"  {d}: only {len(rows)} hourly rows — skip")
            continue
        n = len(rows)
        u_sum = sum(r["ws"] * math.sin(math.radians(r["wd"])) for r in rows)
        v_sum = sum(r["ws"] * math.cos(math.radians(r["wd"])) for r in rows)
        wd_vec = (math.degrees(math.atan2(u_sum, v_sum)) + 360.0) % 360.0
        daily.append({
            "date": d,
            "n_hours": n,
            "T_mean_C":    sum(r["T_C"] for r in rows) / n,
            "RH_mean_pct": sum(r["RH"]  for r in rows) / n,
            "P_mean_hPa":  sum(r["P"]   for r in rows) / n,
            "ws_mean_ms":  sum(r["ws"]  for r in rows) / n,
            "wd_vec_deg":  wd_vec,
        })
    return daily


def predict_day(obs_row: dict, cal: WeatherCalibration, cfg: GridConfig,
                grid_cache: dict) -> dict:
    XX, YY, topo = grid_cache["XX"], grid_cache["YY"], grid_cache["topo"]
    cy, cx = grid_cache["cy"], grid_cache["cx"]

    obs_ref = ReferenceObs(
        T_avg_C=obs_row["T_mean_C"], RH_pct=obs_row["RH_mean_pct"],
        P_hPa=obs_row["P_mean_hPa"], ws_ms=obs_row["ws_mean_ms"],
        wd_deg=obs_row["wd_vec_deg"],
    )
    init = build_taipei_state(XX, YY, topo, cfg, perturbation=-1.0, obs_ref=obs_ref)
    obs_state = build_taipei_state(XX, YY, topo, cfg, perturbation=0.0, obs_ref=obs_ref)

    raw = run_ensemble(
        initial_state=init, obs=obs_state, topography=topo, cfg=cfg,
        pressure_balance=1.0, n_workers=1,
    )
    ranked = rank_ensemble(raw)
    top = ranked[0]["state"]

    T_int_K = float(top["T"][cy, cx])
    h_ctr   = float(top["h"][cy, cx])
    q_int   = float(top["q"][cy, cx])
    u = float(top["u"][cy, cx])
    v = float(top["v"][cy, cx])

    T_pred_C = cal.T_scale * T_int_K + cal.T_offset_K - 273.15
    RH_pred  = cal.map_humidity(q_int, T_pred_C)
    wind_pred = cal.map_wind(u, v)
    wd_pred = float((math.degrees(math.atan2(-u, -v)) + 360.0) % 360.0)
    P_pred = cal.map_pressure(h_ctr)

    return {
        "T_C":    T_pred_C,
        "RH_pct": RH_pred,
        "ws_ms":  wind_pred,
        "wd_deg": wd_pred,
        "P_hPa":  P_pred,
        "top_family": ranked[0].get("name", "?"),
    }


def main():
    print("=" * 76)
    print("OUT-OF-SAMPLE VALIDATION — Taipei B-calibration")
    print("=" * 76)

    cal_dict = json.loads(CAL_FILE.read_text(encoding="utf-8"))["calibration"]
    cal = WeatherCalibration(**cal_dict)
    print(f"Loaded calibration: {cal.fitted_date}")
    print(f"  T_scale={cal.T_scale:.4f}  T_offset_K={cal.T_offset_K:+.3f}  "
          f"q_to_rh_ratio={cal.q_to_rh_ratio:.3f}  wind_scale={cal.wind_scale:.3f}")

    oos_days = fetch_obs(OOS_START, OOS_END)
    print(f"\nHeld-out set: {len(oos_days)} days")
    if not oos_days:
        print("No out-of-sample data available (ERA5 archive lag). Abort.")
        return

    cfg = GridConfig(NX=64, NY=48, DX=24000.0, DY=24000.0, DT=60.0, STEPS=120)
    XX, YY, _x, _y = build_grid(cfg)
    topo = build_topography(XX, YY)
    cy = int(np.argmin(np.abs(YY[:, 0])))
    cx = int(np.argmin(np.abs(XX[0, :])))
    grid_cache = {"XX": XX, "YY": YY, "topo": topo, "cy": cy, "cx": cx}

    print(f"\n{'date':<12} {'var':<6} {'obs':>8} {'pred':>8} {'Δ':>8}")
    print("-" * 50)

    results = []
    for d in oos_days:
        pred = predict_day(d, cal, cfg, grid_cache)

        def angle_diff(a: float, b: float) -> float:
            """Shortest signed angular distance (deg)."""
            diff = (a - b + 540.0) % 360.0 - 180.0
            return diff

        row = {
            "date": d["date"],
            "top_family": pred["top_family"],
            "obs":  {"T_C": d["T_mean_C"], "RH_pct": d["RH_mean_pct"],
                     "P_hPa": d["P_mean_hPa"], "ws_ms": d["ws_mean_ms"],
                     "wd_deg": d["wd_vec_deg"]},
            "pred": pred,
            "err": {
                "T_C":    pred["T_C"]    - d["T_mean_C"],
                "RH_pct": pred["RH_pct"] - d["RH_mean_pct"],
                "P_hPa":  pred["P_hPa"]  - d["P_mean_hPa"],
                "ws_ms":  pred["ws_ms"]  - d["ws_mean_ms"],
                "wd_deg": angle_diff(pred["wd_deg"], d["wd_vec_deg"]),
            },
        }
        results.append(row)
        print(f"{d['date']}  T     {d['T_mean_C']:>7.2f}  {pred['T_C']:>7.2f}  {row['err']['T_C']:>+7.2f}°C")
        print(f"{'':<12}  RH    {d['RH_mean_pct']:>7.1f}  {pred['RH_pct']:>7.1f}  {row['err']['RH_pct']:>+7.2f}%")
        print(f"{'':<12}  wind  {d['ws_mean_ms']:>7.2f}  {pred['ws_ms']:>7.2f}  {row['err']['ws_ms']:>+7.2f} m/s")
        print(f"{'':<12}  wdir  {d['wd_vec_deg']:>7.0f}  {pred['wd_deg']:>7.0f}  {row['err']['wd_deg']:>+7.0f}°")
        print(f"{'':<12}  P     {d['P_mean_hPa']:>7.1f}  {pred['P_hPa']:>7.1f}  {row['err']['P_hPa']:>+7.2f} hPa")
        print(f"{'':<12}  family={pred['top_family']}")
        print()

    # Aggregate
    errs_T  = np.array([r["err"]["T_C"]    for r in results])
    errs_RH = np.array([r["err"]["RH_pct"] for r in results])
    errs_ws = np.array([r["err"]["ws_ms"]  for r in results])
    errs_wd = np.array([r["err"]["wd_deg"] for r in results])
    errs_P  = np.array([r["err"]["P_hPa"]  for r in results])

    def rmse(x): return float(np.sqrt(np.mean(x**2)))
    def bias(x): return float(np.mean(x))
    def mae(x):  return float(np.mean(np.abs(x)))

    in_sample = {
        "T_C": 0.382, "RH_pct": 3.13, "ws_ms": 1.074, "P_hPa": 3.337,
    }

    print("=" * 76)
    print(f"AGGREGATE (N={len(results)} days out-of-sample)")
    print("=" * 76)
    print(f"{'var':<8} {'RMSE':>10} {'MAE':>10} {'bias':>10}   in-sample   ratio (OOS/IS)")
    print("-" * 76)
    for name, arr, iv in [
        ("T (°C)",  errs_T,  in_sample["T_C"]),
        ("RH (%)",  errs_RH, in_sample["RH_pct"]),
        ("ws (m/s)", errs_ws, in_sample["ws_ms"]),
        ("P (hPa)", errs_P,  in_sample["P_hPa"]),
    ]:
        r, m, b = rmse(arr), mae(arr), bias(arr)
        print(f"{name:<8} {r:>10.3f} {m:>10.3f} {b:>+10.3f}   {iv:>8.3f}   {r/iv:>6.2f}x")
    print(f"{'wd (°)':<8} {rmse(errs_wd):>10.1f} {mae(errs_wd):>10.1f} {bias(errs_wd):>+10.1f}   (not fitted)")

    summary = {
        "training_range":   ["2026-03-15", "2026-04-13"],
        "held_out_range":   [OOS_START.isoformat(), OOS_END.isoformat()],
        "n_days": len(results),
        "in_sample_rmse":   in_sample,
        "out_of_sample": {
            "T_C":    {"rmse": rmse(errs_T),  "mae": mae(errs_T),  "bias": bias(errs_T)},
            "RH_pct": {"rmse": rmse(errs_RH), "mae": mae(errs_RH), "bias": bias(errs_RH)},
            "ws_ms":  {"rmse": rmse(errs_ws), "mae": mae(errs_ws), "bias": bias(errs_ws)},
            "wd_deg": {"rmse": rmse(errs_wd), "mae": mae(errs_wd), "bias": bias(errs_wd)},
            "P_hPa":  {"rmse": rmse(errs_P),  "mae": mae(errs_P),  "bias": bias(errs_P)},
        },
        "per_day": results,
    }
    OUT_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {OUT_FILE}")


if __name__ == "__main__":
    main()
