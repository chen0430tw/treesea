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


def geostrophic_wind_from_h(h, DX: float, DY: float, F0: float, g: float = 9.81):
    """Derive (u, v) in geostrophic balance with h field.

    Standard f-plane geostrophic balance (e.g., Vallis 2006, eq 2.218):
        u_g = -(g/f) ∂h/∂y
        v_g = +(g/f) ∂h/∂x

    Use this to construct self-consistent background wind instead of prescribing
    arbitrary u_bg, v_bg sinusoids that don't balance the h field (which drives
    spurious ageostrophic oscillations during spin-up, per Rossby 1938 and
    Dickinson-Williamson 1972 normal-mode-initialization framework).
    """
    from ._xp import get_xp
    xp = get_xp(h)
    # Centered differences with periodic wrap (matches existing grad_x/grad_y)
    dhdx = (xp.roll(h, -1, axis=-1) - xp.roll(h, 1, axis=-1)) / (2.0 * DX)
    dhdy = (xp.roll(h, -1, axis=-2) - xp.roll(h, 1, axis=-2)) / (2.0 * DY)
    u_g = -(g / F0) * dhdy
    v_g = +(g / F0) * dhdx
    return u_g, v_g
