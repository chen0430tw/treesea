# ops.py
"""
QCU-ISA 三层指令集定义。

Layer 0 — 标准量子门（Standard Gates）
    参考 OpenQASM qelib1.inc / IBM basis / Clifford+T 标准
    覆盖所有量子编程语言的通用门，作为外部语言的编译目标。

Layer 1 — QCU 相位指令（Phase Instructions）
    QCU 特有，直接操作腔 mode 的相位和驱动参数。
    对应 Hamiltonian 中的 ε、χ、boost_phase_trim 等物理量。

Layer 2 — QCU 涌现指令（Emergence Instructions）
    QCU 特有，触发高层涌现计算行为。
    答案不是逐步算出的，而是让系统演化到锁定态后坍缩读出。
"""

from __future__ import annotations

from enum import Enum, auto


# ══════════════════════════════════════════════════════════════
# Layer 0 — 标准量子门
# 参考：IBM {RZ, SX, X, CX}、Google {RZ, fSim}、
#        IonQ {GPi, GPi2, MS}、OpenQASM qelib1.inc
# ══════════════════════════════════════════════════════════════

class GateType(Enum):
    """标准量子门集（Clifford + T + 旋转族）。

    单比特 Pauli / Clifford
    -----------------------
    X       Pauli-X，比特翻转，RX(π)
    Y       Pauli-Y，比特+相位翻转，RY(π)
    Z       Pauli-Z，相位翻转，RZ(π)
    H       Hadamard，叠加门，创建 |+⟩ / |−⟩
    S       相位门，RZ(π/2)，S² = Z
    T       π/4 相位门，RZ(π/4)，T² = S（最贵的门，纠错代价高）
    SDG     S† 逆门，RZ(−π/2)
    TDG     T† 逆门，RZ(−π/4)
    SX      √X 门，RX(π/2)，IBM 原生门之一

    单比特旋转（参数化）
    --------------------
    RX      绕 X 轴旋转 θ rad，RX(θ) = exp(−iθX/2)
    RY      绕 Y 轴旋转 θ rad，RY(θ) = exp(−iθY/2)
    RZ      绕 Z 轴旋转 θ rad，RZ(θ) = exp(−iθZ/2)
            IBM 虚拟门：零时间，只调整后续脉冲相位
    P       全局相位门，P(λ) = diag(1, e^iλ)，等价于 U1(λ)
    U       通用单比特门，U(θ,φ,λ)，三参数覆盖 SU(2) 全空间

    双比特 Clifford
    ---------------
    CX      CNOT，|ctrl=1⟩ 时翻转 tgt
    CY      Controlled-Y
    CZ      Controlled-Z，|11⟩ 上翻转相位；QCU 原生双比特操作
    SWAP    交换两 qubit 态，3×CX 分解
    ISWAP   带 i 相位的 SWAP，Google 原生门族
    ECR     Echoed Cross-Resonance，IBM 新一代双比特原生门

    多比特
    ------
    CCX     Toffoli，三比特受控-X，量子与门
    CSWAP   Fredkin，三比特受控-SWAP
    MCX     多控制-X（n 控制比特）

    测量 / 初始化
    -------------
    MEAS    测量并写入经典比特，触发波函数坍缩
    RESET   将 qubit 强制复位到 |0⟩
    ID      恒等门（空闲，保持 qubit 不变，持续 t 时间）
    BARRIER 同步屏障，阻止编译器跨越此点重排门
    """

    # 单比特 Pauli / Clifford
    X    = auto()
    Y    = auto()
    Z    = auto()
    H    = auto()
    S    = auto()
    T    = auto()
    SDG  = auto()
    TDG  = auto()
    SX   = auto()

    # 单比特旋转
    RX   = auto()
    RY   = auto()
    RZ   = auto()
    P    = auto()
    U    = auto()

    # 双比特
    CX   = auto()
    CY   = auto()
    CZ   = auto()
    SWAP = auto()
    ISWAP = auto()
    ECR  = auto()

    # 多比特
    CCX  = auto()
    CSWAP = auto()
    MCX  = auto()

    # 测量 / 初始化
    MEAS  = auto()
    RESET = auto()
    ID    = auto()
    BARRIER = auto()


