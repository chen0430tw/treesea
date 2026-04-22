import math

import numpy as np

from tree_diagram.io.himawari_amv import (
    _phase_correlation_shift,
    _shift_to_uv,
    compute_pseudo_amv,
)


def test_phase_correlation_shift_detects_translation():
    prev = np.zeros((16, 20), dtype=np.float32)
    prev[5:9, 6:10] = 1.0
    curr = np.zeros_like(prev)
    curr[7:11, 9:13] = 1.0  # +2y, +3x

    dy, dx, quality = _phase_correlation_shift(prev, curr)

    assert quality > 1.0
    assert abs(dy - 2.0) <= 0.25
    assert abs(dx - 3.0) <= 0.25


def test_shift_to_uv_converts_image_motion_to_east_north():
    lat = np.linspace(25.4, 24.8, 12)
    lon = np.linspace(121.2, 122.0, 16)

    u, v = _shift_to_uv(dx_pix=2.0, dy_pix=-1.0, lat=lat, lon=lon, dt_seconds=600.0)

    assert u > 0.0
    assert v > 0.0


def test_compute_pseudo_amv_reports_mean_vector():
    prev = np.zeros((18, 24), dtype=np.float32)
    prev[6:11, 7:12] = 280.0
    curr = np.zeros_like(prev)
    curr[7:12, 9:14] = 280.0
    lat = np.linspace(25.4, 24.8, prev.shape[0])
    lon = np.linspace(121.2, 122.0, prev.shape[1])

    report = compute_pseudo_amv(prev, curr, lat, lon, dt_seconds=600.0, tile_rows=3, tile_cols=4)

    assert report["mean_speed_ms"] > 0.0
    assert 0.0 <= report["mean_direction_deg"] < 360.0
    assert report["valid_fraction"] > 0.5
    assert report["tile_u_ms"].shape == (3, 4)
    assert report["tile_v_ms"].shape == (3, 4)
