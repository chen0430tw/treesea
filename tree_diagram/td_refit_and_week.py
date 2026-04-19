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
from tree_diagram.numerics.weather_state import WeatherState
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

# Forecast-mode families: zero rotation (rotation was only useful for OOS
# ensemble-ranking diversity; for point forecast the uniform-rotation creates
# advective contamination from rotated background and ends up fusing to
# climatological wind direction regardless of today's obs).
def _forecast_families():
    return [dict(f, wind_rot_deg=0.0) for f in DEFAULT_BRANCHES]

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
    u, v = float(top.u[cy,cx]), float(top.v[cy,cx])
    wd_td = (math.degrees(math.atan2(-u, -v)) + 360.0) % 360.0
    return dict(T_int=float(top.T[cy,cx]), h_ctr=float(top.h[cy,cx]),
                q_int=float(top.q[cy,cx]), u=u, v=v, wd_td=wd_td)


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

# Fit wind-direction offset: circular median of (obs_wd - td_wd) across training days.
# Wraps each diff to [-180, 180]; simple median is robust if diffs cluster.
wd_diffs = []
for r in rows:
    obs_wd = r["obs"]["wd_vec_deg"]
    td_wd = r["td"]["wd_td"]
    d = (obs_wd - td_wd + 540.0) % 360.0 - 180.0
    wd_diffs.append(d)
wd_offset = float(np.median(wd_diffs))
print(f"Wind-dir offset: circular-median(obs - td) = {wd_offset:+.1f}° (n={len(wd_diffs)})")

cal = WeatherCalibration(
    location_name="Taipei (256×192+τ_cond+Kessler+wd_offset)",
    fitted_date="2026-04-19 (finer grid + τ_condense + Kessler precip + wd Coriolis-offset)",
    T_offset_K=Tf["theilsen"]["intercept"], T_scale=Tf["theilsen"]["slope"],
    h_to_pressure_k=h2p, q_to_rh_ratio=q_rh,
    wind_scale=wf["theilsen_median"]["scale"],
    wind_dir_offset_deg=wd_offset,
)
print(f"Calibration: T_scale={cal.T_scale:.4f} T_offset_K={cal.T_offset_K:+.3f} "
      f"q_to_rh={cal.q_to_rh_ratio:.3f} wind_scale={cal.wind_scale:.3f} h2p={cal.h_to_pressure_k:+.5f}")

CAL_OUT.write_text(json.dumps({
    "scheme": "B (256×192, τ_condense=600, Kessler precip, wind_nudge decay, wd offset)",
    "calibration": {
        "location_name": cal.location_name, "fitted_date": cal.fitted_date,
        "T_offset_K": cal.T_offset_K, "T_scale": cal.T_scale,
        "h_to_pressure_k": cal.h_to_pressure_k,
        "q_to_rh_ratio": cal.q_to_rh_ratio, "wind_scale": cal.wind_scale,
        "wind_dir_offset_deg": cal.wind_dir_offset_deg,
    }}, indent=2))

# Build climatology obs (for days 2-7 to relax toward instead of today's pinned values)
climo_T  = float(np.mean([d["T_mean_C"]    for d in obs_days]))
climo_RH = float(np.mean([d["RH_mean_pct"] for d in obs_days]))
climo_P  = float(np.mean([d["P_mean_hPa"]  for d in obs_days]))
climo_ws = float(np.mean([d["ws_mean_ms"]  for d in obs_days]))
u_s = sum(d["ws_mean_ms"] * math.sin(math.radians(d["wd_vec_deg"])) for d in obs_days)
v_s = sum(d["ws_mean_ms"] * math.cos(math.radians(d["wd_vec_deg"])) for d in obs_days)
climo_wd = (math.degrees(math.atan2(u_s, v_s)) + 360.0) % 360.0
climo_ref = ReferenceObs(T_avg_C=climo_T, RH_pct=climo_RH, P_hPa=climo_P,
                          ws_ms=climo_ws, wd_deg=climo_wd)
print(f"Climatology obs for free days: T={climo_T:.1f}°C  RH={climo_RH:.1f}%  "
      f"P={climo_P:.1f}hPa  wind={climo_ws:.2f} m/s @ {climo_wd:.0f}°")

# Week forecast
print("\nWeek forecast (zero wind_rot, climo obs days 2-7, wind_nudge decay τ=2d)...")
today_obs = ReferenceObs(T_avg_C=24.0, RH_pct=82.5, P_hPa=1009.0, ws_ms=3.6, wd_deg=270.0)
# Init wind uniform at today value (not Gaussian-blended) — prevents advection
# from far-field climo-direction cells polluting the center.
_init_base = build_taipei_state(XX, YY, topo, cfg_day, perturbation=-1.0, obs_ref=today_obs)
_today_wd_rad = math.radians(today_obs.wd_deg)
_u_today = -today_obs.ws_ms * math.sin(_today_wd_rad)
_v_today = -today_obs.ws_ms * math.cos(_today_wd_rad)
init = _gpu(WeatherState(
    h=_init_base.h, T=_init_base.T, q=_init_base.q,
    u=np.full_like(_init_base.u, _u_today),
    v=np.full_like(_init_base.v, _v_today),
))
def _make_uniform_wind_obs(obs_ref, base_fn):
    """Build obs state with UNIFORM (u,v) = obs wind value everywhere, while
    keeping h/T/q spatial structure from build_taipei_state. Spectral-nudging
    style: large-scale wind forcing baked into obs target across full grid,
    not Gaussian-localized at center (which advection dilutes on fine grids)."""
    base = base_fn(XX, YY, topo, cfg_day, perturbation=0.0, obs_ref=obs_ref)
    wd_rad = math.radians(obs_ref.wd_deg)
    u_uniform = -obs_ref.ws_ms * math.sin(wd_rad)
    v_uniform = -obs_ref.ws_ms * math.cos(wd_rad)
    return WeatherState(
        h=base.h, T=base.T, q=base.q,
        u=np.full_like(base.u, u_uniform),
        v=np.full_like(base.v, v_uniform),
    )

