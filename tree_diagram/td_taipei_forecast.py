"""台北明日天气预测 — 使用安全模式 API。

上一版把 TD 内部的 T 变量当成了 2 米气温，得到 43°C 的荒谬结果。
修复：
  1. 使用新的 run_safe(mode='regime_only') 只输出 regime（默认安全）
  2. 若要定量输出，必须提供 WeatherCalibration（观测锚定）
  3. 内部状态一律经 weather_contract 验证，非物理值直接标 invalid

今天观测（2026-04-19）：
  - 温度：高 29°C / 低 19°C（平均 24°C）
  - 相对湿度：82.5%
  - 气压：1009 hPa
  - 风速：3.6 m/s 西风
"""
from __future__ import annotations
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from tree_diagram.numerics.forcing import GridConfig, build_grid, build_topography, geostrophic_wind_from_h
from tree_diagram.numerics.weather_state import WeatherState
from tree_diagram.numerics.weather_contract import WeatherCalibration
from tree_diagram.pipeline.oracle_pipeline import WeatherOraclePipeline


# 台北 30 天气候均值（用作 obs 的 anchor；B-scheme 拟合时提供）
TAIPEI_CLIMO_T_C      = 21.6     # 2026-03-15 .. 2026-04-13 ERA5 mean
TAIPEI_CLIMO_P_HPA    = 1011.9
TAIPEI_CLIMO_WS_MS    = 1.95
TAIPEI_CLIMO_WD_DEG   = 51.0     # NE wind (climo-derived from 30-day ERA5 vector mean)
TAIPEI_WIND_ANCHOR_MIN = 0.25    # keep some obs response even near-climo
TAIPEI_WIND_ANCHOR_MAX = 1.00
TAIPEI_WIND_INCREMENT_WIDTH = 1.4  # wider than station weight; synoptic increment
TAIPEI_STRUCTURE_ANCHOR_MAX = 0.75

# Hard cap on cloud-top AMV contribution to the near-surface wind anchor.
# AMV (Atmospheric Motion Vector) from band-13 brightness-temperature tracking
# is a cloud-top pseudo-wind, NOT a near-surface flow — it routinely disagrees
# with the boundary-layer anchor by 90°+ during frontal / synoptic transitions.
# This cap bounds AMV's influence to a 15% increment on top of the observed
# anchor, with an additional cos²(angle) conflict-downweight applied inside
# build_taipei_state so that a 150° mis-match (cloud-top vs surface) gives
# AMV effectively zero influence instead of a full override.
_AMV_MAX_WEIGHT = 0.15

# Hard cap on satellite structure-strip contribution to the near-surface wind
# anchor. Strip orientation is a cloud-band axis — it only constrains the
# *direction* of synoptic flow to within ±90°, not which sign along that axis
# and definitely not near-surface vs cloud-top. Previously
# `TAIPEI_STRUCTURE_ANCHOR_MAX = 0.75` let one strip dominate 75% of the wind
# anchor; authorised 2026-04-22 to bound strip as an increment with the same
# principles as AMV:
#   * base cap at 0.15 (ceiling irrespective of strip_count / confidence)
#   * mixed_strip gets an extra 0.5 factor (semantically impure — averages
#     front / moist / shear proxies, so its orientation is the weakest prior)
#   * cos²(angle) conflict-downweight vs the obs-derived anchor — large angle
#     or anti-aligned strip gives zero influence, same geometry as AMV guard
_STRIP_MAX_WEIGHT = 0.15
_STRIP_MIXED_TYPE_FACTOR = 0.5
TAIPEI_STRUCTURE_WIND_WIDTH = 0.9

# 台北今天观测（默认 obs — td_taipei_forecast.py 对外仍以此为"今天"）
TAIPEI_TEMP_AVG_C   = 24.0
TAIPEI_HUMIDITY_PCT = 82.5
TAIPEI_PRESSURE_HPA = 1009.0
TAIPEI_WIND_MS      = 3.6
TAIPEI_WIND_FROM_DEG = 270.0     # westerly


