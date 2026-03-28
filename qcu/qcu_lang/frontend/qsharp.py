# qsharp.py
"""
Q# (.qs) → QCircuit 前端解析器（轻量，无额外依赖）。

支持的 Q# 语法子集
------------------
  use q = Qubit();
  use (q0, q1, q2) = (Qubit(), Qubit(), Qubit());

  单比特门：  H X Y Z S T I
  伴随门：    Adjoint S(q)  Adjoint T(q)
  旋转门：    Rx(θ, q)  Ry(θ, q)  Rz(θ, q)  R1(θ, q)
  双比特门：  CNOT(ctrl, tgt)  CZ(ctrl, tgt)  SWAP(a, b)
  三比特门：  CCNOT(c0, c1, tgt)
  测量：      M(q)  Measure([PauliZ], [q])
  注释：      // ...

不支持（静默跳过）：
  classical control flow、函数调用、多操作体 operation、@EntryPoint
"""

from __future__ import annotations

import math
import re
from typing import List, Optional

from ..ir.circuit import QCircuit, QGate
from ..ir.ops import GateType

# ── 门名称 → GateType 映射 ────────────────────────────────────
_QS_GATE: dict[str, GateType] = {
    "H":     GateType.H,
    "X":     GateType.X,
    "Y":     GateType.Y,
    "Z":     GateType.Z,
    "S":     GateType.S,
    "T":     GateType.T,
    "I":     GateType.ID,
    "CNOT":  GateType.CX,
    "CZ":    GateType.CZ,
    "SWAP":  GateType.SWAP,
    "CCNOT": GateType.CCX,
    "CSWAP": GateType.CSWAP,
}

_QS_ADJOINT: dict[str, GateType] = {
    "S": GateType.SDG,
    "T": GateType.TDG,
    "X": GateType.X,   # Adjoint X = X
    "H": GateType.H,   # Adjoint H = H
}

_QS_ROT: dict[str, GateType] = {
    "Rx": GateType.RX,
    "Ry": GateType.RY,
    "Rz": GateType.RZ,
    "R1": GateType.P,   # R1(θ) = P(θ) = RZ(θ) up to global phase
}


def _parse_angle(s: str) -> float:
    """将 Q# 角度字符串转为 float（支持 Math.PI、PI、pi、数字）。"""
    s = s.strip()
    s = re.sub(r'Math\.PI|Math\.Pi', str(math.pi), s)
    s = re.sub(r'\bPI\b|\bpi\b', str(math.pi), s)
    try:
        return float(eval(s, {"__builtins__": {}}, {"pi": math.pi}))  # noqa: S307
    except Exception:
        return 0.0


