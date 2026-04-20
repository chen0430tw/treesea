"""weather_bridge.py — UMDST worldline ↔ atmospheric physics bridge.

Translates a CandidateWorldline's abstract parameters (rho, A, sigma, n, family)
into shallow-water branch physics parameters, runs the 2D mesoscale solver,
and returns a score in [0, 1] that downstream TD consumers (run_tree_diagram,
CandidatePipeline) can normalize into a weather_alignment offset on
EvaluationResult.

Per white-paper §4.4: UMDST does NOT re-derive molecular dynamics in software;
it black-boxes complex kinetics and exposes a unified evaluation API. This
module is the thin layer that feeds a single evaluation into that API.

Mapping (ranges grounded in operational NWP / FDDA literature):
    rho   (field coupling, 0.2–1.0) → nudging    (1.0e-4 – 2.0e-4 /s)
    A     (amplitude,      0.3–0.9) → pg_scale   (0.90 – 1.25, dimensionless)
    sigma (spread/noise,   0.1–0.7) → drag       (0.5e-5 – 2.5e-5 /s Ekman)
    n / N_OPT                       → humid_couple via log-Gaussian envelope
    family                          → base diffusion (Kh, Kt, Kq) + wind rotation

Two execution modes:
    run_worldline_weather(w, ...)       serial, one candidate, numpy
    run_worldlines_batched(ws, ...)     all candidates batched, cupy if available

Two-pass normalization (weather_scores_to_alignments) converts raw scores to
worldline-alignment values in [-0.15, +0.10], which attach_weather_alignment
(worldline_kernel.py) folds back into EvaluationResult.final_balanced_score.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from .forcing import GridConfig, build_grid, build_topography
from .weather_state import WeatherState, build_initial_state, build_obs
from .dynamics import branch_step
from .ranking import score_state
from ..core.worldline_kernel import CandidateWorldline


# =====================================================================
# Atmospheric / physical constants (SI units, ISA 1976 where applicable)
# =====================================================================

# Ideal-gas constants
R_DRY_AIR: float   = 287.04   # J/(kg·K) specific gas constant, dry air
R_WATER_VAPOR: float = 461.5  # J/(kg·K) specific gas constant, water vapor
CP_AIR: float      = 1004.0   # J/(kg·K) specific heat at constant pressure
CV_AIR: float      = 717.0    # J/(kg·K) specific heat at constant volume
KAPPA: float       = R_DRY_AIR / CP_AIR   # ≈ 0.2859

# Latent heats (J/kg)
LV_VAPORIZATION: float = 2.501e6   # at 0°C
LS_SUBLIMATION:  float = 2.834e6   # at 0°C
LF_FUSION:       float = 3.337e5   # at 0°C

# Earth
GRAVITY_STD: float = 9.80665        # m/s² standard gravity
OMEGA_EARTH: float = 7.2921159e-5   # rad/s sidereal rotation rate
RADIUS_EARTH: float = 6.371e6       # m mean radius

# ISA sea-level reference
P0_SEA_LEVEL:   float = 101325.0    # Pa
T0_SEA_LEVEL:   float = 288.15      # K
RHO0_SEA_LEVEL: float = 1.225       # kg/m³
LAPSE_STD: float      = 6.5e-3      # K/m ISA tropospheric

# Mid-latitude 500 hPa climatology (used as domain anchor for the solver)
H_BASELINE_500HPA: float = 5700.0   # m geopotential height at 500 hPa (std atm)
T_MID_CLIMO_K:     float = 268.0    # K approx -5°C at 500 hPa
P_MID_HPA:         float = 500.0    # hPa

# Subtropical Taipei-class point values (25° N reference)
TAIPEI_LAT_DEG:       float = 25.03
TAIPEI_F_CORIOLIS:    float = 2.0 * OMEGA_EARTH * math.sin(math.radians(TAIPEI_LAT_DEG))
TAIPEI_ROSSBY_DEF_M:  float = math.sqrt(GRAVITY_STD * H_BASELINE_500HPA) / TAIPEI_F_CORIOLIS
# ≈ 3.7e6 m; gravity-wave Rossby radius of deformation for this climo

# Physical bounds (sanity guards; historical atmospheric extremes)
WIND_MAX_MS:   float = 80.0    # ~jet stream peak; surface cap usually 35
T_MIN_K:       float = 180.0
T_MAX_K:       float = 330.0
Q_MIN_KGKG:    float = 1e-5
Q_MAX_KGKG:    float = 0.030
P_MIN_HPA:     float = 870.0   # Typhoon Tip 1979, tropical-cyclone low
P_MAX_HPA:     float = 1085.0  # Siberian anticyclone, surface high

# UMDST n-optimality (matches worldline_kernel._N_OPT / _N_SIGMA)
N_OPT_DEFAULT:   float = 20000.0
N_SIGMA_DEFAULT: float = 5000.0


# =====================================================================
# Parameter bound dataclasses (named constants, not magic numbers)
# =====================================================================

@dataclass(frozen=True)
class _Bounds:
    low: float
    high: float
    def clip(self, x: float) -> float:
        return max(self.low, min(self.high, x))


# FDDA (four-dimensional data assimilation) nudging rate bounds.
# WRF default "strong" nudging: ~6e-4 /s (τ ≈ 28 min). Mesoscale
# reanalysis typical: 1e-4 – 2e-4 /s (τ = 1.4 – 2.8 h). We stay
# in the reanalysis band so physics still dominates.
NUDGING_BOUNDS = _Bounds(low=1.0e-4, high=2.0e-4)

# Pressure-gradient force multiplier (dimensionless).
# 1.0 = WMO-standard PGF; low/high clip tunes relative magnitude.
PG_SCALE_BOUNDS = _Bounds(low=0.90, high=1.25)

# Ekman boundary-layer friction rate (1/s). τ_Ekman for atmosphere
# surface layer: 12–24 h = 1.16e-5 – 2.31e-5 /s. We allow a bit
# more range to let UMDST sigma drive stronger dissipation regimes.
DRAG_BOUNDS = _Bounds(low=0.5e-5, high=2.5e-5)

# Humid-coupling factor (dimensionless multiplier on saturation q).
HUMID_COUPLE_BOUNDS = _Bounds(low=0.75, high=1.25)


# =====================================================================
# Family-specific base physics coefficients
# =====================================================================
# Each UMDST family maps to a distinct atmospheric mixing regime.
# Kh, Kt, Kq (m²/s scale — dimensioned via cfg inside solver).

_FAMILY_KhKtKq: Dict[str, Tuple[float, float, float]] = {
    "batch":      (360.0, 180.0, 130.0),   # balanced mixing (phase-like)
    "network":    (520.0, 260.0, 180.0),   # high-mix, dense connectivity
    "phase":      (240.0, 120.0,  95.0),   # weak-mix, laminar
    "electrical": (300.0, 150.0, 125.0),   # strong PG regime
    "ascetic":    (220.0, 110.0,  90.0),   # minimal mixing
    "hybrid":     (340.0, 175.0, 220.0),   # moisture-biased (higher Kq)
    "composite":  (330.0, 170.0, 135.0),   # terrain-aware
}
_FAMILY_KhKtKq_DEFAULT = _FAMILY_KhKtKq["batch"]

# Per-family wind-rotation offset (deg). Breaks directional symmetry
# across candidates so the ranker can discriminate.
_FAMILY_WIND_ROT: Dict[str, float] = {
    "batch":         0.0,
    "network":      +20.0,
    "phase":        -30.0,
    "electrical":   +10.0,
    "ascetic":      -15.0,
    "hybrid":       -10.0,
    "composite":    +30.0,
}


# =====================================================================
# Core translation: worldline parameters → branch physics parameters
# =====================================================================

def worldline_to_branch_params(
    w: CandidateWorldline,
    seed,  # ProblemSeed — unused but retained for future seed-aware tuning
    n_opt: float = N_OPT_DEFAULT,
    n_sigma: float = N_SIGMA_DEFAULT,
) -> dict:
    """Map a worldline's (rho, A, sigma, n, family) to branch_step params."""
    rho   = float(w.params.get("rho",   0.5))
    A     = float(w.params.get("A",     0.5))
    sigma = float(w.params.get("sigma", 0.3))
    n     = float(w.params.get("n",     1.0))

    # rho → nudging (linear: 0.2 → low, 1.0 → high)
    nudging = NUDGING_BOUNDS.clip(
        NUDGING_BOUNDS.low + (rho - 0.2) / 0.8 * (NUDGING_BOUNDS.high - NUDGING_BOUNDS.low)
    )

    # A → pg_scale (linear: 0.3 → low, 0.9 → high)
    pg_scale = PG_SCALE_BOUNDS.clip(
        PG_SCALE_BOUNDS.low + (A - 0.3) / 0.6 * (PG_SCALE_BOUNDS.high - PG_SCALE_BOUNDS.low)
    )

    # sigma → drag (linear: 0.1 → low, 0.7 → high)
    drag = DRAG_BOUNDS.clip(
        DRAG_BOUNDS.low + (sigma - 0.1) / 0.6 * (DRAG_BOUNDS.high - DRAG_BOUNDS.low)
    )

    # n → humid_couple via log-Gaussian centred on n_opt (worldline_kernel
    # _umdst_batched_step uses the same Gaussian in linear-n space; we use
    # log-space here to stay well-behaved across n ranges 1e3–3e4).
    if n_opt > 0.0 and n > 0.0:
        log_ratio = math.log(n / n_opt)
        gauss = math.exp(-0.5 * (log_ratio / 0.8) ** 2)
    else:
        gauss = 0.5
    humid_couple = HUMID_COUPLE_BOUNDS.clip(0.80 + gauss * 0.30)

    Kh, Kt, Kq = _FAMILY_KhKtKq.get(w.family, _FAMILY_KhKtKq_DEFAULT)
    wind_rot   = _FAMILY_WIND_ROT.get(w.family, 0.0)

    return {
        "name":         w.template,
        "Kh":           Kh,
        "Kt":           Kt,
        "Kq":           Kq,
        "drag":         drag,
        "humid_couple": humid_couple,
        "nudging":      nudging,
        "pg_scale":     pg_scale,
        "wind_rot_deg": wind_rot,
        # Wind nudging runs at the same strength as T/q nudging (FDDA parity).
        "wind_nudge":   nudging,
    }


