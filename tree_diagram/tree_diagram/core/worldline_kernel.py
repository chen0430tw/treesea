from __future__ import annotations
import itertools
import math
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np

try:
    import torch
    _TORCH_OK = True
except ImportError:
    _TORCH_OK = False

from .problem_seed import ProblemSeed
from .background_inference import ProblemBackground

# ---------------------------------------------------------------------------
# Physics constants
# ---------------------------------------------------------------------------
BASE_H = 5400.0
G      = 9.81
F0     = 8.0e-5
CP     = 1004.0
LV     = 2.5e6
# Physical domain (fixed geographic extent — resolution set by NX/NY)
_DOMAIN_X  = 1_500_000.0   # 1 500 km east-west  (metres)
_DOMAIN_Y  = 1_100_000.0   #  1 100 km north-south (metres)
_DX_REF    = _DOMAIN_X / 127.0   # reference grid spacing at NX=128 (~11 811 m)

# Legacy scalar kept for backward-compat; overridden inside run_tree_diagram.
DX     = _DOMAIN_X / 27.0    # ~55 556 m at NX=28 (original scale)
DY     = _DOMAIN_Y / 20.0    # ~55 000 m at NY=21

# ---------------------------------------------------------------------------
# Per-family UMDST coefficients  (gain, precision, coupling, stress, decay)
# Source: umdst_v03 family_coeffs; atmosphere families mapped to analogs.
# ---------------------------------------------------------------------------
_FAMILY_COEFFS: Dict[str, tuple] = {
    "batch":       (0.060, 0.020, 0.026, 0.018, 0.008),
    "network":     (0.052, 0.016, 0.032, 0.021, 0.010),
    "phase":       (0.050, 0.018, 0.020, 0.022, 0.010),
    "electrical":  (0.044, 0.030, 0.016, 0.040, 0.016),
    "ascetic":     (0.030, 0.022, 0.014, 0.012, 0.006),
    "hybrid":      (0.055, 0.014, 0.024, 0.035, 0.018),
    "composite":   (0.055, 0.014, 0.024, 0.035, 0.018),
    # Atmosphere families → closest subject analog
    "weak_mix":    (0.045, 0.015, 0.018, 0.025, 0.012),   # default (gentle)
    "balanced":    (0.050, 0.018, 0.020, 0.022, 0.010),   # phase-like
    "high_mix":    (0.055, 0.014, 0.024, 0.035, 0.018),   # hybrid-like
    "humid_bias":  (0.052, 0.016, 0.032, 0.021, 0.010),   # network-like
    "strong_pg":   (0.060, 0.020, 0.026, 0.018, 0.008),   # batch-like
    "terrain_lock":(0.044, 0.030, 0.016, 0.040, 0.016),   # electrical-like
}
_FAMILY_COEFFS_DEFAULT = (0.045, 0.015, 0.018, 0.025, 0.012)

# Gain modifier group per family:
#   0 = batch      1+0.16*sigmoid(10*(phase-0.55))
#   1 = phase      1+0.10*progress
#   2 = hybrid     1+0.12*sin(progress*pi)
#   3 = electrical 0.92+0.10*sin(progress*2pi)
#   4 = network    0.98+0.10*sigmoid(8*(ac-0.65))
#   5 = ascetic    0.82+0.20*progress
_FAMILY_MOD_GROUP: Dict[str, int] = {
    "batch": 0, "strong_pg": 0, "balanced": 0, "high_mix": 0,
    "phase": 1, "humid_bias": 1,
    "hybrid": 2, "composite": 2,
    "electrical": 3, "terrain_lock": 3,
    "network": 4,
    "ascetic": 5, "weak_mix": 5,
}

_UMDST_N_BASELINE = 183.0   # steps for n=15000, rho=0.7 (neutral point)
_N_OPT            = 20000.0  # alignment fixed point
_N_SIGMA          = 5000.0   # Gaussian half-width for n_scale envelope
_UMDST_REF_STEPS  = 300.0    # reference rollout length the UMDST rates were
                              # calibrated for (td_ai_singularity etc. use ~300).
                              # Longer rollouts (weather 7-day ≈ 13440 steps)
                              # need step_scale = _UMDST_REF_STEPS / total_steps
                              # so phase/stress/instab traverse a consistent
                              # cumulative range; otherwise instability saturates
                              # within ~140 steps and phase collapses to 0.


# ---------------------------------------------------------------------------
# NumPy grid engine
# ---------------------------------------------------------------------------
class _GridEngine:
    def lap(self, f, dx, dy):
        return ((np.roll(f,-1,-2)-2*f+np.roll(f,1,-2))/dy**2
              + (np.roll(f,-1,-1)-2*f+np.roll(f,1,-1))/dx**2)

    def grad_x(self, f, dx):
        return (np.roll(f,-1,-1) - np.roll(f,1,-1)) / (2*dx)

    def grad_y(self, f, dy):
        return (np.roll(f,-1,-2) - np.roll(f,1,-2)) / (2*dy)

    def smooth(self, f, alpha=0.06):
        return ((1-alpha)*f
                + alpha*(np.roll(f,1,-2)+np.roll(f,-1,-2)
                        +np.roll(f,1,-1)+np.roll(f,-1,-1))/4)

    def bilinear_sample(self, field, px, py):
        px = np.clip(px, 0.0, field.shape[-1]-1.001)
        py = np.clip(py, 0.0, field.shape[-2]-1.001)
        x0 = np.floor(px).astype(int); y0 = np.floor(py).astype(int)
        x1 = np.clip(x0+1, 0, field.shape[-1]-1)
        y1 = np.clip(y0+1, 0, field.shape[-2]-1)
        wx = px-x0; wy = py-y0
        b = np.arange(field.shape[0])[:,None,None]
        return ((1-wx)*(1-wy)*field[b,y0,x0] + wx*(1-wy)*field[b,y0,x1]
              + (1-wx)*wy*field[b,y1,x0] + wx*wy*field[b,y1,x1])

    def semi_lagrangian(self, field, u, v, dx, dy, dt):
        H, W = field.shape[-2], field.shape[-1]
        jj, ii = np.meshgrid(np.arange(H), np.arange(W), indexing='ij')
        dep_x = ii[None] - u*dt/dx
        dep_y = jj[None] - v*dt/dy
        return self.bilinear_sample(field, dep_x, dep_y)


# ---------------------------------------------------------------------------
# Torch grid engine
# ---------------------------------------------------------------------------
class _TorchGridEngine:
    def lap(self, f, dx, dy):
        return ((torch.roll(f,-1,-2)-2*f+torch.roll(f,1,-2))/dy**2
              + (torch.roll(f,-1,-1)-2*f+torch.roll(f,1,-1))/dx**2)

    def grad_x(self, f, dx):
        return (torch.roll(f,-1,-1) - torch.roll(f,1,-1)) / (2*dx)

    def grad_y(self, f, dy):
        return (torch.roll(f,-1,-2) - torch.roll(f,1,-2)) / (2*dy)

    def smooth(self, f, alpha=0.06):
        return ((1-alpha)*f
                + alpha*(torch.roll(f,1,-2)+torch.roll(f,-1,-2)
                        +torch.roll(f,1,-1)+torch.roll(f,-1,-1))/4)

    def bilinear_sample(self, field, px, py):
        W = field.shape[-1]; H = field.shape[-2]
        px = px.clamp(0.0, W - 1.001)
        py = py.clamp(0.0, H - 1.001)
        x0 = px.long(); y0 = py.long()
        x1 = (x0 + 1).clamp(0, W - 1)
        y1 = (y0 + 1).clamp(0, H - 1)
        wx = (px - x0.to(px.dtype))
        wy = (py - y0.to(py.dtype))
        b  = torch.arange(field.shape[0], device=field.device)[:, None, None]
        return ((1-wx)*(1-wy)*field[b,y0,x0] + wx*(1-wy)*field[b,y0,x1]
              + (1-wx)*wy*field[b,y1,x0] + wx*wy*field[b,y1,x1])

    def semi_lagrangian(self, field, u, v, dx, dy, dt):
        H, W = field.shape[-2], field.shape[-1]
        dev  = field.device
        jj = torch.arange(H, device=dev, dtype=field.dtype)
        ii = torch.arange(W, device=dev, dtype=field.dtype)
        jj, ii = torch.meshgrid(jj, ii, indexing='ij')
        dep_x = ii[None] - u * dt / dx
        dep_y = jj[None] - v * dt / dy
        return self.bilinear_sample(field, dep_x, dep_y)


_ENG       = _GridEngine()
_TORCH_ENG = _TorchGridEngine() if _TORCH_OK else None
_COORD_CACHE: dict = {}


def _get_coords(NY: int, NX: int):
    key = (NY, NX)
    if key not in _COORD_CACHE:
        x = np.linspace(-1.0, 1.0, NX)
        y = np.linspace(-1.0, 1.0, NY)
        _COORD_CACHE[key] = np.meshgrid(x, y)
    return _COORD_CACHE[key]


