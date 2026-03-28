# circuit.py
"""
QCU 通用量子电路 IR。

数据结构：
  QGate   — 单条指令（标准门 / 相位指令 / 涌现指令）
  QCircuit — 指令序列 + qubit/clbit 寄存器

设计原则：
  - 三层指令统一用 QGate 表示，由 layer 字段区分
  - 不可变（frozen dataclass），方便复制和传递
  - 前端解析结果、编译中间态、后端输入都是 QCircuit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Union

from .ops import GateType, PhaseOp, EmergeOp

# 指令类型联合
OpType = Union[GateType, PhaseOp, EmergeOp]


@dataclass(frozen=True)
class QGate:
    """单条量子指令。

    Attributes
    ----------
    op : GateType | PhaseOp | EmergeOp
        指令类型（三层 ISA 之一）
    qubits : tuple of int
        作用的逻辑 qubit 索引
    clbits : tuple of int
        关联的经典比特索引（MEAS 指令使用）
    params : tuple of float | complex
        数值参数（角度、幅度、时长等）
    meta : dict
        扩展字段（来源行号、注释、原始 QASM 文本等）
    """
    op: OpType
    qubits: tuple = ()
    clbits: tuple = ()
    params: tuple = ()
    meta: dict = field(default_factory=dict, hash=False, compare=False)

    @property
    def layer(self) -> int:
        """返回 ISA 层级：0=标准门 1=相位指令 2=涌现指令"""
        if isinstance(self.op, GateType):
            return 0
        if isinstance(self.op, PhaseOp):
            return 1
        return 2

    def __repr__(self) -> str:
        parts = [self.op.name]
        if self.qubits:
            parts.append(f"q={list(self.qubits)}")
        if self.params:
            parts.append(f"p={[round(float(p.real) if hasattr(p,'real') else p, 4) for p in self.params]}")
        if self.clbits:
            parts.append(f"c={list(self.clbits)}")
        return f"QGate({', '.join(parts)})"


@dataclass
class QCircuit:
    """量子电路 IR。

    Attributes
    ----------
    n_qubits : int
        逻辑 qubit 数量
    n_clbits : int
        经典比特数量（用于测量结果）
    gates : list of QGate
        指令序列（按执行顺序）
    name : str
        电路名称（可选）
    metadata : dict
        来源信息（原始语言、文件名、版本等）
    """
    n_qubits: int
    n_clbits: int = 0
    gates: List[QGate] = field(default_factory=list)
    name: str = ""
    metadata: dict = field(default_factory=dict)

    # ── 构建接口 ──────────────────────────────

    def append(self, gate: QGate) -> "QCircuit":
        """追加一条指令，返回 self 支持链式调用。"""
        self.gates.append(gate)
        return self

    def extend(self, gates) -> "QCircuit":
        self.gates.extend(gates)
        return self

    # Layer 0 便捷方法
    def h(self, q: int):
        return self.append(QGate(GateType.H, (q,)))

    def x(self, q: int):
        return self.append(QGate(GateType.X, (q,)))

    def y(self, q: int):
        return self.append(QGate(GateType.Y, (q,)))

    def z(self, q: int):
        return self.append(QGate(GateType.Z, (q,)))

    def s(self, q: int):
        return self.append(QGate(GateType.S, (q,)))

    def t(self, q: int):
        return self.append(QGate(GateType.T, (q,)))

    def rx(self, theta: float, q: int):
        return self.append(QGate(GateType.RX, (q,), params=(theta,)))

    def ry(self, theta: float, q: int):
        return self.append(QGate(GateType.RY, (q,), params=(theta,)))

    def rz(self, theta: float, q: int):
        return self.append(QGate(GateType.RZ, (q,), params=(theta,)))

    def cx(self, ctrl: int, tgt: int):
        return self.append(QGate(GateType.CX, (ctrl, tgt)))

    def cz(self, ctrl: int, tgt: int):
        return self.append(QGate(GateType.CZ, (ctrl, tgt)))

    def measure(self, q: int, c: int):
        return self.append(QGate(GateType.MEAS, (q,), clbits=(c,)))

    def reset(self, q: int):
        return self.append(QGate(GateType.RESET, (q,)))

    # Layer 1 便捷方法
    def phase_shift(self, mode: int, theta: float):
        return self.append(QGate(PhaseOp.PHASE_SHIFT, params=(mode, theta)))

    def phase_trim(self, mode0: int, mode1: int, delta: float):
        return self.append(QGate(PhaseOp.PHASE_TRIM, params=(mode0, mode1, delta)))

    def phase_lock(self, mode0: int, mode1: int, gamma: float):
        return self.append(QGate(PhaseOp.PHASE_LOCK, params=(mode0, mode1, gamma)))

    def drive_boost(self, mode: int, factor: float):
        return self.append(QGate(PhaseOp.DRIVE_BOOST, params=(mode, factor)))

    def dispersive_wait(self, qubit: int, mode: int, duration: float):
        return self.append(QGate(PhaseOp.DISPERSIVE_WAIT, params=(qubit, mode, duration)))

    def free_evolve(self, duration: float):
        return self.append(QGate(PhaseOp.FREE_EVOLVE, params=(duration,)))

    # Layer 2 便捷方法
    def qcl_pcm(self, gamma_pcm: float, duration: float):
        return self.append(QGate(EmergeOp.QCL_PCM, params=(gamma_pcm, duration)))

    def qcl_qim(self, omega_x: float, gamma_qim: float, duration: float):
        return self.append(QGate(EmergeOp.QCL_QIM, params=(omega_x, gamma_qim, duration)))

    def qcl_boost(self, eps_boost: float, gamma_boost: float, trim: float, duration: float):
        return self.append(QGate(EmergeOp.QCL_BOOST, params=(eps_boost, gamma_boost, trim, duration)))

    def phase_lock_wait(self, C_threshold: float = 0.01):
        return self.append(QGate(EmergeOp.PHASE_LOCK_WAIT, params=(C_threshold,)))

    def collapse_scan(self, candidates: Any, C_threshold: float = 0.01):
        return self.append(QGate(EmergeOp.COLLAPSE_SCAN,
                                  meta={"candidates": candidates, "C_threshold": C_threshold}))

    def sync_emerge(self):
        return self.append(QGate(EmergeOp.SYNC_EMERGE))

    def phase_anneal(self, schedule: list):
        return self.append(QGate(EmergeOp.PHASE_ANNEAL, meta={"schedule": schedule}))

    def set_noise(self, *,
                  T1: float = None,
                  Tphi: float = None,
                  kappa: float = None,
                  d: int = None,
                  preset: str = None) -> "QCircuit":
        """标注电路噪声参数，供 QCUExecutor 自动推导 IQPUConfig。

        Parameters
        ----------
        T1 : float, optional
            qubit 纵向弛豫时间（μs），典型值 50–200
        Tphi : float, optional
            纯退相干时间（μs），典型值 100–500
        kappa : float, optional
            腔泄漏率，典型值 0.005–0.05
        d : int, optional
            Fock 截断维度，默认 6
        preset : str, optional
            预设档位："ideal" / "nisq" / "noisy"
            显式参数会覆盖预设值

        Returns
        -------
        QCircuit
            self（支持链式调用）

        Examples
        --------
        >>> circ.set_noise(preset="nisq")
        >>> circ.set_noise(T1=50., Tphi=100., kappa=0.02)
        >>> circ.set_noise(preset="ideal", d=8)   # ideal + 更高 Fock 截断
        """
        noise: dict = {}
        if preset is not None:
            noise["preset"] = preset
        if T1    is not None: noise["T1"]    = float(T1)
        if Tphi  is not None: noise["Tphi"]  = float(Tphi)
        if kappa is not None: noise["kappa"] = float(kappa)
        if d     is not None: noise["d"]     = int(d)
        self.metadata["noise"] = noise
        return self

    # ── 查询接口 ──────────────────────────────

    def layer0_gates(self) -> List[QGate]:
        return [g for g in self.gates if g.layer == 0]

    def layer1_gates(self) -> List[QGate]:
        return [g for g in self.gates if g.layer == 1]

    def layer2_gates(self) -> List[QGate]:
        return [g for g in self.gates if g.layer == 2]

    @property
    def depth(self) -> int:
        """电路深度（串行步数，忽略并行性）。"""
        return len(self.gates)

    @property
    def t_count(self) -> int:
        """T 门数量（纠错代价指标）。"""
        return sum(1 for g in self.gates if g.op in (GateType.T, GateType.TDG))

    @property
    def two_qubit_count(self) -> int:
        """双比特门数量。"""
        from .ops import GATE_QUBIT_COUNT
        return sum(
            1 for g in self.gates
            if isinstance(g.op, GateType) and GATE_QUBIT_COUNT.get(g.op, 0) == 2
        )

    def __len__(self) -> int:
        return len(self.gates)

    def __repr__(self) -> str:
        return (
            f"QCircuit(name={self.name!r}, "
            f"qubits={self.n_qubits}, clbits={self.n_clbits}, "
            f"depth={self.depth}, T={self.t_count}, 2q={self.two_qubit_count})"
        )
