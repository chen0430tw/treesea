"""Safe dynamics — 带物理护栏的 weather integrator。

针对旧 dynamics.py 会漂到 43°C 的病灶，按 GPT 方案给 6 刀修复：

  1. T 异常量分解：T = T_ref + T'，只积分 T'，硬 clip ±8 K
  2. T' / q / u / v 全加 clip
  3. Newtonian cooling + humidity relaxation（回气候态弹簧）
  4. q_sat 饱和约束 + latent heating 限幅（0.15 K/step, 1.5 K/hour）
  5. CFL 自适应 dt（C=0.4）
  6. 更准确的 Tetens 饱和比湿

实际使用：
  from .dynamics_safe import branch_step_safe
  state = branch_step_safe(state, params, obs, topography, cfg)

安全版本不破坏向后兼容——旧 branch_step 仍存在于 dynamics.py。
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .forcing import GridConfig
from .weather_state import WeatherState
from .dynamics import grad_x, grad_y, lap, semi_lagrangian, smooth


# ────────────────────────────────────────────────────────────────────
# 物理限幅常数
# ────────────────────────────────────────────────────────────────────
T_PRIME_CLIP_K          = 8.0      # T 异常量硬限 ±8 K
U_CLIP_MS               = 20.0     # 风速分量硬限 ±20 m/s
Q_MIN                   = 1e-6
Q_MAX_SCALAR            = 0.030

# Latent heating 每步 / 每小时硬限
LATENT_HEATING_STEP_K   = 0.15
LATENT_HEATING_HOUR_K   = 1.5

# CFL 系数
CFL_FACTOR              = 0.40

# 松弛时间常数（秒）
TAU_T_SEC               = 12 * 3600.0   # 12 小时
TAU_Q_SEC               = 6 * 3600.0    # 6 小时


# ────────────────────────────────────────────────────────────────────
# Tetens 饱和比湿
# ────────────────────────────────────────────────────────────────────

def saturation_q_tetens(T_K: np.ndarray, p_hpa: float = 500.0) -> np.ndarray:
    """Tetens 饱和比湿 q_sat(T, p)。

    T_K: 温度 (K)
    p_hpa: 气压层 (hPa)，默认 500 hPa (TD 的内部层)

    返回：饱和比湿 (kg/kg)
    """
    T_C = T_K - 273.15
    # Tetens over water
    e_sat_hpa = 6.112 * np.exp(17.67 * T_C / (T_C + 243.5))
    # 避免 p - e_sat 过小
    e_sat_hpa = np.minimum(e_sat_hpa, 0.9 * p_hpa)
    q_sat = 0.622 * e_sat_hpa / (p_hpa - e_sat_hpa)
    return q_sat


# ────────────────────────────────────────────────────────────────────
# CFL 自适应 dt
# ────────────────────────────────────────────────────────────────────

def compute_cfl_dt(u: np.ndarray, v: np.ndarray, DX: float, DY: float,
                   dt_target: float, cfl: float = CFL_FACTOR) -> tuple[float, int]:
    """计算 CFL 安全 dt。返回 (dt_safe, n_substeps)。

    若 dt_target 超过 CFL 限制，拆分成 n_substeps 个小步。
    """
    u_max = float(np.max(np.abs(u))) + 1e-6
    v_max = float(np.max(np.abs(v))) + 1e-6
    dt_cfl = cfl * min(DX / u_max, DY / v_max)
    if dt_target <= dt_cfl:
        return dt_target, 1
    n = int(np.ceil(dt_target / dt_cfl))
    return dt_target / n, n


# ────────────────────────────────────────────────────────────────────
# 冷凝 + 有限幅 latent heating
# ────────────────────────────────────────────────────────────────────

@dataclass
class LatentHeatingBudget:
    """跟踪累计 latent heating 不超过每小时上限。"""
    hour_accumulator_K: np.ndarray
    hour_counter_steps: int
    steps_per_hour: int
    step_cap_K: float = LATENT_HEATING_STEP_K
    hour_cap_K: float = LATENT_HEATING_HOUR_K


def condensation_limited(
    T: np.ndarray,
    q: np.ndarray,
    humid_couple: float,
    LV: float,
    CP: float,
    budget: LatentHeatingBudget,
) -> tuple[np.ndarray, np.ndarray]:
    """饱和约束 + 限幅 latent heating。

    1. q = min(q, q_sat × humid_couple)
    2. excess = max(0, q - q_sat)
    3. ΔT_latent = (LV/CP) × excess，限到 step_cap_K
    4. 如果该格点累计已达 hour_cap_K，则 0
    5. q -= excess_used, T += ΔT_limited
    """
    qs = saturation_q_tetens(T)
    q_target = qs * humid_couple
    excess = np.maximum(0.0, q - q_target)

    # Raw latent heating
    dT_raw = (LV / CP) * excess

    # Step cap
    dT_step = np.minimum(dT_raw, budget.step_cap_K)

    # Hour cap (per gridpoint)
    room_this_hour = np.maximum(0.0, budget.hour_cap_K - budget.hour_accumulator_K)
    dT_limited = np.minimum(dT_step, room_this_hour)

    # Actual excess removed proportional to actual heating applied
    # ΔT_limited / dT_raw is the fraction applied
    with np.errstate(divide='ignore', invalid='ignore'):
        frac = np.where(dT_raw > 1e-10, dT_limited / dT_raw, 0.0)
    excess_used = excess * frac

    q_new = q - excess_used
    T_new = T + dT_limited

    # Update hour accumulator
    budget.hour_accumulator_K = budget.hour_accumulator_K + dT_limited
    budget.hour_counter_steps += 1
    if budget.hour_counter_steps >= budget.steps_per_hour:
        budget.hour_accumulator_K = np.zeros_like(budget.hour_accumulator_K)
        budget.hour_counter_steps = 0

    return T_new, q_new


# ────────────────────────────────────────────────────────────────────
# T_ref + T' 异常量分解
# ────────────────────────────────────────────────────────────────────

def split_T_anomaly(T: np.ndarray, T_ref: np.ndarray) -> np.ndarray:
    """T = T_ref + T'. Returns T_prime with clip."""
    T_prime = T - T_ref
    return np.clip(T_prime, -T_PRIME_CLIP_K, T_PRIME_CLIP_K)


