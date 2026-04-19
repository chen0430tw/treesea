"""Weather output contract — regime (safe) vs. quantitative (gated).

Two distinct output types:

  WeatherRegimeReport
    Safe default. Lists which DEFAULT_BRANCHES family dominated and with
    what confidence. No temperature in Celsius, no %RH. Purely qualitative.

  WeatherQuantEstimate
    Requires a WeatherCalibration instance. Maps internal state (h, T, q)
    to real-world observables (temperature_2m, RH, wind_10m) via a fitted
    observation-anchored transform. Without calibration, no instance of
    this class can be produced.

The shallow-water + simplified-thermodynamics pipeline in this module is
demo-grade. It is NOT a replacement for WRF/GFS NWP output. Treating
internal T as 2-meter air temperature is a semantic leak.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from .weather_sanity import (
    DEFAULT_BOUNDS, SanityBounds, ValidationReport,
    validate_state_arrays, require_calibration,
)


# ────────────────────────────────────────────────────────────────────
# Regime output (safe, always available)
# ────────────────────────────────────────────────────────────────────

@dataclass
class WeatherRegimeReport:
    """Qualitative regime identification. Always safe to return.

    Contains the dominant DEFAULT_BRANCHES family name, its weight, and a
    confidence level based on ensemble spread. Does NOT contain temperature
    or humidity in user-facing units.
    """
    dominant_family: str
    family_weights: dict[str, float]       # normalized to sum 1
    score_spread: float                    # lower = more certain
    confidence: str                        # "high" | "moderate" | "low"
    validation: ValidationReport           # physical sanity of underlying state
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "dominant_family": self.dominant_family,
            "family_weights": self.family_weights,
            "score_spread": self.score_spread,
            "confidence": self.confidence,
            "validation": self.validation.to_dict(),
            "notes": list(self.notes),
        }

    def human_summary(self) -> str:
        lines = [
            f"Dominant regime: {self.dominant_family}",
            f"Confidence:      {self.confidence}",
            f"Score spread:    {self.score_spread:.4f}",
        ]
        if not self.validation.valid:
            lines.append(
                f"⚠ Integration produced non-physical state "
                f"({', '.join(self.validation.offending_fields)}); "
                f"regime label is the only safe output."
            )
        if self.notes:
            lines.append("Notes:")
            lines.extend(f"  - {n}" for n in self.notes)
        lines.append("")
        lines.append("Top family weights:")
        for fam, w in sorted(self.family_weights.items(),
                             key=lambda kv: -kv[1])[:3]:
            lines.append(f"  {fam:<15s} {w:.3f}")
        return "\n".join(lines)


def regime_report_from_ranked(
    ranked: list[dict],
    validation: ValidationReport,
) -> WeatherRegimeReport:
    """Build regime report from ensemble-ranked output + validation report."""
    names = [r.get("name", "unknown") for r in ranked]
    scores = np.array([float(r.get("score", 0.0)) for r in ranked])
    # shift + normalize
    scores = scores - scores.min() + 1e-6
    weights = scores / scores.sum()

    family_weights = {n: float(w) for n, w in zip(names, weights)}
    dominant = names[int(np.argmax(scores))]
    spread = float(np.std(scores))

    # Confidence heuristic
    if spread < 0.02:
        confidence = "low"          # members too similar = weak discrimination
    elif spread < 0.08:
        confidence = "moderate"
    else:
        confidence = "high"

    notes = []
    if not validation.valid:
        notes.append(
            f"underlying integration violated bounds "
            f"({', '.join(validation.offending_fields)})"
        )

    return WeatherRegimeReport(
        dominant_family=dominant,
        family_weights=family_weights,
        score_spread=spread,
        confidence=confidence,
        validation=validation,
        notes=notes,
    )


# ────────────────────────────────────────────────────────────────────
# Calibration (required for quantitative output)
# ────────────────────────────────────────────────────────────────────

@dataclass
class WeatherCalibration:
    """Observation-anchored mapping from internal state to real-world observables.

    Required inputs (fit against recent measured weather data at the target
    location):

      T_offset_K      : additive offset T_internal → T_2m (K)
      T_scale         : multiplicative scale for T
      h_to_pressure_k : coefficient converting h anomaly to surface pressure change
      q_to_rh_ratio   : multiplicative ratio q_internal → q_2m used for RH calc
      wind_scale      : scale for wind magnitude

    Without a calibration, no quantitative output can be returned (see
    WeatherQuantEstimate.from_state guarded by weather_sanity.require_calibration).

    Fitting procedure (not implemented here, but recommended):
      1. run pipeline on past week with recorded observations
      2. fit T_offset_K = mean(T_observed - T_integrator_center)
      3. fit h_to_pressure_k via linear regression
      4. fit q_to_rh_ratio from humidity residuals

    Until you do this fit for your location, calibration=None → regime_only.
    """
    location_name: str
    fitted_date: str
    T_offset_K: float
    T_scale: float = 1.0
    h_to_pressure_k: float = 0.02          # hPa per meter of h anomaly
    q_to_rh_ratio: float = 1.0
    wind_scale: float = 1.0

    def map_temperature(self, T_internal_K: float) -> float:
        """T_internal → T_2m in Kelvin."""
        return self.T_scale * T_internal_K + self.T_offset_K

    def map_pressure(self, h_center_m: float, h_baseline: float = 5700.0) -> float:
        """h anomaly → surface pressure (hPa, reference-centered)."""
        # Using 1013.0 hPa as standard reference; h_to_pressure_k in hPa/m
        return 1013.0 - self.h_to_pressure_k * (h_center_m - h_baseline)

    def map_humidity(self, q_internal: float, T_2m_C: float) -> float:
        """q_internal + T_2m → relative humidity %."""
        # Tetens saturation vapor pressure
        e_sat = 6.11 * np.exp(17.27 * T_2m_C / (T_2m_C + 237.3))
        q_effective = q_internal * self.q_to_rh_ratio
        e_actual = q_effective * 1013.0 / (0.622 + q_effective)
        rh = 100.0 * e_actual / e_sat
        return float(np.clip(rh, 0.0, 100.0))

    def map_wind(self, u_internal: float, v_internal: float) -> float:
        """wind magnitude internal → 10m wind m/s."""
        return float(self.wind_scale * np.sqrt(u_internal**2 + v_internal**2))


# ────────────────────────────────────────────────────────────────────
# Quantitative estimate (guarded by calibration)
# ────────────────────────────────────────────────────────────────────

@dataclass
class WeatherQuantEstimate:
    """Calibrated quantitative estimate. Only produced via from_state()."""
    location: str
    temperature_2m_C: float
    relative_humidity_pct: float
    wind_speed_10m_ms: float
    wind_direction_deg: float
    surface_pressure_hpa: float
    validation: ValidationReport
    calibration_date: str
    caveat: str

    def to_dict(self) -> dict:
        return {
            "location": self.location,
            "temperature_2m_C": self.temperature_2m_C,
            "relative_humidity_pct": self.relative_humidity_pct,
            "wind_speed_10m_ms": self.wind_speed_10m_ms,
            "wind_direction_deg": self.wind_direction_deg,
            "surface_pressure_hpa": self.surface_pressure_hpa,
            "validation": self.validation.to_dict(),
            "calibration_date": self.calibration_date,
            "caveat": self.caveat,
        }


def quant_estimate_from_state(
    state_dict: dict,
    validation: ValidationReport,
    calibration: Optional[WeatherCalibration],
    center_xy: tuple[int, int],
) -> WeatherQuantEstimate:
    """Build quantitative estimate from internal state + calibration.

    Raises UnsafeTemperatureRead if calibration is None or state is invalid.
    """
    require_calibration(calibration=calibration)
    if not validation.valid:
        from .weather_sanity import UnsafeTemperatureRead
        raise UnsafeTemperatureRead(
            f"Cannot produce quantitative forecast: underlying state violates "
            f"bounds ({', '.join(validation.offending_fields)}). "
            f"Use regime_only mode instead."
        )

    cy, cx = center_xy
    T_internal = float(state_dict["T"][cy, cx])
    h_center = float(state_dict["h"][cy, cx])
    q_internal = float(state_dict["q"][cy, cx])
    u = float(state_dict["u"][cy, cx])
    v = float(state_dict["v"][cy, cx])

    T_2m_K = calibration.map_temperature(T_internal)
    T_2m_C = T_2m_K - 273.15
    rh = calibration.map_humidity(q_internal, T_2m_C)
    wind = calibration.map_wind(u, v)
    wind_dir = float((np.degrees(np.arctan2(-u, -v)) + 360.0) % 360.0)
    pressure = calibration.map_pressure(h_center)

    return WeatherQuantEstimate(
        location=calibration.location_name,
        temperature_2m_C=round(T_2m_C, 2),
        relative_humidity_pct=round(rh, 1),
        wind_speed_10m_ms=round(wind, 2),
        wind_direction_deg=round(wind_dir, 0),
        surface_pressure_hpa=round(pressure, 1),
        validation=validation,
        calibration_date=calibration.fitted_date,
        caveat=(
            "This is a shallow-water pipeline output post-calibration, NOT a "
            "WRF/GFS-grade operational forecast. Use for regime confirmation only."
        ),
    )
