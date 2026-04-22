import numpy as np

from tree_diagram.core.himawari_structure import extract_himawari_structure_snapshot


def test_himawari_structure_finds_cold_cloud_patch():
    tbb = np.full((10, 12), 289.0, dtype=float)
    tbb[3:7, 4:8] = 268.0

    snap = extract_himawari_structure_snapshot(tbb, top_k_per_kind=2, min_pixels=3, threshold_quantile=0.85)

    cold = [p for p in snap.patches if p.kind == "cold_cloud"]
    assert cold
    assert cold[0].metrics["cold_anom"] > 0.0
    assert cold[0].max_score > 0.0


def test_himawari_structure_finds_gradient_front():
    tbb = np.full((10, 12), 289.0, dtype=float)
    tbb[:, 6:] = 272.0

    snap = extract_himawari_structure_snapshot(tbb, top_k_per_kind=2, min_pixels=3, threshold_quantile=0.80)

    fronts = [p for p in snap.patches if p.kind == "tbb_gradient_front"]
    assert fronts
    assert fronts[0].metrics["tbb_grad"] > 0.0


def test_himawari_structure_finds_convective_seed():
    yy, xx = np.mgrid[:11, :11]
    r2 = (yy - 5) ** 2 + (xx - 5) ** 2
    tbb = 289.0 - 18.0 * np.exp(-r2 / 4.0)

    snap = extract_himawari_structure_snapshot(tbb, top_k_per_kind=2, min_pixels=3, threshold_quantile=0.82)

    conv = [p for p in snap.patches if p.kind == "convective_core_seed"]
    assert conv
    cy, cx = conv[0].centroid_yx
    assert abs(cy - 5.0) < 2.0
    assert abs(cx - 5.0) < 2.0
