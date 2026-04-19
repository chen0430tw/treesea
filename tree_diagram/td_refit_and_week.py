"""Re-fit B-calibration at current physics + run 7-day forecast.
Portable: uses Path(__file__) relative paths so it runs local (numpy) or cluster (cupy)."""
from __future__ import annotations
import sys, time, json, math
from datetime import date, timedelta
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from tree_diagram.numerics.forcing import GridConfig, build_grid, build_topography
from tree_diagram.numerics.ensemble import DEFAULT_BRANCHES, _rotate_wind_inplace
from tree_diagram.numerics.dynamics_batched import (
    batched_branch_step, stack_families, unstack_families
)
from tree_diagram.numerics.ranking import score_state
from tree_diagram.numerics.weather_contract import WeatherCalibration
from tree_diagram.numerics._xp import has_cupy
from td_taipei_forecast import build_taipei_state, ReferenceObs
from calibration.fit_calibration_b import fit_two_param, fit_scale_through_origin, invert_q_to_rh_ratio

OBS_PATH = HERE / "calibration" / "taipei_obs_daily.json"
CAL_OUT  = HERE / "calibration" / "taipei_calibration_b.json"
TAU_PERSIST_DAYS = 2.0
TODAY = date(2026, 4, 19)

cfg_fit = GridConfig(NX=256, NY=192, DX=6000.0, DY=6000.0, DT=60.0, STEPS=120)
cfg_day = GridConfig(NX=256, NY=192, DX=6000.0, DY=6000.0, DT=60.0, STEPS=1440)
XX, YY, _, _ = build_grid(cfg_fit)
topo = build_topography(XX, YY)
cy = int(np.argmin(np.abs(YY[:, 0])))
cx = int(np.argmin(np.abs(XX[0, :])))

if has_cupy():
    import cupy as cp
    topo_g = cp.asarray(topo)
    print("Using cupy (GPU)")
else:
    topo_g = topo
    print("Using numpy (CPU)")

def _gpu(s): return s.to_gpu() if has_cupy() else s


def fit_day(obs_ref):
    init = _gpu(build_taipei_state(XX, YY, topo, cfg_fit, perturbation=-1.0, obs_ref=obs_ref))
    obs_state = _gpu(build_taipei_state(XX, YY, topo, cfg_fit, perturbation=0.0, obs_ref=obs_ref))
    rotated = [_rotate_wind_inplace(init, f["wind_rot_deg"]) for f in DEFAULT_BRANCHES]
    state_b = stack_families(rotated)
    params = {k: [f[k] for f in DEFAULT_BRANCHES] for k in ["drag","humid_couple","nudging","pg_scale","wind_nudge"]}
    bud = None
    for _ in range(cfg_fit.STEPS):
        state_b, bud = batched_branch_step(state_b, params, obs_state, topo_g, cfg_fit, bud)
    states = unstack_families(state_b)
    scored = [(float(score_state(st, obs_state, cfg_fit)["score"]), st) for st in states]
    scored.sort(key=lambda x: -x[0])
    top = scored[0][1]
    return dict(T_int=float(top.T[cy,cx]), h_ctr=float(top.h[cy,cx]),
                q_int=float(top.q[cy,cx]),
                u=float(top.u[cy,cx]), v=float(top.v[cy,cx]))


print(f"Fitting B-calibration on 30 days ({'GPU batched' if has_cupy() else 'CPU numpy'})...")
t0 = time.time()
obs_days = json.loads(OBS_PATH.read_text())["days"]
rows = []
for d in obs_days:
    obs_ref = ReferenceObs(T_avg_C=d["T_mean_C"], RH_pct=d["RH_mean_pct"],
                           P_hPa=d["P_mean_hPa"], ws_ms=d["ws_mean_ms"], wd_deg=d["wd_vec_deg"])
    rows.append({"obs": d, "td": fit_day(obs_ref)})
print(f"Fit done in {time.time()-t0:.1f}s")

T_int = np.array([r["td"]["T_int"] for r in rows])
T_real = np.array([r["obs"]["T_mean_C"] + 273.15 for r in rows])
q_int = np.array([r["td"]["q_int"] for r in rows])
h_ctr = np.array([r["td"]["h_ctr"] for r in rows])
win_int = np.array([math.sqrt(r["td"]["u"]**2 + r["td"]["v"]**2) for r in rows])
win_real = np.array([r["obs"]["ws_mean_ms"] for r in rows])
RH_real = np.array([r["obs"]["RH_mean_pct"] for r in rows])
P_real = np.array([r["obs"]["P_mean_hPa"] for r in rows])

Tf = fit_two_param(T_int, T_real); wf = fit_scale_through_origin(win_int, win_real)
T_2m_C_ts = Tf["theilsen"]["slope"] * T_int + Tf["theilsen"]["intercept"] - 273.15
q_rh = float(np.median(invert_q_to_rh_ratio(q_int, T_2m_C_ts, RH_real)))
dh = h_ctr - 5700.0; mask = np.abs(dh) > 10.0
h2p = float(np.median((1013 - P_real[mask]) / dh[mask])) if mask.sum() >= 3 else 0.02

