"""Batched branch_step — evaluates all ensemble families in one tensor call.

Goal: amortize GPU kernel-launch overhead by processing 6 families simultaneously.
State arrays become (B, NY, NX) instead of (NY, NX). Each op runs on the
full tensor; launch count drops from 6× to 1×.

This is a specialized path for ensemble sweeps. The scalar-branch
dynamics.branch_step remains the reference implementation — this module mirrors
its physics step-for-step but with a batched tensor layout.

Key constraints:
  - obs (WeatherState) is shared across batch — its fields stay 2D
  - topography is 2D, broadcasts against batched state
  - Each family has its own physics params; params dict takes array of shape (B,)
  - Latent-heat accumulator becomes batched (B, NY, NX)
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

from .forcing import GridConfig
from .weather_state import WeatherState
from ._xp import get_xp
from .dynamics import (
    T_PRIME_CLIP_K, U_CLIP_MS, Q_MIN, Q_MAX_SCALAR,
    LATENT_HEATING_STEP_K, LATENT_HEATING_HOUR_K,
    CFL_FACTOR, TAU_T_SEC, TAU_Q_SEC, TAU_FRICTION_SEC,
    SMAGORINSKY_C, SMAGORINSKY_MIN_NU, SMAGORINSKY_MAX_NU,
    T_RAD_COOL_K_PER_DAY, TAU_CONDENSE_SEC,
    Q_PRECIP_THRESHOLD_KGKG, TAU_PRECIP_SEC,
)
from . import dynamics as _dyn


# --------------------------------------------------------------------------
# Low-level ops — axis-agnostic variants (work on 2D or 3D tensors)
# --------------------------------------------------------------------------

def _roll_x(f, shift, xp):
    return xp.roll(f, shift, axis=-1)

def _roll_y(f, shift, xp):
    return xp.roll(f, shift, axis=-2)

def _grad_x(f, DX):
    xp = get_xp(f)
    return (_roll_x(f, -1, xp) - _roll_x(f, 1, xp)) / (2.0 * DX)

def _grad_y(f, DY):
    xp = get_xp(f)
    return (_roll_y(f, -1, xp) - _roll_y(f, 1, xp)) / (2.0 * DY)

def _smooth(field, alpha=0.05):
    xp = get_xp(field)
    neighbors = (_roll_x(field, -1, xp) + _roll_x(field, 1, xp)
                 + _roll_y(field, -1, xp) + _roll_y(field, 1, xp))
    return (1.0 - alpha) * field + alpha * 0.25 * neighbors

def _smag_diffusion(field, nu, DX, DY):
    return _grad_x(nu * _grad_x(field, DX), DX) + _grad_y(nu * _grad_y(field, DY), DY)


def _bilinear_sample_batched(field, px, py):
    """field: (B, NY, NX). px, py: (B, NY, NX). Returns (B, NY, NX)."""
    xp = get_xp(field)
    B, NY, NX = field.shape
    px = xp.clip(px, 0.0, NX - 1.0)
    py = xp.clip(py, 0.0, NY - 1.0)
    ix = xp.floor(px).astype(xp.int64)
    iy = xp.floor(py).astype(xp.int64)
    fx = px - ix
    fy = py - iy
    ix1 = xp.clip(ix + 1, 0, NX - 1)
    iy1 = xp.clip(iy + 1, 0, NY - 1)
    b = xp.arange(B, dtype=xp.int64).reshape(-1, 1, 1)
    v00 = field[b, iy,  ix]
    v01 = field[b, iy,  ix1]
    v10 = field[b, iy1, ix]
    v11 = field[b, iy1, ix1]
    return ((1.0 - fx) * (1.0 - fy) * v00
            + fx * (1.0 - fy) * v01
            + (1.0 - fx) * fy  * v10
            + fx * fy  * v11)


def _semi_lagrangian_batched(field, u, v, dt, DX, DY):
    """All of shape (B, NY, NX). Returns (B, NY, NX)."""
    xp = get_xp(field)
    B, NY, NX = field.shape
    jj, ii = xp.mgrid[0:NY, 0:NX]
    jj = jj.astype(xp.float64); ii = ii.astype(xp.float64)
    px = ii - u * dt / DX
    py = jj - v * dt / DY
    return _bilinear_sample_batched(field, px, py)


def _saturation_q(T_K, p_hpa=500.0):
    xp = get_xp(T_K)
    T_C = T_K - 273.15
    e_sat = 6.112 * xp.exp(17.67 * T_C / (T_C + 243.5))
    e_sat = xp.minimum(e_sat, 0.9 * p_hpa)
    return 0.622 * e_sat / (p_hpa - e_sat)


def _smag_nu_batched(u, v, DX, DY):
    xp = get_xp(u)
    dudx = _grad_x(u, DX); dudy = _grad_y(u, DY)
    dvdx = _grad_x(v, DX); dvdy = _grad_y(v, DY)
    S_norm = xp.sqrt(2.0 * (dudx**2 + dvdy**2) + (dudy + dvdx)**2 + 1e-12)
    Delta = float(np.sqrt(DX * DY))
    return xp.clip((SMAGORINSKY_C * Delta) ** 2 * S_norm,
                   SMAGORINSKY_MIN_NU, SMAGORINSKY_MAX_NU)


# --------------------------------------------------------------------------
# Batched step
# --------------------------------------------------------------------------

@dataclass
class BatchedBudget:
    hour_accumulator_K: np.ndarray   # (B, NY, NX)
    hour_counter_steps: int
    steps_per_hour: int
    step_cap_K: float = LATENT_HEATING_STEP_K
    hour_cap_K: float = LATENT_HEATING_HOUR_K


def _condensation_limited_batched(T, q, humid_couple_bc, LV, CP, budget, sub_dt: float):
    """T,q: (B,NY,NX). humid_couple_bc: (B,1,1). τ-relaxed condensation."""
    xp = get_xp(T)
    qs = _saturation_q(T)
    q_target = qs * humid_couple_bc
    excess = xp.maximum(0.0, q - q_target)
    condense_frac = float(1.0 - np.exp(-sub_dt / TAU_CONDENSE_SEC))
    q_released = excess * condense_frac
    dT_raw = (LV / CP) * q_released
    dT_step = xp.minimum(dT_raw, budget.step_cap_K)
    room = xp.maximum(0.0, budget.hour_cap_K - budget.hour_accumulator_K)
    dT_limited = xp.minimum(dT_step, room)
    safe_dT_raw = xp.where(dT_raw > 1e-10, dT_raw, 1.0)
    frac = xp.where(dT_raw > 1e-10, dT_limited / safe_dT_raw, 0.0)
    excess_used = q_released * frac
    q_new = q - excess_used
    T_new = T + dT_limited
    # Kessler precip drain
    precip_excess = xp.maximum(0.0, q_new - Q_PRECIP_THRESHOLD_KGKG)
    precip = precip_excess * float(sub_dt / TAU_PRECIP_SEC)
    q_new = q_new - precip
    budget.hour_accumulator_K = budget.hour_accumulator_K + dT_limited
    budget.hour_counter_steps += 1
    if budget.hour_counter_steps >= budget.steps_per_hour:
        budget.hour_accumulator_K = xp.zeros_like(budget.hour_accumulator_K)
        budget.hour_counter_steps = 0
    return T_new, q_new


def _combine_T_anom(T_prime, T_ref):
    xp = get_xp(T_prime)
    return T_ref + xp.clip(T_prime, -T_PRIME_CLIP_K, T_PRIME_CLIP_K)


def _to_b11(xp, vec, B):
    """Convert a (B,) array or Python list to (B,1,1) tensor."""
    arr = xp.asarray(vec, dtype=xp.float64).reshape(B, 1, 1)
    return arr


def batched_branch_step(state_b: WeatherState, params_b: dict,
                         obs: WeatherState, topography, cfg: GridConfig,
                         budget: BatchedBudget | None = None) -> tuple[WeatherState, BatchedBudget]:
    """Run one branch_step for all B families simultaneously.

    state_b: WeatherState with fields of shape (B, NY, NX).
    params_b: dict with keys drag/humid_couple/nudging/pg_scale/wind_nudge,
              each a (B,)-shape array (or Python list).
    obs, topography: 2D as usual (shared across batch).
    """
    xp = get_xp(state_b.h)
    B = state_b.h.shape[0]

    DX, DY = cfg.DX, cfg.DY
    G, F0 = cfg.G, cfg.F0
    LV, CP = cfg.LV, cfg.CP

    drag_bc         = _to_b11(xp, params_b["drag"], B)
    humid_couple_bc = _to_b11(xp, params_b["humid_couple"], B)
    nudging_bc      = _to_b11(xp, params_b["nudging"], B)
    pg_scale_bc     = _to_b11(xp, params_b["pg_scale"], B)
    wind_nudge_bc   = _to_b11(xp, params_b.get("wind_nudge", [0.0] * B), B)
    h_nudge_bc      = _to_b11(xp, params_b.get("h_nudge", [0.0] * B), B)

    h, u, v, T, q = state_b.h, state_b.u, state_b.v, state_b.T, state_b.q

    # CFL: gravity wave speed included (shallow water requires c_g = sqrt(g*h))
    u_max = float(xp.max(xp.abs(u))) + 1e-6
    v_max = float(xp.max(xp.abs(v))) + 1e-6
    c_g = float(np.sqrt(G * cfg.BASE_H))
    dt_cfl = CFL_FACTOR * min(DX / (u_max + c_g), DY / (v_max + c_g))
    if cfg.DT <= dt_cfl:
        sub_dt, n_sub = cfg.DT, 1
    else:
        n_sub = int(np.ceil(cfg.DT / dt_cfl))
        sub_dt = cfg.DT / n_sub

    if budget is None:
        steps_per_hour = max(1, int(3600.0 / cfg.DT))
        budget = BatchedBudget(
            hour_accumulator_K=xp.zeros_like(T),
            hour_counter_steps=0,
            steps_per_hour=steps_per_hour,
        )

    T_ref = obs.T       # (NY, NX), broadcasts
    q_clim = obs.q

    dtopox = _grad_x(topography, DX)
    dtopoy = _grad_y(topography, DY)

    for _ in range(n_sub):
        nu_smag = _smag_nu_batched(u, v, DX, DY)

        h_adv = _semi_lagrangian_batched(h, u, v, sub_dt, DX, DY)
        u_adv = _semi_lagrangian_batched(u, u, v, sub_dt, DX, DY)
        v_adv = _semi_lagrangian_batched(v, u, v, sub_dt, DX, DY)
        T_adv = _semi_lagrangian_batched(T, u, v, sub_dt, DX, DY)
        q_adv = _semi_lagrangian_batched(q, u, v, sub_dt, DX, DY)

        dhdx = _grad_x(h_adv, DX); dhdy = _grad_y(h_adv, DY)
        friction_rate = 1.0 / TAU_FRICTION_SEC + drag_bc

        u_new = (u_adv - sub_dt * G * pg_scale_bc * dhdx - sub_dt * G * 0.05 * dtopox
                 + sub_dt * F0 * v_adv - sub_dt * friction_rate * u_adv
                 + sub_dt * _smag_diffusion(u_adv, nu_smag, DX, DY)
                 + sub_dt * wind_nudge_bc * (obs.u - u_adv))
        v_new = (v_adv - sub_dt * G * pg_scale_bc * dhdy - sub_dt * G * 0.05 * dtopoy
                 - sub_dt * F0 * u_adv - sub_dt * friction_rate * v_adv
                 + sub_dt * _smag_diffusion(v_adv, nu_smag, DX, DY)
                 + sub_dt * wind_nudge_bc * (obs.v - v_adv))

        div = _grad_x(u_new, DX) + _grad_y(v_new, DY)
        h_new = (h_adv - sub_dt * cfg.BASE_H * div
                 + sub_dt * _smag_diffusion(h_adv, nu_smag, DX, DY)
                 + sub_dt * h_nudge_bc * (obs.h - h_adv))

        T_diff = 0.3 * _smag_diffusion(T_adv, nu_smag, DX, DY)
        T_nudge = nudging_bc * (obs.T - T_adv)
        T_relax = -(T_adv - T_ref) / TAU_T_SEC
        T_rad = -_dyn.T_RAD_COOL_K_PER_DAY / 86400.0
        T_new = T_adv + sub_dt * (T_diff + T_nudge + T_relax + T_rad)

        q_diff = 0.5 * _smag_diffusion(q_adv, nu_smag, DX, DY)
        q_nudge = nudging_bc * (obs.q - q_adv)
        q_relax = -(q_adv - q_clim) / TAU_Q_SEC
        q_new = q_adv + sub_dt * (q_diff + q_nudge + q_relax)

        T_new, q_new = _condensation_limited_batched(T_new, q_new, humid_couple_bc,
                                                      LV, CP, budget, sub_dt)

        h_new = _smooth(h_new)
        u_new = _smooth(u_new)
        v_new = _smooth(v_new)
        T_new = _smooth(T_new)
        q_new = _smooth(q_new)

        h_new = xp.clip(h_new, cfg.BASE_H - 1500.0, cfg.BASE_H + 1500.0)
        u_new = xp.clip(u_new, -U_CLIP_MS, U_CLIP_MS)
        v_new = xp.clip(v_new, -U_CLIP_MS, U_CLIP_MS)
        q_new = xp.clip(q_new, Q_MIN, Q_MAX_SCALAR)
        T_new = _combine_T_anom(T_new - T_ref, T_ref)

        h, u, v, T, q = h_new, u_new, v_new, T_new, q_new

    return WeatherState(h=h, u=u, v=v, T=T, q=q), budget


def stack_families(states: list[WeatherState]) -> WeatherState:
    """Stack a list of per-family 2D WeatherStates into one batched (B,NY,NX)."""
    xp = get_xp(states[0].h)
    return WeatherState(
        h=xp.stack([s.h for s in states]),
        u=xp.stack([s.u for s in states]),
        v=xp.stack([s.v for s in states]),
        T=xp.stack([s.T for s in states]),
        q=xp.stack([s.q for s in states]),
    )


def unstack_families(state_b: WeatherState) -> list[WeatherState]:
    """Inverse of stack_families: split (B,NY,NX) back into B x (NY,NX)."""
    B = state_b.h.shape[0]
    return [WeatherState(h=state_b.h[i], u=state_b.u[i], v=state_b.v[i],
                          T=state_b.T[i], q=state_b.q[i]) for i in range(B)]
