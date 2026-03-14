# entanglement_metrics.py
"""
QCU 纠缠度量层。

包含：
- partial_transpose_qubit0()：对 qubit 0 做偏转置
- negativity_qubit0_vs_rest()：qubit 0 与其余自由度的纠缠负值度
"""

from __future__ import annotations

import numpy as np
from .state_repr import dagger


def partial_transpose_qubit0(rho: np.ndarray) -> np.ndarray:
    """对 qubit 0 子系统做偏转置。

    假设希尔伯特空间结构为 qubit_0 ⊗ rest，
    其中 dim(qubit_0) = 2，dim(rest) = DIM / 2。

    Parameters
    ----------
    rho : ndarray, shape (DIM, DIM)
        全系统密度矩阵

    Returns
    -------
    ndarray, shape (DIM, DIM)
        对 qubit 0 做偏转置后的矩阵
    """
    try:
        import cupy
        xp = cupy.get_array_module(rho)
    except ImportError:
        xp = np

    DIM = rho.shape[0]
    assert DIM % 2 == 0, "DIM 必须为偶数（qubit_0 维度=2）"
    dim_rest = DIM // 2
    R = rho.reshape(2, dim_rest, 2, dim_rest)
    R_pt = xp.transpose(R, (2, 1, 0, 3))
    return R_pt.reshape(DIM, DIM)


def negativity_qubit0_vs_rest(rho: np.ndarray) -> float:
    """计算 qubit 0 与其余自由度之间的纠缠负值度 (negativity)。

    负值度 = sum(|λ_i|) for λ_i < 0，其中 λ_i 为偏转置矩阵的本征值。
    值域 [0, 0.5]；0 表示无纠缠，越大纠缠越强。

    Parameters
    ----------
    rho : ndarray, shape (DIM, DIM)
        全系统密度矩阵

    Returns
    -------
    float
        纠缠负值度
    """
    try:
        import cupy
        xp = cupy.get_array_module(rho)
    except ImportError:
        xp = np

    rho_pt = partial_transpose_qubit0(rho)
    rho_pt = 0.5 * (rho_pt + dagger(rho_pt))
    # eigvalsh 需要 cuSolver，统一转回 CPU 做（非热路径，每 obs_every 步一次）
    rho_pt_cpu = rho_pt.get() if hasattr(rho_pt, "get") else rho_pt
    evals = np.linalg.eigvalsh(rho_pt_cpu)
    neg_evals = evals[evals < 0.0]
    return float(np.sum(np.abs(neg_evals)))
