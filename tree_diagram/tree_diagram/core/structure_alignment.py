from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from tree_diagram.core.structure_layer import StructurePatch, StructureSnapshot, extract_structure_snapshot
from tree_diagram.core.structure_mesh_alignment import compare_satellite_payload_to_td_snapshot


_DEFAULT_KIND_MAP = {
    "cold_cloud": "moist",
    "tbb_gradient_front": "front",
    "convective_core_seed": "moist",
}


@dataclass
class PatchAlignment:
    satellite_kind: str
    td_kind: str
    centroid_distance: float
    orientation_delta_deg: float
    area_fraction_delta: float
    alignment_score: float
    satellite_patch: dict[str, Any]
    td_patch: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "satellite_kind": self.satellite_kind,
            "td_kind": self.td_kind,
            "centroid_distance": self.centroid_distance,
            "orientation_delta_deg": self.orientation_delta_deg,
            "area_fraction_delta": self.area_fraction_delta,
            "alignment_score": self.alignment_score,
            "satellite_patch": self.satellite_patch,
            "td_patch": self.td_patch,
        }


def _patch_from_dict(payload: dict[str, Any]) -> StructurePatch:
    return StructurePatch(
        kind=str(payload["kind"]),
        score=float(payload["score"]),
        mean_score=float(payload["mean_score"]),
        max_score=float(payload["max_score"]),
        area_pixels=int(payload["area_pixels"]),
        area_fraction=float(payload["area_fraction"]),
        centroid_yx=[float(payload["centroid_yx"][0]), float(payload["centroid_yx"][1])],
        bbox={k: int(v) for k, v in payload["bbox"].items()},
        orientation_deg=float(payload["orientation_deg"]),
        metrics={str(k): float(v) for k, v in payload.get("metrics", {}).items()},
    )


def load_snapshot_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _best_patch_by_kind(snapshot: StructureSnapshot) -> dict[str, StructurePatch]:
    best: dict[str, StructurePatch] = {}
    for patch in snapshot.patches:
        current = best.get(patch.kind)
        if current is None or patch.score > current.score:
            best[patch.kind] = patch
    return best


def _best_patch_by_kind_from_json(payload: dict[str, Any]) -> dict[str, StructurePatch]:
    patches = [_patch_from_dict(p) for p in payload.get("patches", [])]
    return _best_patch_by_kind(
        StructureSnapshot(
            shape=[int(payload["shape"][0]), int(payload["shape"][1])],
            global_scores={str(k): float(v) for k, v in payload.get("global_scores", {}).items()},
            patches=patches,
            metadata=dict(payload.get("metadata", {})),
        )
    )


def _norm_centroid(patch: StructurePatch, shape: tuple[int, int]) -> tuple[float, float]:
    h, w = shape
    y = patch.centroid_yx[0] / max(1.0, h - 1.0)
    x = patch.centroid_yx[1] / max(1.0, w - 1.0)
    return y, x


def align_patch_pair(
    satellite_patch: StructurePatch,
    td_patch: StructurePatch,
    sat_shape: tuple[int, int],
    td_shape: tuple[int, int],
) -> PatchAlignment:
    sy, sx = _norm_centroid(satellite_patch, sat_shape)
    ty, tx = _norm_centroid(td_patch, td_shape)
    centroid_distance = float(math.hypot(sy - ty, sx - tx))
    angle = abs(satellite_patch.orientation_deg - td_patch.orientation_deg)
    orientation_delta = float(min(angle, 180.0 - angle))
    area_delta = float(abs(satellite_patch.area_fraction - td_patch.area_fraction))
    score = 1.0 - (
        0.55 * min(1.0, centroid_distance / math.sqrt(2.0))
        + 0.25 * min(1.0, orientation_delta / 90.0)
        + 0.20 * min(1.0, area_delta)
    )
    score = float(max(0.0, min(1.0, score)))
    return PatchAlignment(
        satellite_kind=satellite_patch.kind,
        td_kind=td_patch.kind,
        centroid_distance=centroid_distance,
        orientation_delta_deg=orientation_delta,
        area_fraction_delta=area_delta,
        alignment_score=score,
        satellite_patch=satellite_patch.to_dict(),
        td_patch=td_patch.to_dict(),
    )