# Day 1 obs: uniform TODAY wind across grid (not Gaussian-weighted)
# Days 2-7 obs: uniform CLIMO wind across grid
obs_today_gpu = _gpu(_make_uniform_wind_obs(today_obs, build_taipei_state))
obs_climo_gpu = _gpu(_make_uniform_wind_obs(climo_ref, build_taipei_state))

forecast_branches = _forecast_families()   # wind_rot=0 for all
# No rotation needed — stack init directly
state_b = stack_families([init] * len(forecast_branches))
p_act = {k: [f[k] for f in forecast_branches] for k in
         ["drag","humid_couple","nudging","pg_scale","wind_nudge"]}

t0 = time.time(); daily = []; budget = None
CLIMO_WIND_BOOST = 3.0   # spectral-nudging-style: amplify wind_nudge on climo days to override PGF
for d_idx in range(7):
    if d_idx == 0:
        decay = 1.0
        wind_boost = 1.0
        obs_for_day = obs_today_gpu
    else:
        decay = 1.0                    # climo permanent
        wind_boost = CLIMO_WIND_BOOST  # strong uniform climo wind (spectral nudging)
        obs_for_day = obs_climo_gpu
    pb = {
        "drag": p_act["drag"], "humid_couple": p_act["humid_couple"],
        "pg_scale": p_act["pg_scale"],
        "nudging":    [0.0 for _ in p_act["nudging"]],       # DBG
        "wind_nudge": [0.0 for _ in p_act["wind_nudge"]],    # DBG
    }
    # DEBUG: snapshot state at start of day
    _dbg_u_start = float(state_b.u[0, cy, cx])
    _dbg_v_start = float(state_b.v[0, cy, cx])
    _obs_u_center = float(obs_for_day.u[cy, cx])
    _obs_v_center = float(obs_for_day.v[cy, cx])
    _wn_val = pb["wind_nudge"][0]
    for _ in range(1440):
        state_b, budget = batched_branch_step(state_b, pb, obs_for_day, topo_g, cfg_day, budget)
    fam_states = unstack_families(state_b)
    _dbg_u_end = float(state_b.u[0, cy, cx])
    _dbg_v_end = float(state_b.v[0, cy, cx])
    print(f"  DBG d{d_idx+1}: obs(u,v)=({_obs_u_center:+.2f},{_obs_v_center:+.2f})  "
          f"state fam0 start=({_dbg_u_start:+.2f},{_dbg_v_start:+.2f}) "
          f"end=({_dbg_u_end:+.2f},{_dbg_v_end:+.2f})  wind_nudge={_wn_val:.2e}")
    # Per-day fusion weights: score each family against the day's obs target
    day_scores = np.array([float(score_state(st, obs_for_day, cfg_day)["score"]) for st in fam_states])
    daily.append({
        "centers": [(float(st.T[cy,cx]), float(st.h[cy,cx]), float(st.q[cy,cx]),
                     float(st.u[cy,cx]), float(st.v[cy,cx])) for st in fam_states],
        "scores": day_scores,
    })
print(f"Week done in {time.time()-t0:.1f}s")

print(f"\n{'Date':<12} {'Mode':<5} {'decay':>6} {'T':>7} {'RH':>6} {'Wind':>14}  {'P':>8}")
for d_idx in range(7):
    date_str = (TODAY + timedelta(days=d_idx+1)).isoformat()
    decay = math.exp(-d_idx / TAU_PERSIST_DAYS)
    day = daily[d_idx]
    # TEMP: uniform weights to match probe behavior and isolate physics
    w_day = np.ones(len(day["centers"])) / len(day["centers"])
    Ts = np.array([c[0] for c in day["centers"]]); qs = np.array([c[2] for c in day["centers"]])
    hs = np.array([c[1] for c in day["centers"]])
    us = np.array([c[3] for c in day["centers"]]); vs = np.array([c[4] for c in day["centers"]])
    T_int = np.average(Ts, weights=w_day); q = np.average(qs, weights=w_day)
    h = np.average(hs, weights=w_day); u = np.average(us, weights=w_day); v = np.average(vs, weights=w_day)
    T_C = cal.T_scale * T_int + cal.T_offset_K - 273.15
    RH = cal.map_humidity(q, T_C); ws = cal.map_wind(u, v)
    wd_raw = (math.degrees(math.atan2(-u, -v)) + 360.0) % 360.0
    wd = wd_raw   # TEMP: print RAW wd, offset disabled to see linear h_bg effect
    P = cal.map_pressure(h)
    mode = "DA" if d_idx == 0 else "free"
    print(f"{date_str:<12} {mode:<5} {decay:>5.2f}  {T_C:>5.1f}°C {RH:>5.1f}% {ws:>4.1f} m/s @ {wd:>3.0f}° {P:>6.1f}hPa")
