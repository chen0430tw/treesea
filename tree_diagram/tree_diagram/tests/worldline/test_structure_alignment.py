import json
from pathlib import Path

import numpy as np

from tree_diagram.core.structure_alignment import (
    satellite_alignment_scores_for_fields,
    scan_td_probe_against_satellite,
)


def test_scan_td_probe_against_satellite_finds_best_frame(tmp_path: Path):
    satellite = {
        "version": "tdstruct.v1",
        "shape": [6, 6],
        "global_scores": {},
        "patches": [
            {
                "kind": "cold_cloud",
                "score": 3.0,
                "mean_score": 2.0,
                "max_score": 3.2,
                "area_pixels": 4,
                "area_fraction": 4 / 36,
                "centroid_yx": [3.5, 3.5],
                "bbox": {"y0": 3, "y1": 4, "x0": 3, "x1": 4},
                "orientation_deg": 90.0,
                "metrics": {"tbb": 272.0, "cold_anom": 10.0},
            },
            {
                "kind": "tbb_gradient_front",
                "score": 2.5,
                "mean_score": 2.0,
                "max_score": 2.9,
                "area_pixels": 4,
                "area_fraction": 4 / 36,
                "centroid_yx": [3.0, 2.5],
                "bbox": {"y0": 2, "y1": 4, "x0": 2, "x1": 3},
                "orientation_deg": 90.0,
                "metrics": {"tbb_grad": 8.0, "tbb": 278.0},
            },
            {
                "kind": "convective_core_seed",
                "score": 2.7,
                "mean_score": 2.1,
                "max_score": 3.1,
                "area_pixels": 4,
                "area_fraction": 4 / 36,
                "centroid_yx": [3.5, 3.5],
                "bbox": {"y0": 3, "y1": 4, "x0": 3, "x1": 4},
                "orientation_deg": 90.0,
                "metrics": {"tbb": 272.0, "tbb_grad": 6.0, "laplacian": 2.0},
            },
        ],
        "metadata": {},
    }
    sat_path = tmp_path / "sat.json"
    sat_path.write_text(json.dumps(satellite), encoding="utf-8")

    shape = (3, 6, 6)
    h = np.zeros(shape)
    T = np.full(shape, 289.0)
    q = np.zeros(shape)
    u = np.zeros(shape)
    v = np.zeros(shape)

    # Frame 1 aligns with the satellite structures.
    T[1, 3:5, 3:5] = 268.0
    T[1, :, 3:] = np.minimum(T[1, :, 3:], 276.0)
    q[1, 3:5, 3:5] = 1.0
    q[1, 2:5, 2:4] = 1.5
    u[1, 2:5, 2:4] = 3.0
    v[1, 2:5, 2:4] = -3.0

    probe_path = tmp_path / "probe.npz"
    np.savez_compressed(probe_path, h=h, T=T, q=q, u=u, v=v)

    report = scan_td_probe_against_satellite(sat_path, probe_path, top_k_per_kind=2, min_pixels=2, threshold_quantile=0.80)

    assert report["best_frame"] is not None
    assert report["best_frame"]["frame_idx"] == 1
    assert report["best_frame"]["frame_score"] > 0.3


def test_satellite_alignment_scores_for_fields_prefers_matching_candidate(tmp_path: Path):
    satellite = {
        "version": "tdstruct.v1",
        "shape": [6, 6],
        "global_scores": {},
        "patches": [
            {
                "kind": "cold_cloud",
                "score": 3.0,
                "mean_score": 2.0,
                "max_score": 3.2,
                "area_pixels": 4,
                "area_fraction": 4 / 36,
                "centroid_yx": [3.5, 3.5],
                "bbox": {"y0": 3, "y1": 4, "x0": 3, "x1": 4},
                "orientation_deg": 90.0,
                "metrics": {"tbb": 272.0, "cold_anom": 10.0},
            },
            {
                "kind": "tbb_gradient_front",
                "score": 2.5,
                "mean_score": 2.0,
                "max_score": 2.9,
                "area_pixels": 4,
                "area_fraction": 4 / 36,
                "centroid_yx": [3.0, 2.5],
                "bbox": {"y0": 2, "y1": 4, "x0": 2, "x1": 3},
                "orientation_deg": 90.0,
                "metrics": {"tbb_grad": 8.0, "tbb": 278.0},
            },
            {
                "kind": "convective_core_seed",
                "score": 2.7,
                "mean_score": 2.1,
                "max_score": 3.1,
                "area_pixels": 4,
                "area_fraction": 4 / 36,
                "centroid_yx": [3.5, 3.5],
                "bbox": {"y0": 3, "y1": 4, "x0": 3, "x1": 4},
                "orientation_deg": 90.0,
                "metrics": {"tbb": 272.0, "tbb_grad": 6.0, "laplacian": 2.0},
            },
        ],
        "metadata": {},
    }
    sat_path = tmp_path / "sat.json"
    sat_path.write_text(json.dumps(satellite), encoding="utf-8")

    h = np.zeros((2, 6, 6))
    T = np.full((2, 6, 6), 289.0)
    q = np.zeros((2, 6, 6))
    u = np.zeros((2, 6, 6))
    v = np.zeros((2, 6, 6))

    # candidate 0: aligned
    T[0, 3:5, 3:5] = 268.0
    T[0, :, 3:] = np.minimum(T[0, :, 3:], 276.0)
    q[0, 3:5, 3:5] = 1.0
    q[0, 2:5, 2:4] = 1.5
    u[0, 2:5, 2:4] = 3.0
    v[0, 2:5, 2:4] = -3.0

    # candidate 1: mostly flat / mismatched
    q[1, 0:2, 0:2] = 0.2
    u[1, 0:2, 0:2] = 0.5
    v[1, 0:2, 0:2] = 0.5

    scores = satellite_alignment_scores_for_fields(
        sat_path,
        h,
        T,
        q,
        u,
        v,
        top_k_per_kind=2,
        min_pixels=2,
        threshold_quantile=0.80,
    )

    assert scores.shape == (2,)
    assert scores[0] > scores[1]
