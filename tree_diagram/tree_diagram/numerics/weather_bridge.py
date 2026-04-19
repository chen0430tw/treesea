"""weather_bridge.py — Maps worldline candidates to weather branch parameters.

Every CandidateWorldline is translated into a set of physics parameters that
the 2D mesoscale solver (branch_step) can run.  This bridge is the connective
tissue between the abstract scoring layer (UMDST/VFT) and the numerical
simulation layer, making Tree Diagram a truly integrated dual-prototype system.

Mapping rationale
-----------------
rho   (field coupling, 0.2–1.0) → nudging strength (0.00012–0.00018)
      High rho = stronger push toward observed state
A     (amplitude,     0.3–0.9)  → pg_scale (0.95–1.20)
      High A = stronger pressure gradient forcing
sigma (noise/spread, 0.1–0.7)  → drag (0.8e-5–2.2e-5)
      High sigma = more dissipation
n/n_opt                         → humid_couple via Gaussian centred at n_opt
      At optimal n, condensation coupling is maximised (1.10)
family                          → base diffusion coefficients (Kh, Kt, Kq)
      Each family reflects a distinct atmospheric mixing regime
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from .forcing import GridConfig, build_grid, build_topography
from .weather_state import WeatherState, build_initial_state, build_obs
from .dynamics import branch_step
from .ranking import score_state
from ..core.worldline_kernel import CandidateWorldline, _batch_n_opt
from ..core.problem_seed import ProblemSeed


# ---------------------------------------------------------------------------
# Family → base diffusion coefficients
# ---------------------------------------------------------------------------

_FAMILY_KhKtKq: dict = {
    "batch":      (360, 180, 130),   # balanced mixing
    "network":    (520, 260, 180),   # high-mix (high connectivity)
    "phase":      (240, 120,  95),   # weak-mix (low turbulence)
    "electrical": (300, 150, 125),   # strong pressure gradient regime
    "ascetic":    (220, 110,  90),   # minimal mixing
    "hybrid":     (340, 175, 220),   # moisture-biased
    "composite":  (330, 170, 135),   # terrain-aware
}

# Per-family wind-rotation offset (deg). Breaks the directional symmetry
# that otherwise makes every candidate end up with the same center-cell
# wind direction, letting the ranking layer actually discriminate.
_FAMILY_WIND_ROT: dict = {
    "batch":        0.0,
    "network":    +20.0,
    "phase":      -30.0,
    "electrical": +10.0,
    "ascetic":    -15.0,
    "hybrid":     -10.0,
    "composite":  +30.0,
}


def worldline_to_branch_params(
    w: CandidateWorldline,
    seed: ProblemSeed,
    n_opt: float,
) -> dict:
    """Translate worldline parameters into weather branch physics parameters.

    Parameters
    ----------
    w       : the candidate worldline
    seed    : problem seed (used for context but not directly mapped)
    n_opt   : optimal n from resonance locking formula
    """
    rho = w.params.get("rho", 0.5)
    A = w.params.get("A", 0.5)
    sigma = w.params.get("sigma", 0.3)
    n = w.params.get("n", 1.0)

    # rho → nudging  (linear: 0.2→0.00012, 1.0→0.00018)
    nudging = 0.00012 + (rho - 0.2) / 0.8 * 0.00006
    nudging = max(0.00010, min(0.00020, nudging))

    # A → pg_scale  (linear: 0.3→0.95, 0.9→1.20)
    pg_scale = 0.95 + (A - 0.3) / 0.6 * 0.25
    pg_scale = max(0.90, min(1.25, pg_scale))

    # sigma → drag  (linear: 0.1→0.8e-5, 0.7→2.2e-5)
    drag = 0.8e-5 + (sigma - 0.1) / 0.6 * 1.4e-5
    drag = max(0.5e-5, min(2.5e-5, drag))

    # n / n_opt → humid_couple via Gaussian centered at n_opt
    # At n=n_opt: humid_couple = 1.10 (optimal condensation coupling)
    # Far from n_opt: approaches 0.80 (weaker coupling)
    if n_opt > 0:
        log_ratio = math.log(max(n, 1.0) / max(n_opt, 1.0))
        gauss = math.exp(-0.5 * (log_ratio / 0.8) ** 2)
    else:
        gauss = 0.5
    humid_couple = 0.80 + gauss * 0.30   # range [0.80, 1.10]
    humid_couple = max(0.75, min(1.25, humid_couple))

    # family → base diffusion coefficients
    Kh, Kt, Kq = _FAMILY_KhKtKq.get(w.family, _FAMILY_KhKtKq["batch"])
    wind_rot = _FAMILY_WIND_ROT.get(w.family, 0.0)

    return {
        "name": w.template,
        "Kh": Kh,
        "Kt": Kt,
        "Kq": Kq,
        "drag": drag,
        "humid_couple": humid_couple,
        "nudging": nudging,
        "pg_scale": pg_scale,
        "wind_rot_deg": wind_rot,
        "wind_nudge": nudging,   # same strength as T/q nudging (FDDA parity)
    }


# ---------------------------------------------------------------------------
# Shared grid/state cache (module-level, built once per process)
# ---------------------------------------------------------------------------

_GRID_CACHE: Optional[tuple] = None


def _get_grid(cfg: GridConfig) -> tuple:
    """Return (XX, YY, topography, initial_state, obs) — built once and cached."""
    global _GRID_CACHE
    if _GRID_CACHE is None:
        XX, YY, _, _ = build_grid(cfg)
        topography = build_topography(XX, YY)
        initial_state = build_initial_state(XX, YY, topography, cfg)
        obs = build_obs(XX, YY, topography, cfg)
        _GRID_CACHE = (topography, initial_state, obs)
    return _GRID_CACHE


# ---------------------------------------------------------------------------
# Run weather simulation for a single worldline
# ---------------------------------------------------------------------------

def run_worldline_weather(
    w: CandidateWorldline,
    seed: ProblemSeed,
    n_opt: float,
    cfg: GridConfig,
) -> float:
    """Run reduced-step weather simulation for worldline w.

    Returns a raw weather score in [0, 1].  Uses cfg.STEPS steps
    (caller should pass a reduced-step config, e.g. STEPS=60).
    """
    branch_params = worldline_to_branch_params(w, seed, n_opt)
    topography, initial_state, obs = _get_grid(cfg)

    state = WeatherState(
        h=initial_state.h.copy(),
        u=initial_state.u.copy(),
        v=initial_state.v.copy(),
        T=initial_state.T.copy(),
        q=initial_state.q.copy(),
    )
    budget = None
    for _ in range(cfg.STEPS):
        state, budget = branch_step(state, branch_params, obs, topography, cfg, budget)

    metric = score_state(state, obs, cfg)
    return float(metric["score"])


# ---------------------------------------------------------------------------
# Two-pass normalization: raw weather scores → weather_alignment
# ---------------------------------------------------------------------------

def weather_scores_to_alignments(raw_scores: list) -> list:
    """Convert a list of raw weather scores [0,1] to alignment values.

    Alignment is centred at 0, capped to [-0.15, +0.10]:
      - best worldline gets +0.10
      - worst worldline gets -0.15
      - average worldline gets ~0.0

    Uses a linear stretch from (mean - 1.5*std, mean + 1.0*std)
    to (-0.15, +0.10).
    """
    if not raw_scores:
        return []

    arr = np.array(raw_scores, dtype=float)
    mean = float(arr.mean())
    std = float(arr.std()) if len(arr) > 1 else 0.0

    # Avoid division by zero when all scores are identical
    if std < 1e-9:
        return [0.0] * len(raw_scores)

    lo = mean - 1.5 * std
    hi = mean + 1.0 * std
    span = hi - lo

    alignments = []
    for s in raw_scores:
        if span < 1e-9:
            a = 0.0
        else:
            t = (s - lo) / span          # 0..1
            a = -0.15 + t * 0.25         # -0.15..+0.10
        a = max(-0.15, min(0.10, a))
        alignments.append(float(a))

    return alignments
