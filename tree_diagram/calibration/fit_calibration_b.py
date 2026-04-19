"""Fit WeatherCalibration — B-scheme: per-day obs-anchored initial states.

B-scheme pipeline:
  1. Load 30 days of Taipei ERA5 obs
  2. For each day d, build obs-anchored initial state (ReferenceObs → build_taipei_state)
  3. Run TD forward, extract center-cell final internal (T, h, q, u, v)
  4. Pair with same-day surface obs (calibration tests the mapping, not forecast skill)
  5. Fit per-variable:
       T:    T_real_K = slope*T_internal_K + offset        [Theil-Sen + OLS, 2-param]
       wind: ws_real = wind_scale * |wind_internal|         [median ratio, 1-param]
       q→RH: q_to_rh_ratio                                  [inverse Tetens, 1-param]
       P:    h_to_pressure_k = (1013-P_real)/(h_center-5700) [median, 1-param]
  6. Report slope/intercept/R²/RMSE for OLS AND Theil-Sen
  7. Save WeatherCalibration JSON

References
----------
Theil-Sen: robust to 29.3% outliers, standard in climatology/meteorology.
  - Wikipedia: earth sciences standard
  - scipy.stats.theilslopes returns (median_slope, median_intercept, lo_slope, hi_slope)
"""
from __future__ import annotations
import json
import math
import sys
import time
from pathlib import Path
import numpy as np
from scipy import stats as sp_stats

sys.path.insert(0, str(Path("D:/treesea/tree_diagram").resolve()))

from tree_diagram.numerics.forcing import GridConfig, build_grid, build_topography
from tree_diagram.numerics.ensemble import run_ensemble
from tree_diagram.numerics.ranking import rank_ensemble
from tree_diagram.numerics.weather_contract import WeatherCalibration
from td_taipei_forecast import build_taipei_state, ReferenceObs

OBS_FILE = Path("D:/treesea/tree_diagram/calibration/taipei_obs_daily.json")
CAL_OUT  = Path("D:/treesea/tree_diagram/calibration/taipei_calibration_b.json")


# ---------------------------------------------------------------------------
# Per-day TD runs
# ---------------------------------------------------------------------------

def run_td_for_day(obs_ref: ReferenceObs, cfg: GridConfig, grid_cache: dict) -> dict:
    """Run TD with obs_ref as initial-state anchor, return center-cell final state."""
    XX, YY, topo = grid_cache["XX"], grid_cache["YY"], grid_cache["topo"]

    init = build_taipei_state(XX, YY, topo, cfg, perturbation=-1.0, obs_ref=obs_ref)
    obs_state = build_taipei_state(XX, YY, topo, cfg, perturbation=0.0, obs_ref=obs_ref)

    raw = run_ensemble(
        initial_state=init, obs=obs_state, topography=topo, cfg=cfg,
        pressure_balance=1.0, n_workers=1,
    )
    ranked = rank_ensemble(raw)
    top = ranked[0]["state"]

    cy, cx = grid_cache["cy"], grid_cache["cx"]
    return {
        "T_internal_K": float(top["T"][cy, cx]),
        "h_center_m":   float(top["h"][cy, cx]),
        "q_internal":   float(top["q"][cy, cx]),
        "u_center":     float(top["u"][cy, cx]),
        "v_center":     float(top["v"][cy, cx]),
        "top_family":   ranked[0].get("name", "unknown"),
        "top_score":    float(ranked[0].get("score", 0.0)),
    }


# ---------------------------------------------------------------------------
# Fit helpers
# ---------------------------------------------------------------------------