@dataclass
class ReferenceObs:
    """Observed surface meteorology at Taipei for a single day.

    Feeds into build_taipei_state so each day's initial state is obs-anchored,
    producing distinct TD internal states for B-scheme regression.
    """
    T_avg_C: float = TAIPEI_TEMP_AVG_C
    RH_pct:  float = TAIPEI_HUMIDITY_PCT
    P_hPa:   float = TAIPEI_PRESSURE_HPA
    ws_ms:   float = TAIPEI_WIND_MS
    wd_deg:  float = TAIPEI_WIND_FROM_DEG   # direction FROM (compass bearing)


def _wind_components(ws_ms: float, wd_deg: float) -> tuple[float, float]:
    """Meteorological direction-FROM to model (u east+, v north+) components."""
    wd_rad = math.radians(wd_deg)
    return -ws_ms * math.sin(wd_rad), -ws_ms * math.cos(wd_rad)


def _geostrophic_slopes_from_uv(u_ms: float, v_ms: float, cfg: GridConfig) -> tuple[float, float]:
    """Inverse f-plane geostrophic balance: target (u, v) -> linear h slopes."""
    half_x = 0.5 * cfg.NX * cfg.DX
    half_y = 0.5 * cfg.NY * cfg.DY
    slope_x = v_ms * cfg.F0 / cfg.G * half_x
    slope_y = -u_ms * cfg.F0 / cfg.G * half_y
    return slope_x, slope_y


def _wind_anchor_alpha(obs_ref: ReferenceObs) -> float:
    """Blend weight for the synoptic wind increment.

    This is not "single-station overwrite". It is a bounded analysis-style
    increment strength: strong when direction departs far from climatology or
    speed anomaly is large, weak-but-nonzero near climatology.
    """
    dir_delta = abs(((obs_ref.wd_deg - TAIPEI_CLIMO_WD_DEG + 180.0) % 360.0) - 180.0)
    dir_term = min(1.0, dir_delta / 180.0)
    speed_term = min(1.0, abs(obs_ref.ws_ms - TAIPEI_CLIMO_WS_MS) / max(1.0, TAIPEI_CLIMO_WS_MS + 1.5))
    alpha = 0.25 + 0.55 * dir_term + 0.20 * speed_term
    return float(np.clip(alpha, TAIPEI_WIND_ANCHOR_MIN, TAIPEI_WIND_ANCHOR_MAX))


def _wind_components_from_strip_orientation(
    orientation_deg: float,
    reference_u: float,
    reference_v: float,
    ws_ms: float,
    *,
    strip_type: str | None = None,
) -> tuple[float, float]:
    """Convert a strip axis orientation into an along-strip wind guess.

    orientation_deg follows the structure-layer convention on array/image
    indices:
      0°  -> +x axis
      90° -> +y axis (downward on the raster)
    A strip implies an axis but not a sign. We therefore choose the sign whose
    vector is closest to the reference wind (typically the station observation),
    so this stays a bounded analysis increment instead of a free overwrite.
    """
    orient = float(orientation_deg)
    if strip_type in {"front_strip", "mixed_strip"}:
        # Front-like strips describe the band axis; the relevant synoptic
        # increment is the cross-strip/background-turning direction rather than
        # blindly following the band itself.
        orient = (orient - 90.0) % 180.0
    theta = math.radians(orient)
    # Convert image-space axis (x right, y down) into model wind components
    # (u east+, v north+): x stays east+, raster y must flip sign into north+.
    cand_a = np.asarray([math.cos(theta), -math.sin(theta)], dtype=np.float64)
    cand_b = -cand_a
    ref = np.asarray([reference_u, reference_v], dtype=np.float64)
    pick = cand_a if float(cand_a @ ref) >= float(cand_b @ ref) else cand_b
    return float(ws_ms * pick[0]), float(ws_ms * pick[1])


