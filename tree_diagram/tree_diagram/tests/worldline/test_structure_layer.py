import json

import numpy as np

from tree_diagram.core.structure_layer import (
    extract_structure_sequence,
    extract_structure_snapshot,
    structure_sequence_json,
    structure_snapshot_json,
)


def _make_grid(H=64, W=64):
    x = np.linspace(-1.0, 1.0, W)
    y = np.linspace(-1.0, 1.0, H)
    return np.meshgrid(x, y)


def test_front_patch_detects_vertical_boundary():
    XX, YY = _make_grid()
    h = np.zeros_like(XX)
    T = 270.0 + 6.0 * np.tanh(12.0 * XX)
    q = 0.010 + 0.004 * np.tanh(12.0 * XX)
    u = np.zeros_like(XX)
    v = np.zeros_like(XX)

    snap = extract_structure_snapshot(h, T, q, u, v)
    fronts = [p for p in snap.patches if p.kind == "front"]
    assert fronts
    top = fronts[0]
    assert abs(top.centroid_yx[1] - 31.5) < 6.0
    assert 60.0 <= top.orientation_deg <= 120.0


def test_shear_patch_detects_horizontal_shear_band():
    XX, YY = _make_grid()
    h = np.zeros_like(XX)
    T = np.full_like(XX, 272.0)
    q = np.full_like(XX, 0.008)
    u = 8.0 * np.tanh(10.0 * YY)
    v = np.zeros_like(XX)

    snap = extract_structure_snapshot(h, T, q, u, v)
    shears = [p for p in snap.patches if p.kind == "shear"]
    assert shears
    top = shears[0]
    assert abs(top.centroid_yx[0] - 31.5) < 6.0


def test_moist_patch_detects_blob():
    XX, YY = _make_grid()
    h = np.zeros_like(XX)
    T = np.full_like(XX, 272.0)
    q = 0.006 + 0.010 * np.exp(-20.0 * ((XX - 0.25) ** 2 + (YY + 0.15) ** 2))
    u = np.zeros_like(XX)
    v = np.zeros_like(XX)

    snap = extract_structure_snapshot(h, T, q, u, v)
    moist = [p for p in snap.patches if p.kind == "moist"]
    assert moist
    top = moist[0]
    assert top.centroid_yx[1] > 32.0
    assert top.centroid_yx[0] < 32.0


def test_sequence_tracks_moving_moist_patch():
    XX, YY = _make_grid()
    h = np.zeros((3, *XX.shape))
    T = np.full((3, *XX.shape), 272.0)
    u = np.zeros((3, *XX.shape))
    v = np.zeros((3, *XX.shape))
    q = np.empty((3, *XX.shape))
    centers = [(-0.2, -0.2), (0.0, -0.05), (0.2, 0.1)]
    for t, (cx, cy) in enumerate(centers):
        q[t] = 0.006 + 0.010 * np.exp(-18.0 * ((XX - cx) ** 2 + (YY - cy) ** 2))

    seq = extract_structure_sequence(h, T, q, u, v, max_link_distance=12.0)
    moist_tracks = [tr for tr in seq.tracks if tr.kind == "moist"]
    assert moist_tracks
    assert moist_tracks[0].persistence >= 3


def test_snapshot_and_sequence_json_roundtrip():
    XX, YY = _make_grid()
    h = np.zeros_like(XX)
    T = 270.0 + 6.0 * np.tanh(12.0 * XX)
    q = 0.010 + 0.004 * np.tanh(12.0 * XX)
    u = np.zeros_like(XX)
    v = np.zeros_like(XX)
    snap = extract_structure_snapshot(h, T, q, u, v)
    seq = extract_structure_sequence(h[None], T[None], q[None], u[None], v[None])
    snap_payload = json.loads(structure_snapshot_json(snap))
    seq_payload = json.loads(structure_sequence_json(seq))
    assert snap_payload["version"] == "tdstruct.v1"
    assert seq_payload["version"] == "tdstruct.v1"