def fit_two_param(x: np.ndarray, y: np.ndarray) -> dict:
    """Fit y = slope*x + intercept via Theil-Sen (primary) and OLS (compare)."""
    # Theil-Sen
    ts = sp_stats.theilslopes(y, x, alpha=0.95)
    ts_slope, ts_intercept = float(ts[0]), float(ts[1])
    ts_pred = ts_slope * x + ts_intercept
    ts_resid = y - ts_pred

    # OLS
    ols_slope, ols_intercept, ols_r, ols_p, ols_stderr = sp_stats.linregress(x, y)
    ols_pred = ols_slope * x + ols_intercept
    ols_resid = y - ols_pred

    def stats(resid):
        return {
            "rmse": float(np.sqrt(np.mean(resid**2))),
            "mae":  float(np.mean(np.abs(resid))),
            "max":  float(np.max(np.abs(resid))),
        }

    return {
        "theilsen": {
            "slope": ts_slope, "intercept": ts_intercept,
            "slope_ci95": [float(ts[2]), float(ts[3])],
            **stats(ts_resid),
        },
        "ols": {
            "slope": float(ols_slope), "intercept": float(ols_intercept),
            "r_squared": float(ols_r**2), "p_value": float(ols_p),
            **stats(ols_resid),
        },
        "n": int(len(x)),
    }


def fit_scale_through_origin(x: np.ndarray, y: np.ndarray) -> dict:
    """Fit y = scale*x (no intercept) via median ratio + OLS through origin."""
    # Robust: median of y/x
    mask = np.abs(x) > 1e-6
    ratio_ts = float(np.median(y[mask] / x[mask]))
    # OLS through origin: slope = sum(xy)/sum(x²)
    ratio_ols = float(np.sum(x * y) / np.sum(x**2))

    resid_ts = y - ratio_ts * x
    resid_ols = y - ratio_ols * x
    return {
        "theilsen_median": {"scale": ratio_ts,
                            "rmse": float(np.sqrt(np.mean(resid_ts**2))),
                            "mae":  float(np.mean(np.abs(resid_ts)))},
        "ols_through_origin": {"scale": ratio_ols,
                               "rmse": float(np.sqrt(np.mean(resid_ols**2))),
                               "mae":  float(np.mean(np.abs(resid_ols)))},
        "n": int(len(x)),
    }


def invert_q_to_rh_ratio(q_internal: np.ndarray, T_2m_C: np.ndarray,
                         RH_pct: np.ndarray) -> np.ndarray:
    """Per-sample q_to_rh_ratio required to match target RH at given T."""
    e_sat = 6.11 * np.exp(17.27 * T_2m_C / (T_2m_C + 237.3))
    e_actual = e_sat * RH_pct / 100.0
    q_eff = 0.622 * e_actual / (1013.0 - e_actual)
    return q_eff / q_internal


# ---------------------------------------------------------------------------
# Main B-scheme fit
# ---------------------------------------------------------------------------