# ---------------------------------------------------------------------------
# Vectorised UMDST 1-step — Torch/GPU path
#
# Now uses per-family (g_gain, g_prec, g_coup, g_stress) coefficient tensors
# and per-family gain modifier determined by mod_group.
# ---------------------------------------------------------------------------
def _umdst_batched_step(
    output_power,   # (B,)
    load_tol,       # (B,)
    ac,             # (B,) aim_coupling
    stress,         # (B,)
    phase,          # (B,)
    md,             # (B,) marginal_decay
    instab,         # (B,)
    A,              # (B,)
    rho,            # (B,)
    sigma,          # (B,)
    n,              # (B,)
    g_gain,         # (B,) per-family gain coefficient
    g_prec,         # (B,) per-family precision coefficient
    g_coup,         # (B,) per-family coupling coefficient
    g_stress,       # (B,) per-family stress coefficient
    progress: float,  # scalar 0.0–1.0
    mod_group,        # (B,) int tensor, 0–5
    spatial_het=None, # (B,) combined spatial heterogeneity signal [0,1]
    wind_rms=None,    # (B,) normalised RMS wind speed [0,2]
    step_scale: float = 1.0,  # NEW: per-step rate scaling, see _UMDST_REF_STEPS
):
    """Vectorised UMDST 1-step. Returns (new_phase, new_stress, new_instab).

    spatial_het: combined spatial heterogeneity (h_std, T_std, q_std weighted).
                 Boosts phase gain and drives instability when fields are diverse.
    wind_rms:    normalised RMS wind speed.  Drives stress accumulation.
    """
    std    = torch.exp(-4.0 * sigma)
    n_steps = (24.0 + torch.sqrt(n.float()) * 1.2 + 18.0 * rho).clamp(min=24.0)
    n_scale = (n_steps / _UMDST_N_BASELINE).clamp(0.5, 2.0)
    # Gaussian envelope: peaks at n=_N_OPT, making n=20000 the dynamical fixed point
    n_gauss = torch.exp(-0.5 * ((n.float() - _N_OPT) / _N_SIGMA) ** 2)
    n_scale = (n_scale * n_gauss).clamp(0.5, 2.0)

    gain = (g_gain * A * (0.55 + 0.45 * rho) * std
            * (0.7 + 0.3 * ac)
            * torch.exp(-1.8 * md)
            * (1.0 - 0.35 * stress)
            * n_scale)
    precision_gain = g_prec * A * (1.0 - 0.4 * sigma) * (1.0 - 0.35 * stress)
    coupling_gain  = g_coup * A * std * (0.8 + 0.2 * output_power)

    # Per-family gain modifier (6 groups)
    _pi = math.pi
    m0 = 1.0 + 0.16 * torch.sigmoid(10.0 * (phase - 0.55))      # batch
    m1 = 1.0 + 0.10 * progress                                    # phase-linear
    m2 = 1.0 + 0.12 * math.sin(progress * _pi)                   # hybrid-sin
    m3 = 0.92 + 0.10 * math.sin(progress * 2.0 * _pi)            # electrical
    m4 = 0.98 + 0.10 * torch.sigmoid(8.0 * (ac - 0.65))          # network
    m5 = 0.82 + 0.20 * progress                                   # ascetic

    mg = mod_group
    modifier = ((mg == 0).float() * m0
              + (mg == 1).float() * m1
              + (mg == 2).float() * m2
              + (mg == 3).float() * m3
              + (mg == 4).float() * m4
              + (mg == 5).float() * m5)
    gain = gain * modifier

    # Spatial heterogeneity feedback: diverse fields boost gain and instability
    if spatial_het is not None:
        gain = gain * (1.0 + 0.10 * spatial_het.clamp(0.0, 1.0))

    stress_up        = g_stress * A * (0.8 + 0.4 * rho) * (0.55 + 0.45 * sigma)
    stress_down      = 0.010 + 0.014 * load_tol
    instability_up   = 0.012 * A + 0.010 * sigma + 0.014 * stress
    instability_down = 0.008 * load_tol

    # Wind and spatial heterogeneity add to stress/instability
    if wind_rms is not None:
        stress_up = stress_up + 0.004 * wind_rms.clamp(0.0, 2.0)
    if spatial_het is not None:
        instability_up = instability_up + 0.005 * spatial_het.clamp(0.0, 1.0)

    # step_scale dampens per-step rates for long rollouts; clamped to [0,1]
    # upstream so short rollouts (step_scale=1.0) are unchanged from legacy.
    #
    # Long-only proportional decay: decay_coef = 1.0 - step_scale. At short
    # rollout (step_scale=1) decay_coef=0 → zero extra decay, legacy preserved.
    # At long rollout (step_scale≪1) decay_coef→1 → −0.020·state term bounds
    # stress/instab equilibria away from 1.0 so phase is not collapsed by
    # indefinite growth of (0.012·A + 0.010·σ + …) over 10⁴ steps.
    decay_coef = (1.0 - step_scale)
    new_phase  = (phase  + step_scale * (gain
                  + 0.20 * precision_gain + 0.16 * coupling_gain
                  - 0.05 * instab - 0.04 * stress)).clamp(0.0, 1.0)
    new_stress = (stress + step_scale * (stress_up - stress_down
                  - 0.020 * decay_coef * stress)).clamp(0.0, 1.0)
    new_instab = (instab + step_scale * (instability_up - instability_down
                  - 0.020 * decay_coef * instab)).clamp(0.0, 1.0)
    return new_phase, new_stress, new_instab


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class UnifiedState:
    """Full state for all B candidates simultaneously."""
    h:   object   # (B, H, W)
    T:   object   # (B, H, W)
    q:   object   # (B, H, W)
    u:   object   # (B, H, W)
    v:   object   # (B, H, W)
    phase:       object   # (B,)
    stress:      object   # (B,)
    instability: object   # (B,)
    obs_h:      object   # (H, W)
    obs_T:      object   # (H, W)
    obs_q:      object   # (H, W)
    obs_u:      object   # (H, W)
    obs_v:      object   # (H, W)
    topography: object   # (H, W)


@dataclass
class EvaluationResult:
    family:          str
    template:        str
    params:          Dict
    feasibility:     float
    stability:       float
    field_fit:       float
    risk:            float
    balanced_score:  float
    nutrient_gain:   float
    branch_status:   str
    weather_score:         Optional[float] = None
    weather_alignment:     Optional[float] = None
    final_balanced_score:  Optional[float] = None


# ---------------------------------------------------------------------------
# Candidate generation — unified pool, no plan/weather split
# ---------------------------------------------------------------------------
_CANDIDATE_SPECS: Dict = {
    "batch":      {
        "n":[12000,16000,18000,20000,22000,24000,28000], "rho":[0.5,0.8,1.0], "A":[0.7,0.9], "sigma":[0.01,0.03],
        "Kh":360.0, "Kt":180.0, "Kq":130.0, "drag":1.5e-5,
        "humid_couple":1.00, "nudging":1.6e-4, "pg_scale":1.00,
    },
    "network":    {
        "n":[10000,14000,16000,20000,24000], "rho":[0.8,1.0], "A":[0.6,0.8], "sigma":[0.02],
        "Kh":300.0, "Kt":150.0, "Kq":125.0, "drag":1.2e-5,
        "humid_couple":0.95, "nudging":1.5e-4, "pg_scale":1.00,
    },
    "phase":      {
        "n":[10000,14000,18000,22000], "rho":[0.5,1.0], "A":[0.6,0.75], "sigma":[0.04],
        "Kh":330.0, "Kt":170.0, "Kq":135.0, "drag":1.6e-5,
        "humid_couple":1.02, "nudging":1.5e-4, "pg_scale":1.04,
    },
    "electrical": {
        "n":[10000,14000,18000,20000,24000], "rho":[0.6,1.0], "A":[0.7], "sigma":[0.05],
        "Kh":240.0, "Kt":120.0, "Kq":95.0, "drag":1.2e-5,
        "humid_couple":0.80, "nudging":1.4e-4, "pg_scale":1.00,
    },
    "ascetic":    {
        "n":[10000,14000,18000,22000], "rho":[0.2,0.4], "A":[0.4,0.55], "sigma":[0.03],
        "Kh":240.0, "Kt":120.0, "Kq":95.0, "drag":1.2e-5,
        "humid_couple":0.80, "nudging":1.4e-4, "pg_scale":1.00,
    },
    "hybrid":     {
        "n":[12000,14000,18000,22000,26000], "rho":[0.7,1.0], "A":[0.75], "sigma":[0.08],
        "Kh":520.0, "Kt":260.0, "Kq":180.0, "drag":1.8e-5,
        "humid_couple":1.05, "nudging":1.7e-4, "pg_scale":1.00,
    },
    "composite":  {
        "n":[16000,18000,20000,22000,26000], "rho":[0.8,1.0], "A":[0.8], "sigma":[0.04],
        "Kh":340.0, "Kt":175.0, "Kq":220.0, "drag":1.5e-5,
        "humid_couple":1.24, "nudging":1.6e-4, "pg_scale":1.00,
    },
    "weak_mix":    {
        "n":[10000,12000,16000,20000], "rho":[0.5,0.7], "A":[0.6,0.7], "sigma":[0.03,0.05],
        "Kh":240.0, "Kt":120.0, "Kq":95.0, "drag":1.2e-5,
        "humid_couple":0.80, "nudging":1.4e-4, "pg_scale":1.00,
    },
    "balanced":    {
        "n":[12000,14000,18000,22000], "rho":[0.6,0.8], "A":[0.65,0.75], "sigma":[0.03,0.05],
        "Kh":360.0, "Kt":180.0, "Kq":130.0, "drag":1.5e-5,
        "humid_couple":1.00, "nudging":1.6e-4, "pg_scale":1.00,
    },
    "high_mix":    {
        "n":[14000,16000,20000,24000], "rho":[0.7,1.0], "A":[0.7,0.85], "sigma":[0.02,0.04],
        "Kh":520.0, "Kt":260.0, "Kq":180.0, "drag":1.8e-5,
        "humid_couple":1.05, "nudging":1.7e-4, "pg_scale":1.00,
    },
    "humid_bias":  {
        "n":[12000,14000,18000,22000], "rho":[0.6,0.8], "A":[0.65,0.75], "sigma":[0.03,0.05],
        "Kh":340.0, "Kt":175.0, "Kq":220.0, "drag":1.5e-5,
        "humid_couple":1.24, "nudging":1.6e-4, "pg_scale":1.00,
    },
    "strong_pg":   {
        "n":[10000,12000,16000,20000], "rho":[0.5,0.7], "A":[0.6,0.7], "sigma":[0.03,0.05],
        "Kh":300.0, "Kt":150.0, "Kq":125.0, "drag":1.2e-5,
        "humid_couple":0.95, "nudging":1.5e-4, "pg_scale":1.18,
    },
    "terrain_lock":{
        "n":[10000,12000,16000,20000], "rho":[0.5,0.8], "A":[0.6,0.75], "sigma":[0.03,0.05],
        "Kh":330.0, "Kt":170.0, "Kq":135.0, "drag":1.6e-5,
        "humid_couple":1.02, "nudging":1.5e-4, "pg_scale":1.04,
    },
}


