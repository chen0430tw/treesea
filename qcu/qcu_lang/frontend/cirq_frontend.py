# cirq_frontend.py
"""
Cirq → QCircuit 前端转换器。

依赖（可选）：cirq-core >= 1.3
  pip install cirq-core

支持的 Cirq 操作
----------------
单比特门：  H X Y Z S T CZ SWAP
            rx ry rz（cirq.rx / ry / rz）
            ZPowGate HPowGate XPowGate（整数幂次）
双比特门：  CNOT CZ SWAP
三比特门：  CCNOT CSWAP
测量：      cirq.measure / MeasurementGate
Reset：     cirq.reset

不支持（静默跳过）：
  参数化电路（sympy Symbol）、自定义 Gate（无法映射时保留为 noop）

用法
----
import cirq
from qcu_lang.frontend.cirq_frontend import from_cirq

q0, q1 = cirq.LineQubit.range(2)
circuit = cirq.Circuit([cirq.H(q0), cirq.CNOT(q0, q1)])
qcirc = from_cirq(circuit)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, List

from ..ir.circuit import QCircuit, QGate
from ..ir.ops import GateType

if TYPE_CHECKING:
    import cirq


# ── Cirq 门名称 → GateType ────────────────────────────────────

def _cirq_gate_map() -> Dict[str, GateType]:
    """延迟构建映射表（避免 import cirq 失败时模块加载报错）。"""
    import cirq
    return {
        # 单比特
        type(cirq.H):    GateType.H,
        type(cirq.X):    GateType.X,
        type(cirq.Y):    GateType.Y,
        type(cirq.Z):    GateType.Z,
        type(cirq.S):    GateType.S,
        type(cirq.T):    GateType.T,
        # 双比特
        type(cirq.CNOT): GateType.CX,
        type(cirq.CZ):   GateType.CZ,
        type(cirq.SWAP): GateType.SWAP,
    }


def _qubit_index(qubit, qubit_order: List) -> int:
    return qubit_order.index(qubit)


def from_cirq(circuit: "cirq.Circuit", name: str = "") -> QCircuit:
    """将 Cirq Circuit 转换为 QCircuit。

    Parameters
    ----------
    circuit : cirq.Circuit
        Cirq 量子电路
    name : str
        电路名称

    Returns
    -------
    QCircuit
    """
    try:
        import cirq
    except ImportError as e:
        raise ImportError(
            "Cirq 前端需要 cirq-core：pip install cirq-core"
        ) from e

    # 收集所有 qubit，按排序建立索引
    all_qubits = sorted(circuit.all_qubits())
    q_idx = {q: i for i, q in enumerate(all_qubits)}
    n_qubits = len(all_qubits) or 1

    gate_map = _cirq_gate_map()
    gates: List[QGate] = []
    clbit_map: Dict[str, int] = {}
    clbit_count = [0]

    def _clbit(key: str) -> int:
        if key not in clbit_map:
            clbit_map[key] = clbit_count[0]
            clbit_count[0] += 1
        return clbit_map[key]

    for moment in circuit:
        for op in moment.operations:
            g = op.gate
            qbs = tuple(q_idx[q] for q in op.qubits)

            # ── 测量 ──────────────────────────────────────────
            if isinstance(g, cirq.MeasurementGate):
                for i, q in enumerate(op.qubits):
                    key = f"{g.key}_{i}" if len(op.qubits) > 1 else g.key
                    cb = _clbit(key)
                    gates.append(QGate(GateType.MEAS, (q_idx[q],), clbits=(cb,)))
                continue

            # ── Reset ─────────────────────────────────────────
            if isinstance(g, cirq.ResetChannel):
                gates.append(QGate(GateType.RESET, (qbs[0],)))
                continue

            # ── 旋转门：rx / ry / rz ─────────────────────────
            if isinstance(g, cirq.Rz):
                theta = float(g.rads) if hasattr(g, "rads") else float(g._rads)
                gates.append(QGate(GateType.RZ, (qbs[0],), params=(theta,)))
                continue
            if isinstance(g, cirq.Ry):
                theta = float(g.rads) if hasattr(g, "rads") else float(g._rads)
                gates.append(QGate(GateType.RY, (qbs[0],), params=(theta,)))
                continue
            if isinstance(g, cirq.Rx):
                theta = float(g.rads) if hasattr(g, "rads") else float(g._rads)
                gates.append(QGate(GateType.RX, (qbs[0],), params=(theta,)))
                continue

            # ── ZPowGate（Z^t）→ RZ(t·π) ────────────────────
            if isinstance(g, cirq.ZPowGate):
                exponent = float(g.exponent)
                theta = exponent * math.pi
                gates.append(QGate(GateType.RZ, (qbs[0],), params=(theta,)))
                continue

            # ── XPowGate（X^t）→ RX(t·π) ────────────────────
            if isinstance(g, cirq.XPowGate):
                exponent = float(g.exponent)
                if abs(exponent - 1.0) < 1e-9:
                    gates.append(QGate(GateType.X, (qbs[0],)))
                elif abs(exponent - 0.5) < 1e-9:
                    gates.append(QGate(GateType.SX, (qbs[0],)))
                else:
                    theta = exponent * math.pi
                    gates.append(QGate(GateType.RX, (qbs[0],), params=(theta,)))
                continue

            # ── YPowGate（Y^t）→ RY(t·π) ────────────────────
            if isinstance(g, cirq.YPowGate):
                exponent = float(g.exponent)
                theta = exponent * math.pi
                gates.append(QGate(GateType.RY, (qbs[0],), params=(theta,)))
                continue

            # ── HPowGate（H^1 = H）───────────────────────────
            if isinstance(g, cirq.HPowGate):
                if abs(float(g.exponent) - 1.0) < 1e-9:
                    gates.append(QGate(GateType.H, (qbs[0],)))
                continue

            # ── CNotPowGate（CNOT^1）─────────────────────────
            if isinstance(g, cirq.CNotPowGate):
                if abs(float(g.exponent) - 1.0) < 1e-9:
                    gates.append(QGate(GateType.CX, (qbs[0], qbs[1])))
                continue

            # ── CZPowGate（CZ^1）─────────────────────────────
            if isinstance(g, cirq.CZPowGate):
                if abs(float(g.exponent) - 1.0) < 1e-9:
                    gates.append(QGate(GateType.CZ, (qbs[0], qbs[1])))
                continue

            # ── SWAP pow ──────────────────────────────────────
            if isinstance(g, cirq.SwapPowGate):
                if abs(float(g.exponent) - 1.0) < 1e-9:
                    gates.append(QGate(GateType.SWAP, (qbs[0], qbs[1])))
                continue

            # ── CCX / CSWAP ───────────────────────────────────
            if isinstance(g, cirq.CCXPowGate):
                if abs(float(g.exponent) - 1.0) < 1e-9:
                    gates.append(QGate(GateType.CCX, qbs))
                continue

            if isinstance(g, cirq.CSwapGate):
                gates.append(QGate(GateType.CSWAP, qbs))
                continue

            # ── 直接映射（H X Y Z S T CNOT CZ SWAP）─────────
            gt = gate_map.get(type(g))
            if gt is not None:
                gates.append(QGate(gt, qbs))
                continue

            # ── 未知门：noop + 警告 meta ─────────────────────
            gates.append(QGate(
                GateType.ID, qbs[:1] if qbs else (0,),
                meta={"cirq_unknown": str(g)}
            ))

    n_clbits = len(clbit_map)
    return QCircuit(n_qubits=n_qubits, n_clbits=n_clbits,
                    name=name, gates=gates)


def to_cirq(qcirc: QCircuit) -> "cirq.Circuit":
    """将 QCircuit（Layer 0）导出为 Cirq Circuit。

    仅支持 Layer 0 标准门，Layer 1/2 指令跳过。
    """
    try:
        import cirq
    except ImportError as e:
        raise ImportError(
            "Cirq 前端需要 cirq-core：pip install cirq-core"
        ) from e

    qubits = cirq.LineQubit.range(qcirc.n_qubits)
    ops = []

    _GATE_TO_CIRQ = {
        GateType.H:    cirq.H,
        GateType.X:    cirq.X,
        GateType.Y:    cirq.Y,
        GateType.Z:    cirq.Z,
        GateType.S:    cirq.S,
        GateType.T:    cirq.T,
        GateType.CX:   cirq.CNOT,
        GateType.CZ:   cirq.CZ,
        GateType.SWAP: cirq.SWAP,
        GateType.CCX:  cirq.CCX,
    }

    for gate in qcirc.gates:
        if gate.layer != 0:
            continue
        q = [qubits[i] for i in gate.qubits]
        if gate.op == GateType.RZ and gate.params:
            ops.append(cirq.rz(gate.params[0])(*q))
        elif gate.op == GateType.RY and gate.params:
            ops.append(cirq.ry(gate.params[0])(*q))
        elif gate.op == GateType.RX and gate.params:
            ops.append(cirq.rx(gate.params[0])(*q))
        elif gate.op == GateType.MEAS:
            cb = gate.clbits[0] if gate.clbits else 0
            ops.append(cirq.measure(*q, key=str(cb)))
        elif gate.op == GateType.RESET:
            ops.append(cirq.reset(*q))
        else:
            cg = _GATE_TO_CIRQ.get(gate.op)
            if cg is not None:
                ops.append(cg(*q))

    return cirq.Circuit(ops)
