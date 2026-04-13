# readout.py
"""
QCU 读出层。

包含：
- expect()：计算算符期望值 Tr(ρ O)
- ReadoutSnapshot：单时刻观测快照
- compute_step_snapshot_fast()：轻量快照（只算 C / rel_phase）
- compute_step_snapshot_full()：完整快照（含 negativity / sz / n）
- compute_step_snapshot()：兼容旧接口，按 track_entanglement 路由
- compute_final_observables()：提取末态统计量
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .state_repr import wrap_pi
from .phase_modulation import OperatorBank
from .entanglement_metrics import negativity_qubit0_vs_rest


def expect(xp, rho: np.ndarray, op: np.ndarray) -> complex:
    """计算期望值 Tr(ρ O)。

    Parameters
    ----------
    xp : module
        numpy 或 cupy，由调用方传入，不在此处动态判断。
    rho : ndarray
        密度矩阵
    op : ndarray
        可观测量算符
    """
    return xp.trace(rho @ op)


@dataclass
class ReadoutSnapshot:
    """单时刻观测快照。"""
    t: float
    C: float
    rel_phase: list[float]
    negativity: float | None


# ──────────────────────────────────────────────
# 快搜模式：只算 C 和 rel_phase，最小 GPU→CPU 同步
# ──────────────────────────────────────────────

def compute_step_snapshot_fast(xp, t: float, rho, aJ, phi_ref: float):
    """轻量快照：只提取 C 和 rel_phase。

    不算 negativity / sz / n，减少 GPU→CPU 同步次数。
    """
    a0 = complex(expect(xp, rho, aJ[0]))
    a1 = complex(expect(xp, rho, aJ[1])) if len(aJ) >= 2 else 0j

    C = float(abs(a0 - a1))
    rel_phase = [
        float(wrap_pi(np.angle(a0) - phi_ref)),
        float(wrap_pi(np.angle(a1) - phi_ref)),
    ]
    return C, rel_phase


# ──────────────────────────────────────────────
# 高保真模式：完整快照
# ──────────────────────────────────────────────

def compute_step_snapshot_full(
    xp,
    t: float,
    rho,
    ops: OperatorBank,
    phi_ref: float,
    track_negativity: bool,
) -> ReadoutSnapshot:
    """完整快照：C / rel_phase / negativity。"""
    Nm = len(ops.aJ)
    a_vals = [complex(expect(xp, rho, ops.aJ[k])) for k in range(Nm)]

    C = float(abs(a_vals[0] - a_vals[1])) if Nm >= 2 else 0.0
    rel_phase = [float(wrap_pi(np.angle(a_vals[k]) - phi_ref)) for k in range(Nm)]

    neg = negativity_qubit0_vs_rest(xp, rho) if track_negativity else None
    return ReadoutSnapshot(t=t, C=C, rel_phase=rel_phase, negativity=neg)


# ──────────────────────────────────────────────
# 兼容旧接口
# ──────────────────────────────────────────────

def compute_step_snapshot(
    t: float,
    rho,
    ops: OperatorBank,
    phi_ref: float,
    track_entanglement: bool,
) -> ReadoutSnapshot:
    """兼容旧接口：按 track_entanglement 路由到 full 版。"""
    try:
        import cupy
        xp = cupy.get_array_module(rho)
    except ImportError:
        xp = np
    return compute_step_snapshot_full(xp, t, rho, ops, phi_ref, track_entanglement)


# ──────────────────────────────────────────────
# 末态统计量
# ──────────────────────────────────────────────

def compute_final_observables(rho, ops: OperatorBank, phi_ref: float):
    """提取末态统计量。"""
    try:
        import cupy
        xp = cupy.get_array_module(rho)
    except ImportError:
        xp = np

    Nq = len(ops.szJ)
    Nm = len(ops.aJ)

    final_sz = [float(np.real(complex(expect(xp, rho, ops.szJ[j])))) for j in range(Nq)]
    final_n  = [float(np.real(complex(expect(xp, rho, ops.nJ[k])))) for k in range(Nm)]

    a_vals = [complex(expect(xp, rho, ops.aJ[k])) for k in range(Nm)]
    final_rel_phase = [float(wrap_pi(np.angle(a_vals[k]) - phi_ref)) for k in range(Nm)]

    C_end = float(abs(a_vals[0] - a_vals[1])) if Nm >= 2 else 0.0

    if Nm >= 2:
        dtheta_end = float(abs(wrap_pi(np.angle(a_vals[0]) - np.angle(a_vals[1]))))
    else:
        dtheta_end = 0.0

    return final_sz, final_n, final_rel_phase, C_end, dtheta_end
