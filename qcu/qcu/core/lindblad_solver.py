# lindblad_solver.py
"""
Lindblad 主方程 RK4 求解器。

包含：
- lindblad_rhs()：计算 Lindblad 主方程右端项 dρ/dt
- rk4_step()：单步 RK4 时间推进
- alloc_rk4_buffers()：预分配 RK4 所需缓冲区

物理背景
--------
Lindblad 主方程：

    dρ/dt = −i[H, ρ]
            + Σ_k (c_k ρ c_k† − ½ c_k†c_k ρ − ½ ρ c_k†c_k)

其中 c_k 为跳跃算符（jump operators）。
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np

# 跳跃算符缓存类型：list of (c, c†, c†c)
CollapseCache = List[Tuple[np.ndarray, np.ndarray, np.ndarray]]


def alloc_rk4_buffers(DIM: int, xp=None):
    """预分配 RK4 求解所需的 8 个工作缓冲区。

    Parameters
    ----------
    DIM : int
        希尔伯特空间维度
    xp : module, optional
        numpy 或 cupy；默认 numpy。

    Returns
    -------
    tuple of 8 ndarray
        (tmp1, tmp2, k1, k2, k3, k4, work, out)
    """
    if xp is None:
        xp = np
    shape = (DIM, DIM)
    dtype = np.complex128
    return tuple(xp.zeros(shape, dtype=dtype) for _ in range(8))


def lindblad_rhs(
    rho: np.ndarray,
    H: np.ndarray,
    c_cache: CollapseCache,
    tmp1: np.ndarray,
    tmp2: np.ndarray,
    out: np.ndarray,
) -> np.ndarray:
    """计算 Lindblad 主方程右端项 dρ/dt。

    结果写入 out 并返回，不分配新内存。

    Parameters
    ----------
    rho : ndarray
        当前密度矩阵
    H : ndarray
        当前时刻 Hamiltonian
    c_cache : list of (c, c†, c†c)
        预计算的跳跃算符缓存
    tmp1, tmp2 : ndarray
        工作缓冲区（in-place 使用，内容会被覆盖）
    out : ndarray
        输出缓冲区

    Returns
    -------
    out : ndarray
        dρ/dt
    """
    try:
        import cupy
        xp = cupy.get_array_module(rho)
    except ImportError:
        xp = np

    # 相干项：−i[H, ρ]
    xp.matmul(H, rho, out=tmp1)
    xp.matmul(rho, H, out=tmp2)
    out[:] = -1j * (tmp1 - tmp2)

    # 耗散项：Σ_k (c ρ c† − ½ c†c ρ − ½ ρ c†c)
    for c, cd, cd_c in c_cache:
        xp.matmul(c, rho, out=tmp1)
        xp.matmul(tmp1, cd, out=tmp2)
        out[:] += tmp2

        xp.matmul(cd_c, rho, out=tmp1)
        out[:] -= 0.5 * tmp1

        xp.matmul(rho, cd_c, out=tmp1)
        out[:] -= 0.5 * tmp1

    return out


def rk4_step(
    rho: np.ndarray,
    dt: float,
    H: np.ndarray,
    c_cache: CollapseCache,
    buffers: tuple,
) -> np.ndarray:
    """执行一步 RK4 时间推进。

    Parameters
    ----------
    rho : ndarray
        当前密度矩阵（不修改）
    dt : float
        时间步长
    H : ndarray
        当前时刻 Hamiltonian
    c_cache : CollapseCache
        跳跃算符缓存
    buffers : tuple of 8 ndarray
        由 alloc_rk4_buffers() 分配的工作缓冲区

    Returns
    -------
    out : ndarray
        下一时刻密度矩阵（已 Hermitian 化 + 归一化）
    """
    from .state_repr import enforce_density_matrix

    tmp1, tmp2, k1, k2, k3, k4, work, out = buffers

    lindblad_rhs(rho, H, c_cache, tmp1, tmp2, k1)

    work[:] = rho + 0.5 * dt * k1
    lindblad_rhs(work, H, c_cache, tmp1, tmp2, k2)

    work[:] = rho + 0.5 * dt * k2
    lindblad_rhs(work, H, c_cache, tmp1, tmp2, k3)

    work[:] = rho + dt * k3
    lindblad_rhs(work, H, c_cache, tmp1, tmp2, k4)

    out[:] = rho + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
    enforce_density_matrix(out)
    return out
