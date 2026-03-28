# qasm.py
"""
OpenQASM 2.0 / 3.0 → QCircuit 前端解析器。

支持：
  - OpenQASM 2.0（qelib1.inc 标准门库）
  - OpenQASM 3.0（需安装 openqasm3[parser]）

用法：
  from qcu_lang.frontend.qasm import from_qasm_str, from_qasm_file
  circ = from_qasm_str(qasm_text)
  circ = from_qasm_file("circuit.qasm")
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from ..ir.circuit import QCircuit, QGate
from ..ir.ops import GateType


# ── QASM 2.0 标准门名 → GateType 映射 ─────────────────────────

_QASM2_GATE_MAP: Dict[str, GateType] = {
    # Pauli / Clifford
    "x":    GateType.X,
    "y":    GateType.Y,
    "z":    GateType.Z,
    "h":    GateType.H,
    "s":    GateType.S,
    "t":    GateType.T,
    "sdg":  GateType.SDG,
    "tdg":  GateType.TDG,
    "sx":   GateType.SX,
    # 旋转
    "rx":   GateType.RX,
    "ry":   GateType.RY,
    "rz":   GateType.RZ,
    "p":    GateType.P,
    "u":    GateType.U,
    "u1":   GateType.P,     # u1(λ) ≡ P(λ)
    "u2":   GateType.U,     # u2(φ,λ) = U(π/2, φ, λ)
    "u3":   GateType.U,     # u3(θ,φ,λ) = U(θ,φ,λ)
    # 双比特
    "cx":   GateType.CX,
    "cy":   GateType.CY,
    "cz":   GateType.CZ,
    "cnot": GateType.CX,
    "swap": GateType.SWAP,
    "iswap": GateType.ISWAP,
    "ecr":  GateType.ECR,
    # 多比特
    "ccx":  GateType.CCX,
    "toffoli": GateType.CCX,
    "cswap": GateType.CSWAP,
    # 测量 / 初始化
    "measure":   GateType.MEAS,
    "proj_meas": GateType.PROJ_MEAS,
    "reset":     GateType.RESET,
    "id":      GateType.ID,
    "barrier": GateType.BARRIER,
}


# ── 轻量 QASM 2.0 解析器 ─────────────────────────────────────

def _parse_qasm2(text: str) -> QCircuit:
    """轻量 QASM 2.0 解析器（不依赖外部库）。"""
    # 按分号展开为独立语句（先剥注释，再分割）
    stmts = []
    for raw in text.splitlines():
        raw = raw.split("//")[0]
        for part in raw.split(";"):
            s = part.strip()
            if s:
                stmts.append(s)

    qreg: Dict[str, int] = {}       # 寄存器名 → 起始索引
    qreg_size: Dict[str, int] = {}  # 寄存器名 → 大小
    creg: Dict[str, int] = {}
    creg_size: Dict[str, int] = {}
    total_q = 0
    total_c = 0
    gates: List[QGate] = []
    name = ""

    for lineno, line in enumerate(stmts, 1):
        if not line:
            continue

        # OPENQASM 版本声明
        if line.startswith("OPENQASM"):
            continue

        # include（忽略，qelib1.inc 门已内置）
        if line.startswith("include"):
            continue

        # qreg 声明
        m = re.match(r"qreg\s+(\w+)\[(\d+)\]", line)
        if m:
            rname, size = m.group(1), int(m.group(2))
            qreg[rname] = total_q
            qreg_size[rname] = size
            total_q += size
            continue

        # creg 声明
        m = re.match(r"creg\s+(\w+)\[(\d+)\]", line)
        if m:
            rname, size = m.group(1), int(m.group(2))
            creg[rname] = total_c
            creg_size[rname] = size
            total_c += size
            continue

        # measure 语句：measure q[i] -> c[j]（逐位）
        m = re.match(r"measure\s+(\w+)\[(\d+)\]\s*->\s*(\w+)\[(\d+)\]", line)
        if m:
            qr, qi, cr, ci = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
            q_idx = qreg.get(qr, 0) + qi
            c_idx = creg.get(cr, 0) + ci
            gates.append(QGate(GateType.MEAS, (q_idx,), clbits=(c_idx,),
                               meta={"line": lineno}))
            continue

        # measure 语句：measure q -> c（整寄存器广播）
        m = re.match(r"measure\s+(\w+)\s*->\s*(\w+)$", line)
        if m:
            qr, cr = m.group(1), m.group(2)
            if qr in qreg and cr in creg:
                size = qreg_size.get(qr, 1)
                for i in range(size):
                    gates.append(QGate(GateType.MEAS,
                                       (qreg[qr] + i,),
                                       clbits=(creg[cr] + i,),
                                       meta={"line": lineno}))
            continue

        # 门指令解析
        m = re.match(r"(\w+)(?:\(([^)]*)\))?\s+(.*)", line)
        if not m:
            continue

        gate_name = m.group(1).lower()
        params_str = m.group(2) or ""
        args_str = m.group(3)

        if gate_name not in _QASM2_GATE_MAP:
            continue  # 自定义门，跳过

        gate_type = _QASM2_GATE_MAP[gate_name]

        # 解析参数
        params = []
        if params_str.strip():
            for p in params_str.split(","):
                p = p.strip()
                try:
                    params.append(float(eval(p.replace("pi", "3.141592653589793"))))
                except Exception:
                    params.append(0.0)

        # 解析 qubit 参数：支持 q[i]（索引）和 q（整寄存器广播）
        raw_args = [a.strip() for a in args_str.split(",")]
        resolved: List[List[int]] = []  # 每个参数位置的候选 qubit 列表
        broadcast_size = 1
        for arg in raw_args:
            mm = re.match(r"(\w+)\[(\d+)\]", arg)
            if mm:
                rname, idx = mm.group(1), int(mm.group(2))
                resolved.append([qreg.get(rname, 0) + idx])
            elif arg in qreg:
                sz = qreg_size.get(arg, 1)
                broadcast_size = max(broadcast_size, sz)
                resolved.append([qreg[arg] + i for i in range(sz)])
            else:
                resolved.append([0])

        # 广播展开：每个广播位置生成一个 gate
        for bi in range(broadcast_size):
            qubits = tuple(
                slots[bi] if len(slots) > 1 else slots[0]
                for slots in resolved
            )
            gates.append(QGate(gate_type, qubits, params=tuple(params),
                               meta={"line": lineno}))

    circ = QCircuit(n_qubits=total_q, n_clbits=total_c, gates=gates,
                    name=name, metadata={"source": "qasm2"})
    return circ


# ── QASM 3.0 解析器（依赖 openqasm3 库）────────────────────────

def _parse_qasm3(text: str) -> QCircuit:
    """使用 openqasm3 库解析 QASM 3.0。"""
    try:
        from openqasm3 import parse
        import openqasm3.ast as ast
    except ImportError:
        raise ImportError(
            "需要安装 openqasm3 解析库：pip install openqasm3[parser]"
        )

    program = parse(text)
    qreg: Dict[str, int] = {}
    creg: Dict[str, int] = {}
    total_q = 0
    total_c = 0
    gates: List[QGate] = []

    for stmt in program.statements:
        # qubit 声明
        if isinstance(stmt, ast.QubitDeclaration):
            size = stmt.size.value if stmt.size else 1
            qreg[stmt.qubit.name] = total_q
            total_q += int(size)

        # 经典比特声明
        elif isinstance(stmt, ast.ClassicalDeclaration):
            if hasattr(stmt, 'type') and hasattr(stmt.type, 'size'):
                size = stmt.type.size.value if stmt.type.size else 1
                creg[stmt.identifier.name] = total_c
                total_c += int(size)

        # 门调用
        elif isinstance(stmt, ast.QuantumGate):
            gate_name = stmt.name.name.lower()
            gate_type = _QASM2_GATE_MAP.get(gate_name)
            if gate_type is None:
                continue

            # 解析参数
            params = []
            for arg in (stmt.arguments or []):
                try:
                    params.append(float(_eval_qasm3_expr(arg)))
                except Exception:
                    params.append(0.0)

            # 解析 qubit
            qubits = []
            for q in stmt.qubits:
                if hasattr(q, 'name'):
                    name = q.name.name if hasattr(q.name, 'name') else str(q.name)
                    idx = q.indices[0][0].value if q.indices else 0
                    qubits.append(qreg.get(name, 0) + int(idx))

            gates.append(QGate(gate_type, tuple(qubits), params=tuple(params)))

        # 测量
        elif isinstance(stmt, ast.QuantumMeasurementStatement):
            pass  # TODO: 解析 measure → 经典比特

    return QCircuit(n_qubits=total_q, n_clbits=total_c, gates=gates,
                    metadata={"source": "qasm3"})


def _eval_qasm3_expr(node) -> float:
    """简单求值 QASM3 表达式节点。"""
    import openqasm3.ast as ast
    import math
    if isinstance(node, ast.IntegerLiteral):
        return float(node.value)
    if isinstance(node, ast.FloatLiteral):
        return float(node.value)
    if isinstance(node, ast.Identifier):
        return {"pi": math.pi, "tau": 2 * math.pi, "euler": math.e}.get(node.name, 0.0)
    if isinstance(node, ast.BinaryExpression):
        ops = {"+": lambda a,b: a+b, "-": lambda a,b: a-b,
               "*": lambda a,b: a*b, "/": lambda a,b: a/b}
        op = ops.get(str(node.op), lambda a,b: 0)
        return op(_eval_qasm3_expr(node.lhs), _eval_qasm3_expr(node.rhs))
    if isinstance(node, ast.UnaryExpression):
        val = _eval_qasm3_expr(node.expression)
        return -val if str(node.op) == "-" else val
    return 0.0


# ── 公开 API ────────────────────────────────────────────────

def from_qasm_str(text: str) -> QCircuit:
    """从 QASM 字符串解析，自动检测版本。"""
    text = text.strip()
    if "OPENQASM 3" in text or "OPENQASM 3.0" in text:
        return _parse_qasm3(text)
    return _parse_qasm2(text)


def from_qasm_file(path: str) -> QCircuit:
    """从 QASM 文件解析。"""
    text = Path(path).read_text(encoding="utf-8")
    circ = from_qasm_str(text)
    circ.name = Path(path).stem
    circ.metadata["file"] = str(path)
    return circ
