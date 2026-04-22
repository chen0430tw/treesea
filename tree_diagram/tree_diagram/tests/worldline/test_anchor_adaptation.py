import math

import numpy as np
import pytest

from td_taipei_forecast import ReferenceObs, build_taipei_state
from tree_diagram.core.worldline_kernel import (
    _T_EQ_CLIMO_BASE_K,
    _T_EQ_CLIMO_LAPSE_K_PER_M,
    _T_EQ_OBS_BLEND,
    _anchor_relax_temperature,
)
from tree_diagram.numerics.forcing import GridConfig, build_grid, build_topography, geostrophic_wind_from_h


def _angle_from_uv(u: float, v: float) -> float:
    return (math.degrees(math.atan2(-u, -v)) + 360.0) % 360.0


def _angle_diff(a: float, b: float) -> float:
    return abs(((a - b + 180.0) % 360.0) - 180.0)


def test_build_taipei_state_wind_increment_rotates_gradient_toward_obs():
    cfg = GridConfig(NX=64, NY=48, DX=6000.0, DY=6000.0)
    XX, YY, _, _ = build_grid(cfg)
    topo = build_topography(XX, YY)

    climo_obs = ReferenceObs(T_avg_C=21.6, RH_pct=75.0, P_hPa=1011.9, ws_ms=1.95, wd_deg=51.0)
    turned_obs = ReferenceObs(T_avg_C=21.6, RH_pct=75.0, P_hPa=1011.9, ws_ms=6.0, wd_deg=135.0)

    state_climo = build_taipei_state(XX, YY, topo, cfg, perturbation=0.0, obs_ref=climo_obs)
    state_turn = build_taipei_state(XX, YY, topo, cfg, perturbation=0.0, obs_ref=turned_obs)

    u_geo_climo, v_geo_climo = geostrophic_wind_from_h(state_climo.h, cfg.DX, cfg.DY, cfg.F0, cfg.G)
    u_geo_turn, v_geo_turn = geostrophic_wind_from_h(state_turn.h, cfg.DX, cfg.DY, cfg.F0, cfg.G)

    samples = [
        (cfg.NY // 2, cfg.NX // 2),
        (cfg.NY // 2 - 4, cfg.NX // 2 + 4),
        (cfg.NY // 2 + 4, cfg.NX // 2 + 4),
    ]
    climo_err = []
    turn_err = []
    for sample_y, sample_x in samples:
        wd_climo = _angle_from_uv(float(u_geo_climo[sample_y, sample_x]), float(v_geo_climo[sample_y, sample_x]))
        wd_turn = _angle_from_uv(float(u_geo_turn[sample_y, sample_x]), float(v_geo_turn[sample_y, sample_x]))
        climo_err.append(_angle_diff(wd_climo, turned_obs.wd_deg))
        turn_err.append(_angle_diff(wd_turn, turned_obs.wd_deg))

    assert float(np.mean(turn_err)) < float(np.mean(climo_err)), (
        f"obs-driven gradient did not rotate toward obs wind: "
        f"climo_mean={np.mean(climo_err):.1f} turned_mean={np.mean(turn_err):.1f} "
        f"target={turned_obs.wd_deg:.1f}"
    )


def test_anchor_relax_temperature_blends_obs_and_climo():
    topo = np.asarray([[0.0, 500.0]], dtype=np.float64)
    obs_T = np.asarray([[272.0, 274.0]], dtype=np.float64)
    got = _anchor_relax_temperature(obs_T, topo)
    climo = _T_EQ_CLIMO_BASE_K - _T_EQ_CLIMO_LAPSE_K_PER_M * topo
    want = (1.0 - _T_EQ_OBS_BLEND) * climo + _T_EQ_OBS_BLEND * obs_T
    assert np.allclose(got, want)


def test_anchor_relax_temperature_torch_parity():
    torch = pytest.importorskip("torch")
    topo = np.asarray([[0.0, 500.0]], dtype=np.float64)
    obs_T = np.asarray([[272.0, 274.0]], dtype=np.float64)
    got_np = _anchor_relax_temperature(obs_T, topo)
    got_t = _anchor_relax_temperature(torch.as_tensor(obs_T), torch.as_tensor(topo)).cpu().numpy()
    assert np.allclose(got_np, got_t, rtol=1e-6, atol=1e-10)