# =====================================================================
# Grid cache (keyed by (NX, NY, DX, DY) — previous version silently
# returned stale data when called with different cfg on the same process)
# =====================================================================

_GridKey = Tuple[int, int, float, float]
_GRID_CACHE: Dict[_GridKey, Tuple[np.ndarray, np.ndarray, np.ndarray,
                                   WeatherState, WeatherState]] = {}


def _grid_key(cfg: GridConfig) -> _GridKey:
    return (int(cfg.NX), int(cfg.NY), float(cfg.DX), float(cfg.DY))


def _get_grid(cfg: GridConfig):
    """Return (XX, YY, topography, initial_state, obs) for this cfg.

    Cached per (NX, NY, DX, DY). Different dt or STEPS reuse the same
    grid — only spatial layout needs rebuilding.
    """
    key = _grid_key(cfg)
    if key not in _GRID_CACHE:
        XX, YY, _, _ = build_grid(cfg)
        topo = build_topography(XX, YY)
        init = build_initial_state(XX, YY, topo, cfg)
        obs  = build_obs(XX, YY, topo, cfg)
        _GRID_CACHE[key] = (XX, YY, topo, init, obs)
    return _GRID_CACHE[key]


def clear_grid_cache() -> None:
    """Explicit cache flush — useful when topography or climatology changes."""
    _GRID_CACHE.clear()


