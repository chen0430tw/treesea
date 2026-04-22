import json

from tree_diagram.core.structure_layer import StructurePatch, StructureSnapshot
from tree_diagram.core.structure_mesh import (
    build_satellite_structure_mesh,
    build_structure_mesh,
    structure_mesh_json,
)


def _patch(kind, score, cy, cx, orient, area=0.02):
    return StructurePatch(
        kind=kind,
        score=score,
        mean_score=score * 0.9,
        max_score=score * 1.1,
        area_pixels=12,
        area_fraction=area,
        centroid_yx=[float(cy), float(cx)],
        bbox={"y0": int(cy) - 1, "y1": int(cy) + 1, "x0": int(cx) - 1, "x1": int(cx) + 1},
        orientation_deg=float(orient),
        metrics={},
    )


def test_build_structure_mesh_links_front_and_moist_into_mixed_strip():
    snapshot = StructureSnapshot(
        shape=[64, 64],
        global_scores={},
        patches=[
            _patch("front", 3.0, 20, 20, 92),
            _patch("moist", 2.8, 22, 23, 88),
            _patch("shear", 2.5, 55, 55, 10),
        ],
    )

    mesh = build_structure_mesh(snapshot, max_link_distance=8.0, max_orientation_delta_deg=25.0, min_edge_score=0.2)

    assert len(mesh.edges) == 1
    assert mesh.edges[0].edge_type == "front-moist"
    assert mesh.strips
    top = mesh.strips[0]
    assert top.component_size == 2
    assert top.strip_type == "mixed_strip"
    assert len(top.strip_centroid_path) == 2


def test_build_structure_mesh_keeps_separate_components_when_far_apart():
    snapshot = StructureSnapshot(
        shape=[64, 64],
        global_scores={},
        patches=[
            _patch("front", 3.0, 10, 10, 90),
            _patch("front", 2.9, 50, 50, 91),
        ],
    )

    mesh = build_structure_mesh(snapshot, max_link_distance=12.0, max_orientation_delta_deg=25.0, min_edge_score=0.2)

    assert len(mesh.edges) == 0
    assert len(mesh.strips) == 2
    assert all(s.strip_type == "front_strip" for s in mesh.strips)


def test_build_satellite_structure_mesh_and_json_roundtrip():
    payload = {
        "shape": [12, 16],
        "global_scores": {"cold_cloud_mean": 0.3},
        "patches": [
            {
                "kind": "front",
                "score": 3.2,
                "mean_score": 2.5,
                "max_score": 3.4,
                "area_pixels": 8,
                "area_fraction": 8 / (12 * 16),
                "centroid_yx": [6.0, 7.0],
                "bbox": {"y0": 5, "y1": 7, "x0": 6, "x1": 8},
                "orientation_deg": 95.0,
                "metrics": {"tbb_grad": 7.0},
            },
            {
                "kind": "moist",
                "score": 3.0,
                "mean_score": 2.4,
                "max_score": 3.2,
                "area_pixels": 9,
                "area_fraction": 9 / (12 * 16),
                "centroid_yx": [6.5, 8.5],
                "bbox": {"y0": 5, "y1": 8, "x0": 7, "x1": 9},
                "orientation_deg": 100.0,
                "metrics": {"tbb": 274.0},
            },
        ],
    }

    mesh = build_satellite_structure_mesh(payload, max_link_distance=4.0, max_orientation_delta_deg=20.0, min_edge_score=0.2)
    dumped = json.loads(structure_mesh_json(mesh))

    assert dumped["version"] == "tdmesh.v1"
    assert dumped["metadata"]["patch_count"] == 2
    assert dumped["metadata"]["strip_count"] >= 1
