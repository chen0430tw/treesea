# phase_modulation.py
"""
QCU 相位调制层。

包含：
- OperatorBank：预构建并缓存全空间算符（σ_z/σ_x/σ_−/a/n）
- build_H_base()：构建基础 Hamiltonian（色散耦合 + 参考驱动）
- build_H_boost_trim()：构建 BOOST 阶段 Hamiltonian（增强驱动 + 相位修正）
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .state_repr import IQPUConfig, dagger, kron, destroy


@dataclass
class OperatorBank:
    """全空间算符库，由 IQPU 在初始化时构建并持有。

    Attributes
    ----------
    DIM : int
        希尔伯特空间总维度
    szJ : list of ndarray
        各 qubit σ_z 算符（嵌入全空间）
    sxJ : list of ndarray
        各 qubit σ_x 算符（嵌入全空间）
    smJ : list of ndarray
        各 qubit σ_− 算符（嵌入全空间）
    aJ : list of ndarray
        各 mode 湮灭算符（嵌入全空间）
    adJ : list of ndarray
        各 mode 产生算符（嵌入全空间）
    nJ : list of ndarray
        各 mode 光子数算符（嵌入全空间）
    """
    DIM: int
    szJ: list[np.ndarray]
    sxJ: list[np.ndarray]
    smJ: list[np.ndarray]
    aJ: list[np.ndarray]
    adJ: list[np.ndarray]
    nJ: list[np.ndarray]


def build_operator_bank(cfg: IQPUConfig) -> OperatorBank:
    """构建并返回全空间算符库。

    Parameters
    ----------
    cfg : IQPUConfig
        已 finalize() 的配置

    Returns
    -------
    OperatorBank
    """
    Nq, Nm, d = cfg.Nq, cfg.Nm, cfg.d
    dimQ = 2 ** Nq
    dimM = d ** Nm
    DIM = dimQ * dimM

    # 按 profile 选 dtype：fast_search 用 complex64 省内存
    dt = np.complex64 if cfg.dtype == "complex64" else np.complex128

    I2 = np.eye(2, dtype=dt)
    Id = np.eye(d, dtype=dt)

    sz1 = np.array([[1, 0], [0, -1]], dtype=dt)
    sx1 = np.array([[0, 1], [1, 0]], dtype=dt)
    sm1 = np.array([[0, 1], [0, 0]], dtype=dt)  # |g⟩⟨e|

    a1 = destroy(d).astype(dt)
    adag1 = dagger(a1)
    n1 = adag1 @ a1

    IQ = np.eye(dimQ, dtype=dt)
    IM = np.eye(dimM, dtype=dt)

    def embed_qubit(op2, j):
        Q = None
        for q in range(Nq):
            factor = op2 if q == j else I2
            Q = factor if Q is None else kron(Q, factor)
        return kron(Q, IM)

    def embed_mode(opd, k):
        M = None
        for m in range(Nm):
            factor = opd if m == k else Id
            M = factor if M is None else kron(M, factor)
        return kron(IQ, M)

    szJ = [embed_qubit(sz1, j) for j in range(Nq)]
    sxJ = [embed_qubit(sx1, j) for j in range(Nq)]
    smJ = [embed_qubit(sm1, j) for j in range(Nq)]

    aJ = [embed_mode(a1, k) for k in range(Nm)]
    adJ = [dagger(aJ[k]) for k in range(Nm)]
    nJ = [embed_mode(n1, k) for k in range(Nm)]

    return OperatorBank(
        DIM=DIM,
        szJ=szJ, sxJ=sxJ, smJ=smJ,
        aJ=aJ, adJ=adJ, nJ=nJ,
    )


def build_H_base(cfg: IQPUConfig, ops: OperatorBank) -> np.ndarray:
    """构建基础 Hamiltonian（色散耦合 + 参考驱动）。

    H_base = Σ_k wc_k n_k
           + Σ_j ½ wq_j σ_z,j
           + Σ_{j,k} χ_{j,k} σ_z,j n_k
           + Σ_k i(ε_k a†_k − ε_k* a_k)

    Parameters
    ----------
    cfg : IQPUConfig
        已 finalize() 的配置
    ops : OperatorBank
        算符库

    Returns
    -------
    ndarray, shape (DIM, DIM)
    """
    DIM = ops.DIM
    dt = np.complex64 if cfg.dtype == "complex64" else np.complex128
    ft = np.float32 if dt == np.complex64 else np.float64
    H = np.zeros((DIM, DIM), dtype=dt)

    for k in range(cfg.Nm):
        H += ft(cfg.wc[k]) * ops.nJ[k]
    for j in range(cfg.Nq):
        H += ft(0.5 * cfg.wq[j]) * ops.szJ[j]
    for j in range(cfg.Nq):
        for k in range(cfg.Nm):
            H += ft(cfg.chi[j, k]) * (ops.szJ[j] @ ops.nJ[k])

    for k in range(cfg.Nm):
        eps = dt(complex(cfg.eps_drive[k]))
        H += dt(1j) * (eps * ops.adJ[k] - np.conjugate(eps) * ops.aJ[k])

    return H


def build_H_boost_trim(
    cfg: IQPUConfig,
    ops: OperatorBank,
    H_base: np.ndarray,
    eps_boost: float,
    boost_phase_trim: float,
) -> np.ndarray:
    """构建 BOOST 阶段 Hamiltonian。

    BOOST 驱动 = eps_boost × ε_drive，叠加相位修正：
      mode 0：+trim/2，mode 1：−trim/2（单 mode 时无修正）

    Parameters
    ----------
    cfg : IQPUConfig
        已 finalize() 的配置
    ops : OperatorBank
        算符库
    H_base : ndarray
        基础 Hamiltonian
    eps_boost : float
        驱动增强倍数
    boost_phase_trim : float
        两 mode 间相位修正量（rad）

    Returns
    -------
    ndarray, shape (DIM, DIM)
        BOOST Hamiltonian
    """
    H = H_base.copy()

    for k in range(cfg.Nm):
        base_eps = complex(cfg.eps_drive[k])
        delta = 0.0 if cfg.Nm == 1 else ((+0.5 * boost_phase_trim) if k == 0 else (-0.5 * boost_phase_trim))
        target_eps = eps_boost * base_eps * np.exp(1j * delta)
        delta_eps = target_eps - base_eps
        H += 1j * (delta_eps * ops.adJ[k] - np.conjugate(delta_eps) * ops.aJ[k])

    return H
