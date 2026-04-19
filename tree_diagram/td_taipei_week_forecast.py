"""TD 7 天自由演绎预测：2026-04-20 .. 04-26。

架构原则（重要）：
  TD 是大气分子动力学演绎系统，不是数据分析/资料同化工具。
  观测只在 t=0 给初始状态注入一次；之后 TD 凭浅水方程 + Smagorinsky
  + Tetens 凝结 + Newtonian 气候态松弛（τ=15 天）自由演化。
  弹幕动力学自己决定 day 2-7 的轨迹，不是我们用 nudging 把它拉到哪去。

实现：
  - Day 1 可用真 obs nudging（当日资料同化）
  - Day 2-7：DA 关闭（nudging=0, wind_nudge=0），自由长积分
  - 每个 family 独立跑一次 10080 步（7 天），每 1440 步 checkpoint
  - 每天 checkpoint 对 6 个 family 按 day-1 score 加权融合
  - Calibration 只用于 internal → surface readout，不回灌
"""
from __future__ import annotations
import copy
import json
import math
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from tree_diagram.numerics.forcing import GridConfig, build_grid, build_topography
from tree_diagram.numerics.weather_state import WeatherState
from tree_diagram.numerics.ensemble import DEFAULT_BRANCHES, run_ensemble, _rotate_wind_inplace
from tree_diagram.numerics.ranking import rank_ensemble
from tree_diagram.numerics.dynamics import branch_step, LatentHeatingBudget
from tree_diagram.numerics.weather_contract import WeatherCalibration
from td_taipei_forecast import build_taipei_state, ReferenceObs


CAL_FILE = Path(__file__).parent / "calibration" / "taipei_calibration_b.json"
OUT_FILE = Path("D:/treesea/runs/tree_diagram/taipei_week_forecast.json")

TODAY = date(2026, 4, 19)
TAIPEI_TODAY_OBS = ReferenceObs(
    T_avg_C=24.0, RH_pct=82.5, P_hPa=1009.0, ws_ms=3.6, wd_deg=270.0,
)

DAYS_AHEAD = 7
STEPS_PER_DAY = 1440   # 24h at DT=60s


def integrate_family(init_state: WeatherState, obs_state: WeatherState,
                     topography, cfg: GridConfig, family_params: dict,
                     nudging_off_after_day: int = 1) -> list:
    """Run a single family over DAYS_AHEAD days, checkpointing every STEPS_PER_DAY steps.

    Day 1 uses the family's original nudging params (observation-constrained).
    Day 2+ sets nudging=0 and wind_nudge=0 (free molecular dynamics).
    Applies the family's wind_rot_deg to initial state.
    """
    wind_rot = float(family_params.get("wind_rot_deg", 0.0))
    state = _rotate_wind_inplace(init_state, wind_rot)
    budget = None
    checkpoints = []

    for day_idx in range(DAYS_AHEAD):
        # Day index 0 → Day 1 (has today obs); after day 1, switch to free
        params = dict(family_params)
        if day_idx + 1 > nudging_off_after_day:
            params["nudging"] = 0.0
            params["wind_nudge"] = 0.0

        for _ in range(STEPS_PER_DAY):
            state, budget = branch_step(state, params, obs_state, topography, cfg, budget)

        checkpoints.append({
            "T": state.T.copy(),
            "h": state.h.copy(),
            "q": state.q.copy(),
            "u": state.u.copy(),
            "v": state.v.copy(),
        })
    return checkpoints


def score_family_day1(state_dict: dict, obs: WeatherState) -> float:
    """Family ranking score based on day-1 checkpoint (when obs is valid)."""
    from tree_diagram.numerics.ranking import score_state
    state = WeatherState(**state_dict)
    return score_state(state, obs, cfg=None)["score"]


def weighted_average_day(family_states_at_day: list, weights: np.ndarray,
                          cy: int, cx: int) -> dict:
    """Weighted average of center-cell values across families at one day checkpoint."""
    T = np.average([fs["T"][cy, cx] for fs in family_states_at_day], weights=weights)
    h = np.average([fs["h"][cy, cx] for fs in family_states_at_day], weights=weights)
    q = np.average([fs["q"][cy, cx] for fs in family_states_at_day], weights=weights)
    u = np.average([fs["u"][cy, cx] for fs in family_states_at_day], weights=weights)
    v = np.average([fs["v"][cy, cx] for fs in family_states_at_day], weights=weights)
    return {"T": float(T), "h": float(h), "q": float(q),
            "u": float(u), "v": float(v)}


def apply_calibration(center: dict, cal: WeatherCalibration) -> dict:
    T_2m_C = cal.T_scale * center["T"] + cal.T_offset_K - 273.15
    RH = cal.map_humidity(center["q"], T_2m_C)
    wind = cal.map_wind(center["u"], center["v"])
    wd = (math.degrees(math.atan2(-center["u"], -center["v"])) + 360.0) % 360.0
    P = cal.map_pressure(center["h"])
    return {"T_C": round(T_2m_C, 2), "RH_pct": round(RH, 1),
            "ws_ms": round(wind, 2), "wd_deg": round(wd, 0),
            "P_hPa": round(P, 1)}