# 各门所需参数数量
GATE_PARAM_COUNT: dict[GateType, int] = {
    GateType.X: 0, GateType.Y: 0, GateType.Z: 0,
    GateType.H: 0, GateType.S: 0, GateType.T: 0,
    GateType.SDG: 0, GateType.TDG: 0, GateType.SX: 0,
    GateType.RX: 1, GateType.RY: 1, GateType.RZ: 1,
    GateType.P: 1,
    GateType.U: 3,
    GateType.CX: 0, GateType.CY: 0, GateType.CZ: 0,
    GateType.SWAP: 0, GateType.ISWAP: 0, GateType.ECR: 0,
    GateType.CCX: 0, GateType.CSWAP: 0, GateType.MCX: 0,
    GateType.MEAS: 0, GateType.RESET: 0,
    GateType.ID: 0, GateType.BARRIER: 0,
}

# 各门所需 qubit 数量（-1 = 可变）
GATE_QUBIT_COUNT: dict[GateType, int] = {
    GateType.X: 1, GateType.Y: 1, GateType.Z: 1,
    GateType.H: 1, GateType.S: 1, GateType.T: 1,
    GateType.SDG: 1, GateType.TDG: 1, GateType.SX: 1,
    GateType.RX: 1, GateType.RY: 1, GateType.RZ: 1,
    GateType.P: 1, GateType.U: 1,
    GateType.CX: 2, GateType.CY: 2, GateType.CZ: 2,
    GateType.SWAP: 2, GateType.ISWAP: 2, GateType.ECR: 2,
    GateType.CCX: 3, GateType.CSWAP: 3, GateType.MCX: -1,
    GateType.MEAS: 1, GateType.RESET: 1,
    GateType.ID: 1, GateType.BARRIER: -1,
}

# IBM 基础门集（编译目标）
IBM_BASIS = frozenset({GateType.RZ, GateType.SX, GateType.X, GateType.CX})

# Clifford 门集（纠错码友好，不含 T）
CLIFFORD_GATES = frozenset({
    GateType.X, GateType.Y, GateType.Z, GateType.H,
    GateType.S, GateType.SDG, GateType.SX,
    GateType.CX, GateType.CY, GateType.CZ, GateType.SWAP,
})

# 标准通用完备集（Clifford + T）
UNIVERSAL_BASIS = CLIFFORD_GATES | {GateType.T, GateType.TDG}


# ══════════════════════════════════════════════════════════════
# Layer 1 — QCU 相位指令（Phase Instructions）
# QCU 特有，直接操作腔 mode 相位和驱动参数
# ══════════════════════════════════════════════════════════════

