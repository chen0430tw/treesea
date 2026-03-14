from __future__ import annotations
import numpy as np

from .forcing import GridConfig
from .weather_state import WeatherState


# ---------------------------------------------------------------------------
# Spatial operators
# ---------------------------------------------------------------------------

def lap(f: np.ndarray, DX: float, DY: float) -> np.ndarray:
    return (
        (np.roll(f, -1, axis=1) - 2.0 * f + np.roll(f, 1, axis=1)) / (DX * DX)
        + (np.roll(f, -1, axis=0) - 2.0 * f + np.roll(f, 1, axis=0)) / (DY * DY)
    )


def grad_x(f: np.ndarray, DX: float) -> np.ndarray:
    return (np.roll(f, -1, axis=1) - np.roll(f, 1, axis=1)) / (2.0 * DX)


def grad_y(f: np.ndarray, DY: float) -> np.ndarray:
    return (np.roll(f, -1, axis=0) - np.roll(f, 1, axis=0)) / (2.0 * DY)


# ---------------------------------------------------------------------------
# Interpolation / advection
# ---------------------------------------------------------------------------

def bilinear_sample(field: np.ndarray, px: np.ndarray, py: np.ndarray) -> np.ndarray:
    NY, NX = field.shape
    px = np.clip(px, 0.0, NX - 1.0)
    py = np.clip(py, 0.0, NY - 1.0)
    ix = np.floor(px).astype(int)
    iy = np.floor(py).astype(int)
    fx = px - ix
    fy = py - iy
    ix1 = np.clip(ix + 1, 0, NX - 1)
    iy1 = np.clip(iy + 1, 0, NY - 1)
    return (
        (1.0 - fx) * (1.0 - fy) * field[iy,  ix ]
        +       fx  * (1.0 - fy) * field[iy,  ix1]
        + (1.0 - fx) *       fy  * field[iy1, ix ]
        +       fx  *       fy  * field[iy1, ix1]
    )


def semi_lagrangian(
    field: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    dt: float,
    DX: float,
    DY: float,
) -> np.ndarray:
    NY, NX = field.shape
    jj, ii = np.mgrid[0:NY, 0:NX].astype(float)
    px = ii - u * dt / DX
    py = jj - v * dt / DY
    return bilinear_sample(field, px, py)


# ---------------------------------------------------------------------------
# Smoothing
# ---------------------------------------------------------------------------

def smooth(field: np.ndarray, alpha: float = 0.10) -> np.ndarray:
    neighbors = (
        np.roll(field, -1, axis=0)
        + np.roll(field, 1, axis=0)
        + np.roll(field, -1, axis=1)
        + np.roll(field, 1, axis=1)
    )
    return (1.0 - alpha) * field + alpha * 0.25 * neighbors


# ---------------------------------------------------------------------------
# Microphysics
# ---------------------------------------------------------------------------

def saturation_specific_humidity(T: np.ndarray) -> np.ndarray:
    return 0.0045 * np.exp(0.060 * (T - 273.15) / 10.0)


def condensation_and_heating(
    T: np.ndarray,
    q: np.ndarray,
    humid_couple: float,
    LV: float,
    CP: float,
) -> tuple:
    qs = saturation_specific_humidity(T)
    excess = np.maximum(0.0, q - qs * humid_couple)
    q_new = q - excess
    T_new = T + (LV / CP) * excess
    return T_new, q_new


# ---------------------------------------------------------------------------
# Full branch physics step
# ---------------------------------------------------------------------------

def branch_step(
    state: WeatherState,
    params: dict,
    obs: WeatherState,
    topography: np.ndarray,
    cfg: GridConfig,
) -> WeatherState:
    Kh = params["Kh"]
    Kt = params["Kt"]
    Kq = params["Kq"]
    drag = params["drag"]
    humid_couple = params["humid_couple"]
    nudging = params["nudging"]
    pg_scale = params["pg_scale"]

    dt = cfg.DT
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

    # Semi-Lagrangian advection
    h_adv = semi_lagrangian(h, u, v, dt, DX, DY)
    u_adv = semi_lagrangian(u, u, v, dt, DX, DY)
    v_adv = semi_lagrangian(v, u, v, dt, DX, DY)
    T_adv = semi_lagrangian(T, u, v, dt, DX, DY)
    q_adv = semi_lagrangian(q, u, v, dt, DX, DY)

    # Pressure gradient force (geopotential gradient)
    dhdx = grad_x(h_adv, DX)
    dhdy = grad_y(h_adv, DY)

    # Topographic pressure contribution
    dtopox = grad_x(topography, DX)
    dtopoy = grad_y(topography, DY)

    u_new = (
        u_adv
        - dt * G * pg_scale * dhdx
        - dt * G * 0.05 * dtopox
        + dt * F0 * v_adv
        - dt * drag * u_adv
        + dt * Kh * lap(u_adv, DX, DY)
    )
    v_new = (
        v_adv
        - dt * G * pg_scale * dhdy
        - dt * G * 0.05 * dtopoy
        - dt * F0 * u_adv
        - dt * drag * v_adv
        + dt * Kh * lap(v_adv, DX, DY)
    )

    # Height update (divergence)
    div = grad_x(u_new, DX) + grad_y(v_new, DY)
    h_new = h_adv - dt * cfg.BASE_H * div + dt * Kh * lap(h_adv, DX, DY)

    # Temperature diffusion + nudging
    T_new = T_adv + dt * Kt * lap(T_adv, DX, DY) + dt * nudging * (obs.T - T_adv)

    # Moisture diffusion + nudging
    q_new = q_adv + dt * Kq * lap(q_adv, DX, DY) + dt * nudging * (obs.q - q_adv)
    q_new = np.clip(q_new, 1e-6, 0.04)

    # Condensation + latent heating
    T_new, q_new = condensation_and_heating(T_new, q_new, humid_couple, LV, CP)

    # Smooth all fields
    h_new = smooth(h_new)
    u_new = smooth(u_new)
    v_new = smooth(v_new)
    T_new = smooth(T_new)
    q_new = smooth(q_new)

    # Clip for stability
    h_new = np.clip(h_new, cfg.BASE_H - 2000.0, cfg.BASE_H + 2000.0)
    T_new = np.clip(T_new, 200.0, 340.0)
    q_new = np.clip(q_new, 1e-6, 0.04)

    return WeatherState(h=h_new, u=u_new, v=v_new, T=T_new, q=q_new)
