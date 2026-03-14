from __future__ import annotations
from dataclasses import dataclass
import numpy as np

from .forcing import GridConfig


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


def build_obs(
    XX: np.ndarray,
    YY: np.ndarray,
    topography: np.ndarray,
    cfg: GridConfig,
) -> WeatherState:
    h_obs = cfg.BASE_H + 220.0 * np.sin(1.8 * np.pi * XX) * np.cos(1.4 * np.pi * YY) - 0.06 * topography
    u_obs = 14.0 * np.cos(1.2 * np.pi * YY) - 6.0 * np.sin(0.8 * np.pi * XX)
    v_obs = 7.0 * np.sin(1.6 * np.pi * XX) * np.cos(np.pi * YY)
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
    h0 = cfg.BASE_H + 180.0 * np.sin(1.8 * np.pi * XX) * np.cos(1.4 * np.pi * YY) - 0.05 * topography
    u0 = 12.0 * np.cos(1.2 * np.pi * YY) - 5.0 * np.sin(0.8 * np.pi * XX)
    v0 = 5.0 * np.sin(1.6 * np.pi * XX) * np.cos(np.pi * YY)
    T0 = 273.15 + 15.0 * np.cos(np.pi * YY) - 6.0 * np.sin(np.pi * XX) - 0.003 * topography
    q0 = 0.007 + 0.004 * np.cos(np.pi * YY) ** 2 - 0.001 * np.sin(np.pi * XX) ** 2
    q0 = np.clip(q0, 1e-4, 0.025)
    return WeatherState(h=h0, u=u0, v=v0, T=T0, q=q0)
