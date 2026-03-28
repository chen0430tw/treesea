# decompose.py
"""
高级门分解：将复合门拆解为 QCU-ISA 基础门集。

基础门集：{ H, X, Y, Z, S, T, SDG, TDG, SX, RX, RY, RZ, P, U, CX, CZ, MEAS, RESET, ID }

分解规则
--------
SWAP    → CX(a,b) · CX(b,a) · CX(a,b)
ISWAP   → CX(a,b) · H(a) · CX(b,a) · H(a) · S(a) · S(b)
ECR     → RZ(π/4,a) · X(b) · CX(a,b) · X(b) · RZ(-π/4,a)
CCX     → 标准 6-CNOT Toffoli 分解（Clifford+T）
CSWAP   → CCX 辅助 + SWAP 分解
MCX     → 递归 CCX 分解（n控制比特）
"""

from __future__ import annotations

import math
from typing import List

from ..ir.circuit import QGate
from ..ir.ops import GateType


def decompose_gate(gate: QGate) -> List[QGate]:
    """将单个复合门分解为基础门列表。

    若门已是基础门，返回 [gate] 原样。
    """
    op = gate.op
    if not isinstance(op, GateType):
        return [gate]  # Layer 1/2 直接通过

    q = gate.qubits
    p = gate.params

    # ── 已是基础门，直接返回 ──
    _basis = {
        GateType.X, GateType.Y, GateType.Z,
        GateType.H, GateType.S, GateType.T,
        GateType.SDG, GateType.TDG, GateType.SX,
        GateType.RX, GateType.RY, GateType.RZ,
        GateType.P, GateType.U,
        GateType.CX, GateType.CZ,
        GateType.MEAS, GateType.RESET,
        GateType.ID, GateType.BARRIER,
        GateType.CY,  # CY = S†·CX·S，保留原样由 phase_map 处理
    }
    if op in _basis:
        return [gate]

    # ── SWAP ──────────────────────────────────
    if op == GateType.SWAP:
        a, b = q[0], q[1]
        return [
            QGate(GateType.CX, (a, b)),
            QGate(GateType.CX, (b, a)),
            QGate(GateType.CX, (a, b)),
        ]

    # ── iSWAP ─────────────────────────────────
    # iSWAP = CX(a,b)·H(a)·CX(b,a)·H(a)·S(a)·S(b)
    if op == GateType.ISWAP:
        a, b = q[0], q[1]
        return [
            QGate(GateType.CX, (a, b)),
            QGate(GateType.H,  (a,)),
            QGate(GateType.CX, (b, a)),
            QGate(GateType.H,  (a,)),
            QGate(GateType.S,  (a,)),
            QGate(GateType.S,  (b,)),
        ]

    # ── ECR (Echoed Cross-Resonance) ──────────
    # ECR = RZ(π/4,a)·X(b)·CX(a,b)·X(b)·RZ(-π/4,a)
    if op == GateType.ECR:
        a, b = q[0], q[1]
        return [
            QGate(GateType.RZ, (a,), params=(math.pi/4,)),
            QGate(GateType.X,  (b,)),
            QGate(GateType.CX, (a, b)),
            QGate(GateType.X,  (b,)),
            QGate(GateType.RZ, (a,), params=(-math.pi/4,)),
        ]

    # ── CCX / Toffoli ────────────────────────
    # 标准 6-CNOT 分解（Clifford+T，精确实现）
    # 参考：Nielsen & Chuang 4.3节
    if op == GateType.CCX:
        c0, c1, t = q[0], q[1], q[2]
        return [
            QGate(GateType.H,   (t,)),
            QGate(GateType.CX,  (c1, t)),
            QGate(GateType.TDG, (t,)),
            QGate(GateType.CX,  (c0, t)),
            QGate(GateType.T,   (t,)),
            QGate(GateType.CX,  (c1, t)),
            QGate(GateType.TDG, (t,)),
            QGate(GateType.CX,  (c0, t)),
            QGate(GateType.T,   (t,)),
            QGate(GateType.T,   (c1,)),
            QGate(GateType.H,   (t,)),
            QGate(GateType.CX,  (c0, c1)),
            QGate(GateType.T,   (c0,)),
            QGate(GateType.TDG, (c1,)),
            QGate(GateType.CX,  (c0, c1)),
        ]

    # ── CSWAP / Fredkin ───────────────────────
    # CSWAP(c, a, b) = CCX(c,a,b)·CCX(c,b,a)·CCX(c,a,b)
    # 更高效：CX(b,a)·CCX(c,a,b)·CX(b,a)
    if op == GateType.CSWAP:
        c, a, b = q[0], q[1], q[2]
        ccx = decompose_gate(QGate(GateType.CCX, (c, a, b)))
        return [
            QGate(GateType.CX, (b, a)),
            *ccx,
            QGate(GateType.CX, (b, a)),
        ]

    # ── MCX（多控制 X，n 控制比特）──────────────
    # 递归：MCX(c0..cn-1, t) = CCX(c0, cn-1, ancilla) 辅助展开
    # 简化版：n=2 → CCX，n>2 → 未实现报警
    if op == GateType.MCX:
        if len(q) == 3:
            return decompose_gate(QGate(GateType.CCX, q))
        # n>2 控制比特：返回原门并标注（暂不支持）
        return [QGate(op, q, params=p,
                      meta={"decompose_warning": f"MCX({len(q)-1} controls) not fully decomposed"})]

    # 未知门，原样返回
    return [gate]


def decompose_circuit(gates: List[QGate]) -> List[QGate]:
    """对门列表递归分解，直到所有门都是基础门。"""
    result = []
    for gate in gates:
        expanded = decompose_gate(gate)
        if expanded == [gate]:
            result.append(gate)
        else:
            # 递归分解（如 CSWAP 内含 CCX 需再次展开）
            result.extend(decompose_circuit(expanded))
    return result
