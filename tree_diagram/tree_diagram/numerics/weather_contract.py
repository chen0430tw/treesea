"""Weather output contract — sanity bounds + regime/quant output types.

合并自原 weather_sanity.py + weather_output.py。单一模块集中 weather 输出
相关的：
  - 物理限幅常数与校验（SanityBounds / validate_state_arrays）
  - 内部态→观测量的调用闸门（UnsafeTemperatureRead / require_calibration）
  - 输出契约（WeatherRegimeReport / WeatherQuantEstimate）
  - 观测锚定校准映射（WeatherCalibration）

设计原则：
  - 内部态 (h, T, q) 是 integrator variables，不是 2m 气温/RH
  - 规则回收型 WeatherRegimeReport 永远安全（仅 family 标签）
  - 定量 WeatherQuantEstimate 必须经 WeatherCalibration 转换

注意：dynamics.py 已经在积分时做物理限幅，这里是输出时的二次防线。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ====================================================================
# Section 1 — 物理限幅 / 校验
# ====================================================================

T_MIN_K = 193.15     # -80°C
T_MAX_K = 333.15     # +60°C
H500_MIN_M = 4800.0
H500_MAX_M = 6000.0
Q_MIN = 1e-6
Q_MAX = 0.030
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


def clamp_state_arrays(
    h: np.ndarray, u: np.ndarray, v: np.ndarray, T: np.ndarray, q: np.ndarray,
    bounds: SanityBounds = DEFAULT_BOUNDS,
):
    """Clamp arrays to physical bounds (integration-time safety net)."""
    return (
        np.clip(h, bounds.h500_min_m, bounds.h500_max_m),
        np.clip(u, bounds.u_min, bounds.u_max),
        np.clip(v, bounds.v_min, bounds.v_max),
        np.clip(T, bounds.T_min_K, bounds.T_max_K),
        np.clip(q, bounds.q_min, bounds.q_max),
    )


@dataclass
class ValidationReport:
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
        return self.__dict__.copy()


def validate_state_arrays(
    h: np.ndarray, u: np.ndarray, v: np.ndarray, T: np.ndarray, q: np.ndarray,
    bounds: SanityBounds = DEFAULT_BOUNDS,
) -> ValidationReport:
    """Post-integration check; drives whether quant output is permitted."""
    offending = []
    max_T = float(np.max(T)); min_T = float(np.min(T))
    if max_T > bounds.T_max_K or min_T < bounds.T_min_K:
        offending.append("T")
    max_h = float(np.max(h)); min_h = float(np.min(h))
    if max_h > bounds.h500_max_m or min_h < bounds.h500_min_m:
        offending.append("h500")
    max_q = float(np.max(q)); min_q = float(np.min(q))
    if max_q > bounds.q_max or min_q < bounds.q_min:
        offending.append("q")
    max_wind = float(np.max(np.sqrt(u**2 + v**2)))
    if max_wind > bounds.u_max:
        offending.append("wind")
    return ValidationReport(
        valid=(len(offending) == 0), offending_fields=offending,
        max_T_K=max_T, min_T_K=min_T,
        max_h=max_h, min_h=min_h,
        max_q=max_q, min_q=min_q,
        max_wind=max_wind,
    )


# ====================================================================
# Section 2 — Unsafe read gate
# ====================================================================

class UnsafeTemperatureRead(Exception):
    """Raised when trying to read T_internal as 2m air temperature."""
    pass


def require_calibration(*, calibration) -> None:
    if calibration is None:
        raise UnsafeTemperatureRead(
            "Cannot return 2-meter air temperature from a raw WeatherState. "
            "The integrator's T is an internal thermodynamic variable. "
            "Use mode='regime_only' or supply a WeatherCalibration."
        )


# ====================================================================
# Section 3 — 输出契约
# ====================================================================

@dataclass
class WeatherRegimeReport:
    """Qualitative regime identification. Always safe."""
    dominant_family: str
    family_weights: dict[str, float]
    score_spread: float
    confidence: str
    validation: ValidationReport
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
        for fam, w in sorted(self.family_weights.items(), key=lambda kv: -kv[1])[:3]:
            lines.append(f"  {fam:<15s} {w:.3f}")
        return "\n".join(lines)


def regime_report_from_ranked(ranked: list[dict], validation: ValidationReport) -> WeatherRegimeReport:
    names = [r.get("name", "unknown") for r in ranked]
    scores = np.array([float(r.get("score", 0.0)) for r in ranked])
    scores = scores - scores.min() + 1e-6
    weights = scores / scores.sum()
    family_weights = {n: float(w) for n, w in zip(names, weights)}
    dominant = names[int(np.argmax(scores))]
    spread = float(np.std(scores))
    if spread < 0.02:
        confidence = "low"
    elif spread < 0.08:
        confidence = "moderate"
    else:
        confidence = "high"
    notes = []
    if not validation.valid:
        notes.append(f"underlying integration violated bounds ({', '.join(validation.offending_fields)})")
    return WeatherRegimeReport(
        dominant_family=dominant, family_weights=family_weights,
        score_spread=spread, confidence=confidence,
        validation=validation, notes=notes,
    )


# ====================================================================
# Section 4 — 校准映射（定量输出的必要前提）
# ====================================================================

@dataclass
class WeatherCalibration:
    """Observation-anchored mapping from internal state to real-world observables.

    Fit against recent measured weather data at the target location. Without
    a fitted calibration for your location, use regime_only mode instead.
    """
    location_name: str
    fitted_date: str
    T_offset_K: float
    T_scale: float = 1.0
    h_to_pressure_k: float = 0.02
    q_to_rh_ratio: float = 1.0
    wind_scale: float = 1.0
    # Post-process offset for the 1-layer Coriolis veering residual.
    # TD's single-layer shallow-water lacks baroclinic structure / PBL damping,
    # so obs→TD wind direction accumulates an inertial-oscillation rotation
    # (~80° veering at 25°N over 24h). Fitted as circular median(obs-td) across
    # training days. Applied as: corrected_wd = (td_wd + offset) % 360.
    wind_dir_offset_deg: float = 0.0
    # Per-fit baselines for pressure mapping. Model-dependent: our shallow-water
    # runs at BASE_H≈5400 with obs-P offset ±24m. Forcing h_baseline=5700 (old
    # default) made dh dominated by the 300m offset, collapsing the Theil-Sen
    # ratio fit. Fit-time stores mean(h_ctr) and mean(P_real) so the slope is
    # a pure (P vs h) regression around the training data's center of mass.
    h_baseline_m: float = 5700.0
    p_baseline_hPa: float = 1013.0

    def map_temperature(self, T_internal_K: float) -> float:
        return self.T_scale * T_internal_K + self.T_offset_K

    def map_pressure(self, h_center_m: float, h_baseline: float | None = None) -> float:
        hb = self.h_baseline_m if h_baseline is None else h_baseline
        return self.p_baseline_hPa - self.h_to_pressure_k * (h_center_m - hb)

    def map_humidity(self, q_internal: float, T_2m_C: float) -> float:
        e_sat = 6.11 * np.exp(17.27 * T_2m_C / (T_2m_C + 237.3))
        q_eff = q_internal * self.q_to_rh_ratio
        e_actual = q_eff * 1013.0 / (0.622 + q_eff)
        rh = 100.0 * e_actual / e_sat
        return float(np.clip(rh, 0.0, 100.0))

    def map_wind(self, u_internal: float, v_internal: float) -> float:
        return float(self.wind_scale * np.sqrt(u_internal**2 + v_internal**2))


@dataclass
class WeatherQuantEstimate:
    """Calibrated quantitative estimate. Only produced via quant_estimate_from_state."""
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
        d = self.__dict__.copy()
        d["validation"] = self.validation.to_dict()
        return d


def quant_estimate_from_state(
    state_dict: dict, validation: ValidationReport,
    calibration: Optional[WeatherCalibration], center_xy: tuple[int, int],
) -> WeatherQuantEstimate:
    """Build quantitative estimate; raises if calibration missing or state invalid."""
    require_calibration(calibration=calibration)
    if not validation.valid:
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