# =====================================================================
# Serial execution: one worldline, numpy only
# =====================================================================

def run_worldline_weather(
    w: CandidateWorldline,
    seed,
    n_opt: float = N_OPT_DEFAULT,
    cfg: Optional[GridConfig] = None,
) -> float:
    """Run a reduced-step shallow-water simulation for one worldline.

    Returns a raw weather score in [0, 1] (higher = better obs match).
    Caller passes a reduced-step cfg (typical: STEPS=60 for screening,
    STEPS=240 for refinement).
    """
    if cfg is None:
        raise ValueError("cfg required (GridConfig with STEPS set)")

    branch_params = worldline_to_branch_params(w, seed, n_opt)
    _, _, topo, init, obs = _get_grid(cfg)

    # Apply per-family wind rotation at init
    from .ensemble import _rotate_wind_inplace
    state = _rotate_wind_inplace(
        WeatherState(h=init.h.copy(), u=init.u.copy(), v=init.v.copy(),
                     T=init.T.copy(), q=init.q.copy()),
        branch_params["wind_rot_deg"],
    )

    budget = None
    for _ in range(cfg.STEPS):
        state, budget = branch_step(state, branch_params, obs, topo, cfg, budget)

    metric = score_state(state, obs, cfg)
    return float(metric["score"])


# =====================================================================
# Batched execution: all worldlines in parallel (GPU if available)
# =====================================================================

