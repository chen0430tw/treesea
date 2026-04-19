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
from pathlib import Path

import numpy as np

from tree_diagram.numerics.forcing import GridConfig, build_grid, build_topography
from tree_diagram.numerics.weather_state import WeatherState
from tree_diagram.numerics.weather_contract import WeatherCalibration
from tree_diagram.pipeline.oracle_pipeline import WeatherOraclePipeline


# 台北今天观测
TAIPEI_TEMP_AVG_C   = 24.0
TAIPEI_HUMIDITY_PCT = 82.5
TAIPEI_PRESSURE_HPA = 1009.0
TAIPEI_WIND_MS      = 3.6


def build_taipei_state(XX, YY, topography, cfg: GridConfig,
                       perturbation: float = 0.0) -> WeatherState:
    """以台北为中心构建 internal state。

    注意：这里的 T 是 TD 内部参考层温度（~500 hPa 面），不是地面 2m 温度。
    这是 TD 整套 shallow-water + 简化热力学 pipeline 的设计层变量。
    """
    taipei_weight = np.exp(-3.0 * (XX**2 + YY**2))

    # 内部 T 标定：让台北格点落在模型期望的中层温度
    # 对 500 hPa 面，热带春季典型温度 ~ -5°C = 268 K
    T_internal_taipei = 268.0 + perturbation
    h_taipei = 5700.0 + perturbation * 5.0
    u_taipei = TAIPEI_WIND_MS + perturbation * 0.2
    v_taipei = 0.0

    # Tetens 从 24°C + 82.5% RH 算地面比湿；然后按传统变比湿到中层 (约 1/2)
    e_sat = 6.11 * np.exp(17.27 * TAIPEI_TEMP_AVG_C / (TAIPEI_TEMP_AVG_C + 237.3))
    e_actual = e_sat * TAIPEI_HUMIDITY_PCT / 100.0
    q_surface = 0.622 * e_actual / (TAIPEI_PRESSURE_HPA - e_actual)
    q_taipei = q_surface * 0.5  # 中层比湿近似

    # 气候态背景
    h_bg = cfg.BASE_H + 220.0 * np.sin(1.8 * np.pi * XX) * np.cos(1.4 * np.pi * YY) - 0.06 * topography
    u_bg = 14.0 * np.cos(1.2 * np.pi * YY) - 6.0 * np.sin(0.8 * np.pi * XX)
    v_bg = 7.0 * np.sin(1.6 * np.pi * XX) * np.cos(np.pi * YY)
    T_bg = 273.15 + 18.0 * np.cos(np.pi * YY) - 8.0 * np.sin(np.pi * XX) - 0.004 * topography
    q_bg = 0.008 + 0.005 * np.cos(np.pi * YY)**2 - 0.002 * np.sin(np.pi * XX)**2
    q_bg = np.clip(q_bg, 1e-4, 0.025)

    h = taipei_weight * h_taipei + (1 - taipei_weight) * h_bg
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

    cfg = GridConfig(NX=64, NY=48, DX=24000.0, DY=24000.0, DT=60.0, STEPS=240)
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

    cfg = GridConfig(NX=64, NY=48, DX=24000.0, DY=24000.0, DT=60.0, STEPS=240)
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


def demo_calibrated_forecast_with_fake_calibration():
    """Demo: 提供一个示范 calibration（**警告：未经真实拟合**）。

    真正的 calibration 需要跑过去一周的 pipeline 并拟合到实际观测。
    这里只是演示 API 如何使用。
    """
    print("\n" + "=" * 72)
    print("DEMO: calibrated_quant WITH FAKE CALIBRATION (illustrative only)")
    print("=" * 72)

    # 这个 calibration 是伪造的——真实使用必须用历史数据拟合
    fake_cal = WeatherCalibration(
        location_name="Taipei (DEMO)",
        fitted_date="2026-04-19 (FAKE — no real fit)",
        T_offset_K=29.0,           # 粗暴地把 internal 268 K 推到 297 K (24°C)
        T_scale=1.0,
        h_to_pressure_k=0.02,
        q_to_rh_ratio=2.0,          # 内部比湿乘 2 ≈ 地面比湿
        wind_scale=1.0,
    )

    cfg = GridConfig(NX=64, NY=48, DX=24000.0, DY=24000.0, DT=60.0, STEPS=240)
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
        calibration=fake_cal,
    )

    print("Regime:")
    print(regime_report.human_summary())
    print()

    if quant_estimate:
        print("Quantitative (WITH FAKE CALIBRATION — treat as illustrative):")
        print(f"  Temperature 2m:  {quant_estimate.temperature_2m_C}°C")
        print(f"  Relative humidity: {quant_estimate.relative_humidity_pct}%")
        print(f"  Wind 10m:        {quant_estimate.wind_speed_10m_ms} m/s "
              f"from {quant_estimate.wind_direction_deg:.0f}°")
        print(f"  Pressure:        {quant_estimate.surface_pressure_hpa} hPa")
        print(f"  Calibration:     {quant_estimate.calibration_date}")
        print(f"  Caveat:          {quant_estimate.caveat}")

    return regime_report, quant_estimate


if __name__ == "__main__":
    # Part 1: safe default (regime only)
    regime, diag = run_regime_forecast()

    # Part 2: prove that uncalibrated quant mode is refused
    attempt_calibrated_forecast()

    # Part 3: demo calibrated API (with disclaimer)
    regime2, quant = demo_calibrated_forecast_with_fake_calibration()

    # Save outputs
    out_dir = Path("D:/treesea/runs/tree_diagram")
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "regime_only": regime.to_dict(),
        "calibrated_demo": quant.to_dict() if quant else None,
        "diagnostics_hydro": diag["hydro"],
    }
    (out_dir / "taipei_forecast_safe.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nSaved → {out_dir / 'taipei_forecast_safe.json'}")
