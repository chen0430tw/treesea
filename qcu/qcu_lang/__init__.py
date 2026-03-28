# qcu_lang — QCU 量子语言桥接库
"""
qcu_lang 三层指令集架构：

  Layer 0 — 标准量子门      (GateType.*)
  Layer 1 — QCU 相位指令    (PhaseOp.*)
  Layer 2 — QCU 涌现指令    (EmergeOp.*)

快速上手
--------
>>> from qcu_lang import QCircuit, QCUExecutor
>>> circ = QCircuit(n_qubits=2)
>>> circ.h(0).cx(0, 1)
>>> result = QCUExecutor(verbose=False).run(circ)
>>> print(result.final_C)

也可从 QASM 字符串构建：
>>> from qcu_lang import from_qasm_str
>>> circ = from_qasm_str('OPENQASM 2.0; qreg q[2]; h q[0]; cx q[0],q[1];')
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# IR
from .ir.ops import GateType, PhaseOp, EmergeOp
from .ir.circuit import QGate, QCircuit

# 前端
from .frontend.qasm import from_qasm_str, from_qasm_file
from .frontend.qsharp import from_qsharp_str, from_qsharp_file

# 编译器
from .compiler.phase_map import compile_circuit, PhaseStep
from .compiler.optimizer import optimize

# 后端
from .backend.qcu_executor import QCUExecutor, QCUExecResult

__all__ = [
    # ISA
    "GateType", "PhaseOp", "EmergeOp",
    # IR
    "QGate", "QCircuit",
    # 前端
    "from_qasm_str", "from_qasm_file",
    "from_qsharp_str", "from_qsharp_file",
    # 编译器
    "compile_circuit", "PhaseStep", "optimize",
    # 后端
    "QCUExecutor", "QCUExecResult",
]