def build_taipei_state(XX, YY, topography, cfg: GridConfig,
                       perturbation: float = 0.0,
                       obs_ref: ReferenceObs | None = None,
                       structure_strip_orientation_deg: float | None = None,
                       structure_strip_weight: float = 0.0,
                       structure_strip_type: str | None = None,
                       wind_anchor_override_uv: tuple[float, float] | None = None) -> WeatherState:
    """以台北为中心构建 internal state。

    obs_ref 注入当日表面观测 → internal state 的 Taipei 锚点随 obs 变化：
      - surface T 变化 1 K → internal 500 hPa T 变化 ~0.5 K（湿绝热耦合近似）
      - surface P 变化 1 hPa → internal 500 hPa 位势变化 ~-1 m（反气旋抬升）
      - 风向 wd_deg + 风速 ws_ms → (u, v) 向量（meteorological convention）

    注意：这里的 T 是 TD 内部参考层温度（~500 hPa 面），不是地面 2m 温度。
    """
    if obs_ref is None:
        obs_ref = ReferenceObs()

    taipei_weight = np.exp(-3.0 * (XX**2 + YY**2))

    # 内部 T 锚点：气候态 268 K，surface T 偏离 climo 时全量传入（单位 K）
    # 耦合系数 1.0：避免初始就人为压缩 obs 信号；让校准层只做线性映射，不兼做压缩
    T_internal_taipei = 268.0 + 1.0 * (obs_ref.T_avg_C - TAIPEI_CLIMO_T_C) + perturbation

    # Uniform h offset from obs P deviation: shifts entire domain h by a
    # synoptic-scale anomaly (hypsometric ~8 m/hPa at 500 hPa reference).
    # Because it's uniform, ∂h/∂x and ∂h/∂y are unchanged → geostrophic wind
    # is preserved. Gives day-to-day h_center variation that drives varying
    # pressure output via map_pressure (previously h had zero obs-P dependence
    # → bit-exact pressure across all forecast days).
    _h_obs_offset = 8.0 * (obs_ref.P_hPa - TAIPEI_CLIMO_P_HPA) + perturbation * 1.0

    # 风向矢量化（wd 是 FROM 方向；u 向东正，v 向北正）
    u_obs, v_obs = _wind_components(obs_ref.ws_ms, obs_ref.wd_deg)
    u_taipei = u_obs
    v_taipei = v_obs

    # AMV override semantics — bounded, conflict-aware increment.
    #
    # Previous behaviour directly replaced (u_taipei, v_taipei) with the
    # AMV vector. That produced the known failure mode: a cloud-top / TBB
    # motion vector (Himawari band-13 brightness-temperature tracking)
    # was rewriting the near-surface / day-1 wind anchor. For this
    # specific case the AMV pointed ~270° W while the observed surface
    # anchor was ~60° ENE — a 150° disagreement — and the override
    # rotated the day-1 near-surface flow by ~140°. Codex red-lined this
    # path: "cloud-top pseudo-AMV 不该直接改 near-surface / day-1 风向".
    #
    # New semantics (authorised 2026-04-22):
    #   1. cap the AMV weight at `_AMV_MAX_WEIGHT` (0.15) — AMV is at
    #      most a 15% increment on top of the observed anchor
    #   2. downweight smoothly by cos²(angle(AMV, obs)):
    #        aligned  (0°)   → full cap (0.15)
    #        30° off         → ~0.11
    #        perpendicular   → 0
    #        any angle > 90° → 0 (cloud-top drifting opposite the
    #                             surface anchor is evidence of vertical
    #                             decoupling, NOT a correction signal)
    #   3. if either |obs| or |amv| is negligible, skip the conflict
    #      check and fall through to the default cap (no anchor to
    #      conflict with, so just admit the cap-level AMV nudge)
    if wind_anchor_override_uv is not None:
        u_amv = float(wind_anchor_override_uv[0])
        v_amv = float(wind_anchor_override_uv[1])
        obs_mag = math.hypot(u_obs, v_obs)
        amv_mag = math.hypot(u_amv, v_amv)
        if obs_mag > 0.1 and amv_mag > 0.1:
            cos_angle = (u_obs * u_amv + v_obs * v_amv) / (obs_mag * amv_mag)
        else:
            cos_angle = 1.0
        conflict_factor = max(0.0, cos_angle) ** 2
        amv_weight = _AMV_MAX_WEIGHT * conflict_factor
        u_taipei = (1.0 - amv_weight) * u_obs + amv_weight * u_amv
        v_taipei = (1.0 - amv_weight) * v_obs + amv_weight * v_amv

    # 中层比湿：用 T_internal_taipei 的饱和水汽压 + 当日 RH，500 hPa 总压。
    # 水汽密度 ρ_v = e/(R_v·T) 随温度强依赖；旧版 q_surface × 0.5 会超饱和
    # （surface q≈0.016 × 0.5 = 0.008，但 -5°C/500hPa 饱和 q≈0.005）。
    # 新公式直接在内部 T 上算 e_sat，保证 q_taipei 物理上可达。
    T_mid_C = T_internal_taipei - 273.15
    e_sat_mid = 6.11 * math.exp(17.27 * T_mid_C / (T_mid_C + 237.3))
    P_mid_hPa = 500.0
    e_mid = e_sat_mid * obs_ref.RH_pct / 100.0
    q_taipei = 0.622 * e_mid / (P_mid_hPa - e_mid)

    # 气候态背景 — LINEAR h slope so geostrophic wind everywhere equals Taipei
    # climo wind (NE 51°, 1.95 m/s). This IS spectral-nudging-at-init:
    # large-scale wind direction is baked into h gradient, not fought by nudging.
    # Slopes from inverse geostrophic balance:
    #   ∂h/∂x = +v_climo * f/g   (m/m)    → h_slope_x = ∂h/∂x * half_domain_x
    #   ∂h/∂y = -u_climo * f/g   (m/m)
    u_climo, v_climo = _wind_components(TAIPEI_CLIMO_WS_MS, TAIPEI_CLIMO_WD_DEG)
    _slope_x, _slope_y = _geostrophic_slopes_from_uv(u_climo, v_climo, cfg)
    # Periodic-BC safe envelope: linear slope near center fades to EXACTLY 0
    # at X=±1 / Y=±1 via (1-X²)(1-Y²) polynomial → h values wrap seamlessly
    # (avoids np.roll boundary discontinuity that blew wind to U_CLIP_MS=35).
    _env = (1.0 - XX**2) * (1.0 - YY**2)
    h_bg = cfg.BASE_H + _slope_x * XX * _env + _slope_y * YY * _env - 0.006 * topography

    # Analysis-style wind increment: retain climo background, but let strong
    # obs wind anomalies rotate the h gradient locally/regionally instead of
    # leaving the entire domain locked to climatology.
    anchor_alpha = _wind_anchor_alpha(obs_ref)
    target_u = float(u_taipei)
    target_v = float(v_taipei)
    if structure_strip_orientation_deg is not None and structure_strip_weight > 1.0e-6:
        struct_u, struct_v = _wind_components_from_strip_orientation(
            float(structure_strip_orientation_deg),
            u_taipei,
            v_taipei,
            max(obs_ref.ws_ms, TAIPEI_CLIMO_WS_MS),
            strip_type=structure_strip_type,
        )

        # Bounded, conflict-aware strip increment — same principles as the
        # AMV block above.
        #
        # Previous path: `structure_alpha = clip(weight,0,1) * 0.75` let one
        # satellite strip rotate up to 75% of the wind anchor. For the
        # 2026-04-21 case that pinned near-surface wind to ~175° S
        # because a mixed_strip at ori=96.4° (E-W oriented band) forced
        # geostrophy into N-S. Even when AMV had been correctly downweighted
        # to zero, strip alone could still override the 60° ENE surface
        # anchor. Codex red-lined this path on 2026-04-22.
        #
        # New semantics:
        #   1. base cap at `_STRIP_MAX_WEIGHT` (0.15)
        #   2. mixed_strip additional `_STRIP_MIXED_TYPE_FACTOR` (0.5)
        #   3. cos²(angle(struct, target)) conflict factor — identical to
        #      the AMV conflict guard, so a strip pointing anti-parallel
        #      to the surface anchor contributes zero
        target_mag = math.hypot(target_u, target_v)
        struct_mag = math.hypot(struct_u, struct_v)
        if target_mag > 0.1 and struct_mag > 0.1:
            cos_angle = (target_u * struct_u + target_v * struct_v) / (target_mag * struct_mag)
        else:
            cos_angle = 1.0
        conflict_factor = max(0.0, cos_angle) ** 2
        type_factor = (
            _STRIP_MIXED_TYPE_FACTOR if structure_strip_type == "mixed_strip" else 1.0
        )
        structure_alpha = (
            float(np.clip(structure_strip_weight, 0.0, 1.0))
            * _STRIP_MAX_WEIGHT
            * type_factor
            * conflict_factor
        )
        target_u = (1.0 - structure_alpha) * target_u + structure_alpha * struct_u
        target_v = (1.0 - structure_alpha) * target_v + structure_alpha * struct_v
    obs_slope_x, obs_slope_y = _geostrophic_slopes_from_uv(target_u, target_v, cfg)
    inc_slope_x = anchor_alpha * (obs_slope_x - _slope_x)
    inc_slope_y = anchor_alpha * (obs_slope_y - _slope_y)
    inc_env = np.exp(-TAIPEI_WIND_INCREMENT_WIDTH * (XX**2 + YY**2)) * _env
    h_increment = inc_slope_x * XX * inc_env + inc_slope_y * YY * inc_env

    h_analysis = h_bg + h_increment
    T_bg = 273.15 + 18.0 * np.cos(np.pi * YY) - 8.0 * np.sin(np.pi * XX) - 0.004 * topography
    q_bg = 0.008 + 0.005 * np.cos(np.pi * YY)**2 - 0.002 * np.sin(np.pi * XX)**2
    q_bg = np.clip(q_bg, 1e-4, 0.025)

    # h: background geostrophic slope + bounded obs-driven increment + uniform
    # pressure offset. This allows the synoptic wind anchor to rotate without
    # letting one station overwrite the whole domain.
    h = h_analysis + _h_obs_offset
    u, v = geostrophic_wind_from_h(h, cfg.DX, cfg.DY, cfg.F0, cfg.G)
    T = taipei_weight * T_internal_taipei + (1 - taipei_weight) * T_bg
    q = taipei_weight * q_taipei + (1 - taipei_weight) * q_bg
    q = np.clip(q, 1e-4, 0.025)

    return WeatherState(h=h, u=u, v=v, T=T, q=q)