class PhaseOp(Enum):
    """QCU 相位指令集。

    直接操作腔 mode 的相位、驱动幅度、色散耦合，
    是 QCU Hamiltonian 参数的显式接口。

    相位操作
    --------
    PHASE_SHIFT(mode, θ)
        对 mode k 的驱动相位偏移 θ rad。
        物理对应：调整 ε_k 的辐角，H += i(ε e^iθ a† − h.c.)

    PHASE_TRIM(mode0, mode1, δ)
        两腔相位差修正 δ rad：mode0 加 +δ/2，mode1 加 −δ/2。
        物理对应：boost_phase_trim，用于精细调整相位锁定点。

    PHASE_LOCK(mode0, mode1)
        注入同步耗散，驱动两腔振幅差 C(t) 趋近 0。
        物理对应：gamma_sync 跳跃算符，Lindblad 耗散项。

    驱动控制
    --------
    DRIVE_SET(mode, ε)
        设置 mode k 的驱动幅度为 ε（复数）。
        物理对应：eps_drive[k]。

    DRIVE_BOOST(mode, factor)
        将 mode k 的驱动幅度放大 factor 倍。
        物理对应：eps_boost × eps_drive[k]。

    色散耦合
    --------
    DISPERSIVE_WAIT(qubit, mode, t)
        在当前 Hamiltonian 下让 qubit-mode 色散耦合积累相位 t 时间。
        物理对应：χ σ_z n 项自然演化，qubit 状态调制腔相位。
        效果：当 qubit=|0⟩ 与 qubit=|1⟩ 时腔相位演化速率不同。

    自由演化
    --------
    FREE_EVOLVE(t)
        在当前 Hamiltonian 和 collapse cache 下自由演化 t 时间。
        物理对应：rk4_step × (t/dt) 步。
    """

    PHASE_SHIFT      = auto()   # (mode, θ)
    PHASE_TRIM       = auto()   # (mode0, mode1, δ)
    PHASE_LOCK       = auto()   # (mode0, mode1, γ_sync)
    DRIVE_SET        = auto()   # (mode, ε_complex)
    DRIVE_BOOST      = auto()   # (mode, factor)
    DISPERSIVE_WAIT  = auto()   # (qubit, mode, t)
    FREE_EVOLVE      = auto()   # (t)


# 相位指令参数说明（参数名列表）
PHASE_OP_PARAMS: dict[PhaseOp, list[str]] = {
    PhaseOp.PHASE_SHIFT:     ["mode", "theta"],
    PhaseOp.PHASE_TRIM:      ["mode0", "mode1", "delta"],
    PhaseOp.PHASE_LOCK:      ["mode0", "mode1", "gamma_sync"],
    PhaseOp.DRIVE_SET:       ["mode", "epsilon"],
    PhaseOp.DRIVE_BOOST:     ["mode", "factor"],
    PhaseOp.DISPERSIVE_WAIT: ["qubit", "mode", "duration"],
    PhaseOp.FREE_EVOLVE:     ["duration"],
}


# ══════════════════════════════════════════════════════════════
# Layer 2 — QCU 涌现指令（Emergence Instructions）
# QCU 特有，触发高层涌现计算行为
# 答案不是逐步算出的，而是让系统演化到锁定态后坍缩读出
# ══════════════════════════════════════════════════════════════

class EmergeOp(Enum):
    """QCU 涌现指令集。

    这是 QCU 最独特的层。传统量子计算逐门执行，
    而涌现指令让系统在 Hamiltonian 驱动下自然收敛，
    答案从相位动力学中涌现。类比相干 Ising 机（CIM）。

    QCL 协议阶段
    ------------
    QCL_PCM(γ_pcm, t)
        运行 PCM（Phase-Coherent Mode）阶段 t 时间。
        作用：基础相位维护，保持腔 mode 相位稳定。
        参数：γ_pcm — mode 间同步耗散率。

    QCL_QIM(ω_x, γ_qim, t)
        运行 QIM（Quantum Interference Mode）阶段 t 时间。
        作用：注入 σ_x 驱动使 qubit 0 进入叠加，
              通过色散耦合在两腔间引入量子干涉。
        参数：ω_x — σ_x 驱动幅度，γ_qim — 同步耗散率。

    QCL_BOOST(ε_boost, γ_boost, trim, t)
        运行 BOOST 阶段 t 时间。
        作用：强化驱动 + 相位修正，快速锁定两腔相位差。
        参数：ε_boost — 驱动增强倍数，γ_boost — 同步耗散率，
              trim — 相位修正量（rad）。

    QCL_RUN(params)
        运行完整 QCL v6 四阶段协议（PCM→QIM→BOOST→PCM）。
        这是 IQPU.run_qcl_v6() 的直接映射。

    坍缩与读出
    ----------
    PHASE_LOCK_WAIT(C_threshold)
        阻塞等待，直到 C(t) = |⟨a_0⟩ − ⟨a_1⟩| < C_threshold。
        即等待两腔相位自然锁定后再继续执行。
        这是涌现计算的核心：不主动算，等系统收敛。

    COLLAPSE_SCAN(candidates, threshold)
        用当前锁定态的相位分布对候选集做坍缩筛选。
        高概率候选通过，低概率候选被剪枝。
        这是 hash 坍缩加速的直接接口。

    SYNC_EMERGE()
        运行完整相位同步协议，等待涌现，读出最终相位态。
        自动选择参数：PCM → QIM → BOOST → 等待锁定 → 读出。
        一条指令完成从初态到结果的全过程。

    PHASE_ANNEAL(schedule)
        相位退火：按 schedule 逐步降低温度参数（γ_sync、ε_drive），
        让系统从高激发态缓慢退到最低能量相位构型。
        类比量子退火（Quantum Annealing），
        但在相位空间而非 Ising 空间进行。
    """

    QCL_PCM          = auto()   # (gamma_pcm, duration)
    QCL_QIM          = auto()   # (omega_x, gamma_qim, duration)
    QCL_BOOST        = auto()   # (eps_boost, gamma_boost, trim, duration)
    QCL_RUN          = auto()   # (full params dict)

    PHASE_LOCK_WAIT  = auto()   # (C_threshold)
    COLLAPSE_SCAN    = auto()   # (candidates, C_threshold)
    SYNC_EMERGE      = auto()   # ()
    PHASE_ANNEAL     = auto()   # (schedule: list of (gamma, eps, t))


