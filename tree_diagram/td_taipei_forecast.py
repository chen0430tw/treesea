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


def build_taipei_state(XX, YY, topography, cfg: GridConfig,
                       perturbation: float = 0.0,
                       obs_ref: ReferenceObs | None = None) -> WeatherState:
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

    # 内部 h 锚点：与 BASE_H (5400) 对齐，避免在中心形成 300m 高的凸起
    # （凸起会产生巨大局部 PGF，覆盖线性 h_bg 的 climo-directed 梯度）。
    # obs 的气压 P 变化仍反映为小偏移（0.1m/hPa）。
    h_taipei = cfg.BASE_H - 0.1 * (obs_ref.P_hPa - TAIPEI_CLIMO_P_HPA) + perturbation * 1.0

    # 风向矢量化（wd 是 FROM 方向；u 向东正，v 向北正）
    wd_rad = math.radians(obs_ref.wd_deg)
    u_taipei = -obs_ref.ws_ms * math.sin(wd_rad)
    v_taipei = -obs_ref.ws_ms * math.cos(wd_rad)

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
    _wd_rad_c = math.radians(TAIPEI_CLIMO_WD_DEG)
    u_climo = -TAIPEI_CLIMO_WS_MS * math.sin(_wd_rad_c)
    v_climo = -TAIPEI_CLIMO_WS_MS * math.cos(_wd_rad_c)
    _half_x = 0.5 * cfg.NX * cfg.DX      # physical half-domain (m)
    _half_y = 0.5 * cfg.NY * cfg.DY
    _slope_x = 0.0  # DBG
    _slope_y = 0.0
    # Periodic-BC safe envelope: linear slope near center fades to EXACTLY 0
    # at X=±1 / Y=±1 via (1-X²)(1-Y²) polynomial → h values wrap seamlessly
    # (avoids np.roll boundary discontinuity that blew wind to U_CLIP_MS=35).
    _env = (1.0 - XX**2) * (1.0 - YY**2)
    h_bg = cfg.BASE_H + _slope_x * XX * _env + _slope_y * YY * _env  # DBG: removed topo
    u_bg, v_bg = geostrophic_wind_from_h(h_bg, cfg.DX, cfg.DY, cfg.F0, cfg.G)
    T_bg = 273.15 + 18.0 * np.cos(np.pi * YY) - 8.0 * np.sin(np.pi * XX) - 0.004 * topography
    q_bg = 0.008 + 0.005 * np.cos(np.pi * YY)**2 - 0.002 * np.sin(np.pi * XX)**2
    q_bg = np.clip(q_bg, 1e-4, 0.025)

    # h: pure linear h_bg (no Gaussian blend with h_taipei) — Gaussian blending
    # created a BASE_H plateau at center that destroyed the climo-directed
    # geostrophic gradient and produced spurious radial PGF. Tensorearch
    # flagged this as topo-hotspot in build_taipei_state.
    h = h_bg
    u = taipei_weight * u_taipei + (1 - taipei_weight) * u_bg
    v = taipei_weight * v_taipei + (1 - taipei_weight) * v_bg
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
