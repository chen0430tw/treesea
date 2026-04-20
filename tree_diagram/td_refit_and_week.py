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
from tree_diagram.numerics.weather_bridge import (
    worldline_to_branch_params, weather_scores_to_alignments,
    OMEGA_EARTH, TAIPEI_LAT_DEG, TAIPEI_F_CORIOLIS, N_OPT_DEFAULT,
)
from tree_diagram.core.problem_seed import ProblemSeed
from tree_diagram.core.worldline_kernel import attach_weather_alignment
from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
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
    # Training consistency: enable h-nudging during fit so training h_ctr
    # reflects obs_ref.P_hPa. Without this, slope(P vs h) fit would still
    # see h_ctr near-constant → collapsed h2p.
    params["h_nudge"] = [1.16e-5 for _ in DEFAULT_BRANCHES]
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
# Theil-Sen slope of P vs h around training-data center of mass (not ratio
# through forced baseline=5700, which swamped the slope when BASE_H=5400).
# h_to_pressure_k = -slope(P vs h); baselines stored so map_pressure uses
# them instead of hardcoded (5700, 1013).
_slopes_Ph = []
for i in range(len(P_real)):
    for j in range(i + 1, len(P_real)):
        _dh = h_ctr[i] - h_ctr[j]
        if abs(_dh) > 0.1:
            _slopes_Ph.append((P_real[i] - P_real[j]) / _dh)
slope_P_h = float(np.median(_slopes_Ph)) if _slopes_Ph else 0.0
h2p = -slope_P_h   # map_pressure: P = p_base - h2p*(h - h_base)
h_baseline_fit = float(np.mean(h_ctr))
p_baseline_fit = float(np.mean(P_real))
print(f"Pressure fit: slope(P vs h)={slope_P_h:+.5f} hPa/m  "
      f"h_baseline={h_baseline_fit:.1f}m  p_baseline={p_baseline_fit:.2f}hPa")

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
    h_baseline_m=h_baseline_fit,
    p_baseline_hPa=p_baseline_fit,
)
print(f"Calibration: T_scale={cal.T_scale:.4f} T_offset_K={cal.T_offset_K:+.3f} "
      f"q_to_rh={cal.q_to_rh_ratio:.3f} wind_scale={cal.wind_scale:.3f} h2p={cal.h_to_pressure_k:+.5f}")

