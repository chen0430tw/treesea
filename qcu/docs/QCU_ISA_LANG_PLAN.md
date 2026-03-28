# QCU-ISA 与 qcu-lang 规划文档

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
外部量子语言（Q# / QASM / Qiskit）
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

### 提议的基础门集

| 门 | 符号 | 参数 | QCU 物理对应 |
|----|------|------|-------------|
| 相位旋转 | `RZ(θ)` | θ ∈ ℝ | `boost_phase_trim = θ`，直接相位偏移 |
| X 轴旋转 | `RX(θ)` | θ ∈ ℝ | QIM 阶段 `omega_x = θ`，σ_x 驱动 |
| 比特翻转 | `X` | — | `gamma_reset` 强制 qubit 复位 |
| 条件相位 | `CZ` | — | 色散耦合 χ 介导的条件相位积累 |
| 测量 | `MEAS` | — | collapse_scan 读出，触发坍缩 |
| 恒等 | `ID(t)` | t（时长）| 自由演化 t 时间，相位自然漂移 |

### 完备性

`{ RZ, RX, CZ, X, MEAS, ID }` 构成通用量子计算完备集：
- 任意单 qubit 操作可由 RZ + RX 分解
- 任意双 qubit 纠缠可由 CZ + 单 qubit 门实现
- 测量 + 条件操作覆盖经典控制流

### ISA 文件格式（草案）

```
QCU-ISA 1.0
# 单 qubit 操作
RZ   qubit:int  theta:float   # 相位旋转 θ rad
RX   qubit:int  theta:float   # X 轴旋转 θ rad
X    qubit:int                # 比特翻转（π 旋转）
ID   qubit:int  duration:float # 自由演化

# 双 qubit 操作
CZ   ctrl:int   tgt:int       # 条件 Z 相位

# 测量
MEAS qubit:int  clbit:int     # 测量并写入经典比特
```

---

## 第二层：qcu-lang（语言桥接库）

### 定位

独立子库，类比 CUDA 编译器：
- 接收量子编程语言写的电路
- 输出 QCU-ISA 指令序列
- 再由 ISA 执行层映射到 IQPU 参数

### 库结构

```
qcu_lang/
├── ir/
│   ├── circuit.py        # 通用量子电路 IR（QCircuit / QGate）
│   └── ops.py            # 标准门枚举（对应 QCU-ISA）
├── frontend/
│   ├── qasm.py           # OpenQASM 2.0/3.0 → IR
│   └── qiskit_frontend.py # Qiskit QuantumCircuit → IR
├── compiler/
│   ├── decompose.py      # 高级门 → QCU-ISA 基础门分解
│   └── phase_map.py      # QCU-ISA 门 → Hamiltonian 参数
└── backend/
    └── qcu_executor.py   # 生成 QCLProgram 交给 IQPU 执行
```

### 依赖

```bash
pip install openqasm3[parser]   # QASM 解析（必须）
pip install qiskit               # 可选，有 Qiskit 才装
```

### 支持的前端语言

| 语言 | 格式 | 优先级 | 备注 |
|------|------|--------|------|
| OpenQASM 3.0 | 文本 | ★★★ 最先实现 | 通用格式，覆盖所有框架 |
| Qiskit | Python 对象 | ★★★ 同步 | `circuit.data` 结构简单 |
| Q# | .qs 文件 | ★★ 第二阶段 | 通过 `qsharp` Python 包互操作 |
| Cirq | Python 对象 | ★ 可选 | 通过 QASM 中转 |

---

## 第三层：门→相位映射（编译器核心）

### 映射表

| QCU-ISA 门 | IQPU 参数 | 说明 |
|-----------|----------|------|
| `RZ(θ)` | `boost_phase_trim = θ` | BOOST 阶段注入相位差 |
| `RX(θ)` | QIM 阶段 `omega_x = θ` | σ_x 驱动旋转 qubit 0 |
| `X` | `gamma_reset` 单步脉冲 | 强制 qubit 复位再翻转 |
| `CZ` | `chi[j,k]` 色散耦合时长 | 让 qubit 和腔自然积累条件相位 |
| `MEAS` | `compute_final_observables()` | 读出并坍缩 |
| `ID(t)` | 自由演化 t 步 | 不切换 Hamiltonian，纯漂移 |

---

## 实施顺序

```
Phase 1 — ISA 定义（本文档）
  ✅ 定义 QCU-ISA 基础门集
  ✅ 确认物理映射关系

Phase 2 — IR 与编译器骨架
  [ ] qcu_lang/ir/circuit.py     QCircuit / QGate 数据结构
  [ ] qcu_lang/ir/ops.py         门枚举
  [ ] qcu_lang/compiler/decompose.py  门分解规则

Phase 3 — 前端解析
  [ ] qcu_lang/frontend/qasm.py       OpenQASM 3.0 解析
  [ ] qcu_lang/frontend/qiskit_frontend.py  Qiskit 前端

Phase 4 — 后端执行
  [ ] qcu_lang/compiler/phase_map.py  门→Hamiltonian 参数
  [ ] qcu_lang/backend/qcu_executor.py 接入 IQPU

Phase 5 — Q# 前端（可选）
  [ ] 通过 qsharp Python 包互操作
```

---

## 与现有架构的关系

```
现有层                    新增层
─────────────────────────────────────────────────────
qcu_kdrv.sys              （不变，硬件抽象层）
    ↕
IQPU / QCL v6             （不变，物理演化引擎）
    ↑
QCU-ISA 执行层            ← 新增：ISA → Hamiltonian 参数映射
    ↑
qcu-lang 编译器           ← 新增：量子语言 → QCU-ISA
    ↑
Q# / QASM / Qiskit        （外部量子编程语言）
```

QCU-ISA 是 IQPU 的「汇编语言」，qcu-lang 是「高级语言编译器」。
外部语言不感知 Lindblad 方程，只感知门操作。
