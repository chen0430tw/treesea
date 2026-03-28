# QCU-ISA 与 qcu-lang 规划文档

> **状态：已全部完成** ✅（2026-03-28）
> 本文档保留原始规划内容以供参考，末尾附实际完成状态对照。

## 背景：为什么 QCU 需要指令集

GPU 是离散执行模型，有明确的指令集架构（ISA）：

```
PTX (虚拟 ISA) → SASS (硬件 ISA)
MAD.F32 R1, R2, R3
LD.GLOBAL R4, [addr]
```

QCU 是连续演化模型，计算即物理过程：

```
dρ/dt = -i[H,ρ] + Σ(cρc† - ½c†cρ - ½ρc†c)
```

QCL v6 的参数（gamma_pcm、eps_boost 等）是「物理旋钮」，不是指令。
类比：模拟合成器没有指令集，只有振荡器和包络参数。

**问题**：这导致外部量子编程语言（Q#、QASM、Qiskit）没有编译目标。
真实量子芯片（IBM）定义了基础门集 `{ CX, RZ, SX, X, ID }`，
所有量子电路编译到这五个门，每个门对应一段特定微波脉冲——这就是它的「指令集」。

**结论**：QCU 在实现语言桥接前，必须先定义自己的指令集（QCU-ISA）。

---

## 整体架构

```
外部量子语言（Q# / QASM / Qiskit / Cirq）
              ↓
        qcu-lang 编译器
              ↓
        QCU-ISA 基础门集
              ↓
      Hamiltonian 参数 / 相位操作
              ↓
         IQPU 执行引擎
              ↓
          坍缩读出结果
```

---

## 第一层：QCU-ISA（指令集架构）

### 设计原则

QCU 的计算核心是相位动力学，因此基础门集应当：
1. 覆盖相位旋转（单 qubit 旋转门）
2. 覆盖相位纠缠（双 qubit 条件操作，通过色散耦合 χ 实现）
3. 覆盖测量/坍缩（读出层）
4. 最小完备——不超过 6 个原子操作

### 基础门集（已实现）

| 门 | 符号 | 参数 | QCU 物理对应 |
|----|------|------|-------------|
| 相位旋转 | `RZ(θ)` | θ ∈ ℝ | `boost_phase_trim = θ`，直接相位偏移 |
| X 轴旋转 | `RX(θ)` | θ ∈ ℝ | QIM 阶段 `omega_x = θ`，σ_x 驱动 |
| 比特翻转 | `X` | — | `gamma_reset` 强制 qubit 复位 |
| 条件相位 | `CZ` | — | 色散耦合 χ 介导的条件相位积累 |
| 测量 | `MEAS` | — | collapse_scan 读出，触发坍缩 |
| 恒等 | `ID(t)` | t（时长）| 自由演化 t 时间，相位自然漂移 |

**实际实现的门集远超规划**，完整覆盖 Clifford+T 通用门集（27 个 GateType）+ 7 个 PhaseOp + 8 个 EmergeOp，详见 `qcu_lang/ir/ops.py`。

---

## 第二层：qcu-lang（语言桥接库）

### 已实现库结构

```
qcu_lang/
├── ir/
│   ├── circuit.py        # QCircuit / QGate IR，含 set_noise() 噪声标注
│   └── ops.py            # 三层 ISA：GateType / PhaseOp / EmergeOp
├── frontend/
│   ├── qasm.py           # OpenQASM 2.0/3.0 → IR  ✅
│   ├── qiskit_frontend.py # Qiskit QuantumCircuit → IR  ✅
│   ├── qsharp.py         # Q# → IR（轻量 regex 解析器）  ✅
│   └── cirq_frontend.py  # Cirq → IR  ✅
├── compiler/
│   ├── decompose.py      # 高级门 → 基础门（CCX/CSWAP/ISWAP/ECR）  ✅
│   ├── phase_map.py      # 门 → PhaseStep 映射  ✅
│   ├── optimizer.py      # 编译期优化（phase_merge / noop_strip）  ✅
│   └── noise_infer.py    # 噪声模型推导（preset / circuit-inferred）  ✅
├── backend/
│   └── qcu_executor.py   # PhaseStep → IQPU 执行，局部相位执行模型  ✅
└── __init__.py           # 公开 API 导出
```