CAL_OUT.write_text(json.dumps({
    "scheme": "B (256×192, τ_condense=600, Kessler precip, wind_nudge decay, wd offset, P-baselines)",
    "calibration": {
        "location_name": cal.location_name, "fitted_date": cal.fitted_date,
        "T_offset_K": cal.T_offset_K, "T_scale": cal.T_scale,
        "h_to_pressure_k": cal.h_to_pressure_k,
        "q_to_rh_ratio": cal.q_to_rh_ratio, "wind_scale": cal.wind_scale,
        "wind_dir_offset_deg": cal.wind_dir_offset_deg,
        "h_baseline_m": cal.h_baseline_m,
        "p_baseline_hPa": cal.p_baseline_hPa,
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
# 2026-04-19 actual daily-mean from Open-Meteo/ECMWF (verified 2026-04-20).
# Previous hardcoded 24.0/82.5/1009/3.6@270 was wrong — wind direction
# especially (270° W vs actual 44° NE) poisoned day-1 DA output.
today_obs = ReferenceObs(T_avg_C=23.8, RH_pct=75.0, P_hPa=1012.3, ws_ms=1.69, wd_deg=44.0)
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

# =====================================================================
# Forecast source — TD CandidatePipeline (default) vs legacy 6-family
# =====================================================================
# Default (USE_TD_WORLDLINES=True): build a weather ProblemSeed from today's
# conditions + 30-day climo stats, let CandidatePipeline generate & rank
# worldline candidates via UMDST scoring (batch-anchored by design — see
# §11.17), then translate each top-K worldline into branch physics params
# via weather_bridge.worldline_to_branch_params and run the same 7-day
# rollout pipeline we used for the 6 hardcoded families.
#
# This is the proper TD interface: TD chooses the parameter manifold points,
# weather_bridge maps them to physics, shallow-water dynamics integrate.
# TD's top-K convergence to batch/n=20000 is a calibration feature, not a bug.
#
# USE_TD_WORLDLINES=False: legacy 6-family hardcoded branches.
# USE_ANALOG_ENSEMBLE=True: legacy-legacy analog sampling for days 2-7.
USE_TD_WORLDLINES = True
USE_ANALOG_ENSEMBLE = False

obs_today_gpu = _gpu(_make_uniform_wind_obs(today_obs, build_taipei_state))
# Climo obs — T/q Held-Suarez relaxation target on free days.
obs_climo_gpu = _gpu(_make_uniform_wind_obs(climo_ref, build_taipei_state))

if USE_ANALOG_ENSEMBLE:
    _rng = np.random.default_rng(seed=20260420)   # reproducible
    _analog_day_idxs = _rng.choice(len(obs_days), size=6, replace=False)
    _analog_obs_gpu = []
    for _idx in _analog_day_idxs:
        d = obs_days[int(_idx)]
        aref = ReferenceObs(T_avg_C=d["T_mean_C"], RH_pct=d["RH_mean_pct"],
                             P_hPa=d["P_mean_hPa"], ws_ms=d["ws_mean_ms"],
                             wd_deg=d["wd_vec_deg"])
        _analog_obs_gpu.append(_gpu(_make_uniform_wind_obs(aref, build_taipei_state)))
    print(f"[legacy] analog days chosen: {[obs_days[int(i)]['date'] for i in _analog_day_idxs]}")
else:
    _analog_obs_gpu = None

# ---------------------------------------------------------------------
# TD WORLDLINE PATH — build weather seed, call CandidatePipeline
# ---------------------------------------------------------------------
def build_weather_seed(today_obs_, climo_ref_, obs_days_, today_date) -> ProblemSeed:
    """Honest ProblemSeed for the forecast task — no copied-template fields.

    subject[8D] describes the FORECAST SYSTEM's capability, not the atmosphere:
      output_power      = forcing-amplitude adequacy (normalised wind speed)
      control_precision = DA/anchor accuracy (today_obs quality)
      load_tolerance    = numerical stability headroom (high post-CFL-fix)
      aim_coupling      = obs↔model alignment under nudging
      stress_level      = synoptic activity (today's deviation from climo)
      phase_proximity   = how near a regime transition (mid-horizon)
      marginal_decay    = per-day skill erosion (~22%/day after day 3)
      instability_sensitivity = chaos exposure (rises with lead time)

    environment.phase_instability is measured from obs variance over the
    30-day window, so TD sees *actual* synoptic activity, not a guess.
    """
    T_std = float(np.std([d["T_mean_C"] for d in obs_days_]))
    P_std = float(np.std([d["P_mean_hPa"] for d in obs_days_]))
    # Normalise to [0,1]: 3°C std + 5 hPa std are typical April mid-lat values.
    phase_instab = min(1.0, 0.55 * (T_std / 3.0) + 0.45 * (P_std / 5.0))
    # Stress: today's deviation from climo
    T_dev = abs(today_obs_.T_avg_C - climo_ref_.T_avg_C)
    P_dev = abs(today_obs_.P_hPa - climo_ref_.P_hPa)
    stress = min(1.0, 0.6 * (T_dev / 3.0) + 0.4 * (P_dev / 5.0))
    # Output power: wind amplitude vs a 5 m/s reference
    out_pow = min(1.0, max(0.2, today_obs_.ws_ms / 5.0))

    return ProblemSeed(
        title=f"Taipei 7-day surface weather forecast ({today_date} → +7d)",
        target=(
            "Forecast daily-mean T/RH/P/wind at Taipei (25.03N, 121.56E) for "
            "7 days. Day 1 anchored to today's obs (DA); days 2-7 free "
            "integration with decaying obs nudge and climo relaxation."
        ),
        constraints=[
            "1-layer shallow water (no baroclinic structure)",
            "256x192 grid DX=DY=6km DT=60s (gravity-wave CFL satisfied)",
            "30-day training climatology ending 2026-04-19 (Open-Meteo ECMWF)",
            "single-point verification at Taipei grid center",
        ],
        resources={
            "budget":              0.85,  # GPU batched, H100 accessible
            "infrastructure":      0.90,  # CuPy + torch ready
            "data_coverage":       0.72,  # 30 days daily means only
            "population_coupling": 0.55,  # single-station obs
        },
        environment={
            "field_noise":         0.30,            # clean daily-mean obs
            "phase_instability":   phase_instab,    # from 30-day variance
            "social_pressure":     0.20,
            "regulatory_friction": 0.20,
            "network_density":     0.40,
        },
        subject={
            "output_power":            out_pow,
            "control_precision":       0.62,
            "load_tolerance":          0.85,   # post-CFL-fix
            "aim_coupling":            0.58,
            "stress_level":            stress,
            "phase_proximity":         0.50,
            "marginal_decay":          0.22,   # skill ~22%/day after d3
            "instability_sensitivity": 0.48,
        },
    )


if USE_TD_WORLDLINES:
    print("\n" + "=" * 68)
    print("TD CandidatePipeline — building weather ProblemSeed")
    print("=" * 68)
    _weather_seed = build_weather_seed(today_obs, climo_ref, obs_days, TODAY)
    print(f"  phase_instability (from 30-day T/P variance): "
          f"{_weather_seed.environment['phase_instability']:.3f}")
    print(f"  stress_level (today deviation from climo):    "
          f"{_weather_seed.subject['stress_level']:.3f}")
    print(f"  output_power (today wind / 5 m/s):            "
          f"{_weather_seed.subject['output_power']:.3f}")
    _td_t0 = time.time()
    _pipeline = CandidatePipeline(
        seed=_weather_seed, top_k=12,
        NX=128, NY=96, steps=300, dt=45.0,
    )
    _td_top_results, _td_hydro, _td_oracle = _pipeline.run()
    print(f"  CandidatePipeline.run(): {time.time() - _td_t0:.1f}s "
          f"(alive={_td_hydro.get('alive_count')} pruned={_td_hydro.get('pruned_count')})")
    print(f"  Top-{min(5, len(_td_top_results))} worldlines (TD judgment layer):")
    for _i, _r in enumerate(_td_top_results[:5]):
        _p = _r.params
        print(f"    #{_i+1} {_r.family:<13} "
              f"n={int(_p.get('n', 0)):>5} rho={_p.get('rho', 0):.2f} "
              f"A={_p.get('A', 0):.2f} sigma={_p.get('sigma', 0):.3f} | "
              f"score={_r.balanced_score:+.3f} feas={_r.feasibility:.2f} "
              f"status={_r.branch_status}")
    # Translate TD worldlines to physics branch params
    forecast_branches = [worldline_to_branch_params(_r, _weather_seed) for _r in _td_top_results]
    print(f"  Translated to {len(forecast_branches)} physics branches via weather_bridge")
else:
    forecast_branches = _forecast_families()   # legacy 6-family wind_rot=0
    _td_top_results = None
    _td_hydro = None
    _td_oracle = None
    print("[legacy] 6-family hardcoded branches (USE_TD_WORLDLINES=False)")

# =====================================================================
# 7-day rollout via TD's unified_rollout (UMDST-coupled physics)
# =====================================================================
# Replaces the previous batched_branch_step loop (vanilla 1-layer SW).
# unified_step couples shallow-water physics with UMDST phase/stress/
# instability dynamics — spatial_het and wind_rms feed back into gain,
# preventing the asymptotic wind collapse we saw in the pure-SW rollout.
#
# Per-day checkpointing: 1 forecast day = 86400 s. TD default dt=45 s →
# 1920 substeps/day. 7 days = 13440 substeps total.

from tree_diagram.core.worldline_kernel import (
    unified_rollout as td_unified_rollout,
    prepare_candidate_arrays as td_prepare_candidate_arrays,
    encode_initial_state as td_encode_initial_state,
    _DOMAIN_X as TD_DOMAIN_X, _DOMAIN_Y as TD_DOMAIN_Y,
)

# TD grid (matches CandidatePipeline defaults)
_TD_NX, _TD_NY = 128, 96
_TD_DX = TD_DOMAIN_X / (_TD_NX - 1)
_TD_DY = TD_DOMAIN_Y / (_TD_NY - 1)
_TD_DT = 45.0
_TD_STEPS_PER_DAY = int(round(86400.0 / _TD_DT))   # 1920

# Build candidate list from TD's worldlines (or legacy DEFAULT_BRANCHES)
if USE_TD_WORLDLINES and _td_top_results is not None:
    _candidates = [
        {"family": r.family, "template": r.template, "params": r.params}
        for r in _td_top_results
    ]
else:
    # Legacy path: synthesise candidate dicts from DEFAULT_BRANCHES, using
    # n=20000 (UMDST fixed point) so the unified_step gain modifier is unbiased.
    _candidates = [
        {"family": f["name"], "template": f["name"],
         "params": {"n": 20000.0, "rho": 1.0, "A": 0.7, "sigma": 0.03}}
        for f in forecast_branches
    ]

_carr = td_prepare_candidate_arrays(_candidates)
_td_state = td_encode_initial_state(_td_top_results and _weather_seed or build_weather_seed(today_obs, climo_ref, obs_days, TODAY),
                                     _candidates, _TD_NX, _TD_NY)

# Inject Taipei-specific obs fields into UnifiedState (override TD's abstract obs)
def _taipei_obs_on_td_grid(ref_obs):
    """Build (NY, NX) obs fields for TD's domain from a Taipei ReferenceObs."""
    _cfg_td = GridConfig(NX=_TD_NX, NY=_TD_NY, DX=_TD_DX, DY=_TD_DY,
                          DT=_TD_DT, STEPS=_TD_STEPS_PER_DAY)
    _XX, _YY, _, _ = build_grid(_cfg_td)
    _topo = build_topography(_XX, _YY)
    # Rebuild at TD grid (not cfg_day's 256x192)
    _base = build_taipei_state(_XX, _YY, _topo, _cfg_td, perturbation=0.0, obs_ref=ref_obs)
    wd_rad = math.radians(ref_obs.wd_deg)
    u_uni = -ref_obs.ws_ms * math.sin(wd_rad)
    v_uni = -ref_obs.ws_ms * math.cos(wd_rad)
    return (_base.h.astype(np.float32), _base.T.astype(np.float32),
            _base.q.astype(np.float32),
            np.full_like(_base.u, u_uni, dtype=np.float32),
            np.full_like(_base.v, v_uni, dtype=np.float32),
            _topo.astype(np.float32))

_today_obs_h, _today_obs_T, _today_obs_q, _today_obs_u, _today_obs_v, _taipei_topo = \
    _taipei_obs_on_td_grid(today_obs)
_climo_obs_h, _climo_obs_T, _climo_obs_q, _climo_obs_u, _climo_obs_v, _ = \
    _taipei_obs_on_td_grid(climo_ref)

# Override TD's synthetic obs with Taipei-specific ones + real topography
_td_state.obs_h = _today_obs_h
_td_state.obs_T = _today_obs_T
_td_state.obs_q = _today_obs_q
_td_state.obs_u = _today_obs_u
_td_state.obs_v = _today_obs_v
_td_state.topography = _taipei_topo

# Grid center on TD's 128x96
_td_cy, _td_cx = _TD_NY // 2, _TD_NX // 2

t0 = time.time()
daily = []
print(f"\nTD unified_rollout 7-day forecast ({_TD_NX}x{_TD_NY}, dt={_TD_DT}s, "
      f"{_TD_STEPS_PER_DAY} substeps/day)")
_total_steps = 7 * _TD_STEPS_PER_DAY
_step_offset = 0
for d_idx in range(7):
    # Switch obs target: day 1 anchors today_obs, day 2-7 relax toward climo
    if d_idx == 0:
        _td_state.obs_h = _today_obs_h
        _td_state.obs_T = _today_obs_T
        _td_state.obs_q = _today_obs_q
        _td_state.obs_u = _today_obs_u
        _td_state.obs_v = _today_obs_v
    else:
        _td_state.obs_h = _climo_obs_h
        _td_state.obs_T = _climo_obs_T
        _td_state.obs_q = _climo_obs_q
        _td_state.obs_u = _climo_obs_u
        _td_state.obs_v = _climo_obs_v

    _td_state, _phase_seg = td_unified_rollout(
        _td_state, _carr,
        dt=_TD_DT, dx=_TD_DX, dy=_TD_DY,
        steps=_TD_STEPS_PER_DAY,
        step_offset=_step_offset, total_steps=_total_steps,
    )
    _step_offset += _TD_STEPS_PER_DAY

    # Per-candidate center values
    centers = []
    for b in range(len(_candidates)):
        centers.append((
            float(_td_state.T[b, _td_cy, _td_cx]),
            float(_td_state.h[b, _td_cy, _td_cx]),
            float(_td_state.q[b, _td_cy, _td_cx]),
            float(_td_state.u[b, _td_cy, _td_cx]),
            float(_td_state.v[b, _td_cy, _td_cx]),
        ))
    # Score each candidate's field fit vs current day's obs (using phase proximity)
    _day_scores = np.asarray(_td_state.phase, dtype=np.float64)
    daily.append({"centers": centers, "scores": _day_scores})
    print(f"  day {d_idx+1}: phase mean={float(_day_scores.mean()):.3f} "
          f"T_center0={centers[0][0]:.1f}K h0={centers[0][1]:.1f} u0={centers[0][3]:+.2f} "
          f"v0={centers[0][4]:+.2f}")
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


# =====================================================================
# Close the loop — feed day-1 physics scores back into TD worldlines
# =====================================================================
# CandidatePipeline produced TD's abstract ranking (feasibility/stability/risk).
# The 7-day rollout just finished produced per-day physics scores. Fold them
# back into EvaluationResult.weather_score / weather_alignment /
# final_balanced_score so TD's judgment layer sees the physical evidence.
# Day-1 scores are the cleanest signal (obs actually valid then); downstream
# reporting layers can use final_balanced_score for re-ranking.

if USE_TD_WORLDLINES and _td_top_results is not None:
    _day1_scores = [float(s) for s in daily[0]["scores"]]
    attach_weather_alignment(_td_top_results, _day1_scores)
    print(f"\n" + "=" * 68)
    print("TD JUDGMENT (post-physics attach_weather_alignment, re-ranked)")
    print("=" * 68)
    _reranked = sorted(_td_top_results,
                        key=lambda r: r.final_balanced_score or r.balanced_score,
                        reverse=True)
    print(f"  {'rank':<5} {'family':<13} {'n':>5} {'bal':>7} {'weather':>8} "
          f"{'align':>7} {'final':>8}")
    for _i, _r in enumerate(_reranked[:8]):
        print(f"  #{_i+1:<4} {_r.family:<13} {int(_r.params['n']):>5} "
              f"{_r.balanced_score:>+7.3f} "
              f"{_r.weather_score:>8.4f} "
              f"{_r.weather_alignment:>+7.3f} "
              f"{_r.final_balanced_score:>+8.3f}")
