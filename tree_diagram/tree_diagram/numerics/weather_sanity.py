"""Physical sanity bounds + clamping for weather state variables.

Responsibility:
  - Define hard physical limits for each weather state variable.
  - Provide clamp / validate functions used during integration and at output.
  - Prevent demo-grade shallow-water integrator from producing non-physical
    values (e.g. 43°C temperature or 13% humidity in a tropical spring regime).

Philosophy: the internal state variables (h, T, q, u, v) are integrator
quantities, not meteorological observables. If they drift outside physical
bounds, that is a numerical artifact, not a forecast. This module makes the
drift detectable and the output blockable.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


# ────────────────────────────────────────────────────────────────────
# Physical plausibility bounds
# ────────────────────────────────────────────────────────────────────
# These are hard limits on what a healthy atmospheric column can physically
# produce at Earth's surface or mid-troposphere. Values outside bounds are
# numerical artifacts.

# Temperature (Kelvin). Covers -80°C (polar coldest) to +60°C (record desert).
T_MIN_K = 193.15     # -80°C
T_MAX_K = 333.15     # +60°C

# 500 hPa geopotential height (meters). Climatological range worldwide.
H500_MIN_M = 4800.0  # polar winter
H500_MAX_M = 6000.0  # tropical maximum

# Specific humidity (kg/kg). 0 to saturation at 35°C roughly.
Q_MIN = 1e-6         # essentially dry
Q_MAX = 0.030        # ~30 g/kg, near-saturation tropical

# Wind components (m/s). Covers extreme jet streams.
U_MIN = -80.0
U_MAX = 80.0
V_MIN = -80.0
V_MAX = 80.0


@dataclass
class SanityBounds:
    T_min_K: float = T_MIN_K
    T_max_K: float = T_MAX_K
    h500_min_m: float = H500_MIN_M
    h500_max_m: float = H500_MAX_M
    q_min: float = Q_MIN
    q_max: float = Q_MAX
    u_min: float = U_MIN
    u_max: float = U_MAX
    v_min: float = V_MIN
    v_max: float = V_MAX


DEFAULT_BOUNDS = SanityBounds()


# ────────────────────────────────────────────────────────────────────
# Clamping (applied during integration)
# ────────────────────────────────────────────────────────────────────

def clamp_state_arrays(
    h: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    T: np.ndarray,
    q: np.ndarray,
    bounds: SanityBounds = DEFAULT_BOUNDS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Clamp arrays in-place to physical bounds. Returns clamped copies."""
    return (
        np.clip(h, bounds.h500_min_m, bounds.h500_max_m),
        np.clip(u, bounds.u_min, bounds.u_max),
        np.clip(v, bounds.v_min, bounds.v_max),
        np.clip(T, bounds.T_min_K, bounds.T_max_K),
        np.clip(q, bounds.q_min, bounds.q_max),
    )


# ────────────────────────────────────────────────────────────────────
# Validation (applied at output)
# ────────────────────────────────────────────────────────────────────

@dataclass
class ValidationReport:
    """Per-field validation report. `valid=False` means state drifted."""
    valid: bool
    offending_fields: list[str]
    max_T_K: float
    min_T_K: float
    max_h: float
    min_h: float
    max_q: float
    min_q: float
    max_wind: float

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "offending_fields": self.offending_fields,
            "max_T_K": self.max_T_K,
            "min_T_K": self.min_T_K,
            "max_h": self.max_h,
            "min_h": self.min_h,
            "max_q": self.max_q,
            "min_q": self.min_q,
            "max_wind": self.max_wind,
        }


def validate_state_arrays(
    h: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    T: np.ndarray,
    q: np.ndarray,
    bounds: SanityBounds = DEFAULT_BOUNDS,
) -> ValidationReport:
    """Check state arrays against physical bounds. Returns report."""
    offending = []

    max_T = float(np.max(T))
    min_T = float(np.min(T))
    if max_T > bounds.T_max_K or min_T < bounds.T_min_K:
        offending.append("T")

    max_h = float(np.max(h))
    min_h = float(np.min(h))
    if max_h > bounds.h500_max_m or min_h < bounds.h500_min_m:
        offending.append("h500")

    max_q = float(np.max(q))
    min_q = float(np.min(q))
    if max_q > bounds.q_max or min_q < bounds.q_min:
        offending.append("q")

    max_wind = float(np.max(np.sqrt(u**2 + v**2)))
    if max_wind > bounds.u_max:
        offending.append("wind")

    return ValidationReport(
        valid=(len(offending) == 0),
        offending_fields=offending,
        max_T_K=max_T, min_T_K=min_T,
        max_h=max_h, min_h=min_h,
        max_q=max_q, min_q=min_q,
        max_wind=max_wind,
    )


# ────────────────────────────────────────────────────────────────────
# Semantic contract: no internal-state → observable leakage
# ────────────────────────────────────────────────────────────────────

class UnsafeTemperatureRead(Exception):
    """Raised when code tries to read T_internal as a real-world 2m temperature.

    The integrator's T variable is a reference-layer thermodynamic variable,
    not the 2-meter air temperature a user sees in a weather app. Converting
    the two requires an observation-anchored calibration layer (see
    weather_output.WeatherCalibration).
    """
    pass


def require_calibration(*, calibration) -> None:
    """Raise if a quantitative-temperature output is requested without calibration."""
    if calibration is None:
        raise UnsafeTemperatureRead(
            "Cannot return 2-meter air temperature from a raw WeatherState. "
            "The integrator's T is an internal thermodynamic variable, not a "
            "measured observable. Either use mode='regime_only' or supply a "
            "WeatherCalibration instance mapped to real observations."
        )
