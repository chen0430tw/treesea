from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .structure_layer import StructureSnapshot
from .structure_mesh import StructureMesh, StructureStrip, build_satellite_structure_mesh, build_structure_mesh


@dataclass
class StripAlignment:
    satellite_strip_type: str
    td_strip_type: str
    centroid_distance: float
    orientation_delta_deg: float
    strength_delta: float
    alignment_score: float
    satellite_strip: dict[str, Any]
    td_strip: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "satellite_strip_type": self.satellite_strip_type,
            "td_strip_type": self.td_strip_type,
            "centroid_distance": self.centroid_distance,
            "orientation_delta_deg": self.orientation_delta_deg,
            "strength_delta": self.strength_delta,
            "alignment_score": self.alignment_score,
            "satellite_strip": self.satellite_strip,
            "td_strip": self.td_strip,
        }


def _strip_centroid(strip: StructureStrip) -> tuple[float, float]:
    arr = np.asarray(strip.strip_centroid_path, dtype=np.float64)
    if arr.size == 0:
        return 0.0, 0.0
    return float(arr[:, 0].mean()), float(arr[:, 1].mean())


def _norm_centroid(strip: StructureStrip, shape: tuple[int, int]) -> tuple[float, float]:
    h, w = shape
    y, x = _strip_centroid(strip)
    return y / max(1.0, h - 1.0), x / max(1.0, w - 1.0)


def _strip_family(strip_type: str) -> str:
    if strip_type == "mixed_strip":
        return "mixed"
    return strip_type.replace("_strip", "")


def _types_compatible(a: str, b: str) -> bool:
    fa = _strip_family(a)
    fb = _strip_family(b)
    return fa == fb or "mixed" in (fa, fb)


def _strip_has_kind(strip: StructureStrip, kind: str) -> bool:
    return kind in getattr(strip, "member_kinds", [])


def _best_alignment_score(
    alignments: list[StripAlignment],
    *,
    sat_kind: str | None = None,
    td_kind: str | None = None,
    td_requires_any: tuple[str, ...] = (),
) -> float:
    best = 0.0
    for align in alignments:
        sat_strip = align.satellite_strip
        td_strip = align.td_strip
        sat_kinds = tuple(str(k) for k in sat_strip.get("member_kinds", ()))
        td_kinds = tuple(str(k) for k in td_strip.get("member_kinds", ()))
        if sat_kind is not None and sat_kind not in sat_kinds:
            continue
        if td_kind is not None and td_kind not in td_kinds:
            continue
        if td_requires_any and not any(k in td_kinds for k in td_requires_any):
            continue
        best = max(best, float(align.alignment_score))
    return float(best)


def align_strip_pair(
    satellite_strip: StructureStrip,
    td_strip: StructureStrip,
    sat_shape: tuple[int, int],
    td_shape: tuple[int, int],
) -> StripAlignment:
    sy, sx = _norm_centroid(satellite_strip, sat_shape)
    ty, tx = _norm_centroid(td_strip, td_shape)
    centroid_distance = float(math.hypot(sy - ty, sx - tx))
    angle = abs(float(satellite_strip.strip_orientation_deg) - float(td_strip.strip_orientation_deg))
    orientation_delta = float(min(angle, 180.0 - angle))
    strength_delta = float(abs(float(satellite_strip.strip_strength) - float(td_strip.strip_strength)))
    score = 1.0 - (
        0.45 * min(1.0, centroid_distance / math.sqrt(2.0))
        + 0.30 * min(1.0, orientation_delta / 90.0)
        + 0.25 * min(1.0, strength_delta / max(1.0, float(satellite_strip.strip_strength), float(td_strip.strip_strength)))
    )
    score = float(max(0.0, min(1.0, score)))
    return StripAlignment(
        satellite_strip_type=satellite_strip.strip_type,
        td_strip_type=td_strip.strip_type,
        centroid_distance=centroid_distance,
        orientation_delta_deg=orientation_delta,
        strength_delta=strength_delta,
        alignment_score=score,
        satellite_strip=satellite_strip.to_dict(),
        td_strip=td_strip.to_dict(),
    )


def compare_meshes(
    satellite_mesh: StructureMesh,
    td_mesh: StructureMesh,
) -> dict[str, Any]:
    sat_shape = (int(satellite_mesh.shape[0]), int(satellite_mesh.shape[1]))
    td_shape = (int(td_mesh.shape[0]), int(td_mesh.shape[1]))

    alignments: list[StripAlignment] = []
    missing: list[dict[str, str]] = []
    used_td: set[int] = set()

    for sat_strip in satellite_mesh.strips:
        best_idx = None
        best_align = None
        for idx, td_strip in enumerate(td_mesh.strips):
            if idx in used_td:
                continue
            if not _types_compatible(sat_strip.strip_type, td_strip.strip_type):
                continue
            align = align_strip_pair(sat_strip, td_strip, sat_shape, td_shape)
            if best_align is None or align.alignment_score > best_align.alignment_score:
                best_idx = idx
                best_align = align
        if best_idx is None or best_align is None:
            missing.append({"satellite_strip_type": sat_strip.strip_type, "reason": "no compatible td strip"})
            continue
        used_td.add(best_idx)
        alignments.append(best_align)

    mesh_score = float(np.mean([a.alignment_score for a in alignments])) if alignments else 0.0
    front_strip_score = _best_alignment_score(alignments, sat_kind="front", td_kind="front")
    moist_strip_score = _best_alignment_score(alignments, sat_kind="moist", td_kind="moist")
    convective_support_score = _best_alignment_score(
        alignments,
        sat_kind="moist",
        td_kind="moist",
        td_requires_any=("front", "shear"),
    )
    return {
        "mesh_score": mesh_score,
        "component_scores": {
            "tbb_gradient_front": front_strip_score,
            "cold_cloud": moist_strip_score,
            "convective_core_seed": convective_support_score,
        },
        "alignments": [a.to_dict() for a in alignments],
        "missing": missing,
        "satellite_strip_count": len(satellite_mesh.strips),
        "td_strip_count": len(td_mesh.strips),
    }


def compare_satellite_payload_to_td_snapshot(
    satellite_payload: dict[str, Any],
    td_snapshot: StructureSnapshot,
    *,
    satellite_mesh_kwargs: dict[str, Any] | None = None,
    td_mesh_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    satellite_mesh = build_satellite_structure_mesh(satellite_payload, **(satellite_mesh_kwargs or {}))
    td_mesh = build_structure_mesh(td_snapshot, **(td_mesh_kwargs or {}))
    report = compare_meshes(satellite_mesh, td_mesh)
    report["satellite_mesh"] = satellite_mesh.to_dict()
    report["td_mesh"] = td_mesh.to_dict()
    return report
