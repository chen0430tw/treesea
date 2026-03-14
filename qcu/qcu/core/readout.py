# readout.py
"""
QCU 读出层。

包含：
- expect()：计算算符期望值 Tr(ρ O)
- ReadoutSnapshot：单时刻观测快照
- compute_step_snapshot()：在当前密度矩阵上提取观测量
- compute_final_observables()：提取末态统计量
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .state_repr import wrap_pi
from .phase_modulation import OperatorBank
from .entanglement_metrics import negativity_qubit0_vs_rest


def expect(rho: np.ndarray, op: np.ndarray) -> complex:
    """计算期望值 Tr(ρ O)。

    Parameters
    ----------
    rho : ndarray
        密度矩阵
    op : ndarray
        可观测量算符

    Returns
    -------
    complex
        期望值（物理量通常取实部）
    """
    return np.trace(rho @ op)


@dataclass
class ReadoutSnapshot:
    """单时刻观测快照。

    Attributes
    ----------
    t : float
        当前时刻
    C : float
        C(t) = |⟨a_0⟩ − ⟨a_1⟩|（两 mode 振幅差，越小越同步）
    rel_phase : list of float
        各 mode 相对参考相位 arg⟨a_k⟩ − phi_ref
    negativity : float or None
        qubit 0 纠缠负值度（track_entanglement=False 时为 None）
    """
    t: float
    C: float
    rel_phase: List[float]
    negativity: Optional[float]


def compute_step_snapshot(
    t: float,
    rho: np.ndarray,
    ops: OperatorBank,
    phi_ref: float,
    track_entanglement: bool,
) -> ReadoutSnapshot:
    """在当前密度矩阵上提取观测快照。

    Parameters
    ----------
    t : float
        当前时刻
    rho : ndarray
        当前密度矩阵
    ops : OperatorBank
        算符库
    phi_ref : float
        参考相位
    track_entanglement : bool
        是否计算纠缠负值度

    Returns
    -------
    ReadoutSnapshot
    """
    Nm = len(ops.aJ)
    a_vals = [expect(rho, ops.aJ[k]) for k in range(Nm)]

    # C(t) = |⟨a_0⟩ − ⟨a_1⟩|（双 mode 时）
    C = float(abs(a_vals[0] - a_vals[1])) if Nm >= 2 else 0.0

    rel_phase = [float(wrap_pi(np.angle(a_vals[k]) - phi_ref)) for k in range(Nm)]

    neg = negativity_qubit0_vs_rest(rho) if track_entanglement else None

    return ReadoutSnapshot(t=t, C=C, rel_phase=rel_phase, negativity=neg)


def compute_final_observables(
    rho: np.ndarray,
    ops: OperatorBank,
    phi_ref: float,
):
    """提取末态统计量。

    Parameters
    ----------
    rho : ndarray
        末态密度矩阵
    ops : OperatorBank
        算符库
    phi_ref : float
        参考相位

    Returns
    -------
    final_sz : list of float
        各 qubit ⟨σ_z⟩
    final_n : list of float
        各 mode 光子数 ⟨n_k⟩
    final_rel_phase : list of float
        各 mode 相对相位
    C_end : float
        末态 C 值
    dtheta_end : float
        末态两 mode 相位差绝对值
    """
    Nq = len(ops.szJ)
    Nm = len(ops.aJ)

    final_sz = [float(np.real(expect(rho, ops.szJ[j]))) for j in range(Nq)]
    final_n = [float(np.real(expect(rho, ops.nJ[k]))) for k in range(Nm)]

    a_vals = [expect(rho, ops.aJ[k]) for k in range(Nm)]
    final_rel_phase = [float(wrap_pi(np.angle(a_vals[k]) - phi_ref)) for k in range(Nm)]

    C_end = float(abs(a_vals[0] - a_vals[1])) if Nm >= 2 else 0.0

    if Nm >= 2:
        dtheta_end = float(abs(wrap_pi(np.angle(a_vals[0]) - np.angle(a_vals[1]))))
    else:
        dtheta_end = 0.0

    return final_sz, final_n, final_rel_phase, C_end, dtheta_end