def run_regime_forecast():
    """Safe mode: only regime identification. No quantitative temperature output."""
    print("=" * 72)
    print("TAIPEI REGIME FORECAST — WeatherOraclePipeline.run_safe(mode='regime_only')")
    print("=" * 72)
    print(f"Today's observations (2026-04-19):")
    print(f"  T avg: {TAIPEI_TEMP_AVG_C}°C, RH: {TAIPEI_HUMIDITY_PCT}%, "
          f"P: {TAIPEI_PRESSURE_HPA} hPa, wind: {TAIPEI_WIND_MS} m/s W")
    print()

    cfg = GridConfig(NX=256, NY=192, DX=6000.0, DY=6000.0, DT=60.0, STEPS=120)
    XX, YY, x, y = build_grid(cfg)
    topo = build_topography(XX, YY)

    obs = build_taipei_state(XX, YY, topo, cfg, perturbation=0.0)
    init = build_taipei_state(XX, YY, topo, cfg, perturbation=-1.0)  # yesterday

    pipe = WeatherOraclePipeline(cfg=cfg, n_workers=1)
    regime_report, quant_estimate, diagnostics = pipe.run_safe(
        mode="regime_only",
        initial_state=init,
        obs=obs,
        topography=topo,
        pressure_balance=1.0,
    )

    print(regime_report.human_summary())
    print()
    print(f"Hydro diagnostics: pressure_balance="
          f"{diagnostics['hydro'].get('pressure_balance', 0):.3f}  "
          f"mean_score={diagnostics['hydro'].get('mean_score', 0):.3f}")
    print()

    if quant_estimate is None:
        print("(Quantitative estimate withheld — no calibration supplied. "
              "Safe default.)")

    return regime_report, diagnostics


