# collapse_operator.py
"""
QCU 坍缩算符层。

包含：
- build_collapse_cache()：根据物理参数组装跳跃算符列表
- CollapseCache 类型别名

跳跃算符来源
------------
1. 腔光子泄漏：sqrt(κ_k) · a_k
2. qubit 弛豫（T1）：sqrt(1/T1_j) · σ_−,j
3. qubit 纯退相干（Tφ）：sqrt(1/(2Tφ_j)) · σ_z,j
4. mode 间同步耗散：sqrt(γ_sync) · (a_k − a_{k+1})
5. qubit 0 强制复位：sqrt(γ_reset) · σ_−,0
6. qubit 0 相位噪声：sqrt(γ_φ0/2) · σ_z,0
"""

from __future__ import annotations

import numpy as np

from .state_repr import dagger

# 类型别名：list of (c, c†, c†c)
CollapseCache = list[tuple[np.ndarray, np.ndarray, np.ndarray]]


def build_collapse_cache(
    Nq: int,
    Nm: int,
    kappa: np.ndarray,
    T1: np.ndarray,
    Tphi: np.ndarray,
    smJ: list[np.ndarray],
    szJ: list[np.ndarray],
    aJ: list[np.ndarray],
    gamma_sync: float = 0.0,
    gamma_reset_q0: float = 0.0,
    gamma_phi0: float = 0.0,
) -> CollapseCache:
    """组装跳跃算符缓存。

    Parameters
    ----------
    Nq : int
        qubit 数量
    Nm : int
        mode 数量
    kappa : ndarray, shape (Nm,)
        腔光子泄漏率
    T1 : ndarray, shape (Nq,)
        qubit 弛豫时间
    Tphi : ndarray, shape (Nq,)
        qubit 纯退相干时间
    smJ : list of ndarray
        各 qubit 的 σ_− 算符（嵌入全空间）
    szJ : list of ndarray
        各 qubit 的 σ_z 算符（嵌入全空间）
    aJ : list of ndarray
        各 mode 的湮灭算符（嵌入全空间）
    gamma_sync : float
        mode 间同步耗散率（仅 Nm ≥ 2 时生效）
    gamma_reset_q0 : float
        qubit 0 强制复位率
    gamma_phi0 : float
        qubit 0 相位噪声率

    Returns
    -------
    CollapseCache
        跳跃算符列表，每项为 (c, c†, c†c)
    """
    c_ops: list[np.ndarray] = []

    # 1. 腔光子泄漏
    for k in range(Nm):
        if kappa[k] > 0:
            c_ops.append(np.sqrt(kappa[k]) * aJ[k])

    # 2. qubit 弛豫
    for j in range(Nq):
        if np.isfinite(T1[j]) and T1[j] > 0:
            c_ops.append(np.sqrt(1.0 / T1[j]) * smJ[j])

    # 3. qubit 纯退相干
    for j in range(Nq):
        if np.isfinite(Tphi[j]) and Tphi[j] > 0:
            c_ops.append(np.sqrt((1.0 / Tphi[j]) / 2.0) * szJ[j])

    # 4. mode 间同步耗散
    if gamma_sync > 0 and Nm >= 2:
        g = np.sqrt(gamma_sync)
        for k in range(Nm - 1):
            c_ops.append(g * (aJ[k] - aJ[k + 1]))

    # 5. qubit 0 强制复位
    if gamma_reset_q0 > 0:
        c_ops.append(np.sqrt(gamma_reset_q0) * smJ[0])

    # 6. qubit 0 相位噪声
    if gamma_phi0 > 0:
        c_ops.append(np.sqrt(gamma_phi0 / 2.0) * szJ[0])

    # 预计算 c†, c†c，避免运行时重复计算
    cache: CollapseCache = []
    for c in c_ops:
        cd = dagger(c)
        cache.append((c, cd, cd @ c))
    return cache