def generate_candidates(seed: ProblemSeed, bg: ProblemBackground) -> list:
    """Build a flat list of candidates, each with ALL parameters fully specified."""
    ac = float(seed.subject.get("aim_coupling", 0.9))
    md = float(seed.subject.get("marginal_decay", 0.1))
    out = []
    for fam in bg.candidate_families:
        spec = _CANDIDATE_SPECS.get(fam, _CANDIDATE_SPECS["batch"])
        var_keys = [k for k, v in spec.items() if isinstance(v, list)]
        fix_keys = [k for k, v in spec.items() if not isinstance(v, list)]
        for combo in itertools.product(*[spec[k] for k in var_keys]):
            p = dict(zip(var_keys, (float(v) for v in combo)))
            for k in fix_keys:
                p[k] = float(spec[k])
            p["aim_coupling"]   = ac
            p["marginal_decay"] = md
            out.append({"family": fam, "template": f"{fam}_route", "params": p})
    return out


def prepare_candidate_arrays(candidates: list) -> dict:
    """Return numpy dict of per-candidate parameter arrays, including UMDST coefficients."""
    all_keys: set = set()
    for c in candidates:
        all_keys.update(c["params"].keys())
    carr: dict = {"family": np.array([c["family"] for c in candidates], dtype=object)}
    for k in sorted(all_keys):
        carr[k] = np.array([c["params"].get(k, 0.0) for c in candidates], dtype=np.float64)

    # Per-family UMDST coefficient arrays
    _dc = _FAMILY_COEFFS_DEFAULT
    carr["g_gain"]    = np.array([_FAMILY_COEFFS.get(c["family"], _dc)[0] for c in candidates], dtype=np.float32)
    carr["g_prec"]    = np.array([_FAMILY_COEFFS.get(c["family"], _dc)[1] for c in candidates], dtype=np.float32)
    carr["g_coup"]    = np.array([_FAMILY_COEFFS.get(c["family"], _dc)[2] for c in candidates], dtype=np.float32)
    carr["g_stress"]  = np.array([_FAMILY_COEFFS.get(c["family"], _dc)[3] for c in candidates], dtype=np.float32)
    carr["mod_group"] = np.array([_FAMILY_MOD_GROUP.get(c["family"], 0) for c in candidates], dtype=np.int32)
    return carr


# ---------------------------------------------------------------------------
# Initial state encoder (always numpy — cheap, runs once)
# ---------------------------------------------------------------------------
def encode_initial_state(
    seed: ProblemSeed,
    candidates: list,
    NX: int = 28,
    NY: int = 21,
) -> UnifiedState:
    XX, YY = _get_coords(NY, NX)

    topo = (1400.0*np.exp(-7.0*((XX+0.36)**2+(YY-0.06)**2))
           +  720.0*np.exp(-10.5*((XX-0.18)**2+(YY+0.24)**2))
           +  350.0*np.exp(-14.0*((XX+0.05)**2+(YY+0.28)**2)))

    obs_h = np.clip(BASE_H+200*np.exp(-6.8*((XX+0.18)**2+(YY+0.10)**2))
                   -150*np.exp(-8.0*((XX-0.28)**2+(YY-0.14)**2))-0.23*topo,
                   BASE_H-500, BASE_H+500)
    obs_T = np.clip(289.0+7.5*np.exp(-8.2*((XX+0.16)**2+(YY+0.11)**2))
                   -5.8*np.exp(-8.8*((XX-0.24)**2+(YY-0.17)**2))-0.0038*topo
                   +0.8*np.sin(1.2*np.pi*XX)*np.cos(0.8*np.pi*YY), 250.0, 320.0)
    obs_q = np.clip(0.010+0.011*np.exp(-7.6*((XX-0.10)**2+(YY+0.21)**2))
                   +0.0016*np.sin(np.pi*YY), 1e-5, 0.030)
    obs_u = 12.0*np.sin(0.9*np.pi*YY)*np.cos(0.8*np.pi*XX)
    obs_v = -8.5*np.sin(0.8*np.pi*XX)*np.cos(0.9*np.pi*YY)

    env  = seed.environment
    subj = seed.subject
    res  = seed.resources
    pc   = float(res.get("population_coupling", 0.5))
    dc   = float(res.get("data_coverage", 0.5))
    primary   = float(np.clip(
        0.42*subj.get("aim_coupling",0.9)+0.18*subj.get("control_precision",0.8)
        +0.12*subj.get("phase_proximity",0.7)+0.18*pc+0.06*dc
        -0.14*env.get("field_noise",0.3)-0.08*env.get("phase_instability",0.4),
        0.0, 1.0))
    secondary = float(np.clip(
        0.60*env.get("network_density",0.7)+0.20*env.get("infrastructure",0.7)+0.20*dc,
        0.0, 1.0))
    tertiary  = float(np.clip(
        0.75*env.get("phase_instability",0.4)+0.25*env.get("field_noise",0.3),
        0.0, 1.0))

    plan_h = np.full((NY, NX), BASE_H - 350.0 + 700.0 * primary)
    plan_T = np.full((NY, NX), 265.0 + 50.0 * secondary)
    plan_q = np.full((NY, NX), 1e-5 + 0.024 * tertiary)
    plan_u = np.zeros((NY, NX))
    plan_v = np.zeros((NY, NX))

    init_phase  = float(subj.get("phase_proximity", 0.7))
    init_stress = float(subj.get("stress_level", 0.2))
    init_instab = float(subj.get("instability_sensitivity", 0.28))

    B = len(candidates)
    h_arr = np.empty((B, NY, NX), dtype=np.float32)
    T_arr = np.empty((B, NY, NX), dtype=np.float32)
    q_arr = np.empty((B, NY, NX), dtype=np.float32)
    u_arr = np.empty((B, NY, NX), dtype=np.float32)
    v_arr = np.empty((B, NY, NX), dtype=np.float32)
    phase_arr  = np.empty(B, dtype=np.float32)
    stress_arr = np.empty(B, dtype=np.float32)
    instab_arr = np.empty(B, dtype=np.float32)

    # Each candidate receives a small deterministic perturbation to break symmetry.
    # Seed derived from candidate params so rollouts are fully reproducible.
    for b, cand in enumerate(candidates):
        p = cand["params"]
        _seed = int(p["n"] * 13 + p["rho"] * 97 + p["A"] * 53) % (2**31)
        rng = np.random.default_rng(_seed)
        h_arr[b]  = plan_h + rng.normal(0, 18.0, (NY, NX)).astype(np.float32)
        T_arr[b]  = plan_T + rng.normal(0,  0.4, (NY, NX)).astype(np.float32)
        q_arr[b]  = np.clip(plan_q + rng.normal(0, 4e-4, (NY, NX)).astype(np.float32), 1e-5, 0.030)
        u_arr[b]  = plan_u + rng.normal(0,  0.4, (NY, NX)).astype(np.float32)
        v_arr[b]  = plan_v + rng.normal(0,  0.4, (NY, NX)).astype(np.float32)
    phase_arr[:]  = init_phase
    stress_arr[:] = init_stress
    instab_arr[:] = init_instab

    return UnifiedState(
        h=h_arr, T=T_arr, q=q_arr, u=u_arr, v=v_arr,
        phase=phase_arr, stress=stress_arr, instability=instab_arr,
        obs_h=obs_h.astype(np.float32), obs_T=obs_T.astype(np.float32),
        obs_q=obs_q.astype(np.float32), obs_u=obs_u.astype(np.float32),
        obs_v=obs_v.astype(np.float32), topography=topo.astype(np.float32),
    )