# 涌现指令参数说明
EMERGE_OP_PARAMS: dict[EmergeOp, list[str]] = {
    EmergeOp.QCL_PCM:         ["gamma_pcm", "duration"],
    EmergeOp.QCL_QIM:         ["omega_x", "gamma_qim", "duration"],
    EmergeOp.QCL_BOOST:       ["eps_boost", "gamma_boost", "trim", "duration"],
    EmergeOp.QCL_RUN:         ["params"],
    EmergeOp.PHASE_LOCK_WAIT: ["C_threshold"],
    EmergeOp.COLLAPSE_SCAN:   ["candidates", "C_threshold"],
    EmergeOp.SYNC_EMERGE:     [],
    EmergeOp.PHASE_ANNEAL:    ["schedule"],
}


# ══════════════════════════════════════════════════════════════
# ISA 层级映射
# ══════════════════════════════════════════════════════════════

# 标准门 → 对应的 QCU 相位指令（一对一可直接映射的）
GATE_TO_PHASE_MAP: dict[GateType, PhaseOp] = {
    GateType.RZ:   PhaseOp.PHASE_SHIFT,      # RZ(θ) → PHASE_SHIFT(mode, θ)
    GateType.RX:   PhaseOp.FREE_EVOLVE,      # RX(θ) → QIM 阶段 omega_x=θ（近似）
    GateType.CZ:   PhaseOp.DISPERSIVE_WAIT,  # CZ → 色散耦合积累相位
    GateType.X:    PhaseOp.FREE_EVOLVE,      # X → gamma_reset 脉冲
}

# 涌现指令 → 调用的 IQPU 方法
EMERGE_TO_IQPU: dict[EmergeOp, str] = {
    EmergeOp.QCL_PCM:         "_make_cache + rk4_step (PCM phase)",
    EmergeOp.QCL_QIM:         "_make_cache + rk4_step (QIM phase)",
    EmergeOp.QCL_BOOST:       "build_H_boost_trim + rk4_step",
    EmergeOp.QCL_RUN:         "IQPU.run_qcl_v6()",
    EmergeOp.PHASE_LOCK_WAIT: "run_qcl_v6 + poll C(t)",
    EmergeOp.COLLAPSE_SCAN:   "run_qcl_v6 + QCSHMChipRuntime",
    EmergeOp.SYNC_EMERGE:     "IQPU.run_qcl_v6() auto-params",
    EmergeOp.PHASE_ANNEAL:    "sequential rk4_step with schedule",
}
