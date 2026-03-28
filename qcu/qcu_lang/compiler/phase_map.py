# phase_map.py
"""
Layer 0 标准门 → Layer 1 QCU 相位操作 编译器。

每个标准量子门映射为一组 QCU 物理参数变更，
再由 executor 将参数变更应用到 IQPU 上执行。

映射策略
--------
RZ(θ)         → PHASE_SHIFT: boost_phase_trim += θ（直接注入腔相位）
RX(θ)         → FREE_EVOLVE: 短时 QIM 演化，omega_x=θ
H             → RZ(π/2) + RX(π/2) + RZ(π/2) 分解
X             → RX(π)
Y             → RZ(π) + RX(π)
Z             → RZ(π)
S             → RZ(π/2)
T             → RZ(π/4)
CZ            → DISPERSIVE_WAIT: 色散耦合积累 π 相位
CX            → H(tgt) + CZ + H(tgt)
MEAS          → 读出当前态
BARRIER/ID    → 空操作
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

from ..ir.circuit import QGate, QCircuit
from ..ir.ops import GateType, PhaseOp, EmergeOp


@dataclass
class PhaseStep:
    """单步物理执行指令（已解析为 IQPU 可直接使用的参数）。

    kind:
      'phase_shift'   — 给 mode k 注入相位偏移
      'qim_evolve'    — 短时 QIM 演化（sigma_x 驱动）
      'dispersive'    — 色散耦合自由演化
      'free_evolve'   — 无驱动自由演化
      'qcl_phase'     — QCL 协议阶段（PCM/QIM/BOOST）
      'readout'       — 读出末态
      'emerge'        — 完整涌现协议
      'collapse_scan' — 坍缩筛选
      'noop'          — 空操作
    """
    kind: str
    params: dict = field(default_factory=dict)
    source_gate: object = field(default=None, repr=False)


# ── 单门 → PhaseStep 列表 ─────────────────────────────────

# 色散耦合积累 π 相位所需时间（归一化单位）
# 真实值取决于 χ，这里用默认 χ=0.5 的近似: t = π/(2χ) = π
_CZ_DURATION = math.pi


def _gate_to_steps(gate: QGate) -> List[PhaseStep]:
    """将单个 QGate 编译为 PhaseStep 列表。"""
    op = gate.op
    q = gate.qubits
    p = gate.params

    # ── Layer 0: 标准门 ──────────────────────

    if op == GateType.RZ:
        theta = p[0] if p else 0.0
        return [PhaseStep("phase_shift", {"mode": 0, "theta": theta}, gate)]

    if op == GateType.RX:
        theta = p[0] if p else 0.0
        return [PhaseStep("qim_evolve", {"qubit": q[0], "omega_x": theta,
                                          "duration": 0.5}, gate)]

    if op == GateType.RY:
        # RY(θ) = RZ(-π/2) · RX(θ) · RZ(π/2)
        theta = p[0] if p else 0.0
        return [
            PhaseStep("phase_shift", {"mode": 0, "theta": -math.pi/2}, gate),
            PhaseStep("qim_evolve",  {"qubit": q[0], "omega_x": theta, "duration": 0.5}, gate),
            PhaseStep("phase_shift", {"mode": 0, "theta": math.pi/2}, gate),
        ]

    if op == GateType.H:
        # H = RZ(π/2) · RX(π/2) · RZ(π/2)
        return [
            PhaseStep("phase_shift", {"mode": 0, "theta": math.pi/2}, gate),
            PhaseStep("qim_evolve",  {"qubit": q[0], "omega_x": math.pi/2, "duration": 0.5}, gate),
            PhaseStep("phase_shift", {"mode": 0, "theta": math.pi/2}, gate),
        ]

    if op == GateType.X:
        return [PhaseStep("qim_evolve", {"qubit": q[0], "omega_x": math.pi, "duration": 0.5}, gate)]

    if op == GateType.Y:
        return [
            PhaseStep("phase_shift", {"mode": 0, "theta": math.pi}, gate),
            PhaseStep("qim_evolve",  {"qubit": q[0], "omega_x": math.pi, "duration": 0.5}, gate),
        ]

    if op == GateType.Z:
        return [PhaseStep("phase_shift", {"mode": 0, "theta": math.pi}, gate)]

    if op == GateType.S:
        return [PhaseStep("phase_shift", {"mode": 0, "theta": math.pi/2}, gate)]

    if op == GateType.SDG:
        return [PhaseStep("phase_shift", {"mode": 0, "theta": -math.pi/2}, gate)]

    if op == GateType.T:
        return [PhaseStep("phase_shift", {"mode": 0, "theta": math.pi/4}, gate)]

    if op == GateType.TDG:
        return [PhaseStep("phase_shift", {"mode": 0, "theta": -math.pi/4}, gate)]

    if op == GateType.SX:
        return [PhaseStep("qim_evolve", {"qubit": q[0], "omega_x": math.pi/2, "duration": 0.5}, gate)]

    if op == GateType.P:
        lam = p[0] if p else 0.0
        return [PhaseStep("phase_shift", {"mode": 0, "theta": lam}, gate)]

    if op == GateType.U:
        # U(θ,φ,λ) = RZ(λ) · RX(θ) · RZ(φ)
        theta, phi, lam = (p[0] if len(p) > 0 else 0.0,
                           p[1] if len(p) > 1 else 0.0,
                           p[2] if len(p) > 2 else 0.0)
        return [
            PhaseStep("phase_shift", {"mode": 0, "theta": lam}, gate),
            PhaseStep("qim_evolve",  {"qubit": q[0], "omega_x": theta, "duration": 0.5}, gate),
            PhaseStep("phase_shift", {"mode": 0, "theta": phi}, gate),
        ]

    if op == GateType.CZ:
        ctrl, tgt = q[0], q[1]
        return [PhaseStep("dispersive", {"qubit": ctrl, "mode": tgt,
                                          "duration": _CZ_DURATION}, gate)]

    if op == GateType.CX:
        ctrl, tgt = q[0], q[1]
        # CX = H(tgt) · CZ · H(tgt)
        return [
            PhaseStep("qim_evolve",  {"qubit": tgt, "omega_x": math.pi/2, "duration": 0.5}, gate),
            PhaseStep("phase_shift", {"mode": 0, "theta": math.pi/2}, gate),
            PhaseStep("dispersive",  {"qubit": ctrl, "mode": tgt, "duration": _CZ_DURATION}, gate),
            PhaseStep("qim_evolve",  {"qubit": tgt, "omega_x": math.pi/2, "duration": 0.5}, gate),
            PhaseStep("phase_shift", {"mode": 0, "theta": math.pi/2}, gate),
        ]

    if op == GateType.SWAP:
        # SWAP = CX(a,b) · CX(b,a) · CX(a,b)
        a, b = q[0], q[1]
        cx_ab = _gate_to_steps(QGate(GateType.CX, (a, b)))
        cx_ba = _gate_to_steps(QGate(GateType.CX, (b, a)))
        return cx_ab + cx_ba + cx_ab

    if op == GateType.MEAS:
        return [PhaseStep("readout", {"qubit": q[0],
                                       "clbit": gate.clbits[0] if gate.clbits else 0}, gate)]

    if op == GateType.RESET:
        return [PhaseStep("qim_evolve", {"qubit": q[0], "omega_x": 0.0,
                                          "duration": 0.1, "reset": True}, gate)]

    if op in (GateType.ID, GateType.BARRIER):
        return [PhaseStep("noop", {}, gate)]

    # ── Layer 1: 直通 ────────────────────────

    if isinstance(op, PhaseOp):
        return [PhaseStep("phase_op", {"op": op, "params": dict(zip(
            ["p0","p1","p2","p3"], gate.params))}, gate)]

    # ── Layer 2: 涌现指令 ────────────────────

    if op == EmergeOp.QCL_PCM:
        return [PhaseStep("qcl_phase", {"phase": "pcm",
            "gamma": gate.params[0], "duration": gate.params[1]}, gate)]

    if op == EmergeOp.QCL_QIM:
        return [PhaseStep("qcl_phase", {"phase": "qim",
            "omega_x": gate.params[0], "gamma": gate.params[1],
            "duration": gate.params[2]}, gate)]

    if op == EmergeOp.QCL_BOOST:
        return [PhaseStep("qcl_phase", {"phase": "boost",
            "eps_boost": gate.params[0], "gamma": gate.params[1],
            "trim": gate.params[2], "duration": gate.params[3]}, gate)]

    if op in (EmergeOp.QCL_RUN, EmergeOp.SYNC_EMERGE):
        return [PhaseStep("emerge", {"op": op, "meta": gate.meta}, gate)]

    if op == EmergeOp.PHASE_LOCK_WAIT:
        return [PhaseStep("emerge", {"op": op,
            "C_threshold": gate.params[0] if gate.params else 0.01}, gate)]

    if op == EmergeOp.COLLAPSE_SCAN:
        return [PhaseStep("collapse_scan", gate.meta, gate)]

    if op == EmergeOp.PHASE_ANNEAL:
        return [PhaseStep("emerge", {"op": op, "schedule": gate.meta.get("schedule", [])}, gate)]

    return [PhaseStep("noop", {"unknown_op": str(op)}, gate)]


def compile_circuit(circ: QCircuit) -> List[PhaseStep]:
    """将 QCircuit 编译为 PhaseStep 执行序列。"""
    steps = []
    for gate in circ.gates:
        steps.extend(_gate_to_steps(gate))
    return steps
