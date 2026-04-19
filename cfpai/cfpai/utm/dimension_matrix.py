"""
UTM Dimension Matrix — 维度矩阵分析。

白皮书 §10.2：DM = elite 参数分布的局部协方差 / 自适应尺度。
追踪 UTM 搜索过程中参数空间的收缩方向和速度。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class DimensionMatrixSnapshot:
    """单代的维度矩阵快照。"""
    generation: int
    means: dict[str, float]
    stds: dict[str, float]
    covariance: list[list[float]]
    eigenvalues: list[float]
    eigenvectors: list[list[float]]
    contraction_ratio: float  # 相比上一代的收缩比


PARAM_NAMES = [
    "w_mom", "w_trend", "w_vol", "w_volume", "w_dd",
    "lambda_risk", "persistence_bonus", "max_assets",
]


def compute_dimension_matrix(elite_vecs: np.ndarray) -> dict:
    """计算 elite 参数向量集合的维度矩阵。

    Parameters
    ----------
    elite_vecs : ndarray, shape (k, d)
        k 个 elite 参数向量

    Returns
    -------
    dict with keys: means, stds, covariance, eigenvalues, eigenvectors
    """
    means = elite_vecs.mean(axis=0)
    stds = elite_vecs.std(axis=0)

    # 协方差矩阵
    if len(elite_vecs) < 2:
        cov = np.diag(stds ** 2)
    else:
        cov = np.cov(elite_vecs, rowvar=False)

    # 特征分解：揭示参数空间的主方向
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # 降序排列
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    return {
        "means": {k: float(v) for k, v in zip(PARAM_NAMES, means)},
        "stds": {k: float(v) for k, v in zip(PARAM_NAMES, stds)},
        "covariance": cov.tolist(),
        "eigenvalues": eigenvalues.tolist(),
        "eigenvectors": eigenvectors.tolist(),
    }


def track_contraction(history: list[dict]) -> list[DimensionMatrixSnapshot]:
    """追踪多代的收缩序列。

    Parameters
    ----------
    history : list of dict
        每代的 elite 参数快照，格式 [{generation, elite_vecs: ndarray}, ...]

    Returns
    -------
    list of DimensionMatrixSnapshot
    """
    snapshots = []
    prev_volume = None

    for entry in history:
        gen = entry["generation"]
        elite_vecs = np.array(entry["elite_vecs"])
        dm = compute_dimension_matrix(elite_vecs)

        # 超椭球体积 ∝ sqrt(prod(eigenvalues))
        evals = np.array(dm["eigenvalues"])
        evals_pos = np.maximum(evals, 1e-20)
        volume = float(np.sqrt(np.prod(evals_pos)))

        contraction = volume / prev_volume if prev_volume and prev_volume > 0 else 1.0
        prev_volume = volume

        snapshots.append(DimensionMatrixSnapshot(
            generation=gen,
            means=dm["means"],
            stds=dm["stds"],
            covariance=dm["covariance"],
            eigenvalues=dm["eigenvalues"],
            eigenvectors=dm["eigenvectors"],
            contraction_ratio=round(contraction, 4),
        ))

    return snapshots


def sensitivity_ranking(dm: dict) -> list[tuple[str, float]]:
    """根据维度矩阵的特征值，排列参数敏感度。

    返回 [(param_name, sensitivity_score), ...] 按敏感度降序。
    """
    eigenvalues = np.array(dm["eigenvalues"])
    eigenvectors = np.array(dm["eigenvectors"])

    # 每个参数的敏感度 = 其在各主成分上的贡献加权
    total_var = eigenvalues.sum()
    if total_var < 1e-12:
        return [(p, 0.0) for p in PARAM_NAMES]

    sensitivities = []
    for i, name in enumerate(PARAM_NAMES):
        score = sum(
            eigenvalues[j] * eigenvectors[i, j] ** 2
            for j in range(len(eigenvalues))
        ) / total_var
        sensitivities.append((name, round(float(score), 4)))

    sensitivities.sort(key=lambda x: x[1], reverse=True)
    return sensitivities
