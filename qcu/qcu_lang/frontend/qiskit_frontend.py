# qiskit_frontend.py
"""
Qiskit QuantumCircuit → QCircuit 前端适配器。

用法：
  from qcu_lang.frontend.qiskit_frontend import from_qiskit
  circ = from_qiskit(qiskit_circuit)

依赖：
  pip install qiskit
"""

from __future__ import annotations

from typing import Dict

from ..ir.circuit import QCircuit, QGate
from ..ir.ops import GateType


# Qiskit gate 名称 → GateType 映射
_QISKIT_GATE_MAP: Dict[str, GateType] = {
    # Pauli / Clifford
    "x":        GateType.X,
    "y":        GateType.Y,
    "z":        GateType.Z,
    "h":        GateType.H,
    "s":        GateType.S,
    "t":        GateType.T,
    "sdg":      GateType.SDG,
    "tdg":      GateType.TDG,
    "sx":       GateType.SX,
    "sxdg":     GateType.SDG,      # 近似
    # 旋转
    "rx":       GateType.RX,
    "ry":       GateType.RY,
    "rz":       GateType.RZ,
    "p":        GateType.P,
    "u":        GateType.U,
    "u1":       GateType.P,
    "u2":       GateType.U,
    "u3":       GateType.U,
    "r":        GateType.U,
    # 双比特
    "cx":       GateType.CX,
    "cy":       GateType.CY,
    "cz":       GateType.CZ,
    "cnot":     GateType.CX,
    "swap":     GateType.SWAP,
    "iswap":    GateType.ISWAP,
    "ecr":      GateType.ECR,
    "dcx":      GateType.CX,       # 近似：double-CX
    # 多比特
    "ccx":      GateType.CCX,
    "cswap":    GateType.CSWAP,
    "mcx":      GateType.MCX,
    "mct":      GateType.MCX,
    # 测量 / 初始化
    "measure":  GateType.MEAS,
    "reset":    GateType.RESET,
    "id":       GateType.ID,
    "delay":    GateType.ID,
    "barrier":  GateType.BARRIER,
}


def from_qiskit(qiskit_circuit) -> QCircuit:
    """将 Qiskit QuantumCircuit 转换为 QCircuit IR。

    Parameters
    ----------
    qiskit_circuit : qiskit.circuit.QuantumCircuit
        已构建的 Qiskit 量子电路

    Returns
    -------
    QCircuit
    """
    try:
        from qiskit.circuit import QuantumCircuit
    except ImportError:
        raise ImportError("需要安装 Qiskit：pip install qiskit")

    qc = qiskit_circuit
    n_qubits = qc.num_qubits
    n_clbits = qc.num_clbits

    # 建立 qubit → 全局索引映射
    q_index: Dict = {}
    offset = 0
    for qreg in qc.qregs:
        for i, qubit in enumerate(qreg):
            q_index[qubit] = offset + i
        offset += len(qreg)

    # 建立 clbit → 全局索引映射
    c_index: Dict = {}
    offset = 0
    for creg in qc.cregs:
        for i, clbit in enumerate(creg):
            c_index[clbit] = offset + i
        offset += len(creg)

    gates = []
    for instruction in qc.data:
        op = instruction.operation
        gate_name = op.name.lower()
        gate_type = _QISKIT_GATE_MAP.get(gate_name)

        if gate_type is None:
            # 尝试分解：用 Qiskit 的 decompose 展开
            try:
                decomposed = qc.decompose(gates_to_decompose=[op.name])
                sub_circ = from_qiskit(decomposed)
                gates.extend(sub_circ.gates)
            except Exception:
                pass  # 无法分解，跳过
            continue

        # qubit 索引（注意：Qiskit 和 QCU 都用 little-endian）
        qubits = tuple(q_index[q] for q in instruction.qubits)
        clbits = tuple(c_index[c] for c in instruction.clbits)

        # 参数（Qiskit 参数可能是 ParameterExpression，需 float 化）
        params = []
        for p in op.params:
            try:
                params.append(float(p))
            except Exception:
                params.append(0.0)

        gates.append(QGate(
            gate_type,
            qubits,
            clbits=clbits,
            params=tuple(params),
            meta={"qiskit_name": op.name},
        ))

    return QCircuit(
        n_qubits=n_qubits,
        n_clbits=n_clbits,
        gates=gates,
        name=qc.name,
        metadata={
            "source": "qiskit",
            "qiskit_version": _qiskit_version(),
        },
    )


def _qiskit_version() -> str:
    try:
        import qiskit
        return qiskit.__version__
    except Exception:
        return "unknown"


def to_qasm2(circ: QCircuit) -> str:
    """将 QCircuit 导出为 QASM 2.0 字符串（仅 Layer 0 标准门）。

    Layer 1/2 涌现指令不在 QASM 标准中，会被跳过并注释标注。
    """
    _GATE_TO_QASM2 = {v: k for k, v in {
        "x": GateType.X, "y": GateType.Y, "z": GateType.Z,
        "h": GateType.H, "s": GateType.S, "t": GateType.T,
        "sdg": GateType.SDG, "tdg": GateType.TDG, "sx": GateType.SX,
        "rx": GateType.RX, "ry": GateType.RY, "rz": GateType.RZ,
        "p": GateType.P, "cx": GateType.CX, "cy": GateType.CY,
        "cz": GateType.CZ, "swap": GateType.SWAP, "ccx": GateType.CCX,
        "cswap": GateType.CSWAP, "reset": GateType.RESET, "barrier": GateType.BARRIER,
    }.items()}

    lines = [
        'OPENQASM 2.0;',
        'include "qelib1.inc";',
        f'qreg q[{circ.n_qubits}];',
    ]
    if circ.n_clbits:
        lines.append(f'creg c[{circ.n_clbits}];')

    for gate in circ.gates:
        if gate.layer != 0:
            lines.append(f'// [QCU Layer {gate.layer}] {gate.op.name} skipped in QASM2')
            continue

        name = _GATE_TO_QASM2.get(gate.op)
        if name is None:
            continue

        if gate.op == GateType.MEAS:
            q, c = gate.qubits[0], gate.clbits[0] if gate.clbits else 0
            lines.append(f'measure q[{q}] -> c[{c}];')
        elif gate.params:
            params_str = ", ".join(f"{p:.6f}" for p in gate.params)
            qubits_str = ", ".join(f"q[{q}]" for q in gate.qubits)
            lines.append(f'{name}({params_str}) {qubits_str};')
        else:
            qubits_str = ", ".join(f"q[{q}]" for q in gate.qubits)
            lines.append(f'{name} {qubits_str};')

    return "\n".join(lines)