# ---------------------------------------------------------------------------
# NumPy ↔ Torch conversion helpers
# ---------------------------------------------------------------------------
def _state_to_torch(state: UnifiedState, device: str) -> UnifiedState:
    def t(arr):
        return torch.as_tensor(arr, dtype=torch.float32, device=device)
    return UnifiedState(
        h=t(state.h), T=t(state.T), q=t(state.q),
        u=t(state.u), v=t(state.v),
        phase=t(state.phase), stress=t(state.stress), instability=t(state.instability),
        obs_h=t(state.obs_h), obs_T=t(state.obs_T), obs_q=t(state.obs_q),
        obs_u=t(state.obs_u), obs_v=t(state.obs_v),
        topography=t(state.topography),
    )


def _state_to_numpy(state: UnifiedState) -> UnifiedState:
    def n(arr):
        if _TORCH_OK and isinstance(arr, torch.Tensor):
            return arr.cpu().float().numpy()
        return np.asarray(arr, dtype=np.float32)
    return UnifiedState(
        h=n(state.h), T=n(state.T), q=n(state.q),
        u=n(state.u), v=n(state.v),
        phase=n(state.phase), stress=n(state.stress), instability=n(state.instability),
        obs_h=n(state.obs_h), obs_T=n(state.obs_T), obs_q=n(state.obs_q),
        obs_u=n(state.obs_u), obs_v=n(state.obs_v),
        topography=n(state.topography),
    )


def _carr_to_torch(carr: dict, device: str) -> dict:
    out = {}
    for k, v in carr.items():
        if isinstance(v, np.ndarray) and v.dtype != object:
            if v.dtype == np.int32:
                out[k] = torch.as_tensor(v, dtype=torch.long, device=device)
            else:
                out[k] = torch.as_tensor(v, dtype=torch.float32, device=device)
        else:
            out[k] = v
    return out


def _carr_to_numpy(carr: dict) -> dict:
    out = {}
    for k, v in carr.items():
        if _TORCH_OK and isinstance(v, torch.Tensor):
            out[k] = v.cpu().numpy()
        else:
            out[k] = v
    return out


def _subset_state(state: UnifiedState, idx) -> UnifiedState:
    """Return a UnifiedState containing only the selected batch indices.

    Works with both numpy arrays and torch tensors.
    Shared fields (obs_*, topography) are not copied — they are broadcast-safe.
    """
    def sel(arr):
        if _TORCH_OK and isinstance(arr, torch.Tensor):
            t_idx = torch.as_tensor(idx, device=arr.device, dtype=torch.long)
            return arr[t_idx]
        return arr[np.array(idx)]

    return UnifiedState(
        h=sel(state.h), T=sel(state.T), q=sel(state.q),
        u=sel(state.u), v=sel(state.v),
        phase=sel(state.phase), stress=sel(state.stress),
        instability=sel(state.instability),
        obs_h=state.obs_h, obs_T=state.obs_T, obs_q=state.obs_q,
        obs_u=state.obs_u, obs_v=state.obs_v, topography=state.topography,
    )


def _subset_carr(carr: dict, idx, B: int) -> dict:
    """Return a carr dict containing only the selected batch indices."""
    idx_np = np.array(idx)
    out = {}
    for k, v in carr.items():
        if _TORCH_OK and isinstance(v, torch.Tensor) and v.shape[0] == B:
            t_idx = torch.as_tensor(idx_np, device=v.device, dtype=torch.long)
            out[k] = v[t_idx]
        elif isinstance(v, np.ndarray) and v.ndim >= 1 and v.shape[0] == B:
            out[k] = v[idx_np]
        else:
            out[k] = v
    return out


def _merge_states(base: UnifiedState, updated: UnifiedState, alive_idx, B: int) -> UnifiedState:
    """Overwrite base[alive_idx] with updated (len(alive_idx) candidates).

    Shared fields (obs_*, topography) are taken from base unchanged.
    Both base and updated must be numpy UnifiedStates.
    """
    idx = np.array(alive_idx)

    def merge(b, u):
        if isinstance(b, np.ndarray) and b.ndim >= 1 and b.shape[0] == B:
            r = b.copy()
            r[idx] = u
            return r
        return b  # shared 2-D fields

    return UnifiedState(
        h=merge(base.h, updated.h), T=merge(base.T, updated.T),
        q=merge(base.q, updated.q), u=merge(base.u, updated.u),
        v=merge(base.v, updated.v),
        phase=merge(base.phase, updated.phase),
        stress=merge(base.stress, updated.stress),
        instability=merge(base.instability, updated.instability),
        obs_h=base.obs_h, obs_T=base.obs_T, obs_q=base.obs_q,
        obs_u=base.obs_u, obs_v=base.obs_v, topography=base.topography,
    )


