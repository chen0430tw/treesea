from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


_STRUCTURE_VERSION = "tdstruct.v1"


@dataclass
class StructurePatch:
    kind: str
    score: float
    mean_score: float
    max_score: float
    area_pixels: int
    area_fraction: float
    centroid_yx: list[float]
    bbox: dict[str, int]
    orientation_deg: float
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "score": self.score,
            "mean_score": self.mean_score,
            "max_score": self.max_score,
            "area_pixels": self.area_pixels,
            "area_fraction": self.area_fraction,
            "centroid_yx": self.centroid_yx,
            "bbox": self.bbox,
            "orientation_deg": self.orientation_deg,
            "metrics": self.metrics,
        }


@dataclass
class StructureSnapshot:
    shape: list[int]
    global_scores: dict[str, float]
    patches: list[StructurePatch]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": _STRUCTURE_VERSION,
            "shape": self.shape,
            "global_scores": self.global_scores,
            "patches": [p.to_dict() for p in self.patches],
            "metadata": self.metadata,
        }


@dataclass
class StructureTrack:
    kind: str
    frames: list[int]
    centroid_path: list[list[float]]
    score_mean: float
    score_max: float
    persistence: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "frames": self.frames,
            "centroid_path": self.centroid_path,
            "score_mean": self.score_mean,
            "score_max": self.score_max,
            "persistence": self.persistence,
        }


@dataclass
class StructureSequence:
    snapshots: list[StructureSnapshot]
    tracks: list[StructureTrack]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": _STRUCTURE_VERSION,
            "snapshots": [s.to_dict() for s in self.snapshots],
            "tracks": [t.to_dict() for t in self.tracks],
            "metadata": self.metadata,
        }


def _safe_zscore(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr, dtype=np.float64)
    mu = float(arr.mean())
    sig = float(arr.std())
    if sig < 1e-9:
        return np.zeros_like(arr, dtype=np.float64)
    return (arr - mu) / sig