def compare_satellite_to_td_snapshot(
    satellite_payload: dict[str, Any],
    td_snapshot: StructureSnapshot,
    kind_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    kind_map = kind_map or dict(_DEFAULT_KIND_MAP)
    sat_shape = (int(satellite_payload["shape"][0]), int(satellite_payload["shape"][1]))
    td_shape = (int(td_snapshot.shape[0]), int(td_snapshot.shape[1]))
    sat_best = _best_patch_by_kind_from_json(satellite_payload)
    td_best = _best_patch_by_kind(td_snapshot)

    alignments: list[PatchAlignment] = []
    missing: list[dict[str, str]] = []
    for sat_kind, td_kind in kind_map.items():
        sat_patch = sat_best.get(sat_kind)
        td_patch = td_best.get(td_kind)
        if sat_patch is None or td_patch is None:
            missing.append(
                {
                    "satellite_kind": sat_kind,
                    "td_kind": td_kind,
                    "reason": "missing satellite patch" if sat_patch is None else "missing td patch",
                }
            )
            continue
        alignments.append(align_patch_pair(sat_patch, td_patch, sat_shape, td_shape))

    frame_score = float(np.mean([a.alignment_score for a in alignments])) if alignments else 0.0
    return {
        "frame_score": frame_score,
        "alignments": [a.to_dict() for a in alignments],
        "missing": missing,
        "td_global_scores": td_snapshot.global_scores,
    }


def scan_td_probe_against_satellite(
    satellite_json: Path,
    td_probe: Path,
    *,
    top_k_per_kind: int = 4,
    min_pixels: int = 6,
    threshold_quantile: float = 0.93,
) -> dict[str, Any]:
    sat_payload = load_snapshot_json(satellite_json)
    with np.load(td_probe) as data:
        h_seq = np.asarray(data["h"], dtype=np.float64)
        T_seq = np.asarray(data["T"], dtype=np.float64)
        q_seq = np.asarray(data["q"], dtype=np.float64)
        u_seq = np.asarray(data["u"], dtype=np.float64)
        v_seq = np.asarray(data["v"], dtype=np.float64)

    frame_reports = []
    for frame_idx in range(h_seq.shape[0]):
        td_snapshot = extract_structure_snapshot(
            h_seq[frame_idx],
            T_seq[frame_idx],
            q_seq[frame_idx],
            u_seq[frame_idx],
            v_seq[frame_idx],
            top_k_per_kind=top_k_per_kind,
            min_pixels=min_pixels,
            threshold_quantile=threshold_quantile,
        )
        report = compare_satellite_to_td_snapshot(sat_payload, td_snapshot)
        report["frame_idx"] = int(frame_idx)
        frame_reports.append(report)

    best = max(frame_reports, key=lambda r: r["frame_score"]) if frame_reports else None
    return {
        "satellite_json": str(satellite_json),
        "td_probe": str(td_probe),
        "best_frame": best,
        "frame_reports": frame_reports,
    }


def satellite_alignment_scores_for_fields(
    satellite_payload_or_path: dict[str, Any] | Path,
    h: np.ndarray,
    T: np.ndarray,
    q: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    *,
    top_k_per_kind: int = 4,
    min_pixels: int = 6,
    threshold_quantile: float = 0.93,
) -> np.ndarray:
    reports = satellite_alignment_reports_for_fields(
        satellite_payload_or_path,
        h,
        T,
        q,
        u,
        v,
        top_k_per_kind=top_k_per_kind,
        min_pixels=min_pixels,
        threshold_quantile=threshold_quantile,
    )
    return np.asarray([float(r["frame_score"]) for r in reports], dtype=np.float64)


def satellite_alignment_reports_for_fields(
    satellite_payload_or_path: dict[str, Any] | Path,
    h: np.ndarray,
    T: np.ndarray,
    q: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    *,
    top_k_per_kind: int = 4,
    min_pixels: int = 6,
    threshold_quantile: float = 0.93,
) -> list[dict[str, Any]]:
    """Score each candidate field bundle against a satellite structure snapshot.

    Inputs are batched candidate fields with shared shape (N, H, W). Returns one
    compare_satellite_to_td_snapshot() report per candidate.
    """
    if isinstance(satellite_payload_or_path, Path):
        satellite_payload = load_snapshot_json(satellite_payload_or_path)
    else:
        satellite_payload = satellite_payload_or_path

    h = np.asarray(h, dtype=np.float64)
    T = np.asarray(T, dtype=np.float64)
    q = np.asarray(q, dtype=np.float64)
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    if not (h.shape == T.shape == q.shape == u.shape == v.shape) or h.ndim != 3:
        raise ValueError("h/T/q/u/v must share shape (N, H, W)")

    reports: list[dict[str, Any]] = []
    for idx in range(h.shape[0]):
        td_snapshot = extract_structure_snapshot(
            h[idx],
            T[idx],
            q[idx],
            u[idx],
            v[idx],
            top_k_per_kind=top_k_per_kind,
            min_pixels=min_pixels,
            threshold_quantile=threshold_quantile,
        )
        patch_report = compare_satellite_to_td_snapshot(satellite_payload, td_snapshot)
        mesh_report = compare_satellite_payload_to_td_snapshot(satellite_payload, td_snapshot)
        patch_components = {
            str(item["satellite_kind"]): float(item["alignment_score"])
            for item in patch_report.get("alignments", [])
        }
        mesh_components = {
            str(k): float(v)
            for k, v in mesh_report.get("component_scores", {}).items()
        }
        component_scores = {
            "tbb_gradient_front": 0.40 * patch_components.get("tbb_gradient_front", 0.0)
            + 0.60 * mesh_components.get("tbb_gradient_front", 0.0),
            "cold_cloud": 0.35 * patch_components.get("cold_cloud", 0.0)
            + 0.65 * mesh_components.get("cold_cloud", 0.0),
            "convective_core_seed": 0.25 * patch_components.get("convective_core_seed", 0.0)
            + 0.75 * mesh_components.get("convective_core_seed", 0.0),
        }
        report = {
            **patch_report,
            "frame_score": float(
                0.40 * float(patch_report.get("frame_score", 0.0))
                + 0.60 * float(mesh_report.get("mesh_score", 0.0))
            ),
            "component_scores": component_scores,
            "patch_report": patch_report,
            "mesh_report": mesh_report,
        }
        reports.append(report)
    return reports
