from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np


@dataclass
class GridConfig:
    NX: int = 112
    NY: int = 84
    DX: float = 12000.0
    DY: float = 12000.0
    DT: float = 45.0
    STEPS: int = 240
    G: float = 9.81
    F0: float = 8.0e-5
    CP: float = 1004.0
    LV: float = 2.5e6
    BASE_H: float = 5400.0


def build_grid(cfg: GridConfig):
    x = np.linspace(-1.0, 1.0, cfg.NX)
    y = np.linspace(-1.0, 1.0, cfg.NY)
    XX, YY = np.meshgrid(x, y)
    return XX, YY, x, y


def build_topography(XX: np.ndarray, YY: np.ndarray) -> np.ndarray:
    return (
        1400.0 * np.exp(-7.0 * ((XX + 0.36) ** 2 + (YY - 0.06) ** 2))
        + 720.0 * np.exp(-10.5 * ((XX - 0.18) ** 2 + (YY + 0.24) ** 2))
        + 350.0 * np.exp(-14.0 * ((XX + 0.05) ** 2 + (YY + 0.28) ** 2))
    )