def _grad(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    gy, gx = np.gradient(arr)
    return gy, gx


def _component_orientation(coords: np.ndarray) -> float:
    if len(coords) < 2:
        return 0.0
    centered = coords - coords.mean(axis=0, keepdims=True)
    cov = centered.T @ centered / max(1, len(coords) - 1)
    vals, vecs = np.linalg.eigh(cov)
    axis = vecs[:, int(np.argmax(vals))]
    return float((math.degrees(math.atan2(axis[0], axis[1])) + 360.0) % 180.0)


def _connected_components(mask: np.ndarray) -> list[np.ndarray]:
    mask = np.asarray(mask, dtype=bool)
    H, W = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    comps: list[np.ndarray] = []
    for y in range(H):
        for x in range(W):
            if not mask[y, x] or seen[y, x]:
                continue
            stack = [(y, x)]
            seen[y, x] = True
            coords = []
            while stack:
                cy, cx = stack.pop()
                coords.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            comps.append(np.asarray(coords, dtype=np.int32))
    return comps


def _patches_from_score(
    kind: str,
    score_map: np.ndarray,
    *,
    min_pixels: int,
    top_k: int,
    threshold_quantile: float,
    extra_metrics: dict[str, np.ndarray] | None = None,
) -> list[StructurePatch]:
    extra_metrics = extra_metrics or {}
    positive = score_map[np.isfinite(score_map)]
    if positive.size == 0:
        return []
    thresh = float(np.quantile(positive, threshold_quantile))
    mask = score_map >= thresh
    comps = [c for c in _connected_components(mask) if len(c) >= min_pixels]
    H, W = score_map.shape
    patches: list[StructurePatch] = []
    for coords in comps:
        yy = coords[:, 0]
        xx = coords[:, 1]
        values = score_map[yy, xx]
        centroid = [float(yy.mean()), float(xx.mean())]
        bbox = {"y0": int(yy.min()), "y1": int(yy.max()), "x0": int(xx.min()), "x1": int(xx.max())}
        metrics = {
            name: float(arr[yy, xx].mean())
            for name, arr in extra_metrics.items()
        }
        patch = StructurePatch(
            kind=kind,
            score=float(values.mean() + 0.35 * values.max()),
            mean_score=float(values.mean()),
            max_score=float(values.max()),
            area_pixels=int(len(coords)),
            area_fraction=float(len(coords) / (H * W)),
            centroid_yx=centroid,
            bbox=bbox,
            orientation_deg=_component_orientation(coords.astype(np.float64)),
            metrics=metrics,
        )
        patches.append(patch)
    patches.sort(key=lambda p: (-p.score, -p.area_pixels))
    return patches[:top_k]


def extract_structure_snapshot(
    h: np.ndarray,
    T: np.ndarray,
    q: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    *,
    top_k_per_kind: int = 4,
    min_pixels: int = 6,
    threshold_quantile: float = 0.93,
) -> StructureSnapshot:
    h = np.asarray(h, dtype=np.float64)
    T = np.asarray(T, dtype=np.float64)
    q = np.asarray(q, dtype=np.float64)
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    if not (h.shape == T.shape == q.shape == u.shape == v.shape) or h.ndim != 2:
        raise ValueError("h/T/q/u/v must share shape (H, W)")

    speed = np.sqrt(u * u + v * v)
    T_gy, T_gx = _grad(T)
    q_gy, q_gx = _grad(q)
    u_gy, u_gx = _grad(u)
    v_gy, v_gx = _grad(v)
    speed_gy, speed_gx = _grad(speed)

    T_grad = np.sqrt(T_gx * T_gx + T_gy * T_gy)
    q_grad = np.sqrt(q_gx * q_gx + q_gy * q_gy)
    speed_grad = np.sqrt(speed_gx * speed_gx + speed_gy * speed_gy)
    vorticity = v_gx - u_gy
    divergence = u_gx + v_gy
    convergence = np.maximum(-divergence, 0.0)
    q_pos_anom = np.maximum(q - float(q.mean()), 0.0)

    front_score = (
        0.55 * np.maximum(_safe_zscore(T_grad), 0.0)
        + 0.30 * np.maximum(_safe_zscore(q_grad), 0.0)
        + 0.15 * np.maximum(_safe_zscore(convergence), 0.0)
    )
    shear_score = (
        0.55 * np.maximum(_safe_zscore(np.abs(vorticity)), 0.0)
        + 0.45 * np.maximum(_safe_zscore(speed_grad), 0.0)
    )
    moist_score = (
        0.65 * np.maximum(_safe_zscore(q_pos_anom), 0.0)
        + 0.35 * np.maximum(_safe_zscore(q_grad), 0.0)
    )

    patches = []
    patches.extend(
        _patches_from_score(
            "front",
            front_score,
            min_pixels=min_pixels,
            top_k=top_k_per_kind,
            threshold_quantile=threshold_quantile,
            extra_metrics={"T_grad": T_grad, "q_grad": q_grad, "convergence": convergence},
        )
    )
    patches.extend(
        _patches_from_score(
            "shear",
            shear_score,
            min_pixels=min_pixels,
            top_k=top_k_per_kind,
            threshold_quantile=threshold_quantile,
            extra_metrics={"speed_grad": speed_grad, "vorticity": np.abs(vorticity)},
        )
    )
    patches.extend(
        _patches_from_score(
            "moist",
            moist_score,
            min_pixels=min_pixels,
            top_k=top_k_per_kind,
            threshold_quantile=threshold_quantile,
            extra_metrics={"q_anom": q_pos_anom, "q_grad": q_grad},
        )
    )
    patches.sort(key=lambda p: (-p.score, p.kind))

    global_scores = {
        "front_mean": float(front_score.mean()),
        "shear_mean": float(shear_score.mean()),
        "moist_mean": float(moist_score.mean()),
        "front_p95": float(np.quantile(front_score, 0.95)),
        "shear_p95": float(np.quantile(shear_score, 0.95)),
        "moist_p95": float(np.quantile(moist_score, 0.95)),
    }
    return StructureSnapshot(
        shape=[int(h.shape[0]), int(h.shape[1])],
        global_scores=global_scores,
        patches=patches,
        metadata={
            "top_k_per_kind": int(top_k_per_kind),
            "min_pixels": int(min_pixels),
            "threshold_quantile": float(threshold_quantile),
        },
    )


def extract_structure_sequence(
    h_seq: np.ndarray,
    T_seq: np.ndarray,
    q_seq: np.ndarray,
    u_seq: np.ndarray,
    v_seq: np.ndarray,
    *,
    top_k_per_kind: int = 4,
    min_pixels: int = 6,
    threshold_quantile: float = 0.93,
    max_link_distance: float = 8.0,
) -> StructureSequence:
    h_seq = np.asarray(h_seq)
    T_seq = np.asarray(T_seq)
    q_seq = np.asarray(q_seq)
    u_seq = np.asarray(u_seq)
    v_seq = np.asarray(v_seq)
    if not (h_seq.shape == T_seq.shape == q_seq.shape == u_seq.shape == v_seq.shape) or h_seq.ndim != 3:
        raise ValueError("h_seq/T_seq/q_seq/u_seq/v_seq must share shape (T, H, W)")

    snapshots = [
        extract_structure_snapshot(
            h_seq[t], T_seq[t], q_seq[t], u_seq[t], v_seq[t],
            top_k_per_kind=top_k_per_kind,
            min_pixels=min_pixels,
            threshold_quantile=threshold_quantile,
        )
        for t in range(h_seq.shape[0])
    ]

    tracks: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    for frame_idx, snap in enumerate(snapshots):
        unused = set(range(len(snap.patches)))
        next_active: list[dict[str, Any]] = []
        for track in active:
            best = None
            best_dist = None
            for i in list(unused):
                patch = snap.patches[i]
                if patch.kind != track["kind"]:
                    continue
                dy = patch.centroid_yx[0] - track["centroid"][-1][0]
                dx = patch.centroid_yx[1] - track["centroid"][-1][1]
                dist = math.hypot(dy, dx)
                if dist <= max_link_distance and (best_dist is None or dist < best_dist):
                    best = i
                    best_dist = dist
            if best is not None:
                patch = snap.patches[best]
                unused.remove(best)
                track["frames"].append(frame_idx)
                track["centroid"].append(patch.centroid_yx)
                track["scores"].append(patch.score)
                next_active.append(track)
            else:
                tracks.append(track)
        for i in sorted(unused):
            patch = snap.patches[i]
            next_active.append(
                {
                    "kind": patch.kind,
                    "frames": [frame_idx],
                    "centroid": [patch.centroid_yx],
                    "scores": [patch.score],
                }
            )
        active = next_active
    tracks.extend(active)

    final_tracks = [
        StructureTrack(
            kind=t["kind"],
            frames=[int(f) for f in t["frames"]],
            centroid_path=[[float(c[0]), float(c[1])] for c in t["centroid"]],
            score_mean=float(np.mean(t["scores"])),
            score_max=float(np.max(t["scores"])),
            persistence=int(len(t["frames"])),
        )
        for t in tracks
    ]
    final_tracks.sort(key=lambda t: (-t.persistence, -t.score_max, t.kind))
    return StructureSequence(
        snapshots=snapshots,
        tracks=final_tracks,
        metadata={
            "top_k_per_kind": int(top_k_per_kind),
            "min_pixels": int(min_pixels),
            "threshold_quantile": float(threshold_quantile),
            "max_link_distance": float(max_link_distance),
        },
    )


def structure_snapshot_json(snapshot: StructureSnapshot) -> str:
    return json.dumps(snapshot.to_dict(), ensure_ascii=False, indent=2)


def structure_sequence_json(sequence: StructureSequence) -> str:
    return json.dumps(sequence.to_dict(), ensure_ascii=False, indent=2)