def run_worldlines_batched(
    worldlines: List[CandidateWorldline],
    seed,
    n_opt: float = N_OPT_DEFAULT,
    cfg: Optional[GridConfig] = None,
    use_gpu: Optional[bool] = None,
) -> Tuple[List[float], List[WeatherState]]:
    """Batched physics rollout for all worldlines simultaneously.

    Uses dynamics_batched.batched_branch_step — builds a (B, NY, NX) state
    tensor, one substep advances all B candidates at once. On CuPy-capable
    hardware this is ~10× faster than looping run_worldline_weather.

    Parameters
    ----------
    use_gpu : None auto-detects CuPy. True forces GPU (raises if unavailable).
              False forces CPU.

    Returns
    -------
    scores : list[float] in [0, 1], one per worldline, same order as input
    final_states : list[WeatherState], the per-candidate final state
    """
    if cfg is None:
        raise ValueError("cfg required (GridConfig with STEPS set)")
    if not worldlines:
        return [], []

    from ._xp import has_cupy
    from .dynamics_batched import batched_branch_step, stack_families, unstack_families
    from .ensemble import _rotate_wind_inplace

    if use_gpu is None:
        use_gpu = has_cupy()
    elif use_gpu and not has_cupy():
        raise RuntimeError("use_gpu=True but CuPy not importable")

    _, _, topo, init_cpu, obs_cpu = _get_grid(cfg)

    # Move reference grids to the chosen device
    if use_gpu:
        import cupy as cp
        topo_dev = cp.asarray(topo)
        obs_dev  = obs_cpu.to_gpu()
        init_dev = init_cpu.to_gpu()
    else:
        topo_dev = topo
        obs_dev  = obs_cpu
        init_dev = init_cpu

    # Per-worldline branch params
    branch_params_list = [worldline_to_branch_params(w, seed, n_opt) for w in worldlines]

    # Rotate init wind per family, stack into (B, NY, NX)
    rotated = [
        _rotate_wind_inplace(
            WeatherState(h=init_dev.h.copy(), u=init_dev.u.copy(), v=init_dev.v.copy(),
                         T=init_dev.T.copy(), q=init_dev.q.copy()),
            bp["wind_rot_deg"],
        )
        for bp in branch_params_list
    ]
    state_b = stack_families(rotated)

    # Pack per-family param lists for batched_branch_step
    param_keys = ("drag", "humid_couple", "nudging", "pg_scale", "wind_nudge")
    params_b = {k: [float(bp[k]) for bp in branch_params_list] for k in param_keys}

    budget = None
    for _ in range(cfg.STEPS):
        state_b, budget = batched_branch_step(state_b, params_b, obs_dev, topo_dev, cfg, budget)

    final_states = unstack_families(state_b)
    scores = [float(score_state(s, obs_dev, cfg)["score"]) for s in final_states]
    return scores, final_states


# =====================================================================
# Raw score → worldline alignment (two-pass normalization)
# =====================================================================

def weather_scores_to_alignments(raw_scores: List[float]) -> List[float]:
    """Convert raw weather scores [0, 1] to worldline alignments [-0.15, +0.10].

    Strategy: linear stretch from (mean - 1.5·std, mean + 1.0·std) → (-0.15, +0.10).
    The asymmetric stretch penalizes worldlines worse than average harder than it
    rewards better-than-average — matches TD's conservative bias toward feasibility.

    Edge cases:
      - empty input              → empty output
      - all-identical scores     → all-zero alignments
    """
    if not raw_scores:
        return []

    arr = np.asarray(raw_scores, dtype=np.float64)
    mean = float(arr.mean())
    std  = float(arr.std()) if arr.size > 1 else 0.0

    if std < 1e-9:
        return [0.0] * len(raw_scores)

    lo = mean - 1.5 * std
    hi = mean + 1.0 * std
    span = hi - lo  # guaranteed > 0 because std > 1e-9

    alignments = []
    for s in raw_scores:
        t = (float(s) - lo) / span
        a = -0.15 + t * 0.25
        alignments.append(max(-0.15, min(0.10, a)))
    return alignments


__all__ = [
    # Physical constants
    "R_DRY_AIR", "R_WATER_VAPOR", "CP_AIR", "CV_AIR", "KAPPA",
    "LV_VAPORIZATION", "LS_SUBLIMATION", "LF_FUSION",
    "GRAVITY_STD", "OMEGA_EARTH", "RADIUS_EARTH",
    "P0_SEA_LEVEL", "T0_SEA_LEVEL", "RHO0_SEA_LEVEL", "LAPSE_STD",
    "H_BASELINE_500HPA", "T_MID_CLIMO_K", "P_MID_HPA",
    "TAIPEI_LAT_DEG", "TAIPEI_F_CORIOLIS", "TAIPEI_ROSSBY_DEF_M",
    "WIND_MAX_MS", "T_MIN_K", "T_MAX_K", "Q_MIN_KGKG", "Q_MAX_KGKG",
    "P_MIN_HPA", "P_MAX_HPA",
    "N_OPT_DEFAULT", "N_SIGMA_DEFAULT",
    # Bounds
    "NUDGING_BOUNDS", "PG_SCALE_BOUNDS", "DRAG_BOUNDS", "HUMID_COUPLE_BOUNDS",
    # API
    "worldline_to_branch_params",
    "run_worldline_weather",
    "run_worldlines_batched",
    "weather_scores_to_alignments",
    "clear_grid_cache",
]
