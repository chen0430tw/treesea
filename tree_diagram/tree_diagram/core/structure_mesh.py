from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .structure_layer import StructurePatch, StructureSnapshot


_STRUCTURE_MESH_VERSION = "tdmesh.v1"
_SATELLITE_KIND_MAP = {
    "cold_cloud": "moist",
    "tbb_gradient_front": "front",
    "convective_core_seed": "moist",
}
_ALLOWED_EDGE_TYPES = {
    ("front", "front"): "front-front",
    ("front", "moist"): "front-moist",
    ("moist", "front"): "front-moist",
    ("shear", "front"): "shear-front",
    ("front", "shear"): "shear-front",
}


@dataclass
class StructureEdge:
    src_idx: int
    dst_idx: int
    edge_type: str
    distance: float
    direction_diff_deg: float
    strength_compatibility: float
    edge_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "src_idx": self.src_idx,
            "dst_idx": self.dst_idx,
            "edge_type": self.edge_type,
            "distance": self.distance,
            "direction_diff_deg": self.direction_diff_deg,
            "strength_compatibility": self.strength_compatibility,
            "edge_score": self.edge_score,
        }


@dataclass
class StructureStrip:
    patch_indices: list[int]
    edge_indices: list[int]
    member_kinds: list[str]
    strip_type: str
    strip_orientation_deg: float
    strip_centroid_path: list[list[float]]
    strip_strength: float
    component_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "patch_indices": self.patch_indices,
            "edge_indices": self.edge_indices,
            "member_kinds": self.member_kinds,
            "strip_type": self.strip_type,
            "strip_orientation_deg": self.strip_orientation_deg,
            "strip_centroid_path": self.strip_centroid_path,
            "strip_strength": self.strip_strength,
            "component_size": self.component_size,
        }


@dataclass
class StructureMesh:
    shape: list[int]
    patches: list[StructurePatch]
    edges: list[StructureEdge]
    strips: list[StructureStrip]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": _STRUCTURE_MESH_VERSION,
            "shape": self.shape,
            "patches": [p.to_dict() for p in self.patches],
            "edges": [e.to_dict() for e in self.edges],
            "strips": [s.to_dict() for s in self.strips],
            "metadata": self.metadata,
        }


def _orientation_delta_deg(a: float, b: float) -> float:
    delta = abs(float(a) - float(b)) % 180.0
    return min(delta, 180.0 - delta)


def _edge_type(kind_a: str, kind_b: str) -> str | None:
    return _ALLOWED_EDGE_TYPES.get((kind_a, kind_b))


def _weighted_strip_orientation_deg(patches: list[StructurePatch]) -> float:
    weights = np.asarray([max(1.0e-6, p.score) for p in patches], dtype=np.float64)
    angles = np.radians([2.0 * float(p.orientation_deg) for p in patches])
    x = float(np.sum(weights * np.cos(angles)))
    y = float(np.sum(weights * np.sin(angles)))
    if abs(x) + abs(y) < 1.0e-12:
        return 0.0
    return float((0.5 * math.degrees(math.atan2(y, x)) + 180.0) % 180.0)


def _strip_centroid_path(patches: list[StructurePatch], orientation_deg: float) -> list[list[float]]:
    if not patches:
        return []
    theta = math.radians(float(orientation_deg))
    axis = np.asarray([math.sin(theta), math.cos(theta)], dtype=np.float64)  # y, x
    centroids = np.asarray([p.centroid_yx for p in patches], dtype=np.float64)
    origin = centroids.mean(axis=0)
    proj = (centroids - origin) @ axis
    order = np.argsort(proj)
    return [[float(centroids[i, 0]), float(centroids[i, 1])] for i in order]


def _strip_type(patches: list[StructurePatch]) -> str:
    kinds = {p.kind for p in patches}
    if len(kinds) == 1:
        kind = next(iter(kinds))
        if kind == "front":
            return "front_strip"
        if kind == "moist":
            return "moist_strip"
        if kind == "shear":
            return "shear_strip"
    return "mixed_strip"


def _patch_from_payload(payload: dict[str, Any], *, kind_map: dict[str, str] | None = None) -> StructurePatch:
    raw_kind = str(payload["kind"])
    mapped_kind = kind_map.get(raw_kind, raw_kind) if kind_map is not None else raw_kind
    metrics = {str(k): float(v) for k, v in payload.get("metrics", {}).items()}
    if mapped_kind != raw_kind:
        metrics["source_kind"] = raw_kind
    return StructurePatch(
        kind=mapped_kind,
        score=float(payload["score"]),
        mean_score=float(payload["mean_score"]),
        max_score=float(payload["max_score"]),
        area_pixels=int(payload["area_pixels"]),
        area_fraction=float(payload["area_fraction"]),
        centroid_yx=[float(payload["centroid_yx"][0]), float(payload["centroid_yx"][1])],
        bbox={k: int(v) for k, v in payload["bbox"].items()},
        orientation_deg=float(payload["orientation_deg"]),
        metrics=metrics,
    )