# ---------------------------------------------------------------------------
# THE algorithm function — NumPy path
# ---------------------------------------------------------------------------
def unified_step(
    state: UnifiedState,
    carr: dict,
    dt: float,
    dx: float,
    dy: float,
    progress: float = 0.5,
    total_steps: Optional[int] = None,
) -> UnifiedState:
    """One unified step on CPU numpy. All B candidates simultaneously.

    total_steps: full rollout length. Used to derive step_scale so UMDST
    phase/stress/instab rate updates stay consistent across short TD
    judgment rollouts (~300 steps) and long weather rollouts (>10⁴ steps).
    None → legacy behaviour (step_scale=1.0).
    """
    h, T, q, u, v = state.h, state.T, state.q, state.u, state.v
    phase, stress, instab = state.phase, state.stress, state.instability
    topo = state.topography[None]

    # Resolution-adaptive diffusivity: Kh scales as (dx/_DX_REF)^2 so that the
    # diffusion CFL number Kh*dt/dx^2 is constant regardless of grid spacing.
    _res_scale = (dx / _DX_REF) ** 2
    Kh    = carr["Kh"]   [:,None,None] * _res_scale
    Kt    = carr["Kt"]   [:,None,None] * _res_scale
    Kq    = carr["Kq"]   [:,None,None] * _res_scale
    drag  = carr["drag"] [:,None,None]
    hc    = carr["humid_couple"][:,None,None]
    nu    = carr["nudging"]     [:,None,None]
    pg    = carr["pg_scale"]    [:,None,None]
    A     = carr["A"];     rho   = carr["rho"];   sigma = carr["sigma"]
    ac    = carr["aim_coupling"]; md = carr["marginal_decay"]

    h_a = _ENG.semi_lagrangian(h, u, v, dx, dy, dt)
    T_a = _ENG.semi_lagrangian(T, u, v, dx, dy, dt)
    q_a = _ENG.semi_lagrangian(q, u, v, dx, dy, dt)
    u_a = _ENG.semi_lagrangian(u, u, v, dx, dy, dt)
    v_a = _ENG.semi_lagrangian(v, u, v, dx, dy, dt)

    geop   = G * (h_a + 0.18 * topo)
    td_fac = 1.0 + 0.00035 * topo
    du = -dt*pg*_ENG.grad_x(geop, dx) + dt*F0*v_a - dt*drag*td_fac*u_a
    dv = -dt*pg*_ENG.grad_y(geop, dy) - dt*F0*u_a - dt*drag*td_fac*v_a

    div = _ENG.grad_x(u_a, dx) + _ENG.grad_y(v_a, dy)
    dh  = -dt * 0.55 * h_a / BASE_H * div

    dh += dt * Kh * 0.35 * _ENG.lap(h_a, dx, dy)
    dT  = dt * Kt        * _ENG.lap(T_a, dx, dy)
    dq  = dt * Kq        * _ENG.lap(q_a, dx, dy)
    du += dt * Kh        * _ENG.lap(u_a, dx, dy)
    dv += dt * Kh        * _ENG.lap(v_a, dx, dy)

    sat    = 0.0045 * np.exp(0.060 * (T_a - 273.15) / 10.0)
    excess = np.maximum(q_a - sat, 0.0)
    cond   = 0.20 * excess * hc
    T_eq   = 286.5 - 0.0032 * topo
    dT    += dt * ((LV/CP)*cond*1e-4 - 1.4e-5*(T_a - T_eq))
    XX, YY = _get_coords(h.shape[-2], h.shape[-1])
    q_src  = 2.0e-6 * np.exp(-6.0*(XX**2 + YY**2))
    dq    += dt * (q_src[None] - cond)

    dh += dt * nu * (state.obs_h[None] - h_a)
    dT += dt * nu * (state.obs_T[None] - T_a)
    dq += dt * nu * (state.obs_q[None] - q_a)
    du += dt * nu * (state.obs_u[None] - u_a)
    dv += dt * nu * (state.obs_v[None] - v_a)

    new_h = np.clip(_ENG.smooth(h_a + dh, 0.06), BASE_H-500.0, BASE_H+500.0)
    new_T = np.clip(_ENG.smooth(T_a + dT, 0.05), 250.0, 320.0)
    new_q = np.clip(_ENG.smooth(q_a + dq, 0.05), 1e-5,  0.030)
    new_u = np.clip(_ENG.smooth(u_a + du, 0.04), -40.0, 40.0)
    new_v = np.clip(_ENG.smooth(v_a + dv, 0.04), -40.0, 40.0)

    # Spatial statistics — feed back into UMDST to couple field diversity to dynamics
    h_std    = np.std(new_h, axis=(-2, -1)) / BASE_H          # (B,) normalised
    T_std    = np.std(new_T, axis=(-2, -1)) / 10.0            # (B,)
    q_std    = np.std(new_q, axis=(-2, -1)) / 0.005           # (B,)
    wind_rms = np.sqrt(np.mean(new_u**2 + new_v**2, axis=(-2, -1))) / 20.0  # (B,)
    # Combined heterogeneity signal [0, 1]
    spatial_het = np.clip(0.40*h_std + 0.30*T_std + 0.20*q_std + 0.10*wind_rms, 0.0, 1.0)

    # UMDST — per-family coefficients + per-family gain modifier
    # step_scale clamped to [0, 1]: only damp LONGER rollouts; short rollouts
    # (total_steps ≤ _UMDST_REF_STEPS) keep legacy rate exactly.
    step_scale = (float(min(1.0, _UMDST_REF_STEPS / total_steps))
                   if total_steps else 1.0)
    new_phase  = np.empty_like(phase)
    new_stress = np.empty_like(stress)
    new_instab = np.empty_like(instab)
    _pi = math.pi
    for i in range(phase.shape[0]):
        op_i  = float(np.clip(new_h[i].mean() / BASE_H, 0.0, 1.2))
        lt_i  = float(np.clip(new_q[i].mean() / 0.030, 0.0, 1.2))
        ac_i  = float(ac[i]);   stress_i = float(stress[i])
        ph_i  = float(phase[i]); md_i = float(md[i])
        ins_i = float(instab[i])
        A_i   = float(A[i]);    rho_i = float(rho[i]); sigma_i = float(sigma[i])
        n_i   = float(carr["n"][i])
        gg    = float(carr["g_gain"][i]);  gp = float(carr["g_prec"][i])
        gc    = float(carr["g_coup"][i]);  gs = float(carr["g_stress"][i])
        mg    = int(carr["mod_group"][i])

        std_i     = math.exp(-4.0 * sigma_i)
        n_steps_i = max(24.0, 24.0 + math.sqrt(n_i) * 1.2 + 18.0 * rho_i)
        n_scale_i = max(0.5, min(2.0, n_steps_i / _UMDST_N_BASELINE))
        # Gaussian envelope: peaks at n_opt=20000, dynamical fixed point
        n_gauss_i = math.exp(-0.5 * ((n_i - _N_OPT) / _N_SIGMA) ** 2)
        n_scale_i = max(0.5, min(2.0, n_scale_i * n_gauss_i))

        gain_i = (gg * A_i * (0.55 + 0.45 * rho_i) * std_i
                  * (0.7 + 0.3 * ac_i)
                  * math.exp(-1.8 * md_i)
                  * (1.0 - 0.35 * stress_i)
                  * n_scale_i)
        prec_g = gp * A_i * (1.0 - 0.4 * sigma_i) * (1.0 - 0.35 * stress_i)
        coup_g = gc * A_i * std_i * (0.8 + 0.2 * op_i)

        # Per-family gain modifier
        mods = [
            1.0 + 0.16 / (1.0 + math.exp(-10.0 * (ph_i - 0.55))),  # 0 batch
            1.0 + 0.10 * progress,                                    # 1 phase
            1.0 + 0.12 * math.sin(progress * _pi),                   # 2 hybrid
            0.92 + 0.10 * math.sin(progress * 2.0 * _pi),            # 3 electrical
            0.98 + 0.10 / (1.0 + math.exp(-8.0 * (ac_i - 0.65))),   # 4 network
            0.82 + 0.20 * progress,                                   # 5 ascetic
        ]
        gain_i *= mods[mg]

        # Spatial heterogeneity boosts phase gain
        het_i = float(spatial_het[i])
        gain_i *= (1.0 + 0.10 * het_i)

        wrms_i = float(wind_rms[i])
        su  = gs * A_i * (0.8 + 0.4 * rho_i) * (0.55 + 0.45 * sigma_i) + 0.004 * wrms_i
        sd  = 0.010 + 0.014 * lt_i
        iu  = 0.012 * A_i + 0.010 * sigma_i + 0.014 * stress_i + 0.005 * het_i
        id_ = 0.008 * lt_i

        # Long-only proportional decay on stress/instab (see batched version).
        decay_coef = 1.0 - step_scale
        new_phase[i]  = max(0.0, min(1.0,
            ph_i + step_scale * (
                gain_i + 0.20*prec_g + 0.16*coup_g - 0.05*ins_i - 0.04*stress_i)))
        new_stress[i] = max(0.0, min(1.0,
            stress_i + step_scale * (su - sd - 0.020 * decay_coef * stress_i)))
        new_instab[i] = max(0.0, min(1.0,
            ins_i + step_scale * (iu - id_ - 0.020 * decay_coef * ins_i)))

    return UnifiedState(
        h=new_h, T=new_T, q=new_q, u=new_u, v=new_v,
        phase=new_phase, stress=new_stress, instability=new_instab,
        obs_h=state.obs_h, obs_T=state.obs_T, obs_q=state.obs_q,
        obs_u=state.obs_u, obs_v=state.obs_v, topography=state.topography,
    )