def main():
    print("=" * 78)
    print(f"TAIPEI WEEK FORECAST — molecular-dynamics free integration (TD natively)")
    print("=" * 78)
    print("Architecture: t=0 obs injection → {} days × {} steps/day free physics"
          .format(DAYS_AHEAD, STEPS_PER_DAY))
    print("Nudging (DA mode) active only on day 1; days 2-7 are free-running.")
    print()

    cal_dict = json.loads(CAL_FILE.read_text(encoding="utf-8"))["calibration"]
    cal = WeatherCalibration(**cal_dict)

    cfg = GridConfig(NX=256, NY=192, DX=6000.0, DY=6000.0, DT=60.0, STEPS=STEPS_PER_DAY)
    XX, YY, _x, _y = build_grid(cfg)
    topo = build_topography(XX, YY)
    cy = int(np.argmin(np.abs(YY[:, 0])))
    cx = int(np.argmin(np.abs(XX[0, :])))

    print(f"Input (today {TODAY}): T={TAIPEI_TODAY_OBS.T_avg_C}°C  "
          f"RH={TAIPEI_TODAY_OBS.RH_pct}%  P={TAIPEI_TODAY_OBS.P_hPa}hPa  "
          f"wind={TAIPEI_TODAY_OBS.ws_ms} m/s @ {TAIPEI_TODAY_OBS.wd_deg}°\n")

    init = build_taipei_state(XX, YY, topo, cfg, perturbation=-1.0, obs_ref=TAIPEI_TODAY_OBS)
    obs_state = build_taipei_state(XX, YY, topo, cfg, perturbation=0.0, obs_ref=TAIPEI_TODAY_OBS)

    # Integrate each family independently, 10080 steps, checkpoint daily
    family_trajectories = []
    for i, fam in enumerate(DEFAULT_BRANCHES):
        print(f"Family {i+1}/{len(DEFAULT_BRANCHES)}: {fam['name']:<13s}  "
              f"rot={fam['wind_rot_deg']:+6.1f}°  integrating...", end=" ", flush=True)
        checkpoints = integrate_family(init, obs_state, topo, cfg, fam,
                                        nudging_off_after_day=1)
        family_trajectories.append({"name": fam["name"], "params": fam,
                                     "checkpoints": checkpoints})
        print("done.")

    # Weight families by day-1 ensemble score (run standard ensemble for day-1 scoring)
    print("\nRanking families by day-1 ensemble score (for weighted fusion)...")
    day1_cfg = GridConfig(NX=256, NY=192, DX=6000.0, DY=6000.0, DT=60.0, STEPS=STEPS_PER_DAY)
    day1_raw = run_ensemble(initial_state=init, obs=obs_state, topography=topo,
                             cfg=day1_cfg, pressure_balance=1.0, n_workers=1)
    day1_ranked = rank_ensemble(day1_raw)
    scores_by_name = {r["name"]: r["score"] for r in day1_ranked}
    raw_w = np.array([scores_by_name.get(f["name"], 0.0) for f in family_trajectories])
    raw_w = raw_w - raw_w.min() + 1e-6
    weights = raw_w / raw_w.sum()

    print("Weight distribution:")
    for f, w in zip(family_trajectories, weights):
        print(f"  {f['name']:<15s}  score={scores_by_name.get(f['name'],0):.4f}  weight={w:.3f}")

    # Build daily forecasts by weighted-averaging all families at each day's checkpoint
    forecasts = []
    for d in range(DAYS_AHEAD):
        target_day = TODAY + timedelta(days=d + 1)
        family_states_day_d = [f["checkpoints"][d] for f in family_trajectories]
        center = weighted_average_day(family_states_day_d, weights, cy, cx)
        pred = apply_calibration(center, cal)
        pred["date"] = target_day.isoformat()
        pred["mode"] = "DA" if d == 0 else "free"
        forecasts.append(pred)

    print()
    print("=" * 78)
    print(f"{'Date':<12} {'Mode':<5} {'T':>7} {'RH':>6} {'Wind':>14} {'P':>9}")
    print("-" * 78)
    for f in forecasts:
        print(f"{f['date']:<12} {f['mode']:<5} {f['T_C']:>5.1f}°C {f['RH_pct']:>5.1f}% "
              f"{f['ws_ms']:>4.1f} m/s @ {f['wd_deg']:>3.0f}° {f['P_hPa']:>6.1f}hPa")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps({
        "today": TODAY.isoformat(),
        "today_obs": TAIPEI_TODAY_OBS.__dict__,
        "calibration": cal_dict,
        "architecture": {
            "mode": "MD_free_integration",
            "steps_total": DAYS_AHEAD * STEPS_PER_DAY,
            "steps_per_day": STEPS_PER_DAY,
            "da_nudging": "day 1 only",
            "fusion": "top-all weighted by day-1 ensemble score",
        },
        "family_weights": [{"name": f["name"], "weight": float(w)}
                           for f, w in zip(family_trajectories, weights)],
        "forecasts": forecasts,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {OUT_FILE}")


if __name__ == "__main__":
    main()
