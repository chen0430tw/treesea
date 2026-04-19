from __future__ import annotations
from dataclasses import dataclass
import numpy as np

from .forcing import GridConfig, geostrophic_wind_from_h


@dataclass
class WeatherState:
    h: np.ndarray
    u: np.ndarray
    v: np.ndarray
    T: np.ndarray
    q: np.ndarray

    def to_dict(self) -> dict:
        return {"h": self.h, "u": self.u, "v": self.v, "T": self.T, "q": self.q}

    @classmethod
    def from_dict(cls, d: dict) -> "WeatherState":
        return cls(h=d["h"], u=d["u"], v=d["v"], T=d["T"], q=d["q"])

    def to_gpu(self) -> "WeatherState":
        """Transfer all fields to cupy (H100 acceleration path)."""
        import cupy as cp
        return WeatherState(
            h=cp.asarray(self.h), u=cp.asarray(self.u), v=cp.asarray(self.v),
            T=cp.asarray(self.T), q=cp.asarray(self.q),
        )

    def to_cpu(self) -> "WeatherState":
        """Pull fields back to numpy (for IO / reporting)."""
        from ._xp import to_numpy
        return WeatherState(
            h=to_numpy(self.h), u=to_numpy(self.u), v=to_numpy(self.v),
            T=to_numpy(self.T), q=to_numpy(self.q),
        )


def build_obs(
    XX: np.ndarray,
    YY: np.ndarray,
    topography: np.ndarray,
    cfg: GridConfig,
) -> WeatherState:
    # h_bg amplitude scaled 220→22m (synoptic 500hPa perturbations ~20m/1000km).
    # Wind derived geostrophically from h — self-consistent (Rossby adjustment
    # balance; Dickinson-Williamson 1972 NNMI). No more arbitrary wind sinusoids
    # disagreeing with pressure field.
    h_obs = cfg.BASE_H + 22.0 * np.sin(1.8 * np.pi * XX) * np.cos(1.4 * np.pi * YY) - 0.006 * topography
    u_obs, v_obs = geostrophic_wind_from_h(h_obs, cfg.DX, cfg.DY, cfg.F0, cfg.G)
    T_obs = 273.15 + 18.0 * np.cos(np.pi * YY) - 8.0 * np.sin(np.pi * XX) - 0.004 * topography
    q_obs = 0.008 + 0.005 * np.cos(np.pi * YY) ** 2 - 0.002 * np.sin(np.pi * XX) ** 2
    q_obs = np.clip(q_obs, 1e-4, 0.025)
    return WeatherState(h=h_obs, u=u_obs, v=v_obs, T=T_obs, q=q_obs)


def build_initial_state(
    XX: np.ndarray,
    YY: np.ndarray,
    topography: np.ndarray,
    cfg: GridConfig,
) -> WeatherState:
    h0 = cfg.BASE_H + 18.0 * np.sin(1.8 * np.pi * XX) * np.cos(1.4 * np.pi * YY) - 0.005 * topography
    u0, v0 = geostrophic_wind_from_h(h0, cfg.DX, cfg.DY, cfg.F0, cfg.G)
    T0 = 273.15 + 15.0 * np.cos(np.pi * YY) - 6.0 * np.sin(np.pi * XX) - 0.003 * topography
    q0 = 0.007 + 0.004 * np.cos(np.pi * YY) ** 2 - 0.001 * np.sin(np.pi * XX) ** 2
    q0 = np.clip(q0, 1e-4, 0.025)
    return WeatherState(h=h0, u=u0, v=v0, T=T0, q=q0)