# ---------------------------------------------------------------------------
# THE algorithm function — Torch/GPU path
# ---------------------------------------------------------------------------
def _torch_unified_step(
    state: UnifiedState,
    carr: dict,
    dt: float,
    dx: float,
    dy: float,
    progress: float = 0.5,
    total_steps: Optional[int] = None,
) -> UnifiedState:
    """One unified step on GPU. All B candidates simultaneously.

    total_steps: see unified_step docstring. Passed through to
    _umdst_batched_step as step_scale = _UMDST_REF_STEPS / total_steps.
    """
    eng = _TORCH_ENG
    h, T, q, u, v = state.h, state.T, state.q, state.u, state.v
    phase, stress, instab = state.phase, state.stress, state.instability
    topo = state.topography.unsqueeze(0)

    # Resolution-adaptive diffusivity (same scaling as numpy path)
    _res_scale = (dx / _DX_REF) ** 2
    Kh    = carr["Kh"]   [:, None, None] * _res_scale
    Kt    = carr["Kt"]   [:, None, None] * _res_scale
    Kq    = carr["Kq"]   [:, None, None] * _res_scale
    drag  = carr["drag"] [:, None, None]
    hc    = carr["humid_couple"][:, None, None]
    nu    = carr["nudging"]     [:, None, None]
    pg    = carr["pg_scale"]    [:, None, None]
    A     = carr["A"];     rho   = carr["rho"];   sigma = carr["sigma"]
    ac    = carr["aim_coupling"]; md = carr["marginal_decay"]

    h_a = eng.semi_lagrangian(h, u, v, dx, dy, dt)
    T_a = eng.semi_lagrangian(T, u, v, dx, dy, dt)
    q_a = eng.semi_lagrangian(q, u, v, dx, dy, dt)
    u_a = eng.semi_lagrangian(u, u, v, dx, dy, dt)
    v_a = eng.semi_lagrangian(v, u, v, dx, dy, dt)

    geop   = G * (h_a + 0.18 * topo)
    td_fac = 1.0 + 0.00035 * topo
    du = -dt*pg*eng.grad_x(geop, dx) + dt*F0*v_a - dt*drag*td_fac*u_a
    dv = -dt*pg*eng.grad_y(geop, dy) - dt*F0*u_a - dt*drag*td_fac*v_a

    div = eng.grad_x(u_a, dx) + eng.grad_y(v_a, dy)
    dh  = -dt * 0.55 * h_a / BASE_H * div

    dh += dt * Kh * 0.35 * eng.lap(h_a, dx, dy)
    dT  = dt * Kt        * eng.lap(T_a, dx, dy)
    dq  = dt * Kq        * eng.lap(q_a, dx, dy)
    du += dt * Kh        * eng.lap(u_a, dx, dy)
    dv += dt * Kh        * eng.lap(v_a, dx, dy)

    sat    = 0.0045 * torch.exp(0.060 * (T_a - 273.15) / 10.0)
    excess = torch.clamp(q_a - sat, min=0.0)
    cond   = 0.20 * excess * hc
    T_eq   = 286.5 - 0.0032 * topo
    dT    += dt * ((LV/CP)*cond*1e-4 - 1.4e-5*(T_a - T_eq))
    H_dim, W_dim = h.shape[-2], h.shape[-1]
    dev = h.device
    x_t = torch.linspace(-1.0, 1.0, W_dim, device=dev, dtype=h.dtype)
    y_t = torch.linspace(-1.0, 1.0, H_dim, device=dev, dtype=h.dtype)
    YY_t, XX_t = torch.meshgrid(y_t, x_t, indexing='ij')
    q_src = 2.0e-6 * torch.exp(-6.0 * (XX_t**2 + YY_t**2))
    dq   += dt * (q_src[None] - cond)

    dh += dt * nu * (state.obs_h.unsqueeze(0) - h_a)
    dT += dt * nu * (state.obs_T.unsqueeze(0) - T_a)
    dq += dt * nu * (state.obs_q.unsqueeze(0) - q_a)
    du += dt * nu * (state.obs_u.unsqueeze(0) - u_a)
    dv += dt * nu * (state.obs_v.unsqueeze(0) - v_a)

    new_h = (eng.smooth(h_a + dh, 0.06)).clamp(BASE_H-500.0, BASE_H+500.0)
    new_T = (eng.smooth(T_a + dT, 0.05)).clamp(250.0, 320.0)
    new_q = (eng.smooth(q_a + dq, 0.05)).clamp(1e-5,  0.030)
    new_u = (eng.smooth(u_a + du, 0.04)).clamp(-40.0, 40.0)
    new_v = (eng.smooth(v_a + dv, 0.04)).clamp(-40.0, 40.0)

    # Spatial statistics — GPU-vectorised over batch
    h_std    = new_h.std(dim=(-2, -1)) / BASE_H
    T_std    = new_T.std(dim=(-2, -1)) / 10.0
    q_std    = new_q.std(dim=(-2, -1)) / 0.005
    wind_rms = torch.sqrt((new_u**2 + new_v**2).mean(dim=(-2, -1))) / 20.0
    spatial_het = (0.40*h_std + 0.30*T_std + 0.20*q_std + 0.10*wind_rms).clamp(0.0, 1.0)

    op  = (new_h.mean(dim=(-2,-1)) / BASE_H).clamp(0.0, 1.2)
    lt  = (new_q.mean(dim=(-2,-1)) / 0.030).clamp(0.0, 1.2)
    # Clamp step_scale to [0, 1] so short rollouts are unaffected.
    step_scale = (float(min(1.0, _UMDST_REF_STEPS / total_steps))
                   if total_steps else 1.0)
    new_phase, new_stress, new_instab = _umdst_batched_step(
        op, lt, ac, stress, phase, md, instab, A, rho, sigma, carr["n"],
        carr["g_gain"], carr["g_prec"], carr["g_coup"], carr["g_stress"],
        progress=progress, mod_group=carr["mod_group"],
        spatial_het=spatial_het, wind_rms=wind_rms,
        step_scale=step_scale,
    )

    return UnifiedState(
        h=new_h, T=new_T, q=new_q, u=new_u, v=new_v,
        phase=new_phase, stress=new_stress, instability=new_instab,
        obs_h=state.obs_h, obs_T=state.obs_T, obs_q=state.obs_q,
        obs_u=state.obs_u, obs_v=state.obs_v, topography=state.topography,
    )


# ---------------------------------------------------------------------------
# Rollout — collects phase series for UMDST scoring
# ---------------------------------------------------------------------------
def unified_rollout(
    state: UnifiedState,
    carr: dict,
    dt: float,
    dx: float,
    dy: float,
    steps: int,
    step_offset: int = 0,
    total_steps: Optional[int] = None,
):
    """Returns (final_state, phase_series) where phase_series is (B, steps).

    step_offset / total_steps allow continuation: pass step_offset=screen_steps,
    total_steps=full_steps so that progress resumes correctly in phase 2.
    """
    if total_steps is None:
        total_steps = step_offset + steps
    phase_list = []
    for s in range(steps):
        progress = min(1.0, (step_offset + s + 1) / total_steps)
        state = unified_step(state, carr, dt, dx, dy,
                              progress=progress, total_steps=total_steps)
        phase_list.append(state.phase.copy())
    phase_series = np.stack(phase_list, axis=1)   # (B, steps)
    return state, phase_series


def _torch_rollout(
    state: UnifiedState,
    carr: dict,
    dt: float,
    dx: float,
    dy: float,
    steps: int,
    step_offset: int = 0,
    total_steps: Optional[int] = None,
):
    """Returns (final_state, phase_series) where phase_series is (B, steps) tensor."""
    if total_steps is None:
        total_steps = step_offset + steps
    phase_list = []
    for s in range(steps):
        progress = min(1.0, (step_offset + s + 1) / total_steps)
        state = _torch_unified_step(state, carr, dt, dx, dy,
                                     progress=progress, total_steps=total_steps)
        phase_list.append(state.phase)
    phase_series = torch.stack(phase_list, dim=1)  # (B, steps)
    return state, phase_series


# ---------------------------------------------------------------------------
# Scoring — UMDST evaluate_score aligned
# ---------------------------------------------------------------------------
@dataclass
class ScoreBreakdown:
    """Structured output from score_candidate_breakdown.

    Each field is a (B,) numpy array of per-candidate values. `score` is
    the final composite; the other fields are the primary components that
    went into it. Downstream layers (EvaluationResult assembly, IPL, CBF,
    UTM, vein rerank) should consume these directly rather than surrogates
    like `0.40*phase + 0.35*score + 0.25*A`.
    """
    score:          np.ndarray
    field_fit:      np.ndarray   # [0, 1] obs match — higher = closer to obs
    p_blow:         np.ndarray   # [0, 1] blow-up risk — higher = dangerous
    repeatability:  np.ndarray   # [0, 1] — higher = more stable
    variance_proxy: np.ndarray
    disagree_proxy: np.ndarray
    ood_proxy:      np.ndarray
    phase_max:      np.ndarray
    phase_final:    np.ndarray
    e_cons:         np.ndarray
    n_penalty:      np.ndarray
    family:         np.ndarray   # object array of family names


def score_candidate_breakdown(
    final: UnifiedState,
    phase_series: np.ndarray,   # (B, steps) numpy
    carr: dict,
    seed: ProblemSeed,
) -> ScoreBreakdown:
    """Score candidates and return the full component breakdown.

    Replaces ad-hoc MSE+phase combination with:
      score = 1.80*phase_max + 0.70*field_fit - 1.35*p_blow
              - 0.55*n_penalty - 0.80*U + 0.50*repeatability
    where U = variance_proxy + disagree_proxy + ood_proxy,
    and p_blow is estimated from field error (E_cons proxy) + state indicators.

    score_candidates(...) is kept as a thin wrapper that returns only the
    final score array, for callers that don't need the breakdown.
    """
    phase_max      = phase_series.max(axis=1)          # (B,)
    phase_final    = phase_series[:, -1]                # (B,)
    variance_proxy = phase_series.var(axis=1)           # (B,)

    disagree_proxy = 0.25 * final.stress + 0.25 * final.instability
    ood_proxy      = (np.maximum(0.0, phase_final - 1.0)
                      + np.maximum(0.0, final.instability - 0.8))
    repeatability  = np.maximum(0.0, 1.0 - (variance_proxy + 0.5 * final.instability))

    # Field error — use ABSOLUTE obs-relative normalisation (not min-max over
    # the batch). Min-max amplifies ε-noise into [0,1] when candidates all
    # converge, producing false discrimination signal. Absolute normalisation
    # against obs RMS gives a physically meaningful magnitude.
    def _abs_norm(err, ref_var):
        return err / (ref_var + 1e-12)

    h_err = ((final.h - final.obs_h[None])**2).mean(axis=(1, 2))
    T_err = ((final.T - final.obs_T[None])**2).mean(axis=(1, 2))
    q_err = ((final.q - final.obs_q[None])**2).mean(axis=(1, 2))
    w_err = ((final.u - final.obs_u[None])**2
             + (final.v - final.obs_v[None])**2).mean(axis=(1, 2))
    h_ref = float(final.obs_h.var())
    T_ref = float(final.obs_T.var())
    q_ref = float(final.obs_q.var())
    w_ref = float((final.obs_u**2 + final.obs_v**2).mean())
    e_cons = (_abs_norm(h_err, h_ref)*0.35 + _abs_norm(T_err, T_ref)*0.30
              + _abs_norm(q_err, q_ref)*0.20 + _abs_norm(w_err, w_ref)*0.15)

    # Direct field-fit evidence in [0, 1] — candidates whose final state
    # matches obs score higher. Unlike phase_max (UMDST-abstract), this is
    # a physics-grounded signal that stays sharp even when phase dynamics
    # are dampened (e.g. long weather rollouts with step_scale < 1).
    field_fit = 1.0 / (1.0 + e_cons)

    # p_blow: logistic blow-up risk (no prev trajectory → impact term = 0)
    raw    = (2.2 * np.minimum(e_cons, 10.0)   # clip runaway e_cons
              + 1.6 * final.stress
              + 1.9 * final.instability
              + 0.8 * variance_proxy * 8.0
              + 0.6 * ood_proxy
              - 1.8)
    p_blow = 1.0 / (1.0 + np.exp(-np.clip(raw, -20.0, 20.0)))

    n_penalty = np.minimum(1.0, np.abs(carr["n"] - 20000.0) / 10000.0)

    U = variance_proxy + disagree_proxy + ood_proxy
    score = (1.80 * phase_max
             + 0.70 * field_fit        # direct forecast-evidence weight
             - 1.35 * p_blow
             - 0.55 * n_penalty
             - 0.80 * U
             + 0.50 * repeatability)

    # Family anchor prior — batch gets a small reality-anchor bonus so TD
    # doesn't drift purely into abstract-phase configurations, but the bonus
    # is halved (+0.04 vs legacy +0.08) and family-size-normalised so large
    # candidate pools don't let batch sink top-k alone. The remaining
    # discrimination is done by the diversity gate in run_tree_diagram().
    family_arr = np.asarray(carr["family"])
    _, family_counts = np.unique(family_arr, return_counts=True)
    min_family_count = int(family_counts.min()) if len(family_counts) else 1
    for i, fam in enumerate(family_arr):
        if fam == "batch":
            my_count = int(np.sum(family_arr == fam))
            # Scale down bonus if batch is over-represented in the pool.
            scale = (min_family_count / max(1, my_count)) ** 0.5
            score[i] += 0.04 * scale

    return ScoreBreakdown(
        score=score,
        field_fit=field_fit,
        p_blow=p_blow,
        repeatability=repeatability,
        variance_proxy=variance_proxy,
        disagree_proxy=disagree_proxy,
        ood_proxy=ood_proxy,
        phase_max=phase_max,
        phase_final=phase_final,
        e_cons=e_cons,
        n_penalty=n_penalty,
        family=family_arr,
    )


