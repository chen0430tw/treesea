from tree_diagram.core.structure_layer import StructurePatch, StructureSnapshot
from tree_diagram.core.structure_mesh_alignment import compare_satellite_payload_to_td_snapshot


def _patch(kind, score, cy, cx, orient, area=0.03):
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


def test_compare_satellite_payload_to_td_snapshot_aligns_front_strip():
    satellite_payload = {
        "shape": [12, 16],
        "global_scores": {},
        "patches": [
            {
                "kind": "tbb_gradient_front",
                "score": 3.0,
                "mean_score": 2.4,
                "max_score": 3.2,
                "area_pixels": 10,
                "area_fraction": 10 / (12 * 16),
                "centroid_yx": [7.0, 5.0],
                "bbox": {"y0": 6, "y1": 8, "x0": 4, "x1": 6},
                "orientation_deg": 95.0,
                "metrics": {"tbb_grad": 8.0},
            },
            {
                "kind": "cold_cloud",
                "score": 2.8,
                "mean_score": 2.2,
                "max_score": 3.0,
                "area_pixels": 10,
                "area_fraction": 10 / (12 * 16),
                "centroid_yx": [7.5, 6.5],
                "bbox": {"y0": 6, "y1": 9, "x0": 5, "x1": 7},
                "orientation_deg": 100.0,
                "metrics": {"tbb": 274.0},
            },
        ],
    }
    td_snapshot = StructureSnapshot(
        shape=[64, 64],
        global_scores={},
        patches=[
            _patch("front", 3.1, 38, 20, 92),
            _patch("moist", 2.9, 40, 24, 96),
            _patch("shear", 2.0, 10, 50, 10),
        ],
    )

    report = compare_satellite_payload_to_td_snapshot(
        satellite_payload,
        td_snapshot,
        satellite_mesh_kwargs={"max_link_distance": 4.0, "max_orientation_delta_deg": 20.0, "min_edge_score": 0.2},
        td_mesh_kwargs={"max_link_distance": 8.0, "max_orientation_delta_deg": 20.0, "min_edge_score": 0.2},
    )

    assert report["mesh_score"] > 0.4
    assert report["alignments"]
    assert report["component_scores"]["tbb_gradient_front"] > 0.0
    top = report["alignments"][0]
    assert top["satellite_strip_type"] in {"mixed_strip", "front_strip"}
    assert top["td_strip_type"] in {"mixed_strip", "front_strip"}


def test_compare_satellite_payload_to_td_snapshot_rewards_convective_support_when_moist_is_front_organized():
    satellite_payload = {
        "shape": [12, 16],
        "global_scores": {},
        "patches": [
            {
                "kind": "tbb_gradient_front",
                "score": 3.2,
                "mean_score": 2.6,
                "max_score": 3.4,
                "area_pixels": 10,
                "area_fraction": 10 / (12 * 16),
                "centroid_yx": [7.0, 5.0],
                "bbox": {"y0": 6, "y1": 8, "x0": 4, "x1": 6},
                "orientation_deg": 95.0,
                "metrics": {"tbb_grad": 8.0},
            },
            {
                "kind": "cold_cloud",
                "score": 3.0,
                "mean_score": 2.4,
                "max_score": 3.2,
                "area_pixels": 10,
                "area_fraction": 10 / (12 * 16),
                "centroid_yx": [7.5, 6.5],
                "bbox": {"y0": 6, "y1": 9, "x0": 5, "x1": 7},
                "orientation_deg": 100.0,
                "metrics": {"tbb": 274.0},
            },
            {
                "kind": "convective_core_seed",
                "score": 2.8,
                "mean_score": 2.2,
                "max_score": 3.0,
                "area_pixels": 8,
                "area_fraction": 8 / (12 * 16),
                "centroid_yx": [7.5, 6.5],
                "bbox": {"y0": 7, "y1": 8, "x0": 6, "x1": 7},
                "orientation_deg": 100.0,
                "metrics": {"tbb": 271.0},
            },
        ],
    }
    organized = StructureSnapshot(
        shape=[64, 64],
        global_scores={},
        patches=[
            _patch("front", 3.2, 37, 20, 94),
            _patch("moist", 3.0, 39, 24, 98),
        ],
    )
    unorganized = StructureSnapshot(
        shape=[64, 64],
        global_scores={},
        patches=[
            _patch("moist", 3.0, 39, 24, 98),
        ],
    )

    organized_report = compare_satellite_payload_to_td_snapshot(
        satellite_payload,
        organized,
        satellite_mesh_kwargs={"max_link_distance": 4.0, "max_orientation_delta_deg": 20.0, "min_edge_score": 0.2},
        td_mesh_kwargs={"max_link_distance": 8.0, "max_orientation_delta_deg": 20.0, "min_edge_score": 0.2},
    )
    unorganized_report = compare_satellite_payload_to_td_snapshot(
        satellite_payload,
        unorganized,
        satellite_mesh_kwargs={"max_link_distance": 4.0, "max_orientation_delta_deg": 20.0, "min_edge_score": 0.2},
        td_mesh_kwargs={"max_link_distance": 8.0, "max_orientation_delta_deg": 20.0, "min_edge_score": 0.2},
    )

    assert organized_report["component_scores"]["convective_core_seed"] > unorganized_report["component_scores"]["convective_core_seed"]
    assert organized_report["component_scores"]["cold_cloud"] >= unorganized_report["component_scores"]["cold_cloud"]