---

## 第三层：门→相位映射（编译器核心）

### 映射表（已实现）

| QCU-ISA 门 | PhaseStep kind | IQPU 参数 |
|-----------|---------------|----------|
| `RZ(θ)` | `phase_shift` | `boost_phase_trim += θ`（累积后批量刷新） |
| `RX(θ)` | `qim_evolve` | QIM 阶段 `omega_x = θ` |
| `H` | 3步：`phase_shift + qim_evolve + phase_shift` | RZ(π/2)·RX(π/2)·RZ(π/2) 分解 |
| `CZ` | `dispersive` | 色散耦合自由演化 t = π/(2χ) |
| `CX` | 5步：H(tgt)·CZ·H(tgt) | — |
| `CCX` | 43步（15门×展开） | 标准 Clifford+T Toffoli 分解 |
| `MEAS` | `readout` | `compute_final_observables()` |
| `ID/BARRIER` | `noop` | 空操作，优化器自动剥离 |

---

## 局部相位执行模型（规划外新增）

规划文档未涵盖的重要设计：N-qubit 电路的维度爆炸问题。

任意 N-qubit 酉变换可分解为 2-body 操作序列（类似整数的二进制化）：

```
dim(ℋ_N) = 2^Nq × d^Nm   全局维度（指数爆炸）
dim(ℋ_2) = 2² × d²       局部 2-body 维度（固定）

加速比 = (dim(ℋ_N) / dim(ℋ_2))²
Nq=3, d=6：加速比 = 144 倍（数小时 → 数十秒）
```

executor 中 segment 级操作固定 Nq=2（DIM=144），emerge 级才使用真实 Nq。

---

## 噪声模型推导（规划外新增）

`circ.set_noise()` 标注 + `noise_infer.py` 自动推导 IQPUConfig：

| 档位 | T1 | Tphi | κ | 适用场景 |
|------|----|------|---|---------|
| `"ideal"` | 10⁶ μs | 10⁶ μs | 10⁻⁵ | 算法正确性验证 |
| `"nisq"` | 50 μs | 100 μs | 0.02 | 当前 NISQ 典型硬件 |
| `"noisy"` | 10 μs | 20 μs | 0.05 | 强噪声场景 |
| 电路推导 | T1/(1+n·0.05) | — | — | 无注解时自动校正 |

---

## 实施状态对照

```
Phase 1 — ISA 定义
  ✅ 定义 QCU-ISA 基础门集（扩展为完整 Clifford+T）
  ✅ 确认物理映射关系

Phase 2 — IR 与编译器骨架
  ✅ qcu_lang/ir/circuit.py     QCircuit / QGate
  ✅ qcu_lang/ir/ops.py         三层 ISA 枚举
  ✅ qcu_lang/compiler/decompose.py  门分解（CCX/CSWAP/ISWAP/ECR）
  ✅ qcu_lang/compiler/optimizer.py  编译期优化 pass
  ✅ qcu_lang/compiler/noise_infer.py 噪声模型推导

Phase 3 — 前端解析
  ✅ qcu_lang/frontend/qasm.py          OpenQASM 2.0/3.0
  ✅ qcu_lang/frontend/qiskit_frontend.py  Qiskit
  ✅ qcu_lang/frontend/qsharp.py        Q#
  ✅ qcu_lang/frontend/cirq_frontend.py Cirq

Phase 4 — 后端执行
  ✅ qcu_lang/compiler/phase_map.py     门 → PhaseStep
  ✅ qcu_lang/backend/qcu_executor.py   接入 IQPU，局部相位执行

Phase 5 — 测试
  ✅ tests/test_isa_full.py   60/60 PASS（含 Cirq 5 项 + 噪声模型 7 项）
  ✅ tests/test_qsharp.py      7/7  PASS
```