def score_candidates(
    final: UnifiedState,
    phase_series: np.ndarray,
    carr: dict,
    seed: ProblemSeed,
) -> np.ndarray:
    """Backwards-compatible wrapper returning only the score array.

    Prefer score_candidate_breakdown() when the per-component breakdown
    is needed (EvaluationResult assembly, downstream layers).
    """
    return score_candidate_breakdown(final, phase_series, carr, seed).score


def classify_relative(scores: np.ndarray) -> List[str]:
    """Classify branches by relative score distance from the leader.

    Uses pure fraction-of-span thresholds (no absolute guards), so the
    classification scales with any dynamic range. Previous implementation
    used max(0.20, …) absolute guards, which were larger than the typical
    score span (~0.05–0.20), collapsing every branch into 'active' and
    starving the downstream hydro analysis of branch_status signal.
    """
    best = scores.max()
    span = max(1e-9, best - scores.min())
    out = []
    for s in scores:
        rel = (best - s) / span
        if   rel <= 0.25: out.append("active")
        elif rel <= 0.55: out.append("restricted")
        elif rel <= 0.85: out.append("starved")
        else:             out.append("withered")
    return out


def td_hydro_control(scores: np.ndarray) -> dict:
    s = np.sort(scores)[::-1]
    margin = float(s[0] - s[1]) if len(s) > 1 else 0.0
    spread = float(s[0] - s[-1]) if len(s) > 1 else 0.0
    pb = float(np.clip(
        1.0 + (0.04 if margin < 0.08 else 0.0) - (0.03 if spread > 1.4 else 0.0),
        0.94, 1.08))
    return {"pressure_balance": pb, "top_margin": margin,
            "score_spread": spread, "mean_score": float(scores.mean())}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run_tree_diagram(
    seed: ProblemSeed,
    bg: ProblemBackground,
    NX: int = 128,
    NY: int = 96,
    steps: int = 300,
    top_k: int = 12,
    dt: float = 45.0,
    device: Optional[str] = None,
) -> tuple:
    from .resource_controller import AngioResourceController

    use_torch = False
    if _TORCH_OK:
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        use_torch = True
    else:
        device = "cpu"

    # Physical grid spacing computed from fixed domain size and requested resolution
    DX = _DOMAIN_X / (NX - 1)   # metres (~11 811 m at NX=128)
    DY = _DOMAIN_Y / (NY - 1)   # metres (~11 573 m at NY=96)

    candidates   = generate_candidates(seed, bg)
    B            = len(candidates)
    carr_np      = prepare_candidate_arrays(candidates)
    state_np     = encode_initial_state(seed, candidates, NX, NY)

    screen_steps = max(4, steps // 4)
    refine_steps = steps - screen_steps

    # ---- Phase 1: screening on all B candidates ----
    if use_torch:
        carr_t  = _carr_to_torch(carr_np, device)
        state_t = _state_to_torch(state_np, device)
        final1_t, phase1_t = _torch_rollout(
            state_t, carr_t, dt, DX, DY, screen_steps,
            step_offset=0, total_steps=steps)
        final1 = _state_to_numpy(final1_t)
        phase1 = phase1_t.cpu().numpy()
        carr   = _carr_to_numpy(carr_t)
    else:
        final1, phase1 = unified_rollout(
            state_np, carr_np, dt, DX, DY, screen_steps,
            step_offset=0, total_steps=steps)
        carr = carr_np

    scores1   = score_candidates(final1, phase1, carr, seed)
    statuses1 = classify_relative(scores1)

    alive_idx  = [i for i, s in enumerate(statuses1) if s != "withered"]
    pruned_idx = [i for i, s in enumerate(statuses1) if s == "withered"]

    ctrl = AngioResourceController(total_steps=max(1, refine_steps))
    flow = ctrl.allocate(statuses1)

    # ---- Phase 2: chunked cohort refinement ----
    # Each branch's steps_budget (from AngioResourceController) controls how
    # far into refinement it can go. Split refinement into _REFINE_CHUNKS
    # equal chunks. At each chunk boundary, only candidates with enough
    # remaining budget are advanced; others freeze at their state.
    #
    # This makes reflow_bonus actually matter — active branches keep rolling
    # longer than starved/restricted ones, matching the Angio-whitepaper
    # intent rather than being a no-op log.
    _REFINE_CHUNKS = 4
    if alive_idx and refine_steps > 0:
        chunk_size = max(1, refine_steps // _REFINE_CHUNKS)
        n_chunks = max(1, refine_steps // chunk_size)
        # Per-candidate total budget for the refinement phase (from Angio).
        # For withered candidates this is 0, so they stay at final1.
        per_cand_budget = np.zeros(B, dtype=np.int32)
        for res in flow.resources:
            per_cand_budget[res.index] = res.steps_budget

        # Start state/phase from screening results.
        phase_series = np.zeros((B, steps), dtype=np.float32)
        phase_series[:, :screen_steps] = phase1
        # Running phase tail; will be written progressively per chunk.
        refine_phase = np.zeros((B, n_chunks * chunk_size), dtype=np.float32)

        if use_torch:
            cur_state_t = final1_t   # full (B, ...) — keep everyone present
            cur_state_np = None
        else:
            cur_state_np = final1    # full (B, ...)
            cur_state_t = None

        steps_done_at_end = 0
        last_phase_per_cand = phase1[:, -1].copy()   # carry-forward for frozen

        for chunk_idx in range(n_chunks):
            chunk_start_step = chunk_idx * chunk_size
            chunk_end_step = chunk_start_step + chunk_size
            # Cohort = alive candidates with remaining budget ≥ next chunk's
            # minimum steps (we require steps_budget to cover up to the END
            # of this chunk, so refine candidates drop out gracefully).
            cohort = [
                i for i in alive_idx
                if per_cand_budget[i] >= chunk_end_step
            ]
            if not cohort:
                # Fill remaining refine_phase with carry-forward for everyone
                for i in range(B):
                    refine_phase[i, chunk_start_step:] = last_phase_per_cand[i]
                break

            if use_torch:
                state_cohort = _subset_state(cur_state_t, cohort)
                carr_cohort  = _subset_carr(carr_t, cohort, B)
                state_cohort_new, phase_chunk_t = _torch_rollout(
                    state_cohort, carr_cohort, dt, DX, DY, chunk_size,
                    step_offset=screen_steps + chunk_start_step,
                    total_steps=steps,
                )
                phase_chunk = phase_chunk_t.cpu().numpy()
                # Merge cohort back into full B-dim state
                cur_state_t = _merge_states(cur_state_t, state_cohort_new, cohort, B)
            else:
                state_cohort = _subset_state(cur_state_np, cohort)
                carr_cohort  = _subset_carr(carr_np, cohort, B)
                state_cohort_new, phase_chunk = unified_rollout(
                    state_cohort, carr_cohort, dt, DX, DY, chunk_size,
                    step_offset=screen_steps + chunk_start_step,
                    total_steps=steps,
                )
                cur_state_np = _merge_states(cur_state_np, state_cohort_new, cohort, B)

            # Fill in per-step phase for cohort members; carry-forward for others
            for k, cand_idx in enumerate(cohort):
                refine_phase[cand_idx, chunk_start_step:chunk_end_step] = phase_chunk[k]
                last_phase_per_cand[cand_idx] = phase_chunk[k, -1]
            for i in range(B):
                if i in cohort:
                    continue
                refine_phase[i, chunk_start_step:chunk_end_step] = last_phase_per_cand[i]

            steps_done_at_end = chunk_end_step

        # If we ended before filling all n_chunks*chunk_size, carry-forward remainder
        if steps_done_at_end < n_chunks * chunk_size:
            for i in range(B):
                refine_phase[i, steps_done_at_end:] = last_phase_per_cand[i]

        # Trim phase_series refinement segment to the configured refine_steps
        tail = refine_phase[:, :refine_steps] if n_chunks * chunk_size >= refine_steps \
            else np.pad(refine_phase, ((0, 0), (0, refine_steps - n_chunks * chunk_size)),
                         mode="edge")
        phase_series[:, screen_steps:] = tail

        # Final state: whatever was merged up to the last executed chunk.
        if use_torch:
            final = _state_to_numpy(cur_state_t)
        else:
            final = cur_state_np
    else:
        # No alive branches or no refinement steps — pad phase_series to full width
        pad = np.zeros((B, refine_steps), dtype=np.float32)
        for i in range(B):
            pad[i, :] = phase1[i, -1]
        phase_series = np.concatenate([phase1, pad], axis=1)
        final = final1

    breakdown = score_candidate_breakdown(final, phase_series, carr, seed)
    scores   = breakdown.score
    statuses = classify_relative(scores)
    hydro    = td_hydro_control(scores)
    hydro["pruned_count"] = len(pruned_idx)
    hydro["reflow_bonus"] = float(flow.reflow_bonus)
    hydro["alive_count"]  = len(alive_idx)

    # Diversity gate: per (family, n) keep only the best representative,
    # then global top-k. Prevents a single family (typically batch, which
    # carries the anchor prior + larger candidate count) from sinking all
    # top-k slots. batch remains the reality anchor — it doesn't get
    # deleted, it just stops being a ranking black hole.
    group_best: Dict[tuple, int] = {}
    for i, c in enumerate(candidates):
        key = (c["family"], c["params"].get("n"))
        if key not in group_best or scores[i] > scores[group_best[key]]:
            group_best[key] = i
    reduced_idx = sorted(group_best.values(),
                          key=lambda j: scores[j], reverse=True)
    top_idx = reduced_idx[:top_k]
    hydro["diversity_groups_pre_gate"] = len(group_best)
    hydro["top_k_family_counts"] = _family_counts([candidates[i]["family"] for i in top_idx])

    top_results: List[EvaluationResult] = []
    for i in top_idx:
        c = candidates[i]
        p = c["params"]
        # Use the REAL score components, not reconstructed surrogates.
        # balanced_score  = final composite score
        # field_fit       = direct obs-match evidence in [0, 1]
        # risk            = p_blow in [0, 1]
        # stability       = repeatability in [0, 1]
        # feasibility     = phase_final (how close to reaching target phase)
        # nutrient_gain   = legacy — kept as simple A·rho·(1-σ) proxy
        sig = float(p["sigma"])
        rho = float(p["rho"])
        A   = float(p["A"])

        feasibility = float(np.clip(breakdown.phase_final[i], 0.0, 1.0))
        stability   = float(np.clip(breakdown.repeatability[i], 0.0, 1.0))
        field_fit   = float(np.clip(breakdown.field_fit[i], 0.0, 1.0))
        risk        = float(np.clip(breakdown.p_blow[i], 0.0, 1.0))
        nutrient    = float(np.clip(A * rho * (1 - sig), 0.0, 1.0))

        # weather_score / weather_alignment / final_balanced_score are
        # populated only by attach_weather_alignment. Default None so
        # downstream consumers can detect "not yet scored by physics".
        top_results.append(EvaluationResult(
            family=c["family"],
            template=c["template"],
            params={k: p[k] for k in ("n", "rho", "A", "sigma")},
            feasibility=feasibility,
            stability=stability,
            field_fit=field_fit,
            risk=risk,
            balanced_score=float(scores[i]),
            nutrient_gain=nutrient,
            branch_status=statuses[i],
            weather_score=None,
            weather_alignment=None,
            final_balanced_score=None,
        ))

    return top_results, hydro


def _family_counts(names) -> Dict[str, int]:
    """Small helper — counts per family name (used by hydro diagnostics)."""
    counts: Dict[str, int] = {}
    for n in names:
        counts[n] = counts.get(n, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Forecast-evidence interface — internal replacement for the outer-script
# day-1 score_state loop that previously computed weather_alignment inputs.
# ---------------------------------------------------------------------------
def forecast_evidence(state: UnifiedState) -> np.ndarray:
    """Per-candidate forecast-skill evidence in [0, 1].

    Computed from the field-wise RMS error relative to state.obs_*,
    normalised by the obs field's own amplitude (absolute, not min-max
    batch-relative). Higher = better fit.

    Used by attach_weather_alignment to derive weather_score /
    weather_alignment / final_balanced_score from a post-rollout
    UnifiedState directly — no dependence on the caller computing
    their own scoring function.
    """
    def _np(x):
        return x.cpu().numpy() if hasattr(x, "cpu") else np.asarray(x)

    h    = _np(state.h);     obs_h = _np(state.obs_h)
    T    = _np(state.T);     obs_T = _np(state.obs_T)
    q    = _np(state.q);     obs_q = _np(state.obs_q)
    u    = _np(state.u);     obs_u = _np(state.obs_u)
    v    = _np(state.v);     obs_v = _np(state.obs_v)

    h_err = np.sqrt(((h - obs_h[None]) ** 2).mean(axis=(-2, -1)))
    T_err = np.sqrt(((T - obs_T[None]) ** 2).mean(axis=(-2, -1)))
    q_err = np.sqrt(((q - obs_q[None]) ** 2).mean(axis=(-2, -1)))
    w_err = np.sqrt(((u - obs_u[None]) ** 2
                     + (v - obs_v[None]) ** 2).mean(axis=(-2, -1)))

    h_amp = float(np.std(obs_h)) + 1e-6
    T_amp = float(np.std(obs_T)) + 1e-6
    q_amp = float(np.std(obs_q)) + 1e-9
    w_amp = float(np.sqrt(np.mean(obs_u ** 2 + obs_v ** 2))) + 1e-3

    total = (0.35 * (h_err / h_amp) + 0.30 * (T_err / T_amp)
             + 0.20 * (q_err / q_amp) + 0.15 * (w_err / w_amp))
    evidence = 1.0 / (1.0 + total)
    return np.asarray(evidence, dtype=np.float64)


# ---------------------------------------------------------------------------
# Legacy shims
# ---------------------------------------------------------------------------
CandidateWorldline = EvaluationResult

def generate_worldlines(seed: ProblemSeed, bg: ProblemBackground):
    return generate_candidates(seed, bg)

def evaluate_worldline(seed, field, w):
    from .background_inference import infer_problem_background
    bg = infer_problem_background(seed)
    results, _ = run_tree_diagram(seed, bg, NX=8, NY=8, steps=1, top_k=1)
    return results[0] if results else None

def attach_weather_alignment(results, weather_scores_or_state):
    """Attach per-worldline weather evidence and derived alignments to results.

    Two modes:
      1. weather_scores_or_state is a UnifiedState → compute evidence
         internally via forecast_evidence(state). This is the TD-native path:
         weather rollout produces evidence directly from physics, no external
         scoring function needed.
      2. weather_scores_or_state is a sequence of floats → legacy path,
         caller computed scores externally.

    Mutates each EvaluationResult in place:
      - result.weather_score       ← raw score in [0, 1]
      - result.weather_alignment   ← normalised alignment in [-0.15, +0.10]
      - result.final_balanced_score ← balanced_score + weather_alignment

    Length mismatch (mode 2) raises ValueError.
    """
    if isinstance(weather_scores_or_state, UnifiedState):
        weather_scores = forecast_evidence(weather_scores_or_state)
    else:
        weather_scores = weather_scores_or_state

    if len(weather_scores) != len(results):
        raise ValueError(
            f"weather_scores length {len(weather_scores)} != results length {len(results)}"
        )
    from ..numerics.weather_bridge import weather_scores_to_alignments
    alignments = weather_scores_to_alignments(list(weather_scores))
    for r, s, a in zip(results, weather_scores, alignments):
        r.weather_score        = float(s)
        r.weather_alignment    = float(a)
        r.final_balanced_score = round(float(r.balanced_score) + float(a), 6)
    return results