def combine_T_anomaly(T_prime: np.ndarray, T_ref: np.ndarray) -> np.ndarray:
    return T_ref + np.clip(T_prime, -T_PRIME_CLIP_K, T_PRIME_CLIP_K)


# ────────────────────────────────────────────────────────────────────
# Safe branch step
# ────────────────────────────────────────────────────────────────────

def branch_step_safe(
    state: WeatherState,
    params: dict,
    obs: WeatherState,
    topography: np.ndarray,
    cfg: GridConfig,
    budget: LatentHeatingBudget | None = None,
) -> tuple[WeatherState, LatentHeatingBudget]:
    """Safe single-step weather integrator with six patches applied."""
    Kh = params["Kh"]
    Kt = params["Kt"]
    Kq = params["Kq"]
    drag = params["drag"]
    humid_couple = params["humid_couple"]
    nudging = params["nudging"]
    pg_scale = params["pg_scale"]

    DX = cfg.DX
    DY = cfg.DY
    G = cfg.G
    F0 = cfg.F0
    LV = cfg.LV
    CP = cfg.CP

    h = state.h
    u = state.u
    v = state.v
    T = state.T
    q = state.q

    # ── CFL 自适应 dt ────────────────────────────────────────────
    dt_safe, n_substeps = compute_cfl_dt(u, v, DX, DY, cfg.DT)
    sub_dt = dt_safe

    # ── latent heating budget ────────────────────────────────────
    if budget is None:
        steps_per_hour = max(1, int(3600.0 / cfg.DT))
        budget = LatentHeatingBudget(
            hour_accumulator_K=np.zeros_like(T),
            hour_counter_steps=0,
            steps_per_hour=steps_per_hour,
        )

    # ── T_ref = obs.T（气候态）──────────────────────────────────
    T_ref = obs.T
    q_clim = obs.q

    for _ in range(n_substeps):
        # Semi-Lagrangian advection
        h_adv = semi_lagrangian(h, u, v, sub_dt, DX, DY)
        u_adv = semi_lagrangian(u, u, v, sub_dt, DX, DY)
        v_adv = semi_lagrangian(v, u, v, sub_dt, DX, DY)
        T_adv = semi_lagrangian(T, u, v, sub_dt, DX, DY)
        q_adv = semi_lagrangian(q, u, v, sub_dt, DX, DY)

        # 压力梯度力
        dhdx = grad_x(h_adv, DX)
        dhdy = grad_y(h_adv, DY)
        dtopox = grad_x(topography, DX)
        dtopoy = grad_y(topography, DY)

        u_new = (
            u_adv
            - sub_dt * G * pg_scale * dhdx
            - sub_dt * G * 0.05 * dtopox
            + sub_dt * F0 * v_adv
            - sub_dt * drag * u_adv
            + sub_dt * Kh * lap(u_adv, DX, DY)
        )
        v_new = (
            v_adv
            - sub_dt * G * pg_scale * dhdy
            - sub_dt * G * 0.05 * dtopoy
            - sub_dt * F0 * u_adv
            - sub_dt * drag * v_adv
            + sub_dt * Kh * lap(v_adv, DX, DY)
        )

        # Height update
        div = grad_x(u_new, DX) + grad_y(v_new, DY)
        h_new = h_adv - sub_dt * cfg.BASE_H * div + sub_dt * Kh * lap(h_adv, DX, DY)

        # ── 温度：先按气候态松弛 + 扩散 + nudging ─────────────
        T_new = T_adv + sub_dt * Kt * lap(T_adv, DX, DY) + sub_dt * nudging * (obs.T - T_adv)
        # Newtonian cooling: T' → 0 with timescale τ_T
        T_prime_raw = T_new - T_ref
        T_new = T_ref + T_prime_raw * (1.0 - sub_dt / TAU_T_SEC)

        # ── 湿度：扩散 + nudging + 回气候态 ────────────────────
        q_new = q_adv + sub_dt * Kq * lap(q_adv, DX, DY) + sub_dt * nudging * (obs.q - q_adv)
        q_new = q_new - sub_dt * (q_new - q_clim) / TAU_Q_SEC

        # ── 饱和约束 + 限幅 latent heating ───────────────────
        T_new, q_new = condensation_limited(T_new, q_new, humid_couple, LV, CP, budget)

        # ── 平滑 ──────────────────────────────────────────────
        h_new = smooth(h_new)
        u_new = smooth(u_new)
        v_new = smooth(v_new)
        T_new = smooth(T_new)
        q_new = smooth(q_new)

        # ── 硬限 ──────────────────────────────────────────────
        h_new = np.clip(h_new, cfg.BASE_H - 1500.0, cfg.BASE_H + 1500.0)
        u_new = np.clip(u_new, -U_CLIP_MS, U_CLIP_MS)
        v_new = np.clip(v_new, -U_CLIP_MS, U_CLIP_MS)
        q_new = np.clip(q_new, Q_MIN, Q_MAX_SCALAR)
        # T 通过 T' clip 间接约束
        T_new = combine_T_anomaly(T_new - T_ref, T_ref)

        # 下一子步
        h, u, v, T, q = h_new, u_new, v_new, T_new, q_new

    return WeatherState(h=h, u=u, v=v, T=T, q=q), budget
