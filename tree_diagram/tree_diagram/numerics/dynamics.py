"""Weather dynamics — 带物理护栏的 integrator（Held-Suarez + Smagorinsky 校准）。

此模块是 TD 的 weather 分支的单一真相源。早期 demo 版 branch_step 会漂到
43°C（T/q/wind 无约束），后来按 GPT 六刀修复 + Held-Suarez/Smagorinsky
校准。本次重构合并 dynamics.py / dynamics_safe.py 两条线，去掉 legacy。

包含：
  - 低层数值算子（grad/lap/bilinear_sample/semi_lagrangian/smooth）
  - Tetens 饱和比湿
  - CFL 自适应 dt
  - Newtonian cooling / humidity relaxation (H-S 1994 标准松弛时间)
  - Latent heating budget（step / hour cap）
  - Smagorinsky 子网格粘性
  - T = T_ref + T' 异常量分解
  - branch_step（集成所有护栏，返回 tuple[state, budget]）
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .forcing import GridConfig
from .weather_state import WeatherState
from ._xp import get_xp


# ====================================================================
# Section 1 — 低层数值算子（numpy/cupy dispatch via get_xp）
# ====================================================================

def lap(f, DX: float, DY: float):
    xp = get_xp(f)
    return (
        (xp.roll(f, -1, axis=1) - 2.0 * f + xp.roll(f, 1, axis=1)) / (DX * DX)
        + (xp.roll(f, -1, axis=0) - 2.0 * f + xp.roll(f, 1, axis=0)) / (DY * DY)
    )


def grad_x(f, DX: float):
    xp = get_xp(f)
    return (xp.roll(f, -1, axis=1) - xp.roll(f, 1, axis=1)) / (2.0 * DX)


def grad_y(f, DY: float):
    xp = get_xp(f)
    return (xp.roll(f, -1, axis=0) - xp.roll(f, 1, axis=0)) / (2.0 * DY)


def bilinear_sample(field, px, py):
    xp = get_xp(field)
    NY, NX = field.shape
    px = xp.clip(px, 0.0, NX - 1.0)
    py = xp.clip(py, 0.0, NY - 1.0)
    ix = xp.floor(px).astype(int)
    iy = xp.floor(py).astype(int)
    fx = px - ix
    fy = py - iy
    ix1 = xp.clip(ix + 1, 0, NX - 1)
    iy1 = xp.clip(iy + 1, 0, NY - 1)
    return (
        (1.0 - fx) * (1.0 - fy) * field[iy,  ix ]
        +       fx  * (1.0 - fy) * field[iy,  ix1]
        + (1.0 - fx) *       fy  * field[iy1, ix ]
        +       fx  *       fy  * field[iy1, ix1]
    )


def semi_lagrangian(field, u, v,
                    dt: float, DX: float, DY: float):
    xp = get_xp(field)
    NY, NX = field.shape
    jj, ii = xp.mgrid[0:NY, 0:NX]
    jj = jj.astype(float)
    ii = ii.astype(float)
    px = ii - u * dt / DX
    py = jj - v * dt / DY
    return bilinear_sample(field, px, py)


def smooth(field, alpha: float = 0.10):
    xp = get_xp(field)
    neighbors = (
        xp.roll(field, -1, axis=0) + xp.roll(field, 1, axis=0)
        + xp.roll(field, -1, axis=1) + xp.roll(field, 1, axis=1)
    )
    return (1.0 - alpha) * field + alpha * 0.25 * neighbors


# ====================================================================
# Section 2 — 物理限幅常数（Held-Suarez + Smagorinsky）
# ====================================================================

T_PRIME_CLIP_K          = 25.0
U_CLIP_MS               = 35.0
Q_MIN                   = 1e-6
Q_MAX_SCALAR            = 0.030
LATENT_HEATING_STEP_K   = 0.5
LATENT_HEATING_HOUR_K   = 5.0
CFL_FACTOR              = 0.40
TAU_T_SEC               = 15 * 86400.0
TAU_Q_SEC               = 7 * 86400.0
TAU_FRICTION_SEC        = 1.0 * 86400.0   # 24h — compromise: damps inertial oscillation within ~1.4 periods, preserves wind magnitude on multi-day free integration (12h was too aggressive, 5d too weak)
SMAGORINSKY_C           = 0.17
SMAGORINSKY_MIN_NU      = 100.0
SMAGORINSKY_MAX_NU      = 5.0e4

# Radiative cooling rate — mid-tropospheric IR emission to space.
# Held-Suarez / SWAMPE standard: ~1.5 K/day in free troposphere, balances
# condensational latent heating on multi-day timescale. Without this, free
# integration runs away to condensation-driven warm equilibrium. Exposed
# as module-level for sweep tuning.
T_RAD_COOL_K_PER_DAY    = 1.5

# Condensation relaxation timescale — supersaturated q condenses over τ,
# not one-shot per step. Real cloud microphysics timescales are ~10-30 min.
# Old code released all excess-capped-by-T in a single step, creating sharp
# Day-2 spikes in free integration. Exponential relaxation smears the release.
TAU_CONDENSE_SEC        = 600.0

# Kessler-style warm-rain autoconversion (1969): cloud water above threshold
# precipitates out linearly, leaving the system permanently. Prevents RH from
# pinning at 100% during multi-day free integration.
# Classical parameters (Kessler 1969, AMS 2004 review): a_K ≈ 1e-3/s, q_c ≈ 1 g/kg.
Q_PRECIP_THRESHOLD_KGKG = 0.001
TAU_PRECIP_SEC          = 1000.0


# ====================================================================
# Section 3 — 物理子模块
# ====================================================================

def saturation_q_tetens(T_K, p_hpa: float = 500.0):
    xp = get_xp(T_K)
    T_C = T_K - 273.15
    e_sat_hpa = 6.112 * xp.exp(17.67 * T_C / (T_C + 243.5))
    e_sat_hpa = xp.minimum(e_sat_hpa, 0.9 * p_hpa)
    return 0.622 * e_sat_hpa / (p_hpa - e_sat_hpa)


def compute_cfl_dt(u, v, DX: float, DY: float,
                   dt_target: float, cfl: float = CFL_FACTOR,
                   c_gravity: float = 0.0) -> tuple[float, int]:
    """CFL for shallow water: must include gravity wave speed c = sqrt(g*h),
    not just advection. Without c_gravity the scheme is numerically unstable
    on fine grids (DX ≤ ~12km) regardless of wind magnitude — any perturbation
    excites gravity waves that grow to clip bounds (±35 m/s)."""
    xp = get_xp(u)
    u_max = float(xp.max(xp.abs(u))) + 1e-6
    v_max = float(xp.max(xp.abs(v))) + 1e-6
    # Effective wave speed = advection + gravity wave
    u_eff = u_max + c_gravity
    v_eff = v_max + c_gravity
    dt_cfl = cfl * min(DX / u_eff, DY / v_eff)
    if dt_target <= dt_cfl:
        return dt_target, 1
    n = int(np.ceil(dt_target / dt_cfl))
    return dt_target / n, n


@dataclass
class LatentHeatingBudget:
    hour_accumulator_K: np.ndarray
    hour_counter_steps: int
    steps_per_hour: int
    step_cap_K: float = LATENT_HEATING_STEP_K
    hour_cap_K: float = LATENT_HEATING_HOUR_K


def condensation_limited(T, q, humid_couple: float,
                         LV: float, CP: float,
                         budget: LatentHeatingBudget,
                         sub_dt: float = 60.0):
    """Relaxation-based condensation: excess_q decays toward 0 with τ = TAU_CONDENSE_SEC.

    Per step: fraction released = 1 - exp(-sub_dt/τ). Safety caps (step_cap_K,
    hour_cap_K) still apply as upper bounds on dT, protecting against
    pathological excess bursts.
    """
    xp = get_xp(T)
    qs = saturation_q_tetens(T)
    q_target = qs * humid_couple
    excess = xp.maximum(0.0, q - q_target)
    import math as _math
    condense_frac = float(1.0 - _math.exp(-sub_dt / TAU_CONDENSE_SEC))
    q_released = excess * condense_frac
    dT_raw = (LV / CP) * q_released
    dT_step = xp.minimum(dT_raw, budget.step_cap_K)
    room = xp.maximum(0.0, budget.hour_cap_K - budget.hour_accumulator_K)
    dT_limited = xp.minimum(dT_step, room)
    # Track what fraction of the already-scaled release actually stuck
    frac = xp.where(dT_raw > 1e-10, dT_limited / xp.where(dT_raw > 1e-10, dT_raw, 1.0), 0.0)
    excess_used = q_released * frac
    q_new = q - excess_used
    T_new = T + dT_limited
    # Kessler autoconversion: q above threshold drains as precipitation,
    # leaving the system. Prevents indefinite RH=100% pinning in free integration.
    precip_excess = xp.maximum(0.0, q_new - Q_PRECIP_THRESHOLD_KGKG)
    precip = precip_excess * float(sub_dt / TAU_PRECIP_SEC)
    q_new = q_new - precip
    budget.hour_accumulator_K = budget.hour_accumulator_K + dT_limited
    budget.hour_counter_steps += 1
    if budget.hour_counter_steps >= budget.steps_per_hour:
        budget.hour_accumulator_K = xp.zeros_like(budget.hour_accumulator_K)
        budget.hour_counter_steps = 0
    return T_new, q_new


def combine_T_anomaly(T_prime, T_ref):
    xp = get_xp(T_prime)
    return T_ref + xp.clip(T_prime, -T_PRIME_CLIP_K, T_PRIME_CLIP_K)


def smagorinsky_nu(u, v, DX: float, DY: float,
                   C_smag: float = SMAGORINSKY_C):
    xp = get_xp(u)
    dudx = grad_x(u, DX); dudy = grad_y(u, DY)
    dvdx = grad_x(v, DX); dvdy = grad_y(v, DY)
    S_norm = xp.sqrt(2.0 * (dudx**2 + dvdy**2) + (dudy + dvdx)**2 + 1e-12)
    Delta = float(np.sqrt(DX * DY))
    return xp.clip((C_smag * Delta) ** 2 * S_norm, SMAGORINSKY_MIN_NU, SMAGORINSKY_MAX_NU)


def smagorinsky_diffusion(field, nu_field,
                          DX: float, DY: float):
    return grad_x(nu_field * grad_x(field, DX), DX) + grad_y(nu_field * grad_y(field, DY), DY)


# ====================================================================
# Section 4 — 主积分步
# ====================================================================

def branch_step(
    state: WeatherState,
    params: dict,
    obs: WeatherState,
    topography: np.ndarray,
    cfg: GridConfig,
    budget: LatentHeatingBudget | None = None,
) -> tuple[WeatherState, LatentHeatingBudget]:
    """Single weather-integrator step with all physical guardrails.

    Returns (state, budget). If budget is None, a fresh one is created.
    Caller typically loops:
        budget = None
        for _ in range(cfg.STEPS):
            state, budget = branch_step(state, params, obs, topo, cfg, budget)
    """
    drag = params["drag"]
    humid_couple = params["humid_couple"]
    nudging = params["nudging"]
    pg_scale = params["pg_scale"]

    DX, DY = cfg.DX, cfg.DY
    G, F0 = cfg.G, cfg.F0
    LV, CP = cfg.LV, cfg.CP

    h, u, v, T, q = state.h, state.u, state.v, state.T, state.q
    xp = get_xp(h)

    c_g = float(np.sqrt(G * cfg.BASE_H))
    dt_safe, n_substeps = compute_cfl_dt(u, v, DX, DY, cfg.DT, c_gravity=c_g)
    sub_dt = dt_safe

    if budget is None:
        steps_per_hour = max(1, int(3600.0 / cfg.DT))
        budget = LatentHeatingBudget(
            hour_accumulator_K=xp.zeros_like(T),
            hour_counter_steps=0,
            steps_per_hour=steps_per_hour,
        )

    T_ref = obs.T
    q_clim = obs.q

    for _ in range(n_substeps):
        nu_smag = smagorinsky_nu(u, v, DX, DY)

        h_adv = semi_lagrangian(h, u, v, sub_dt, DX, DY)
        u_adv = semi_lagrangian(u, u, v, sub_dt, DX, DY)
        v_adv = semi_lagrangian(v, u, v, sub_dt, DX, DY)
        T_adv = semi_lagrangian(T, u, v, sub_dt, DX, DY)
        q_adv = semi_lagrangian(q, u, v, sub_dt, DX, DY)

        dhdx = grad_x(h_adv, DX); dhdy = grad_y(h_adv, DY)
        dtopox = grad_x(topography, DX); dtopoy = grad_y(topography, DY)

        friction_rate = 1.0 / TAU_FRICTION_SEC + drag
        # Wind nudging (FDDA-style) — pulls (u,v) toward obs. Historically
        # absent: TD's wind was open-loop w.r.t. obs, which means direction
        # couldn't be discriminated by the ensemble. Gated by wind_nudge param
        # (default 0 = backward compat; ≈nudging for parity with T/q).
        wind_nudge = params.get("wind_nudge", 0.0)
        u_new = (u_adv - sub_dt * G * pg_scale * dhdx - sub_dt * G * 0.05 * dtopox
                 + sub_dt * F0 * v_adv - sub_dt * friction_rate * u_adv
                 + sub_dt * smagorinsky_diffusion(u_adv, nu_smag, DX, DY)
                 + sub_dt * wind_nudge * (obs.u - u_adv))
        v_new = (v_adv - sub_dt * G * pg_scale * dhdy - sub_dt * G * 0.05 * dtopoy
                 - sub_dt * F0 * u_adv - sub_dt * friction_rate * v_adv
                 + sub_dt * smagorinsky_diffusion(v_adv, nu_smag, DX, DY)
                 + sub_dt * wind_nudge * (obs.v - v_adv))

        div = grad_x(u_new, DX) + grad_y(v_new, DY)
        # h-nudging: without it, synoptic pressure anomaly from obs (encoded
        # as uniform h offset in build_taipei_state) can't propagate past
        # init, so multi-day forecasts with varying analog obs P all show
        # the same model h_center → bit-exact pressure output.
        h_nudge = params.get("h_nudge", 0.0)
        h_new = (h_adv - sub_dt * cfg.BASE_H * div
                 + sub_dt * smagorinsky_diffusion(h_adv, nu_smag, DX, DY)
                 + sub_dt * h_nudge * (obs.h - h_adv))

        T_diff = 0.3 * smagorinsky_diffusion(T_adv, nu_smag, DX, DY)
        T_nudge = nudging * (obs.T - T_adv)
        T_relax = -(T_adv - T_ref) / TAU_T_SEC
        # Radiative cooling — balances condensational latent heating. Read
        # module-global so sweep can tune it per-task.
        T_rad = -T_RAD_COOL_K_PER_DAY / 86400.0
        T_new = T_adv + sub_dt * (T_diff + T_nudge + T_relax + T_rad)

        q_diff = 0.5 * smagorinsky_diffusion(q_adv, nu_smag, DX, DY)
        q_nudge = nudging * (obs.q - q_adv)
        q_relax = -(q_adv - q_clim) / TAU_Q_SEC
        q_new = q_adv + sub_dt * (q_diff + q_nudge + q_relax)

        T_new, q_new = condensation_limited(T_new, q_new, humid_couple, LV, CP, budget, sub_dt)

        h_new = smooth(h_new, alpha=0.05)
        u_new = smooth(u_new, alpha=0.05)
        v_new = smooth(v_new, alpha=0.05)
        T_new = smooth(T_new, alpha=0.05)
        q_new = smooth(q_new, alpha=0.05)

        h_new = xp.clip(h_new, cfg.BASE_H - 1500.0, cfg.BASE_H + 1500.0)
        u_new = xp.clip(u_new, -U_CLIP_MS, U_CLIP_MS)
        v_new = xp.clip(v_new, -U_CLIP_MS, U_CLIP_MS)
        q_new = xp.clip(q_new, Q_MIN, Q_MAX_SCALAR)
        T_new = combine_T_anomaly(T_new - T_ref, T_ref)

        h, u, v, T, q = h_new, u_new, v_new, T_new, q_new

    return WeatherState(h=h, u=u, v=v, T=T, q=q), budget
