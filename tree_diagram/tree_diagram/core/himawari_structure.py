from __future__ import annotations

from typing import Any

import numpy as np

from tree_diagram.core.structure_layer import (
    StructureSnapshot,
    _patches_from_score,
    _safe_zscore,
)


def extract_himawari_structure_snapshot(
    tbb: np.ndarray,
    *,
    top_k_per_kind: int = 4,
    min_pixels: int = 3,
    threshold_quantile: float = 0.90,
    metadata: dict[str, Any] | None = None,
) -> StructureSnapshot:
    tbb = np.asarray(tbb, dtype=np.float64)
    if tbb.ndim != 2:
        raise ValueError("tbb must have shape (H, W)")

    gy, gx = np.gradient(tbb)
    grad = np.sqrt(gx * gx + gy * gy)
    lap = np.gradient(gx, axis=1) + np.gradient(gy, axis=0)

    cold_anom = np.maximum(float(tbb.mean()) - tbb, 0.0)
    cold_score = np.maximum(_safe_zscore(cold_anom), 0.0)
    front_score = np.maximum(_safe_zscore(grad), 0.0)
    convective_score = (
        0.50 * cold_score
        + 0.30 * front_score
        + 0.20 * np.maximum(_safe_zscore(lap), 0.0)
    )

    patches = []
    patches.extend(
        _patches_from_score(
            "cold_cloud",
            cold_score,
            min_pixels=min_pixels,
            top_k=top_k_per_kind,
            threshold_quantile=threshold_quantile,
            extra_metrics={"tbb": tbb, "cold_anom": cold_anom},
        )
    )
    patches.extend(
        _patches_from_score(
            "tbb_gradient_front",
            front_score,
            min_pixels=min_pixels,
            top_k=top_k_per_kind,
            threshold_quantile=threshold_quantile,
            extra_metrics={"tbb_grad": grad, "tbb": tbb},
        )
    )
    patches.extend(
        _patches_from_score(
            "convective_core_seed",
            convective_score,
            min_pixels=min_pixels,
            top_k=top_k_per_kind,
            threshold_quantile=threshold_quantile,
            extra_metrics={"tbb": tbb, "tbb_grad": grad, "laplacian": lap},
        )
    )
    patches.sort(key=lambda p: (-p.score, p.kind))

    global_scores = {
        "cold_cloud_mean": float(cold_score.mean()),
        "front_mean": float(front_score.mean()),
        "convective_mean": float(convective_score.mean()),
        "cold_cloud_p95": float(np.quantile(cold_score, 0.95)),
        "front_p95": float(np.quantile(front_score, 0.95)),
        "convective_p95": float(np.quantile(convective_score, 0.95)),
        "tbb_mean": float(tbb.mean()),
        "tbb_min": float(tbb.min()),
        "tbb_max": float(tbb.max()),
    }
    return StructureSnapshot(
        shape=[int(tbb.shape[0]), int(tbb.shape[1])],
        global_scores=global_scores,
        patches=patches,
        metadata={
            "source": "himawari_tbb",
            "top_k_per_kind": int(top_k_per_kind),
            "min_pixels": int(min_pixels),
            "threshold_quantile": float(threshold_quantile),
            **(metadata or {}),
        },
    )