cal = WeatherCalibration(
    location_name="Taipei (256×192+τ_cond+Kessler)",
    fitted_date="2026-04-19 (finer grid + τ_condense + Kessler precip)",
    T_offset_K=Tf["theilsen"]["intercept"], T_scale=Tf["theilsen"]["slope"],
    h_to_pressure_k=h2p, q_to_rh_ratio=q_rh,
    wind_scale=wf["theilsen_median"]["scale"],
)
print(f"Calibration: T_scale={cal.T_scale:.4f} T_offset_K={cal.T_offset_K:+.3f} "
      f"q_to_rh={cal.q_to_rh_ratio:.3f} wind_scale={cal.wind_scale:.3f} h2p={cal.h_to_pressure_k:+.5f}")

CAL_OUT.write_text(json.dumps({
    "scheme": "B (256×192, τ_condense=600, Kessler precip τ=1000, wind_nudge decay)",
    "calibration": {
        "location_name": cal.location_name, "fitted_date": cal.fitted_date,
        "T_offset_K": cal.T_offset_K, "T_scale": cal.T_scale,
        "h_to_pressure_k": cal.h_to_pressure_k,
        "q_to_rh_ratio": cal.q_to_rh_ratio, "wind_scale": cal.wind_scale,
    }}, indent=2))

# Week forecast
print("\nWeek forecast (wind_nudge decay τ_persist=2 days)...")
obs_ref = ReferenceObs(T_avg_C=24.0, RH_pct=82.5, P_hPa=1009.0, ws_ms=3.6, wd_deg=270.0)
init = _gpu(build_taipei_state(XX, YY, topo, cfg_day, perturbation=-1.0, obs_ref=obs_ref))
obs_state = _gpu(build_taipei_state(XX, YY, topo, cfg_day, perturbation=0.0, obs_ref=obs_ref))
rotated = [_rotate_wind_inplace(init, f["wind_rot_deg"]) for f in DEFAULT_BRANCHES]
state_b = stack_families(rotated)
p_act = {k: [f[k] for f in DEFAULT_BRANCHES] for k in ["drag","humid_couple","nudging","pg_scale","wind_nudge"]}

t0 = time.time(); daily = []; day1_scores = None; budget = None
for d_idx in range(7):
    decay = math.exp(-d_idx / TAU_PERSIST_DAYS)
    pb = {
        "drag": p_act["drag"], "humid_couple": p_act["humid_couple"],
        "pg_scale": p_act["pg_scale"],
        "nudging":    [n * decay for n in p_act["nudging"]],
        "wind_nudge": [w * decay for w in p_act["wind_nudge"]],
    }
    for _ in range(1440):
        state_b, budget = batched_branch_step(state_b, pb, obs_state, topo_g, cfg_day, budget)
    fam_states = unstack_families(state_b)
    if d_idx == 0:
        day1_scores = np.array([float(score_state(st, obs_state, cfg_day)["score"]) for st in fam_states])
    daily.append([(float(st.T[cy,cx]), float(st.h[cy,cx]), float(st.q[cy,cx]),
                   float(st.u[cy,cx]), float(st.v[cy,cx])) for st in fam_states])
print(f"Week done in {time.time()-t0:.1f}s")

w = day1_scores - day1_scores.min() + 1e-6; w = w / w.sum()
print(f"\n{'Date':<12} {'Mode':<5} {'decay':>6} {'T':>7} {'RH':>6} {'Wind':>14}  {'P':>8}")
for d_idx in range(7):
    date_str = (TODAY + timedelta(days=d_idx+1)).isoformat()
    decay = math.exp(-d_idx / TAU_PERSIST_DAYS)
    Ts = np.array([c[0] for c in daily[d_idx]]); qs = np.array([c[2] for c in daily[d_idx]])
    hs = np.array([c[1] for c in daily[d_idx]])
    us = np.array([c[3] for c in daily[d_idx]]); vs = np.array([c[4] for c in daily[d_idx]])
    T_int = np.average(Ts, weights=w); q = np.average(qs, weights=w)
    h = np.average(hs, weights=w); u = np.average(us, weights=w); v = np.average(vs, weights=w)
    T_C = cal.T_scale * T_int + cal.T_offset_K - 273.15
    RH = cal.map_humidity(q, T_C); ws = cal.map_wind(u, v)
    wd = (math.degrees(math.atan2(-u, -v)) + 360.0) % 360.0
    P = cal.map_pressure(h)
    mode = "DA" if d_idx == 0 else "free"
    print(f"{date_str:<12} {mode:<5} {decay:>5.2f}  {T_C:>5.1f}°C {RH:>5.1f}% {ws:>4.1f} m/s @ {wd:>3.0f}° {P:>6.1f}hPa")