def attempt_calibrated_forecast():
    """尝试 calibrated_quant 模式——但没有真实校准数据，应被拒绝。"""
    print("\n" + "=" * 72)
    print("ATTEMPTING calibrated_quant MODE WITHOUT CALIBRATION")
    print("=" * 72)

    cfg = GridConfig(NX=256, NY=192, DX=6000.0, DY=6000.0, DT=60.0, STEPS=120)
    XX, YY, x, y = build_grid(cfg)
    topo = build_topography(XX, YY)
    obs = build_taipei_state(XX, YY, topo, cfg, perturbation=0.0)
    init = build_taipei_state(XX, YY, topo, cfg, perturbation=-1.0)

    pipe = WeatherOraclePipeline(cfg=cfg, n_workers=1)
    try:
        regime_report, quant_estimate, diagnostics = pipe.run_safe(
            mode="calibrated_quant",
            initial_state=init,
            obs=obs,
            topography=topo,
            calibration=None,           # 缺失校准
        )
        print("ERROR: should have refused!")
    except Exception as e:
        print(f"✓ Correctly refused: {type(e).__name__}")
        print(f"  Message: {str(e)[:200]}")


CAL_B_FILE = Path("D:/treesea/tree_diagram/calibration/taipei_calibration_b.json")
CAL_A_FILE = Path("D:/treesea/tree_diagram/calibration/taipei_calibration.json")


