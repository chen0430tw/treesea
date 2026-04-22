import numpy as np
import pytest

from tree_diagram.io.himawari_extract import (
    GeoBBox,
    _pick_primary_variable,
    bbox_slices,
    compute_field_features,
)


def test_bbox_slices_select_expected_window():
    lat = np.linspace(28.0, 20.0, 9)
    lon = np.linspace(118.0, 126.0, 9)
    bbox = GeoBBox(lon_min=121.0, lon_max=123.0, lat_min=23.0, lat_max=25.0)

    lat_slice, lon_slice = bbox_slices(lat, lon, bbox)

    assert lat_slice.start < lat_slice.stop
    assert lon_slice.start < lon_slice.stop
    assert lat[lat_slice].min() <= 25.0
    assert lat[lat_slice].max() >= 23.0
    assert lon[lon_slice].min() <= 121.0
    assert lon[lon_slice].max() >= 123.0


def test_compute_field_features_reports_gradient_signal():
    field = np.zeros((6, 6), dtype=float)
    field[:, 3:] = 10.0

    feats = compute_field_features(field)

    assert feats["field_mean"] > 0.0
    assert feats["field_max"] == 10.0
    assert feats["edge_mean"] > 0.0
    assert feats["edge_p90"] >= feats["edge_mean"]
    assert 0.0 < feats["cold_frac_p10"] <= 1.0
    assert 0.0 < feats["warm_frac_p90"] <= 1.0


def test_bbox_slices_raises_when_bbox_outside_domain():
    lat = np.linspace(50.0, 40.0, 11)
    lon = np.linspace(145.0, 155.0, 11)
    bbox = GeoBBox(lon_min=121.2, lon_max=122.0, lat_min=24.8, lat_max=25.4)

    with pytest.raises(ValueError):
        bbox_slices(lat, lon, bbox)


def test_pick_primary_variable_prefers_infrared_band_13():
    names = ["band_id", "tbb_14", "tbb_13", "albedo_01"]
    assert _pick_primary_variable(names) == "tbb_13"
