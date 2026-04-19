"""Fit WeatherCalibration (A-scheme: single-shot offset fit).

A-scheme assumptions:
  - TD is run ONCE with default Taipei obs
  - The center-cell internal (T, h, q, u, v) becomes the "fixed internal anchor"
  - Calibration offsets are chosen so the anchor maps to the 30-day mean observation
  - T_scale = 1.0 (cannot fit slope from a single internal point)

This is a minimum-viable calibration to prove the plumbing:
  load obs → run TD → solve offsets → save JSON → load JSON in forecast.
B-scheme (per-day initial states, true linear fit) will build on this.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path("D:/treesea/tree_diagram").resolve()))

from tree_diagram.numerics.forcing import GridConfig, build_grid, build_topography
from tree_diagram.numerics.ensemble import run_ensemble
from tree_diagram.numerics.ranking import rank_ensemble
from tree_diagram.numerics.weather_contract import WeatherCalibration
from td_taipei_forecast import build_taipei_state

OBS_FILE = Path("D:/treesea/tree_diagram/calibration/taipei_obs_daily.json")
CAL_OUT  = Path("D:/treesea/tree_diagram/calibration/taipei_calibration.json")


def load_obs_means():
    d = json.loads(OBS_FILE.read_text(encoding="utf-8"))
    days = d["days"]
    T_mean = np.mean([r["T_mean_C"] for r in days])
    RH_mean = np.mean([r["RH_mean_pct"] for r in days])
    P_mean = np.mean([r["P_mean_hPa"] for r in days])
    ws_mean = np.mean([r["ws_mean_ms"] for r in days])
    return {
        "n_days": len(days),
        "T_mean_C": float(T_mean),
        "RH_mean_pct": float(RH_mean),
        "P_mean_hPa": float(P_mean),
        "ws_mean_ms": float(ws_mean),
        "date_range": (days[0]["date"], days[-1]["date"]),
    }


def run_td_and_extract_center():
    """Run TD once and return center-cell internal state."""
    cfg = GridConfig(NX=256, NY=192, DX=6000.0, DY=6000.0, DT=60.0, STEPS=240)
    XX, YY, x, y = build_grid(cfg)
    topo = build_topography(XX, YY)
    obs = build_taipei_state(XX, YY, topo, cfg, perturbation=0.0)
    init = build_taipei_state(XX, YY, topo, cfg, perturbation=-1.0)

    raw = run_ensemble(
        initial_state=init, obs=obs, topography=topo, cfg=cfg,
        pressure_balance=1.0, n_workers=1,
    )
    ranked = rank_ensemble(raw)
    top = ranked[0]["state"]

    cy = int(np.argmin(np.abs(YY[:, 0])))
    cx = int(np.argmin(np.abs(XX[0, :])))

    return {
        "T_internal_K": float(top["T"][cy, cx]),
        "h_center_m":   float(top["h"][cy, cx]),
        "q_internal":   float(top["q"][cy, cx]),
        "u_center":     float(top["u"][cy, cx]),
        "v_center":     float(top["v"][cy, cx]),
        "top_worldline": ranked[0].get("name", "unknown"),
        "top_score": float(ranked[0].get("score", 0.0)),
    }


def solve_q_to_rh_ratio(q_internal: float, T_2m_C: float, target_rh_pct: float) -> float:
    """Invert map_humidity to find q_to_rh_ratio that yields target_rh at given T_2m."""
    e_sat = 6.11 * math.exp(17.27 * T_2m_C / (T_2m_C + 237.3))
    # Target: 100 * e_actual / e_sat = target_rh
    # e_actual = q_eff * 1013 / (0.622 + q_eff)
    # Solve for q_eff given target_rh:
    e_actual = e_sat * target_rh_pct / 100.0
    # e_actual * (0.622 + q_eff) = q_eff * 1013
    # 0.622 * e_actual + e_actual * q_eff = q_eff * 1013
    # q_eff * (1013 - e_actual) = 0.622 * e_actual
    q_eff = 0.622 * e_actual / (1013.0 - e_actual)
    return q_eff / q_internal


def fit_calibration(obs_means: dict, anchor: dict) -> WeatherCalibration:
    T_real_K = obs_means["T_mean_C"] + 273.15
    T_offset_K = T_real_K - anchor["T_internal_K"]

    wind_internal = math.sqrt(anchor["u_center"]**2 + anchor["v_center"]**2)
    wind_scale = obs_means["ws_mean_ms"] / max(wind_internal, 1e-3)

    T_2m_C = anchor["T_internal_K"] + T_offset_K - 273.15
    q_to_rh_ratio = solve_q_to_rh_ratio(anchor["q_internal"], T_2m_C, obs_means["RH_mean_pct"])

    # h_to_pressure_k: solve P = 1013 - k*(h_center - 5700)
    dh = anchor["h_center_m"] - 5700.0
    if abs(dh) > 10.0:
        h_to_pressure_k = (1013.0 - obs_means["P_mean_hPa"]) / dh
    else:
        h_to_pressure_k = 0.02   # h is too close to baseline to resolve; use default

    return WeatherCalibration(
        location_name="Taipei (A-scheme mean-fit)",
        fitted_date=f"2026-04-19 (A-scheme from {obs_means['date_range'][0]}..{obs_means['date_range'][1]}, N={obs_means['n_days']} days)",
        T_offset_K=float(T_offset_K),
        T_scale=1.0,
        h_to_pressure_k=float(h_to_pressure_k),
        q_to_rh_ratio=float(q_to_rh_ratio),
        wind_scale=float(wind_scale),
    )


def main():
    print("=" * 72)
    print("A-SCHEME CALIBRATION FIT")
    print("=" * 72)

    obs_means = load_obs_means()
    print(f"\n30-day observation means ({obs_means['date_range'][0]} .. {obs_means['date_range'][1]}):")
    print(f"  T_real:  {obs_means['T_mean_C']:.2f}°C  ({obs_means['T_mean_C']+273.15:.2f} K)")
    print(f"  RH:      {obs_means['RH_mean_pct']:.1f}%")
    print(f"  P:       {obs_means['P_mean_hPa']:.1f} hPa")
    print(f"  wind:    {obs_means['ws_mean_ms']:.2f} m/s")

    print(f"\nRunning TD once (NX=64 NY=48 STEPS=240)...")
    anchor = run_td_and_extract_center()
    wind_mag = math.sqrt(anchor["u_center"]**2 + anchor["v_center"]**2)
    print(f"Center-cell internal anchor (top worldline: {anchor['top_worldline']}, score={anchor['top_score']:.3f}):")
    print(f"  T_internal:  {anchor['T_internal_K']:.2f} K  ({anchor['T_internal_K']-273.15:.2f}°C)")
    print(f"  h_center:    {anchor['h_center_m']:.1f} m")
    print(f"  q_internal:  {anchor['q_internal']:.6f}")
    print(f"  wind:        ({anchor['u_center']:+.2f}, {anchor['v_center']:+.2f}) = {wind_mag:.2f} m/s")

    print(f"\nFitting calibration (T_scale=1.0, solving offsets)...")
    cal = fit_calibration(obs_means, anchor)
    print(f"  T_offset_K:       {cal.T_offset_K:+.3f}")
    print(f"  T_scale:          {cal.T_scale:.3f}  (fixed for A-scheme)")
    print(f"  h_to_pressure_k:  {cal.h_to_pressure_k:+.5f}")
    print(f"  q_to_rh_ratio:    {cal.q_to_rh_ratio:.3f}")
    print(f"  wind_scale:       {cal.wind_scale:.3f}")

    # Verify: apply calibration back to anchor, check residuals
    print(f"\nVerification (anchor → calibrated):")
    T_2m_K = cal.T_scale * anchor["T_internal_K"] + cal.T_offset_K
    T_2m_C = T_2m_K - 273.15
    print(f"  T:   {T_2m_C:.2f}°C  (target {obs_means['T_mean_C']:.2f}°C)  Δ={T_2m_C-obs_means['T_mean_C']:+.3f}")

    rh = cal.map_humidity(anchor["q_internal"], T_2m_C)
    print(f"  RH:  {rh:.1f}%   (target {obs_means['RH_mean_pct']:.1f}%)  Δ={rh-obs_means['RH_mean_pct']:+.2f}")

    wind = cal.map_wind(anchor["u_center"], anchor["v_center"])
    print(f"  wind:{wind:.2f} m/s (target {obs_means['ws_mean_ms']:.2f})  Δ={wind-obs_means['ws_mean_ms']:+.3f}")

    P = cal.map_pressure(anchor["h_center_m"])
    print(f"  P:   {P:.1f} hPa (target {obs_means['P_mean_hPa']:.1f})  Δ={P-obs_means['P_mean_hPa']:+.3f}")

    # Save
    out = {
        "scheme": "A (single-shot mean offset)",
        "fitted_on": "2026-04-19",
        "obs_means_30d": obs_means,
        "internal_anchor": anchor,
        "calibration": {
            "location_name": cal.location_name,
            "fitted_date": cal.fitted_date,
            "T_offset_K": cal.T_offset_K,
            "T_scale": cal.T_scale,
            "h_to_pressure_k": cal.h_to_pressure_k,
            "q_to_rh_ratio": cal.q_to_rh_ratio,
            "wind_scale": cal.wind_scale,
        },
        "caveat": (
            "A-scheme: T_scale fixed at 1.0 (cannot resolve slope from a single "
            "internal point). All offsets are the mean-match values — no per-day "
            "initial conditions were varied. For predictive validation, upgrade "
            "to B-scheme (per-day obs injection + linear regression)."
        ),
    }
    CAL_OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {CAL_OUT}")


if __name__ == "__main__":
    main()
