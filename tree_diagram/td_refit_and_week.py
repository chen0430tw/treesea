"""Run a 7-day Taipei forecast with TD worldline selection + physical surface diagnostics.

This script keeps two layers separate:
1. TD native judgment / governance:
   CandidatePipeline -> top worldlines -> hydro / oracle / phase diagnostics
2. Weather diagnostics:
   unified_rollout internal state (h, T, q, u, v at the TD mid-level reference)
   -> physical surface conversion (2 m T / RH / surface pressure / 10 m wind)

No MOS / Theil-Sen / WeatherCalibration regression is used here.
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from td_taipei_forecast import ReferenceObs, build_taipei_state
from tree_diagram.core.background_inference import infer_problem_background as td_infer_bg
from tree_diagram.core.problem_seed import ProblemSeed
from tree_diagram.core.worldline_kernel import (
    _TORCH_OK,
    _DOMAIN_X as TD_DOMAIN_X,
    _DOMAIN_Y as TD_DOMAIN_Y,
    _carr_to_torch,
    _state_to_numpy,
    _state_to_torch,
    _torch_rollout,
    attach_weather_alignment,
    encode_initial_state as td_encode_initial_state,
    forecast_evidence,
    generate_candidates as td_generate_candidates,
    prepare_candidate_arrays as td_prepare_candidate_arrays,
    unified_rollout as td_unified_rollout,
)
from tree_diagram.numerics.forcing import GridConfig, build_grid, build_topography
from tree_diagram.numerics.weather_bridge import (
    CP_AIR,
    GRAVITY_STD,
    LV_VAPORIZATION,
    P_MID_HPA,
    R_DRY_AIR,
    R_WATER_VAPOR,
)
from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline

try:
    import torch
except Exception:  # pragma: no cover - torch is optional locally
    torch = None

OBS_PATH = HERE / "calibration" / "taipei_obs_daily.json"
TODAY = date(2026, 4, 19)
TAU_PERSIST_DAYS = 2.0
EPSILON = R_DRY_AIR / R_WATER_VAPOR
Z0_URBAN_M = 1.0
TAIPEI_STATION_ELEV_M = 9.0
PRESSURE_ENCODER_M_PER_HPA = 8.0
BL_TOP_ABOVE_SURFACE_M = 1500.0   # subtropical boundary-layer top (AGL)
BL_EFFECTIVE_LAPSE_K_PER_M = 3.0e-3  # stable subtropical BL lapse, see
                                      # _surface_from_internal() docstring.

TD_NX = 128
TD_NY = 96
TD_DX = TD_DOMAIN_X / (TD_NX - 1)
TD_DY = TD_DOMAIN_Y / (TD_NY - 1)
TD_DT = 45.0
TD_STEPS_PER_DAY = int(round(86400.0 / TD_DT))   # 1920 substeps @ dt=45s
TD_SAMPLE_STRIDE = 240                             # 8 samples/day (every 3 h)
TD_SAMPLES_PER_DAY = TD_STEPS_PER_DAY // TD_SAMPLE_STRIDE
TD_CFG = GridConfig(NX=TD_NX, NY=TD_NY, DX=TD_DX, DY=TD_DY, DT=TD_DT, STEPS=TD_STEPS_PER_DAY)
TD_XX, TD_YY, _, _ = build_grid(TD_CFG)
TD_TOPO = build_topography(TD_XX, TD_YY).astype(np.float32)
TD_CY, TD_CX = TD_NY // 2, TD_NX // 2


def _candidate_key(params: dict, family: str) -> tuple:
    return (
        family,
        int(params.get("n", 0)),
        round(float(params.get("rho", 0.0)), 4),
        round(float(params.get("A", 0.0)), 4),
        round(float(params.get("sigma", 0.0)), 4),
    )


def _saturation_vapor_pressure_hpa(T_k: float) -> float:
    T_c = T_k - 273.15
    return 6.112 * math.exp(17.67 * T_c / (T_c + 243.5))


def _saturation_mixing_ratio(T_k: float, p_pa: float) -> float:
    e_sat_pa = 100.0 * _saturation_vapor_pressure_hpa(T_k)
    return EPSILON * e_sat_pa / max(1.0, p_pa - e_sat_pa)


def _moist_adiabatic_lapse_rate(T_k: float, p_pa: float) -> float:
    rs = max(0.0, min(0.5, _saturation_mixing_ratio(T_k, p_pa)))
    numerator = GRAVITY_STD * (1.0 + LV_VAPORIZATION * rs / (R_DRY_AIR * T_k))
    denominator = CP_AIR + (LV_VAPORIZATION**2 * rs * EPSILON) / (R_DRY_AIR * T_k**2)
    return numerator / denominator


def _relative_humidity_midlevel_pct(T_mid_k: float, q_mid: float, p_mid_hpa: float = P_MID_HPA) -> float:
    """Decode RH from the model's mid-level moisture state.

    build_taipei_state() encodes the surface humidity signal into a 500 hPa-layer
    specific humidity using Tetens at the internal mid-level reference. The most
    self-consistent inverse for this one-layer model is therefore to recover RH at
    the same mid-level, then carry that RH marker down to the surface diagnostics.
    """
    q_mid = max(1.0e-6, min(0.03, q_mid))
    e_actual_hpa = q_mid * p_mid_hpa / (EPSILON + (1.0 - EPSILON) * q_mid)
    e_sat_mid_hpa = _saturation_vapor_pressure_hpa(T_mid_k)
    return float(np.clip(100.0 * e_actual_hpa / max(1.0e-6, e_sat_mid_hpa), 0.0, 100.0))


def _surface_from_internal(
    *,
    h_mid_m: float,
    T_mid_k: float,
    q_mid: float,
    u_mid: float,
    v_mid: float,
    surface_elevation_m: float,
    pressure_anchor_h_mid_m: float,
    pressure_anchor_surface_hpa: float,
) -> dict:
    """Convert TD mid-level state (~500 hPa) to surface diagnostics.

    Temperature: **two-layer lapse-rate conversion** from h_mid_m down to 2 m.
    Single-layer moist-adiabatic lapse over the full 5400 m column over-warms
    T_2m by ~3 K for subtropical coastal locations because the lower 1-2 km
    is typically more stable than free-atmosphere moist adiabatic:
      - Free atmosphere (h_mid_m → surface+BL_top): use moist adiabatic Γm
        computed at (T_mid, p_mid). Small in cold / tropical regimes (~5 K/km).
      - Boundary layer (surface+BL_top → 2 m): use a subtropical stable
        lapse BL_EFFECTIVE_LAPSE_K_PER_M (~3 K/km), representing the
        nighttime-inversion plus weak daytime mixing average over a day.
    This reduces the total column lapse correction from ~29 K (single layer)
    to ~25 K, aligning T_2m with observed climatology without any regression.
    """
    z_mid = max(h_mid_m, surface_elevation_m + 50.0)
    z_2m = surface_elevation_m + 2.0
    z_10m = surface_elevation_m + 10.0
    z_BL_top = surface_elevation_m + BL_TOP_ABOVE_SURFACE_M
    dz_ref = max(50.0, z_mid - surface_elevation_m)

    p_mid_pa = P_MID_HPA * 100.0
    gamma_m = _moist_adiabatic_lapse_rate(T_mid_k, p_mid_pa)

    # Free-atmosphere portion: moist adiabatic from h_mid_m down to BL top
    dz_free = max(0.0, z_mid - z_BL_top)
    T_at_BL_top_k = T_mid_k + gamma_m * dz_free
    # Boundary-layer portion: stable subtropical lapse from BL top down to 2 m
    dz_BL = max(0.0, z_BL_top - z_2m)
    T_2m_k = T_at_BL_top_k + BL_EFFECTIVE_LAPSE_K_PER_M * dz_BL
    # Retain dz_to_2m for downstream hypsometric pressure calc (uses full dz)
    dz_to_2m = max(0.0, z_mid - z_2m)

    q_mid = max(1.0e-6, min(0.03, q_mid))
    rh_mid_pct = _relative_humidity_midlevel_pct(T_mid_k, q_mid, P_MID_HPA)
    Tv_mid = T_mid_k * (1.0 + 0.61 * q_mid)
    Tv_2m = T_2m_k * (1.0 + 0.61 * q_mid)
    Tv_bar = max(180.0, 0.5 * (Tv_mid + Tv_2m))
    p_surface_pa_hypsometric = p_mid_pa * math.exp(GRAVITY_STD * dz_to_2m / (R_DRY_AIR * Tv_bar))
    p_surface_hpa_hypsometric = p_surface_pa_hypsometric / 100.0
    p_surface_hpa = pressure_anchor_surface_hpa + (
        h_mid_m - pressure_anchor_h_mid_m
    ) / PRESSURE_ENCODER_M_PER_HPA

    wind_mid_ms = math.hypot(u_mid, v_mid)
    log_num = math.log((z_10m - surface_elevation_m + Z0_URBAN_M) / Z0_URBAN_M)
    log_den = math.log((dz_ref + Z0_URBAN_M) / Z0_URBAN_M)
    wind_10m_ms = wind_mid_ms * log_num / max(1.0e-6, log_den)
    wind_dir_deg = (math.degrees(math.atan2(-u_mid, -v_mid)) + 360.0) % 360.0

    return {
        "temperature_2m_C": T_2m_k - 273.15,
        "relative_humidity_pct": rh_mid_pct,
        "surface_pressure_hpa": float(np.clip(p_surface_hpa, 870.0, 1085.0)),
        "surface_pressure_hpa_hypsometric": p_surface_hpa_hypsometric,
        "wind_speed_10m_ms": wind_10m_ms,
        "wind_direction_deg": wind_dir_deg,
        "gamma_m_K_per_km": gamma_m * 1000.0,
        "relative_humidity_mid_pct": rh_mid_pct,
    }


def _diurnal_deviation(hour_local: float) -> float:
    """Dimensionless diurnal deviation ∈ [-1, +1] at a given local solar hour.

    Peak +1 at 14:00, trough -1 at 05:00. Piecewise cosines so heating
    (05→14, 9 h) and cooling (14→05, 15 h) have distinct timescales —
    reproduces the typical subtropical mid-day max / pre-dawn min offset
    better than a symmetric sinusoid.

    This is a surface 2-m diagnostic only; the TD internal state does not
    see it. Amplitude modulation (RH/wind) is applied by _apply_diurnal_t2m.
    """
    h = hour_local % 24.0
    if 5.0 <= h <= 14.0:
        t = (h - 5.0) / 9.0
        return -math.cos(math.pi * t)
    if h > 14.0:
        t = (h - 14.0) / 15.0
    else:
        t = (h + 10.0) / 15.0
    return math.cos(math.pi * t)


def _apply_diurnal_t2m(surface: dict, hour_local: float) -> dict:
    """Add a diurnal T2m deviation to a surface diagnostic dict.

    Applies only to `temperature_2m_C`; all other fields untouched.
    Amplitude modulation:
      - base 8 K (clear-sky subtropical spring typical)
      - scaled by (1 − 0.008·RH) — moist/cloudy atmospheres dampen diurnal
      - scaled by 1/(1+0.15·wind10) — turbulent mixing dampens diurnal
    Hard floors (0.2 × base, 0.3 × base) prevent amplitude collapsing to 0.
    The TD internal state h/T/q/u/v is NOT modified.
    """
    rh = float(surface.get("relative_humidity_pct", 75.0))
    ws = float(surface.get("wind_speed_10m_ms", 0.0))
    base_amplitude = 8.0
    rh_factor   = max(0.2, 1.0 - 0.008 * rh)
    wind_factor = max(0.3, 1.0 / (1.0 + 0.15 * ws))
    amplitude = base_amplitude * rh_factor * wind_factor
    delta_T = amplitude * _diurnal_deviation(hour_local)
    out = dict(surface)
    out["temperature_2m_C"] = surface["temperature_2m_C"] + delta_T
    out["diurnal_delta_K"]  = float(delta_T)
    out["diurnal_amplitude_K"] = float(amplitude)
    return out


def _physical_summary_from_centers(
    centers: np.ndarray,
    surface_elevation_m: float,
    pressure_anchor_h_mid_m: float,
    pressure_anchor_surface_hpa: float,
) -> dict:
    T_mid = float(np.median(centers[:, 0]))
    h_mid = float(np.median(centers[:, 1]))
    q_mid = float(np.median(centers[:, 2]))
    u_mid = float(np.median(centers[:, 3]))
    v_mid = float(np.median(centers[:, 4]))
    surface = _surface_from_internal(
        h_mid_m=h_mid,
        T_mid_k=T_mid,
        q_mid=q_mid,
        u_mid=u_mid,
        v_mid=v_mid,
        surface_elevation_m=surface_elevation_m,
        pressure_anchor_h_mid_m=pressure_anchor_h_mid_m,
        pressure_anchor_surface_hpa=pressure_anchor_surface_hpa,
    )
    surface["ensemble_spread"] = {
        "T_mid_std_K": float(np.std(centers[:, 0])),
        "h_mid_std_m": float(np.std(centers[:, 1])),
        "q_mid_std": float(np.std(centers[:, 2])),
        "wind_mid_std_ms": float(np.std(np.hypot(centers[:, 3], centers[:, 4]))),
    }
    return surface


def _wrap_angle_diff_deg(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _surface_score(surface: dict, target_obs: ReferenceObs) -> float:
    """Higher is better. Score is intentionally relative, not calibrated."""
    t_err = abs(surface["temperature_2m_C"] - target_obs.T_avg_C) / 4.0
    rh_err = abs(surface["relative_humidity_pct"] - target_obs.RH_pct) / 20.0
    p_err = abs(surface["surface_pressure_hpa"] - target_obs.P_hPa) / 4.0
    ws_err = abs(surface["wind_speed_10m_ms"] - target_obs.ws_ms) / 3.0
    wd_err = _wrap_angle_diff_deg(surface["wind_direction_deg"], target_obs.wd_deg) / 60.0
    weighted = 0.30 * t_err + 0.20 * rh_err + 0.25 * p_err + 0.15 * ws_err + 0.10 * wd_err
    return float(max(-4.0, 1.0 - weighted))


def _candidate_surface_diagnostics(
    centers: np.ndarray,
    surface_elevation_m: float,
    pressure_anchor_h_mid_m: float,
    pressure_anchor_surface_hpa: float,
) -> list[dict]:
    out: list[dict] = []
    for row in centers:
        out.append(
            _surface_from_internal(
                h_mid_m=float(row[1]),
                T_mid_k=float(row[0]),
                q_mid=float(row[2]),
                u_mid=float(row[3]),
                v_mid=float(row[4]),
                surface_elevation_m=surface_elevation_m,
                pressure_anchor_h_mid_m=pressure_anchor_h_mid_m,
                pressure_anchor_surface_hpa=pressure_anchor_surface_hpa,
            )
        )
    return out


def _norm_spread(arr: np.ndarray) -> np.ndarray:
    lo = float(arr.min())
    hi = float(arr.max())
    if hi - lo < 1.0e-12:
        return np.zeros_like(arr, dtype=np.float64)
    return (arr - lo) / (hi - lo)


def _field_fit_scores(
    h: np.ndarray,
    T: np.ndarray,
    q: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    obs_fields: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray],
) -> np.ndarray:
    obs_h, obs_T, obs_q, obs_u, obs_v = obs_fields
    h_err = ((h - obs_h[None]) ** 2).mean(axis=(1, 2))
    T_err = ((T - obs_T[None]) ** 2).mean(axis=(1, 2))
    q_err = ((q - obs_q[None]) ** 2).mean(axis=(1, 2))
    w_err = ((u - obs_u[None]) ** 2 + (v - obs_v[None]) ** 2).mean(axis=(1, 2))
    composite = (
        0.35 * _norm_spread(h_err)
        + 0.30 * _norm_spread(T_err)
        + 0.20 * _norm_spread(q_err)
        + 0.15 * _norm_spread(w_err)
    )
    return 1.0 - composite


def _build_weather_seed(today_obs_: ReferenceObs, climo_ref_: ReferenceObs, obs_days_: list[dict], today_date: date) -> ProblemSeed:
    T_std = float(np.std([d["T_mean_C"] for d in obs_days_]))
    P_std = float(np.std([d["P_mean_hPa"] for d in obs_days_]))
    phase_instab = min(1.0, 0.55 * (T_std / 3.0) + 0.45 * (P_std / 5.0))

    T_dev = abs(today_obs_.T_avg_C - climo_ref_.T_avg_C)
    P_dev = abs(today_obs_.P_hPa - climo_ref_.P_hPa)
    stress = min(1.0, 0.6 * (T_dev / 3.0) + 0.4 * (P_dev / 5.0))
    out_pow = min(1.0, max(0.2, today_obs_.ws_ms / 5.0))

    return ProblemSeed(
        title=f"Taipei 7-day surface weather forecast ({today_date} -> +7d)",
        target=(
            "Forecast daily-mean T/RH/P/wind at Taipei (25.03N, 121.56E) for "
            "7 days. Day 1 anchored to 2026-04-19 observations; days 2-7 relax "
            "toward climatology with exponential persistence decay."
        ),
        constraints=[
            "1-layer shallow water (no baroclinic structure)",
            "128x96 TD grid, dt=45 s for unified_rollout",
            "30-day climatology ending 2026-04-19",
            "point diagnostic at Taipei grid center",
        ],
        resources={
            "budget": 0.85,
            "infrastructure": 0.90,
            "data_coverage": 0.72,
            "population_coupling": 0.55,
        },
        environment={
            "field_noise": 0.30,
            "phase_instability": phase_instab,
            "social_pressure": 0.20,
            "regulatory_friction": 0.20,
            "network_density": 0.40,
        },
        subject={
            "output_power": out_pow,
            "control_precision": 0.62,
            "load_tolerance": 0.85,
            "aim_coupling": 0.58,
            "stress_level": stress,
            "phase_proximity": 0.50,
            "marginal_decay": 0.22,
            "instability_sensitivity": 0.48,
        },
    )


def _state_to_fields(state) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    return (
        state.h.astype(np.float32),
        state.T.astype(np.float32),
        state.q.astype(np.float32),
        state.u.astype(np.float32),
        state.v.astype(np.float32),
    )


def _blend_fields(a: tuple[np.ndarray, ...], b: tuple[np.ndarray, ...], w: float) -> tuple[np.ndarray, ...]:
    return tuple((w * ax + (1.0 - w) * bx).astype(np.float32) for ax, bx in zip(a, b))


def _select_device() -> str:
    if _TORCH_OK and torch is not None and torch.cuda.is_available():
        return "cuda"
    return "cpu"


def main() -> int:
    device = _select_device()
    obs_days = json.loads(OBS_PATH.read_text(encoding="utf-8"))["days"]

    climo_T = float(np.mean([d["T_mean_C"] for d in obs_days]))
    climo_RH = float(np.mean([d["RH_mean_pct"] for d in obs_days]))
    climo_P = float(np.mean([d["P_mean_hPa"] for d in obs_days]))
    climo_ws = float(np.mean([d["ws_mean_ms"] for d in obs_days]))
    u_sum = sum(d["ws_mean_ms"] * math.sin(math.radians(d["wd_vec_deg"])) for d in obs_days)
    v_sum = sum(d["ws_mean_ms"] * math.cos(math.radians(d["wd_vec_deg"])) for d in obs_days)
    climo_wd = (math.degrees(math.atan2(u_sum, v_sum)) + 360.0) % 360.0
    climo_ref = ReferenceObs(
        T_avg_C=climo_T,
        RH_pct=climo_RH,
        P_hPa=climo_P,
        ws_ms=climo_ws,
        wd_deg=climo_wd,
    )

    today_obs = ReferenceObs(T_avg_C=23.8, RH_pct=75.0, P_hPa=1012.3, ws_ms=1.69, wd_deg=44.0)

    print("=" * 68)
    print("TD CandidatePipeline - weather worldline selection")
    print("=" * 68)
    weather_seed = _build_weather_seed(today_obs, climo_ref, obs_days, TODAY)
    print(f"  device:            {device}")
    print(f"  phase_instability: {weather_seed.environment['phase_instability']:.3f}")
    print(f"  stress_level:      {weather_seed.subject['stress_level']:.3f}")
    print(f"  output_power:      {weather_seed.subject['output_power']:.3f}")

    t0 = time.time()
    pipeline = CandidatePipeline(
        seed=weather_seed,
        top_k=12,
        NX=TD_NX,
        NY=TD_NY,
        steps=300,
        dt=TD_DT,
        device=device,
    )
    td_top_results, td_hydro, td_oracle = pipeline.run()
    print(f"  CandidatePipeline.run(): {time.time() - t0:.1f}s")
    print(f"  alive={td_hydro.get('alive_count')} pruned={td_hydro.get('pruned_count')}")
    print(f"  Top-{min(5, len(td_top_results))} worldlines:")
    for idx, result in enumerate(td_top_results[:5], start=1):
        params = result.params
        print(
            f"    #{idx} {result.family:<13} "
            f"n={int(params.get('n', 0)):>5} rho={params.get('rho', 0):.2f} "
            f"A={params.get('A', 0):.2f} sigma={params.get('sigma', 0):.3f} | "
            f"score={result.balanced_score:+.3f} feas={result.feasibility:.2f} "
            f"status={result.branch_status}"
        )

    bg = td_infer_bg(weather_seed)
    all_candidates = td_generate_candidates(weather_seed, bg)
    candidate_lookup = {_candidate_key(c["params"], c["family"]): c for c in all_candidates}
    top_keys = [_candidate_key(r.params, r.family) for r in td_top_results]
    missing = [k for k in top_keys if k not in candidate_lookup]
    if missing:
        raise KeyError(f"Missing full candidate specs for {len(missing)} TD top results")
    candidates = [candidate_lookup[k] for k in top_keys]
    carr = td_prepare_candidate_arrays(candidates)

    today_init_state = build_taipei_state(TD_XX, TD_YY, TD_TOPO, TD_CFG, perturbation=-1.0, obs_ref=today_obs)
    today_obs_state = build_taipei_state(TD_XX, TD_YY, TD_TOPO, TD_CFG, perturbation=0.0, obs_ref=today_obs)
    climo_obs_state = build_taipei_state(TD_XX, TD_YY, TD_TOPO, TD_CFG, perturbation=0.0, obs_ref=climo_ref)
    today_fields = _state_to_fields(today_obs_state)
    climo_fields = _state_to_fields(climo_obs_state)
    init_fields = _state_to_fields(today_init_state)
    pressure_anchor_h_mid_m = float(climo_obs_state.h[TD_CY, TD_CX])
    pressure_anchor_surface_hpa = float(climo_ref.P_hPa)

    td_state = td_encode_initial_state(weather_seed, candidates, TD_NX, TD_NY)
    td_state.topography = TD_TOPO
    td_state.obs_h, td_state.obs_T, td_state.obs_q, td_state.obs_u, td_state.obs_v = today_fields
    td_state.h = np.repeat(init_fields[0][None], len(candidates), axis=0).astype(np.float32)
    td_state.T = np.repeat(init_fields[1][None], len(candidates), axis=0).astype(np.float32)
    td_state.q = np.repeat(init_fields[2][None], len(candidates), axis=0).astype(np.float32)
    td_state.u = np.repeat(init_fields[3][None], len(candidates), axis=0).astype(np.float32)
    td_state.v = np.repeat(init_fields[4][None], len(candidates), axis=0).astype(np.float32)
    use_torch_rollout = device.startswith("cuda")
    if use_torch_rollout:
        carr_dev = _carr_to_torch(carr, device)
        td_state_dev = _state_to_torch(td_state, device)
    else:
        carr_dev = None
        td_state_dev = None

    print("\n" + "=" * 68)
    print("TD unified_rollout - 7 day forecast")
    print("=" * 68)
    print(f"  grid={TD_NX}x{TD_NY} dt={TD_DT}s substeps/day={TD_STEPS_PER_DAY} rollout_device={device}")

    t0 = time.time()
    total_steps = 7 * TD_STEPS_PER_DAY
    step_offset = 0
    daily: list[dict] = []
    day1_alignment_state = None

    def _read_centers_numpy(state):
        return np.stack(
            [
                state.T[:, TD_CY, TD_CX],
                state.h[:, TD_CY, TD_CX],
                state.q[:, TD_CY, TD_CX],
                state.u[:, TD_CY, TD_CX],
                state.v[:, TD_CY, TD_CX],
            ],
            axis=1,
        ).astype(np.float64)

    def _read_centers_torch(state):
        return torch.stack(
            [
                state.T[:, TD_CY, TD_CX],
                state.h[:, TD_CY, TD_CX],
                state.q[:, TD_CY, TD_CX],
                state.u[:, TD_CY, TD_CX],
                state.v[:, TD_CY, TD_CX],
            ],
            dim=1,
        ).detach().cpu().numpy().astype(np.float64)

    for day_idx in range(7):
        decay = math.exp(-day_idx / TAU_PERSIST_DAYS)
        blended_fields = _blend_fields(today_fields, climo_fields, decay)
        if use_torch_rollout:
            obs_tensors = tuple(torch.as_tensor(arr, dtype=torch.float32, device=device) for arr in blended_fields)
            td_state_dev.obs_h, td_state_dev.obs_T, td_state_dev.obs_q, td_state_dev.obs_u, td_state_dev.obs_v = obs_tensors
        else:
            td_state.obs_h, td_state.obs_T, td_state.obs_q, td_state.obs_u, td_state.obs_v = blended_fields

        # Chunked rollout: 8 chunks × 240 substeps. Sample centers at end of
        # each chunk so we can build proper daily-mean diagnostics instead of
        # only day-end snapshots.
        day_samples: list[np.ndarray] = []
        for _ in range(TD_SAMPLES_PER_DAY):
            if use_torch_rollout:
                td_state_dev, _ = _torch_rollout(
                    td_state_dev, carr_dev,
                    dt=TD_DT, dx=TD_DX, dy=TD_DY,
                    steps=TD_SAMPLE_STRIDE,
                    step_offset=step_offset, total_steps=total_steps,
                )
                day_samples.append(_read_centers_torch(td_state_dev))
            else:
                td_state, _ = td_unified_rollout(
                    td_state, carr,
                    dt=TD_DT, dx=TD_DX, dy=TD_DY,
                    steps=TD_SAMPLE_STRIDE,
                    step_offset=step_offset, total_steps=total_steps,
                )
                day_samples.append(_read_centers_numpy(td_state))
            step_offset += TD_SAMPLE_STRIDE

        # Day-end full state (last chunk result) — for phase / TD-native evidence
        # / field-fit and the attach_weather_alignment anchor.
        alignment_state = td_state_dev if use_torch_rollout else td_state
        if use_torch_rollout:
            phase_values = td_state_dev.phase.detach().cpu().numpy().astype(np.float64)
            h_field = td_state_dev.h.detach().cpu().numpy().astype(np.float64)
            T_field = td_state_dev.T.detach().cpu().numpy().astype(np.float64)
            q_field = td_state_dev.q.detach().cpu().numpy().astype(np.float64)
            u_field = td_state_dev.u.detach().cpu().numpy().astype(np.float64)
            v_field = td_state_dev.v.detach().cpu().numpy().astype(np.float64)
        else:
            phase_values = np.asarray(td_state.phase, dtype=np.float64)
            h_field = td_state.h.astype(np.float64)
            T_field = td_state.T.astype(np.float64)
            q_field = td_state.q.astype(np.float64)
            u_field = td_state.u.astype(np.float64)
            v_field = td_state.v.astype(np.float64)

        td_native_scores = forecast_evidence(alignment_state)
        if day_idx == 0:
            day1_alignment_state = _state_to_numpy(alignment_state)

        # Per-sample per-candidate surface diagnostics.
        # Shape: (TD_SAMPLES_PER_DAY, n_candidates, surface_dict_fields).
        # Each sample corresponds to a local solar hour (3h stride, midpoints
        # at 1.5, 4.5, 7.5, 10.5, 13.5, 16.5, 19.5, 22.5). The TD rollout has
        # no diurnal forcing, so T2m from the mid-level→surface conversion is
        # nearly constant across the day. We add a surface-diagnostic-only
        # diurnal modulation to T2m (amplitude scaled by RH / wind), leaving
        # TD internal state untouched.
        per_sample_per_cand = []
        for sample_idx, sample_centers in enumerate(day_samples):
            hour_local = sample_idx * 3.0 + 1.5
            per_cand = _candidate_surface_diagnostics(
                sample_centers,
                TAIPEI_STATION_ELEV_M,
                pressure_anchor_h_mid_m,
                pressure_anchor_surface_hpa,
            )
            per_cand = [_apply_diurnal_t2m(s, hour_local) for s in per_cand]
            per_sample_per_cand.append(per_cand)

        # Day-end snapshot summary (kept as _end auxiliary columns). The last
        # sample is at hour 22.5 — apply diurnal so T2m_end is self-consistent
        # with the time-series samples used for T2m_mean/min/max.
        end_centers = day_samples[-1]
        end_summary_base = _physical_summary_from_centers(
            end_centers,
            TAIPEI_STATION_ELEV_M,
            pressure_anchor_h_mid_m,
            pressure_anchor_surface_hpa,
        )
        end_summary = _apply_diurnal_t2m(end_summary_base, TD_SAMPLES_PER_DAY * 3.0 - 1.5)

        n_cand = len(candidates)
        # Per-candidate time-series (shape: n_cand × TD_SAMPLES_PER_DAY).
        T2m_series = np.array(
            [[per_sample_per_cand[s][c]["temperature_2m_C"] for s in range(TD_SAMPLES_PER_DAY)] for c in range(n_cand)]
        )
        RH_series = np.array(
            [[per_sample_per_cand[s][c]["relative_humidity_pct"] for s in range(TD_SAMPLES_PER_DAY)] for c in range(n_cand)]
        )
        P_series = np.array(
            [[per_sample_per_cand[s][c]["surface_pressure_hpa"] for s in range(TD_SAMPLES_PER_DAY)] for c in range(n_cand)]
        )
        ws_series = np.array(
            [[per_sample_per_cand[s][c]["wind_speed_10m_ms"] for s in range(TD_SAMPLES_PER_DAY)] for c in range(n_cand)]
        )
        wd_u_series = np.array(
            [[-math.sin(math.radians(per_sample_per_cand[s][c]["wind_direction_deg"])) * per_sample_per_cand[s][c]["wind_speed_10m_ms"]
              for s in range(TD_SAMPLES_PER_DAY)] for c in range(n_cand)]
        )
        wd_v_series = np.array(
            [[-math.cos(math.radians(per_sample_per_cand[s][c]["wind_direction_deg"])) * per_sample_per_cand[s][c]["wind_speed_10m_ms"]
              for s in range(TD_SAMPLES_PER_DAY)] for c in range(n_cand)]
        )

        # Time-aggregate per candidate, then candidate-median for daily report.
        T2m_cand_mean = T2m_series.mean(axis=1)
        T2m_cand_min  = T2m_series.min(axis=1)
        T2m_cand_max  = T2m_series.max(axis=1)
        RH_cand_mean  = RH_series.mean(axis=1)
        P_cand_mean   = P_series.mean(axis=1)
        ws_cand_mean  = ws_series.mean(axis=1)
        # Daily-mean wind direction via vector-averaging per candidate
        u_cand_mean = wd_u_series.mean(axis=1)
        v_cand_mean = wd_v_series.mean(axis=1)

        summary: dict = {}
        # Main daily (time-averaged) fields — candidate median
        summary["T2m_mean"]       = float(np.median(T2m_cand_mean))
        summary["T2m_min"]        = float(np.median(T2m_cand_min))
        summary["T2m_max"]        = float(np.median(T2m_cand_max))
        summary["RH_mean"]        = float(np.median(RH_cand_mean))
        summary["P_mean"]         = float(np.median(P_cand_mean))
        summary["wind10_mean"]    = float(np.median(ws_cand_mean))
        _u_med = float(np.median(u_cand_mean))
        _v_med = float(np.median(v_cand_mean))
        summary["wind10_dir_mean"] = (math.degrees(math.atan2(-_u_med, -_v_med)) + 360.0) % 360.0
        # Ensemble spread on the time-mean (across candidates)
        summary["T2m_mean_cand_std"] = float(np.std(T2m_cand_mean))
        summary["P_mean_cand_std"]   = float(np.std(P_cand_mean))

        # Day-end auxiliary snapshots
        summary["T2m_end"]         = end_summary["temperature_2m_C"]
        summary["RH_end"]          = end_summary["relative_humidity_pct"]
        summary["P_end"]           = end_summary["surface_pressure_hpa"]
        summary["wind10_end"]      = end_summary["wind_speed_10m_ms"]
        summary["wind10_dir_end"]  = end_summary["wind_direction_deg"]

        # Phase / TD evidence — kept as day-end snapshot (not time-averaged)
        summary["phase_mean"]  = float(np.mean(phase_values))
        summary["phase_std"]   = float(np.std(phase_values))
        summary["td_fit_mean"] = float(np.mean(td_native_scores))
        summary["td_fit_std"]  = float(np.std(td_native_scores))

        # Weather-alignment scores vs obs (for surface_score calculation, use
        # the candidate's daily-MEAN surface — fair comparison to obs daily-mean)
        score_target = today_obs if day_idx == 0 else climo_ref
        candidate_mean_surfaces = [
            {
                "temperature_2m_C":      float(T2m_cand_mean[c]),
                "relative_humidity_pct": float(RH_cand_mean[c]),
                "surface_pressure_hpa":  float(P_cand_mean[c]),
                "wind_speed_10m_ms":     float(ws_cand_mean[c]),
                "wind_direction_deg":    (math.degrees(math.atan2(-float(u_cand_mean[c]), -float(v_cand_mean[c]))) + 360.0) % 360.0,
            }
            for c in range(n_cand)
        ]
        weather_scores = np.asarray(
            [_surface_score(surface, score_target) for surface in candidate_mean_surfaces],
            dtype=np.float64,
        )
        field_scores = _field_fit_scores(h_field, T_field, q_field, u_field, v_field, blended_fields)
        summary["weather_fit_mean"] = float(np.mean(weather_scores))
        summary["weather_fit_std"]  = float(np.std(weather_scores))
        summary["field_fit_mean"]   = float(np.mean(field_scores))
        summary["field_fit_std"]    = float(np.std(field_scores))

        daily.append(
            {
                "date": (TODAY + timedelta(days=day_idx + 1)).isoformat(),
                "mode": "DA" if day_idx == 0 else "relax",
                "decay": decay,
                "summary": summary,
                "scores": phase_values.copy(),
                "td_native_scores": td_native_scores.copy(),
                "weather_scores": weather_scores,
                "field_scores": field_scores,
            }
        )
        print(
            f"  day {day_idx+1}: phase={summary['phase_mean']:.3f}+-{summary['phase_std']:.3f} "
            f"fit={summary['td_fit_mean']:.3f}+-{summary['td_fit_std']:.3f} "
            f"T2m_mean={summary['T2m_mean']:.1f}C (min={summary['T2m_min']:.1f} max={summary['T2m_max']:.1f}) "
            f"T2m_end={summary['T2m_end']:.1f}C "
            f"wind10_mean={summary['wind10_mean']:.1f}m/s"
        )
    print(f"  week done in {time.time() - t0:.1f}s")
    if use_torch_rollout:
        td_state = _state_to_numpy(td_state_dev)

    print("\n" + "=" * 68)
    print("Physical Forecast — daily stats (8 samples/day, 3h stride)")
    print("=" * 68)
    print(f"{'Date':<12} {'Mode':<5} {'decay':>5} "
          f"{'T2m_mean':>9} {'T2m_min':>8} {'T2m_max':>8} "
          f"{'RH':>6} {'P':>8} {'Wind10':>14} {'phase':>11} {'fit':>7}")
    for day in daily:
        s = day["summary"]
        print(
            f"{day['date']:<12} {day['mode']:<5} {day['decay']:>5.2f} "
            f"{s['T2m_mean']:>7.1f}C "
            f"{s['T2m_min']:>6.1f}C "
            f"{s['T2m_max']:>6.1f}C "
            f"{s['RH_mean']:>4.1f}% "
            f"{s['P_mean']:>6.1f}hPa "
            f"{s['wind10_mean']:>4.1f}m/s@{s['wind10_dir_mean']:>3.0f} "
            f"{s['phase_mean']:>5.2f}+-{s['phase_std']:<4.2f} "
            f"{s['td_fit_mean']:>6.3f}"
        )
    print("\nAuxiliary — day-end snapshots:")
    print(f"{'Date':<12} {'T2m_end':>8} {'RH_end':>7} {'P_end':>9} {'Wind10_end':>18}")
    for day in daily:
        s = day["summary"]
        print(
            f"{day['date']:<12} "
            f"{s['T2m_end']:>6.1f}C "
            f"{s['RH_end']:>5.1f}% "
            f"{s['P_end']:>7.1f}hPa "
            f"{s['wind10_end']:>4.1f}m/s@{s['wind10_dir_end']:>3.0f}"
        )

    if day1_alignment_state is None:
        raise RuntimeError("missing day-1 rollout state for TD weather alignment")
    attach_weather_alignment(td_top_results, day1_alignment_state)
    reranked = sorted(
        td_top_results,
        key=lambda result: result.final_balanced_score or result.balanced_score,
        reverse=True,
    )

    print("\n" + "=" * 68)
    print("TD System Self-Eval")
    print("=" * 68)
    print(f"  hydro_state={td_hydro.get('utm_hydro_state')} pressure_balance={td_hydro.get('pressure_balance'):.3f}")
    print(f"  background_emerged={td_oracle.get('background_naturally_emerged')}")
    print(f"  inferred_goal={td_oracle.get('inferred_goal_axis')}")
    print(f"  dominant_pressures={', '.join(td_oracle.get('dominant_pressures', [])[:3])}")
    print(f"  {'rank':<5} {'family':<13} {'n':>5} {'bal':>7} {'weather':>8} {'align':>7} {'final':>8}")
    for idx, result in enumerate(reranked[:8], start=1):
        print(
            f"  #{idx:<4} {result.family:<13} {int(result.params['n']):>5} "
            f"{result.balanced_score:>+7.3f} "
            f"{result.weather_score:>8.4f} "
            f"{result.weather_alignment:>+7.3f} "
            f"{result.final_balanced_score:>+8.3f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