def build_structure_mesh(
    snapshot: StructureSnapshot,
    *,
    max_link_distance: float = 28.0,
    max_orientation_delta_deg: float = 65.0,
    min_edge_score: float = 0.45,
) -> StructureMesh:
    patches = list(snapshot.patches)
    edges: list[StructureEdge] = []
    adjacency: dict[int, list[tuple[int, int]]] = {i: [] for i in range(len(patches))}

    for i in range(len(patches)):
        for j in range(i + 1, len(patches)):
            a = patches[i]
            b = patches[j]
            edge_type = _edge_type(a.kind, b.kind)
            if edge_type is None:
                continue
            dy = float(a.centroid_yx[0] - b.centroid_yx[0])
            dx = float(a.centroid_yx[1] - b.centroid_yx[1])
            dist = float(math.hypot(dy, dx))
            if dist > max_link_distance:
                continue
            direction_delta = _orientation_delta_deg(a.orientation_deg, b.orientation_deg)
            if direction_delta > max_orientation_delta_deg:
                continue
            strength = float(min(a.score, b.score) / max(max(a.score, b.score), 1.0e-9))
            distance_score = max(0.0, 1.0 - dist / max_link_distance)
            direction_score = max(0.0, 1.0 - direction_delta / max_orientation_delta_deg)
            edge_score = float(
                0.40 * distance_score
                + 0.30 * direction_score
                + 0.30 * strength
            )
            if edge_score < min_edge_score:
                continue
            edge = StructureEdge(
                src_idx=i,
                dst_idx=j,
                edge_type=edge_type,
                distance=dist,
                direction_diff_deg=direction_delta,
                strength_compatibility=strength,
                edge_score=edge_score,
            )
            edge_idx = len(edges)
            edges.append(edge)
            adjacency[i].append((j, edge_idx))
            adjacency[j].append((i, edge_idx))

    strips: list[StructureStrip] = []
    seen: set[int] = set()
    for start in range(len(patches)):
        if start in seen:
            continue
        stack = [start]
        component_nodes: list[int] = []
        component_edges: set[int] = set()
        seen.add(start)
        while stack:
            cur = stack.pop()
            component_nodes.append(cur)
            for nxt, edge_idx in adjacency.get(cur, []):
                component_edges.add(edge_idx)
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        comp_patches = [patches[i] for i in component_nodes]
        strip_orientation = _weighted_strip_orientation_deg(comp_patches)
        strip_path = _strip_centroid_path(comp_patches, strip_orientation)
        if component_edges:
            edge_mean = float(np.mean([edges[i].edge_score for i in component_edges]))
        else:
            edge_mean = 0.0
        node_mean = float(np.mean([p.score for p in comp_patches])) if comp_patches else 0.0
        strip_strength = float(0.70 * node_mean + 0.30 * edge_mean)
        strips.append(
            StructureStrip(
                patch_indices=sorted(component_nodes),
                edge_indices=sorted(component_edges),
                member_kinds=sorted({p.kind for p in comp_patches}),
                strip_type=_strip_type(comp_patches),
                strip_orientation_deg=strip_orientation,
                strip_centroid_path=strip_path,
                strip_strength=strip_strength,
                component_size=len(component_nodes),
            )
        )
    strips.sort(key=lambda s: (-s.strip_strength, -s.component_size, s.strip_type))

    return StructureMesh(
        shape=list(snapshot.shape),
        patches=patches,
        edges=edges,
        strips=strips,
        metadata={
            "max_link_distance": float(max_link_distance),
            "max_orientation_delta_deg": float(max_orientation_delta_deg),
            "min_edge_score": float(min_edge_score),
            "patch_count": int(len(patches)),
            "edge_count": int(len(edges)),
            "strip_count": int(len(strips)),
        },
    )


def build_satellite_structure_mesh(
    payload_json: dict[str, Any],
    *,
    max_link_distance: float = 8.0,
    max_orientation_delta_deg: float = 65.0,
    min_edge_score: float = 0.45,
) -> StructureMesh:
    snapshot = StructureSnapshot(
        shape=[int(payload_json["shape"][0]), int(payload_json["shape"][1])],
        global_scores={str(k): float(v) for k, v in payload_json.get("global_scores", {}).items()},
        patches=[_patch_from_payload(p, kind_map=_SATELLITE_KIND_MAP) for p in payload_json.get("patches", [])],
        metadata=dict(payload_json.get("metadata", {})),
    )
    return build_structure_mesh(
        snapshot,
        max_link_distance=max_link_distance,
        max_orientation_delta_deg=max_orientation_delta_deg,
        min_edge_score=min_edge_score,
    )


def dominant_strip_signal(
    mesh: StructureMesh,
    *,
    preferred_types: tuple[str, ...] = ("front_strip", "mixed_strip", "moist_strip"),
) -> dict[str, float] | None:
    candidates = [s for s in mesh.strips if s.strip_type in preferred_types]
    if not candidates:
        candidates = list(mesh.strips)
    if not candidates:
        return None
    best = max(
        candidates,
        key=lambda s: (float(s.strip_strength), float(s.component_size), -float(s.strip_orientation_deg)),
    )
    strength_ref = max(float(mesh.strips[0].strip_strength), 1.0e-6) if mesh.strips else 1.0
    norm_weight = float(np.clip(best.strip_strength / strength_ref, 0.0, 1.0))
    return {
        "strip_type": best.strip_type,
        "orientation_deg": float(best.strip_orientation_deg),
        "weight": norm_weight,
        "strip_strength": float(best.strip_strength),
        "component_size": float(best.component_size),
    }


def structure_mesh_json(mesh: StructureMesh) -> str:
    return json.dumps(mesh.to_dict(), ensure_ascii=False, indent=2)
