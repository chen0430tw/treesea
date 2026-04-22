from __future__ import annotations

import math
import sys
from pathlib import Path

from tree_diagram.numerics.forcing import GridConfig, build_grid, build_topography


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from td_refit_and_week import TAIPEI_STATION_ELEV_M, _surface_from_internal  # noqa: E402
from td_taipei_forecast import ReferenceObs, build_taipei_state  # noqa: E402


def test_surface_wind_uses_low_level_reference_not_full_column():
    cfg = GridConfig(NX=128, NY=96, DX=6000.0, DY=6000.0, DT=45.0, STEPS=1920)
    XX, YY, *_ = build_grid(cfg)
    topo = build_topography(XX, YY)
    obs = ReferenceObs(T_avg_C=25.5, RH_pct=69.0, P_hPa=1012.0, ws_ms=3.5, wd_deg=60.0)
    state = build_taipei_state(XX, YY, topo, cfg, perturbation=0.0, obs_ref=obs)

    cy, cx = state.h.shape[0] // 2, state.h.shape[1] // 2
    h_mid = float(state.h[cy, cx])
    u_mid = float(state.u[cy, cx])
    v_mid = float(state.v[cy, cx])
    mid_ws = math.hypot(u_mid, v_mid)

    surface = _surface_from_internal(
        h_mid_m=h_mid,
        T_mid_k=float(state.T[cy, cx]),
        q_mid=float(state.q[cy, cx]),
        u_mid=u_mid,
        v_mid=v_mid,
        surface_elevation_m=TAIPEI_STATION_ELEV_M,
        pressure_anchor_h_mid_m=h_mid,
        pressure_anchor_surface_hpa=obs.P_hPa,
    )

    new_ratio = surface["wind_speed_10m_ms"] / mid_ws
    old_ratio = math.log((10.0 + 1.0) / 1.0) / math.log((max(50.0, h_mid - TAIPEI_STATION_ELEV_M) + 1.0) / 1.0)

    assert 0.75 <= new_ratio <= 0.90
    assert new_ratio > old_ratio * 2.0
    assert surface["wind_speed_10m_ms"] < mid_ws
    assert surface["wind_speed_10m_ms"] > obs.ws_ms