def main():
    print("=" * 76)
    print("B-SCHEME CALIBRATION FIT (per-day obs-anchored, Theil-Sen + OLS)")
    print("=" * 76)

    obs_days = json.loads(OBS_FILE.read_text(encoding="utf-8"))["days"]
    n_days = len(obs_days)
    print(f"Loaded {n_days} days of Taipei ERA5 obs")

    # Grid cache (built once)
    cfg = GridConfig(NX=64, NY=48, DX=24000.0, DY=24000.0, DT=60.0, STEPS=120)
    XX, YY, _x, _y = build_grid(cfg)
    topo = build_topography(XX, YY)
    cy = int(np.argmin(np.abs(YY[:, 0])))
    cx = int(np.argmin(np.abs(XX[0, :])))
    grid_cache = {"XX": XX, "YY": YY, "topo": topo, "cy": cy, "cx": cx}

    # Run TD for each day
    print(f"\nRunning TD for each day (NX={cfg.NX} NY={cfg.NY} STEPS={cfg.STEPS})...")
    rows = []
    t0 = time.time()
    for i, d in enumerate(obs_days):
        obs_ref = ReferenceObs(
            T_avg_C=d["T_mean_C"], RH_pct=d["RH_mean_pct"],
            P_hPa=d["P_mean_hPa"], ws_ms=d["ws_mean_ms"],
            wd_deg=d["wd_vec_deg"],
        )
        result = run_td_for_day(obs_ref, cfg, grid_cache)
        rows.append({
            "date": d["date"],
            "obs": {"T_C": d["T_mean_C"], "RH_pct": d["RH_mean_pct"],
                    "P_hPa": d["P_mean_hPa"], "ws_ms": d["ws_mean_ms"],
                    "wd_deg": d["wd_vec_deg"]},
            "td": result,
        })
        elapsed = time.time() - t0
        eta = elapsed / (i + 1) * (n_days - i - 1)
        print(f"  [{i+1:2d}/{n_days}] {d['date']}  "
              f"T_obs={d['T_mean_C']:5.2f}°C → T_int={result['T_internal_K']:6.2f}K  "
              f"|wind|={math.sqrt(result['u_center']**2+result['v_center']**2):4.2f}  "
              f"family={result['top_family']:<12s}  elapsed={elapsed:4.0f}s  eta={eta:4.0f}s")

    # Build arrays
    T_internal_K = np.array([r["td"]["T_internal_K"] for r in rows])
    T_real_K     = np.array([r["obs"]["T_C"] + 273.15 for r in rows])
    h_center_m   = np.array([r["td"]["h_center_m"] for r in rows])
    q_internal   = np.array([r["td"]["q_internal"] for r in rows])
    wind_internal = np.array([math.sqrt(r["td"]["u_center"]**2 + r["td"]["v_center"]**2) for r in rows])
    wind_real    = np.array([r["obs"]["ws_ms"] for r in rows])
    RH_real      = np.array([r["obs"]["RH_pct"] for r in rows])
    P_real       = np.array([r["obs"]["P_hPa"] for r in rows])

    # ------ Fits ------
    print("\n" + "=" * 76)
    print("FITTED CALIBRATION (T: 2-param, others: 1-param)")
    print("=" * 76)

    print(f"\n[T] T_real_K = slope·T_internal_K + intercept   (N={n_days})")
    T_fit = fit_two_param(T_internal_K, T_real_K)
    ts, ols = T_fit["theilsen"], T_fit["ols"]
    print(f"  Theil-Sen : slope={ts['slope']:+.4f}  intercept={ts['intercept']:+.3f} K  "
          f"RMSE={ts['rmse']:.3f} K   95% slope CI=[{ts['slope_ci95'][0]:.3f}, {ts['slope_ci95'][1]:.3f}]")
    print(f"  OLS       : slope={ols['slope']:+.4f}  intercept={ols['intercept']:+.3f} K  "
          f"RMSE={ols['rmse']:.3f} K   R²={ols['r_squared']:.3f}  p={ols['p_value']:.2e}")

    print(f"\n[wind] ws_real = wind_scale · |wind_internal|")
    wind_fit = fit_scale_through_origin(wind_internal, wind_real)
    print(f"  Theil-Sen median : scale={wind_fit['theilsen_median']['scale']:.4f}  RMSE={wind_fit['theilsen_median']['rmse']:.3f} m/s")
    print(f"  OLS (origin)     : scale={wind_fit['ols_through_origin']['scale']:.4f}  RMSE={wind_fit['ols_through_origin']['rmse']:.3f} m/s")

    print(f"\n[q→RH] q_to_rh_ratio = q_eff(target RH, T_real) / q_internal")
    # Use Theil-Sen chosen T mapping to get T_2m for per-sample inversion
    T_2m_C_ts = ts["slope"] * T_internal_K + ts["intercept"] - 273.15
    ratios = invert_q_to_rh_ratio(q_internal, T_2m_C_ts, RH_real)
    q_rh_ts = float(np.median(ratios))
    q_rh_ols = float(np.mean(ratios))
    print(f"  Theil-Sen median : q_to_rh_ratio={q_rh_ts:.4f}  (sample range [{ratios.min():.3f}, {ratios.max():.3f}])")
    print(f"  OLS mean         : q_to_rh_ratio={q_rh_ols:.4f}  std={ratios.std():.3f}")

    print(f"\n[P] h_to_pressure_k = (1013-P_real) / (h_center-5700)")
    dh = h_center_m - 5700.0
    mask = np.abs(dh) > 10.0
    if mask.sum() < 3:
        print(f"  h_center too close to baseline (only {mask.sum()} usable samples) — "
              f"fall back to small default h_to_pressure_k=0.02 and report residuals")
        h2p_ts = 0.02
        h2p_ols = 0.02
    else:
        ratios_p = (1013.0 - P_real[mask]) / dh[mask]
        h2p_ts = float(np.median(ratios_p))
        h2p_ols = float(np.mean(ratios_p))
        print(f"  Theil-Sen median : h_to_pressure_k={h2p_ts:+.5f}  (N usable={mask.sum()})")
        print(f"  OLS mean         : h_to_pressure_k={h2p_ols:+.5f}")

    # ------ Build final calibration (use Theil-Sen for robustness) ------
    cal = WeatherCalibration(
        location_name="Taipei (B-scheme Theil-Sen)",
        fitted_date=f"2026-04-19 (B-scheme N={n_days}, {obs_days[0]['date']}..{obs_days[-1]['date']})",
        T_offset_K=ts["intercept"],
        T_scale=ts["slope"],
        h_to_pressure_k=h2p_ts,
        q_to_rh_ratio=q_rh_ts,
        wind_scale=wind_fit["theilsen_median"]["scale"],
    )

    print("\n" + "=" * 76)
    print("FINAL WEATHERCALIBRATION (Theil-Sen):")
    print(f"  T_scale          = {cal.T_scale:+.4f}")
    print(f"  T_offset_K       = {cal.T_offset_K:+.3f} K")
    print(f"  q_to_rh_ratio    = {cal.q_to_rh_ratio:.4f}")
    print(f"  wind_scale       = {cal.wind_scale:.4f}")
    print(f"  h_to_pressure_k  = {cal.h_to_pressure_k:+.5f}")

    # ------ Validation: apply to 30-day samples, compute overall RMSE ------
    print("\n" + "=" * 76)
    print("VALIDATION — apply calibration back to each of 30 days:")
    T_pred = cal.T_scale * T_internal_K + cal.T_offset_K - 273.15
    T_obs  = T_real_K - 273.15
    wind_pred = cal.wind_scale * wind_internal
    RH_pred = np.array([
        cal.map_humidity(q_internal[i], T_pred[i]) for i in range(n_days)
    ])
    P_pred = 1013.0 - cal.h_to_pressure_k * (h_center_m - 5700.0)

    def rmse(a, b): return float(np.sqrt(np.mean((a - b)**2)))
    def bias(a, b): return float(np.mean(a - b))

    print(f"  T   : RMSE={rmse(T_pred, T_obs):.3f}°C  bias={bias(T_pred, T_obs):+.3f}°C  "
          f"range obs=[{T_obs.min():.1f},{T_obs.max():.1f}] pred=[{T_pred.min():.1f},{T_pred.max():.1f}]")
    print(f"  RH  : RMSE={rmse(RH_pred, RH_real):.2f}%   bias={bias(RH_pred, RH_real):+.2f}%")
    print(f"  wind: RMSE={rmse(wind_pred, wind_real):.3f} m/s  bias={bias(wind_pred, wind_real):+.3f} m/s")
    print(f"  P   : RMSE={rmse(P_pred, P_real):.3f} hPa  bias={bias(P_pred, P_real):+.3f} hPa")

    # ------ Save ------
    out = {
        "scheme": "B (per-day obs-anchored, Theil-Sen + OLS)",
        "fitted_on": "2026-04-19",
        "n_days": n_days,
        "date_range": [obs_days[0]["date"], obs_days[-1]["date"]],
        "calibration": {
            "location_name": cal.location_name,
            "fitted_date": cal.fitted_date,
            "T_offset_K": cal.T_offset_K,
            "T_scale": cal.T_scale,
            "h_to_pressure_k": cal.h_to_pressure_k,
            "q_to_rh_ratio": cal.q_to_rh_ratio,
            "wind_scale": cal.wind_scale,
        },
        "fit_diagnostics": {
            "T": T_fit,
            "wind": wind_fit,
            "q_to_rh_ratio_samples": {
                "median": q_rh_ts, "mean": q_rh_ols, "std": float(ratios.std()),
                "min": float(ratios.min()), "max": float(ratios.max()),
            },
            "h_to_pressure_k_samples": {
                "median": h2p_ts, "mean": h2p_ols,
            },
        },
        "validation_rmse": {
            "T_C": rmse(T_pred, T_obs),
            "RH_pct": rmse(RH_pred, RH_real),
            "wind_ms": rmse(wind_pred, wind_real),
            "P_hPa": rmse(P_pred, P_real),
        },
        "training_data": rows,
    }
    CAL_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {CAL_OUT}")


if __name__ == "__main__":
    main()