def load_fitted_calibration() -> tuple[WeatherCalibration | None, str]:
    """Load B-scheme if present, else A-scheme. Returns (cal, scheme_label)."""
    if CAL_B_FILE.exists():
        d = json.loads(CAL_B_FILE.read_text(encoding="utf-8"))["calibration"]
        return WeatherCalibration(**d), "B (per-day Theil-Sen)"
    if CAL_A_FILE.exists():
        d = json.loads(CAL_A_FILE.read_text(encoding="utf-8"))["calibration"]
        return WeatherCalibration(**d), "A (single-shot mean)"
    return None, "none"


def run_calibrated_forecast_with_fitted():
    """Run calibrated_quant using the best available fitted calibration."""
    print("\n" + "=" * 72)
    print("CALIBRATED FORECAST (fitted from 30 days of Taipei ERA5 obs)")
    print("=" * 72)

    cal, scheme = load_fitted_calibration()
    if cal is None:
        print(f"[skip] No fitted calibration found. "
              f"Run calibration/fit_calibration_b.py first.")
        return None, None

    print(f"Scheme: {scheme}")
    print(f"  {cal.fitted_date}")
    print(f"  T_scale={cal.T_scale:+.4f}  T_offset_K={cal.T_offset_K:+.3f}  "
          f"q_to_rh_ratio={cal.q_to_rh_ratio:.3f}  wind_scale={cal.wind_scale:.3f}  "
          f"h_to_pressure_k={cal.h_to_pressure_k:+.5f}")

    cfg = GridConfig(NX=256, NY=192, DX=6000.0, DY=6000.0, DT=60.0, STEPS=120)
    XX, YY, x, y = build_grid(cfg)
    topo = build_topography(XX, YY)
    obs = build_taipei_state(XX, YY, topo, cfg, perturbation=0.0)
    init = build_taipei_state(XX, YY, topo, cfg, perturbation=-1.0)

    pipe = WeatherOraclePipeline(cfg=cfg, n_workers=1)
    regime_report, quant_estimate, diagnostics = pipe.run_safe(
        mode="calibrated_quant",
        initial_state=init,
        obs=obs,
        topography=topo,
        calibration=cal,
    )

    print("\nRegime:")
    print(regime_report.human_summary())
    print()

    if quant_estimate:
        print(f"Quantitative forecast — 2026-04-19 Taipei (scheme {scheme}):")
        print(f"  Temperature 2m:    {quant_estimate.temperature_2m_C}°C")
        print(f"  Relative humidity: {quant_estimate.relative_humidity_pct}%")
        print(f"  Wind 10m:          {quant_estimate.wind_speed_10m_ms} m/s "
              f"from {quant_estimate.wind_direction_deg:.0f}°")
        print(f"  Pressure:          {quant_estimate.surface_pressure_hpa} hPa")
        print(f"  Today's obs input: T={TAIPEI_TEMP_AVG_C}°C  RH={TAIPEI_HUMIDITY_PCT}%  "
              f"P={TAIPEI_PRESSURE_HPA}hPa  wind={TAIPEI_WIND_MS} m/s")

    return regime_report, quant_estimate


if __name__ == "__main__":
    # Part 1: safe default (regime only)
    regime, diag = run_regime_forecast()

    # Part 2: prove that uncalibrated quant mode is refused
    attempt_calibrated_forecast()

    # Part 3: calibrated forecast using A-scheme fit (30-day ERA5)
    regime2, quant = run_calibrated_forecast_with_fitted()

    # Save outputs
    out_dir = Path("D:/treesea/runs/tree_diagram")
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "regime_only": regime.to_dict(),
        "calibrated_quant": quant.to_dict() if quant else None,
        "diagnostics_hydro": diag["hydro"],
    }
    (out_dir / "taipei_forecast_safe.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nSaved → {out_dir / 'taipei_forecast_safe.json'}")