def from_qsharp_str(src: str, name: str = "") -> QCircuit:
    """将 Q# 源码字符串解析为 QCircuit。

    Parameters
    ----------
    src : str
        Q# 源码（完整文件或片段均可）
    name : str
        电路名称

    Returns
    -------
    QCircuit
    """
    lines = src.splitlines()

    # ── 第一遍：收集 qubit 声明，建立名称 → 索引映射 ───────────
    qubit_map: dict[str, int] = {}

    def _alloc(qname: str) -> int:
        if qname not in qubit_map:
            qubit_map[qname] = len(qubit_map)
        return qubit_map[qname]

    # use q = Qubit();
    pat_single = re.compile(r'\buse\s+(\w+)\s*=\s*Qubit\(\)')
    # use (q0, q1, ...) = (Qubit(), Qubit(), ...);
    pat_multi  = re.compile(r'\buse\s*\(([^)]+)\)\s*=\s*\((?:Qubit\(\)\s*,?\s*)+\)')

    for line in lines:
        line_s = line.strip()
        if line_s.startswith("//"):
            continue
        m = pat_multi.search(line_s)
        if m:
            for qn in re.split(r',\s*', m.group(1)):
                _alloc(qn.strip())
            continue
        m = pat_single.search(line_s)
        if m:
            _alloc(m.group(1))

    # ── 第二遍：解析门操作 ──────────────────────────────────────
    gates: List[QGate] = []
    clbit_map: dict[str, int] = {}
    _meas = [0]   # 用列表规避 nonlocal

    def _cb(qname: str) -> int:
        if qname not in clbit_map:
            clbit_map[qname] = _meas[0]
            _meas[0] += 1
        return clbit_map[qname]

    def _q(name: str) -> int:
        """将 qubit 名解析为索引；未见过的名字动态分配。"""
        name = name.strip()
        # 支持数组写法 q[0] 或单名 q0
        m = re.match(r'(\w+)\[(\d+)\]', name)
        if m:
            base, idx = m.group(1), int(m.group(2))
            key = f"{base}_{idx}"
        else:
            key = name
        return _alloc(key)

    for line in lines:
        line_s = line.strip()
        if not line_s or line_s.startswith("//"):
            continue
        # 去掉行尾注释
        line_s = re.sub(r'\s*//.*$', '', line_s)

        # ── Adjoint Gate(q) ──────────────────────────────────
        m = re.match(r'Adjoint\s+(\w+)\(([^)]+)\)\s*;?$', line_s)
        if m:
            gname, args = m.group(1), m.group(2)
            gt = _QS_ADJOINT.get(gname)
            if gt is not None:
                qbs = [_q(a) for a in args.split(',')]
                gates.append(QGate(gt, tuple(qbs)))
            continue

        # ── Rotation Gate(angle, q) ───────────────────────────
        m = re.match(r'(Rx|Ry|Rz|R1)\(([^,]+),([^)]+)\)\s*;?$', line_s)
        if m:
            gname, ang_s, qarg = m.group(1), m.group(2), m.group(3)
            gt = _QS_ROT[gname]
            theta = _parse_angle(ang_s)
            gates.append(QGate(gt, (_q(qarg),), params=(theta,)))
            continue

        # ── Measure: let r = M(q); / M(q) ────────────────────
        m = re.match(r'(?:let\s+\w+\s*=\s*)?M\(([^)]+)\)\s*;?$', line_s)
        if m:
            qarg = m.group(1).strip()
            cb = _cb(qarg)
            gates.append(QGate(GateType.MEAS, (_q(qarg),), clbits=(cb,)))
            continue

        # ── 3-qubit gate: CCNOT(c0, c1, t) ───────────────────
        m = re.match(r'(CCNOT|CSWAP)\(([^)]+)\)\s*;?$', line_s)
        if m:
            gname, args = m.group(1), m.group(2)
            qbs = [_q(a) for a in args.split(',')]
            if len(qbs) == 3:
                gates.append(QGate(_QS_GATE[gname], tuple(qbs)))
            continue

        # ── 2-qubit gate: CNOT(ctrl, tgt) / CZ / SWAP ────────
        m = re.match(r'(CNOT|CZ|SWAP)\(([^)]+)\)\s*;?$', line_s)
        if m:
            gname, args = m.group(1), m.group(2)
            qbs = [_q(a) for a in args.split(',')]
            if len(qbs) == 2:
                gates.append(QGate(_QS_GATE[gname], tuple(qbs)))
            continue

        # ── 1-qubit gate: H(q) / X(q) / … ────────────────────
        m = re.match(r'([A-Z][A-Za-z0-9]*)\(([^)]+)\)\s*;?$', line_s)
        if m:
            gname, qarg = m.group(1), m.group(2).strip()
            gt = _QS_GATE.get(gname)
            if gt is not None:
                gates.append(QGate(gt, (_q(qarg),)))
            continue

    n_qubits = len(qubit_map) or 1
    n_clbits = len(clbit_map)
    return QCircuit(n_qubits=n_qubits, n_clbits=n_clbits,
                    name=name, gates=gates)


def from_qsharp_file(path: str) -> QCircuit:
    """从 .qs 文件读取并解析为 QCircuit。"""
    import pathlib
    src = pathlib.Path(path).read_text(encoding="utf-8")
    return from_qsharp_str(src, name=pathlib.Path(path).stem)
