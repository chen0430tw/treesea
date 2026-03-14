# state_repr.py
"""
QCU 状态表示层。

包含：
- 基础线代工具函数（dagger/kron/basis/destroy/coherent_state）
- 密度矩阵约束函数
- IQPUConfig：虚拟量子芯片参数配置
- IQPURunResult：单次运行结果容器
- build_initial_state()：根据配置初始化密度矩阵
"""

from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass
from typing import List, Optional


# ──────────────────────────────────────────────
# 基础线代工具
# ──────────────────────────────────────────────

def dagger(a: np.ndarray) -> np.ndarray:
    """共轭转置"""
    return np.conjugate(a.T)


def kron(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Kronecker 积"""
    return np.kron(a, b)


def basis(n: int, i: int) -> np.ndarray:
    """Fock 基矢 |i⟩，维度 n，列向量"""
    v = np.zeros((n, 1), dtype=np.complex128)
    v[i, 0] = 1.0
    return v


def destroy(d: int) -> np.ndarray:
    """玻色湮灭算符，截断维度 d"""
    a = np.zeros((d, d), dtype=np.complex128)
    for n in range(1, d):
        a[n - 1, n] = math.sqrt(n)
    return a


def coherent_state(d: int, alpha: complex) -> np.ndarray:
    """相干态 |α⟩，截断维度 d，列向量（已归一化）"""
    alpha = complex(alpha)
    v = np.zeros((d, 1), dtype=np.complex128)
    pref = np.exp(-abs(alpha) ** 2 / 2.0)
    fact = 1.0
    for n in range(d):
        if n > 0:
            fact *= n
        v[n, 0] = pref * (alpha ** n) / math.sqrt(fact)
    v /= (np.linalg.norm(v) + 1e-15)
    return v


def enforce_density_matrix(rho: np.ndarray) -> None:
    """原地强制密度矩阵：Hermitian 化 + 迹归一"""
    rho[:] = 0.5 * (rho + dagger(rho))
    rho /= (np.trace(rho) + 1e-15)


def wrap_pi(x: float) -> float:
    """将角度折叠到 (−π, π]"""
    return (x + np.pi) % (2 * np.pi) - np.pi


# ──────────────────────────────────────────────
# 配置与结果数据类
# ──────────────────────────────────────────────

@dataclass
class IQPUConfig:
    """虚拟量子芯片（IQPU/QCU）运行参数。

    Attributes
    ----------
    Nq : int
        qubit 数量
    Nm : int
        谐振腔（mode）数量
    d : int
        每个 mode 的 Fock 截断维度
    chi : ndarray, shape (Nq, Nm)
        dispersive 耦合强度矩阵
    wc : ndarray, shape (Nm,)
        腔频率（旋转框架中）
    wq : ndarray, shape (Nq,)
        qubit 频率（旋转框架中）
    kappa : ndarray, shape (Nm,)
        腔光子泄漏率
    T1 : ndarray, shape (Nq,)
        qubit 弛豫时间（inf 表示无耗散）
    Tphi : ndarray, shape (Nq,)
        qubit 纯退相干时间（inf 表示无耗散）
    phi_ref : float
        参考相位（rad）
    eps_drive : list of complex, length Nm
        每个 mode 的驱动幅度
    t_max : float
        总演化时长
    dt : float
        RK4 时间步长
    obs_every : int
        每隔多少步观测一次
    qubits_init : list of str
        qubit 初始态，"g"（基态）/ "e"（激发态）/ "+"（叠加态）
    alpha0 : list of complex, length Nm
        每个 mode 相干态的初始振幅
    track_entanglement : bool
        是否在每次观测时计算纠缠负值度
    """
    Nq: int = 2
    Nm: int = 2
    d: int = 6

    chi: Optional[np.ndarray] = None
    wc: Optional[np.ndarray] = None
    wq: Optional[np.ndarray] = None

    kappa: Optional[np.ndarray] = None
    T1: Optional[np.ndarray] = None
    Tphi: Optional[np.ndarray] = None

    phi_ref: float = 0.30
    eps_drive: Optional[List[complex]] = None

    t_max: float = 10.0
    dt: float = 0.05
    obs_every: int = 1

    qubits_init: Optional[List[str]] = None
    alpha0: Optional[List[complex]] = None

    track_entanglement: bool = True

    def finalize(self) -> "IQPUConfig":
        """填充所有 None 字段为合理默认值并转换为 ndarray。"""
        if self.chi is None:
            self.chi = 0.5 * np.ones((self.Nq, self.Nm), dtype=np.float64)
        if self.wc is None:
            self.wc = np.zeros(self.Nm, dtype=np.float64)
        if self.wq is None:
            self.wq = np.zeros(self.Nq, dtype=np.float64)
        if self.kappa is None:
            self.kappa = np.zeros(self.Nm, dtype=np.float64)
        if self.T1 is None:
            self.T1 = np.array([np.inf] * self.Nq, dtype=np.float64)
        if self.Tphi is None:
            self.Tphi = np.array([np.inf] * self.Nq, dtype=np.float64)
        if self.eps_drive is None:
            self.eps_drive = [0.0 + 0.0j] * self.Nm
        if self.qubits_init is None:
            self.qubits_init = ["g"] * self.Nq
        if self.alpha0 is None:
            base = [2.0, 1.5, 1.2, 1.0]
            self.alpha0 = [
                base[k] * np.exp(1j * self.phi_ref) for k in range(self.Nm)
            ]

        self.chi = np.asarray(self.chi, dtype=np.float64)
        self.wc = np.asarray(self.wc, dtype=np.float64)
        self.wq = np.asarray(self.wq, dtype=np.float64)
        self.kappa = np.asarray(self.kappa, dtype=np.float64)
        self.T1 = np.asarray(self.T1, dtype=np.float64)
        self.Tphi = np.asarray(self.Tphi, dtype=np.float64)
        return self


@dataclass
class IQPURunResult:
    """单次 IQPU 运行结果。

    Attributes
    ----------
    label : str
        运行标签
    DIM : int
        希尔伯特空间总维度
    elapsed_sec : float
        运行耗时（秒）
    ts : ndarray
        观测时间点
    rel_phase : ndarray, shape (N_obs, Nm)
        每个 mode 相对参考相位 arg⟨a_k⟩ − phi_ref
    C_log : ndarray
        C(t) = |⟨a_0⟩ − ⟨a_1⟩| 的时序记录
    neg_log : ndarray or None
        纠缠负值度时序（track_entanglement=False 时为 None）
    final_sz : list of float
        末态各 qubit ⟨σ_z⟩
    final_n : list of float
        末态各 mode 光子数 ⟨n_k⟩
    final_rel_phase : list of float
        末态各 mode 相对相位
    C_end : float
        末态 C 值
    dtheta_end : float
        末态两 mode 相位差绝对值
    N_end : float or None
        末态纠缠负值度
    """
    label: str
    DIM: int
    elapsed_sec: float

    ts: np.ndarray
    rel_phase: np.ndarray
    C_log: np.ndarray
    neg_log: Optional[np.ndarray]

    final_sz: List[float]
    final_n: List[float]
    final_rel_phase: List[float]
    C_end: float
    dtheta_end: float
    N_end: Optional[float]


# ──────────────────────────────────────────────
# 初始态构建
# ──────────────────────────────────────────────

def build_initial_state(cfg: IQPUConfig, dimQ: int, dimM: int) -> np.ndarray:
    """根据配置构建初始密度矩阵 ρ(0)。

    Parameters
    ----------
    cfg : IQPUConfig
        已 finalize() 的配置
    dimQ : int
        qubit 子空间维度 = 2^Nq
    dimM : int
        mode 子空间维度 = d^Nm

    Returns
    -------
    rho : ndarray, shape (DIM, DIM)
        初始密度矩阵，DIM = dimQ * dimM
    """
    q = None
    for s in cfg.qubits_init:
        if s == "g":
            v = basis(2, 0)
        elif s == "e":
            v = basis(2, 1)
        else:  # "+"
            v = (basis(2, 0) + basis(2, 1)) / math.sqrt(2.0)
        q = v if q is None else kron(q, v)

    m = None
    for alpha in cfg.alpha0:
        v = coherent_state(cfg.d, alpha)
        m = v if m is None else kron(m, v)

    psi = kron(q, m)
    return psi @ dagger(psi)


# 公开别名（与原型文件保持兼容）
QCUConfig = IQPUConfig
QCURunResult = IQPURunResult
