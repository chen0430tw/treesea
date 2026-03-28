# QCU

QCU 是海端系统，负责高维候选并存、相位调制、局部坍缩、读出与回写，是虚拟量子芯片方向的独立运行系统。

## 一句话定义

QCU 是一个可独立运行的海端求解系统，用于在高维候选空间中执行相位式筛选、局部显形与读出。

## 系统定位

QCU 在系统架构层面相当于一块**QPU 协处理器**，与 NPU 的定位类似：

```
CPU   通用计算
GPU   并行浮点
NPU   神经网络推理
QCU   相位式候选筛选 / 坍缩计算
```

`qcu_kdrv.sys` 是驱动层，Python bridge 是运行时，workloads 是应用层。上层不需要知道内部如何演化，只管提交任务、读取坍缩结果。区别在于：NPU 是真实硅片，QCU 的「硅片」是 Lindblad 方程在 GPU 上的数值解。

---

## 计算范式

QCU 不是传统的量子门计算机。

传统量子计算（IBM、Google）的路线是：用叠加态同时表示所有答案，再用量子门操作振幅，最后测量概率最高的结果。这条路代价极高——需要纠错、维持相干、接近绝对零度的硬件。

QCU 的路线是**相位动力学计算**：信息编码在腔 mode 的相位关系里，计算过程是相位系统在 Hamiltonian 驱动下自然演化到锁定态，答案从物理动力学中涌现，不是被枚举出来的。

### 核心物理量

```
C(t) = |⟨a_0⟩ − ⟨a_1⟩|              # 两腔振幅差，→0 表示相位同步
dtheta = |arg⟨a_0⟩ − arg⟨a_1⟩|      # 两腔相位差
χ_{j,k} σ_z,j n_k                    # 色散耦合：qubit 状态调制腔相位演化
```

qubit 通过色散耦合改变腔的相位演化速度，QCL v6 四阶段协议（PCM → QIM → BOOST → PCM）将系统驱动到目标相位锁定态。这与相干 Ising 机（CIM，日本 NTT）的计算原理同源。

### 为什么保留量子门接口

QCU 内部是连续相位系统，但对外暴露标准量子门接口（QIR/HMPL）。原因是务实的：现有量子计算生态（Qiskit、Cirq、OpenQASM）全部建立在量子门语言上。如果用纯相位语言对外，等于要重新发明编译器、IR 和工具链。

解决方案是在边界做桥接转换：

```
外部（量子门语言）
      ↓ 桥接层
  相位操作
      ↓
QCL 协议 / 腔模演化
      ↓
  涌现结果
```

外部看到的是标准接口，内部跑的是相位动力学。接口和实现分离，不影响与现有工具链的兼容。

### 对 Hash 搜索的加速方式

QCU 加速 hash 搜索不是「更快算一个 hash」，而是**通过坍缩减少需要算的 hash 总数**：

```
全候选空间 N 个
    ↓ QCU 相位协议运行
    ↓ 坍缩 → 高概率区域浮现
缩减后的候选集 M 个（M << N）
    ↓
经典枚举只需验证 M 个
```

这类似于侦探用物证圈出最可能的嫌疑人，再逐个确认——不是更快审问，而是需要审问的人更少了。

## 系统职责

- 状态表示与初始化
- 相位调制
- 候选态重排
- 局部坍缩
- 读出与结果记录
- 参数扫描与批量求解
- solver trace / entanglement metrics 输出

## 输入

典型输入包括：

- state config
- phase / collapse parameters
- workload definition
- scan ranges
- solver setup

配置文件通常位于：

- `configs/qcu_default.yaml`
- `configs/qcu_local_debug.yaml`
- `configs/qcu_cluster.yaml`

## 输出

典型输出包括：

- collapse result
- readout record
- solver trace
- phase scan summary
- entanglement / negativity / runtime metrics

默认输出路径：

- `runs/qcu/`
- `logs/qcu/`
- `checkpoints/qcu/`
- `results/qcu/`

## 目录说明

- `qcu/core/`：核心求解模块（Lindblad RK4、相位调制、读出、纠缠度量）
- `qcu/io/`：状态与结果 I/O
- `qcu/runtime/`：运行时
- `qcu/cli/`：命令入口
- `qcu/distributed/`：分布式执行
- `qcu/workloads/`：任务类型，如 factorization / hash_search / collapse_scan
- `qcu_lang/`：量子语言桥接库（三层 ISA、编译器、QASM/Qiskit/Q# 前端）
- `jobs/`：作业定义
- `slurm/`：Slurm 模板
- `mpi/`：MPI 启动脚本

## 本地运行

```bash
python -m qcu.cli.run_local --config configs/qcu_local_debug.yaml
```

## 集群提交

```bash
python -m qcu.cli.submit --config configs/qcu_cluster.yaml
```

或直接：

```bash
sbatch slurm/qcu_single.sbatch
sbatch slurm/qcu_multi_node.sbatch
```

## MPI 启动

```bash
bash mpi/mpirun_qcu.sh
```

## GPU 加速

QCU 核心求解层（Lindblad RK4）原生支持 CPU / CUDA 双后端，通过 `IQPUConfig.device` 切换。

### 环境要求

- CUDA Toolkit 13.1（`C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.1`）
- `pip install cupy-cuda13x`（对应 CUDA 13.x；勿安装 cupy-cuda12x）

### 实测性能（RTX 3070，单 rk4_step，Nq=2 Nm=2）

| Fock 截断 d | 希尔伯特空间 DIM | CPU ms/步 | GPU ms/步 | 加速比 |
|:-----------:|:---------------:|:---------:|:---------:|:------:|
| 6           | 144             | 23.4      | 23.0      | 1.0x   |
| 8           | 256             | 116.4     | 76.6      | 1.5x   |
| 12          | 576             | 1148      | 649       | 1.8x   |
| 16          | 1024            | 6818.7    | 3834.9    | 1.8x   |

### 为什么 d=6 时 GPU 没有优势

DIM=144 的矩阵太小，单次 matmul 仅需数微秒，但 CUDA kernel launch 本身有 10–50 μs 开销。整个 rk4_step 涉及约 16 次 kernel 调用，launch 开销与计算时间相当，GPU 利用率极低。

**建议**：生产环境使用 `d ≥ 12`（DIM ≥ 576），或通过批量参数扫描让单次 kernel 处理多个初态，以分摊 launch 开销。

---

## 与遠藤理平《14日で作る量子コンピュータ》的对比

遠藤理平（東北大学理学研究科，FIELD AND NETWORK 株式会社 CEO）在其 2020 年著作中用 Python 实现了量子仿真器。两者的本质区别：

### 物理模型

| 维度 | 遠藤理平（书中实现） | QCU |
|------|-------------------|-----|
| **演化方程** | 薛定谔方程 iℏ d\|ψ⟩/dt = H\|ψ⟩ | Lindblad 主方程 dρ/dt = −i[H,ρ] + 耗散项 |
| **量子态** | 状态向量（纯态） | 密度矩阵（混态） |
| **噪声/退相干** | 无，理想封闭系统 | 有：腔泄漏率 κ、qubit 弛豫 T₁、纯退相干 T_φ |
| **系统类型** | 封闭量子系统 | 开放量子系统 |
| **硬件接口** | 纯 Python 脚本 | Windows 内核驱动（qcu_kdrv.sys via ObReferenceObjectByName） |
| **GPU 加速** | 无 | cupy-cuda13x |
| **适用场景** | 教学、理解量子门原理 | 仿真真实量子芯片噪声行为 |

### 更深的区别

遠藤理平的系统里，量子力学是**被模拟的对象**——代码在演示量子力学是什么。QCU 里，量子力学是**计算的基础设施**——相位锁定和坍缩筛选不是在演示量子力学，是在用量子力学干活。

一个是博物馆里的展品，一个是工厂里的机器。

---

## qcu_lang — 量子语言桥接库

`qcu_lang` 是 QCU 的编程接口层，让标准量子程序（QASM、Qiskit）能直接在 QCU 上运行，无需了解内部相位动力学。

### 三层指令集架构

```
Layer 0   标准量子门       H X CX CCX …        （Clifford+T 通用门集）
              ↓ 门分解 + 相位映射
Layer 1   QCU 相位指令    PHASE_TRIM DRIVE_BOOST …   （直接对应物理旋钮）
              ↓
Layer 2   QCU 涌现指令    QCL_BOOST SYNC_EMERGE …    （整协议级操作）
              ↓
       IQPU 执行引擎（Lindblad RK4）
```

外部看到标准量子门接口，内部映射到相位动力学参数。桥接转换在编译器层完成，不影响与现有量子工具链的兼容。

### 快速上手

```python
from qcu_lang import QCircuit, QCUExecutor, from_qasm_str, optimize, compile_circuit

# 方式一：手写电路
circ = QCircuit(n_qubits=2)
circ.h(0).cx(0, 1)
result = QCUExecutor(verbose=False).run(circ)
print(f"C_end={result.final_C:.4f}  dtheta={result.final_dtheta:.6f}")

# 方式二：从 QASM 导入
circ = from_qasm_str("""
OPENQASM 2.0; include "qelib1.inc";
qreg q[2]; h q[0]; cx q[0],q[1];
""")
steps = optimize(compile_circuit(circ))   # 编译 + 优化
result = QCUExecutor(verbose=False).run(circ)

# 方式三：三层混合（标准门 + 相位微调 + 涌现协议）
circ = QCircuit(n_qubits=2, n_clbits=2, name="mixed")
circ.h(0).rz(0.785, 0).cx(0, 1)       # Layer 0
circ.phase_trim(0, 1, 0.012)           # Layer 1
circ.qcl_boost(4.0, 0.9, 0.012, 2.0)  # Layer 2
circ.measure(0, 0).measure(1, 1)
```

### 支持的前端语言

| 前端 | 函数 | 说明 |
|------|------|------|
| QASM 2.0 / 3.0 | `from_qasm_str()` / `from_qasm_file()` | 业界标准，Qiskit 默认格式 |
| Q# | `from_qsharp_str()` / `from_qsharp_file()` | Microsoft 量子语言 |
| Qiskit | `from_qiskit()` | 直接转换 QuantumCircuit 对象 |
| Cirq | `from_cirq()` / `to_cirq()` | Google Cirq，支持双向转换 |

Q# 示例（Toffoli 门，3 qubit）：

```qsharp
namespace Toffoli {
    open Microsoft.Quantum.Intrinsic;
    operation Main() : Unit {
        use (c0, c1, t) = (Qubit(), Qubit(), Qubit());
        X(c0); X(c1);
        CCNOT(c0, c1, t);   // 自动分解为 Clifford+T 序列
        let r0 = M(c0); let r1 = M(c1); let r2 = M(t);
    }
}
```

```python
from qcu_lang import from_qsharp_str, QCUExecutor
circ   = from_qsharp_str(qs_source)   # n_qubits=3 自动识别
result = QCUExecutor(verbose=False).run(circ)
```

### 局部相位执行模型：量子的"二进制化"

传统量子仿真器模拟 N-qubit 系统时，希尔伯特空间维度随 qubit 数**指数增长**：

```
dim(ℋ_N) = 2^Nq × d^Nm

Nq=2, d=6  →  DIM =  2² × 6² =   144   ← 23 ms/step
Nq=3, d=6  →  DIM =  2³ × 6³ = 1,728   ← 约慢 144 倍
Nq=4, d=6  →  DIM =  2⁴ × 6⁴ = 20,736  ← 约慢 20,736 倍
```

QCU 的执行层不这样做。

#### 进制化分解

这里有一个与**数字进制转换**对应的数学结构。

任意整数 N 都可以分解为二进制位序列：

```
N = bₖ·2ᵏ + bₖ₋₁·2ᵏ⁻¹ + … + b₁·2 + b₀
```

信息总量不变，只是把「一个 N 进制位」换成了「k 个 2 进制位的序列」。

量子门的分解遵循完全相同的逻辑：

```
任意 N-qubit 酉变换 U ∈ U(2^N)
  = u_M ∘ u_{M-1} ∘ … ∘ u_1
  其中每个 uᵢ ∈ U(4)（至多 2-qubit 酉变换）
```

"2 进制位" 对应 "2-body 相互作用"。这个分解存在且精确——不是近似，信息量不损失（这是量子门的普遍逼近定理的推论）。

#### 在 QCU 中的实现

QCU 的计算基本单元是**腔 mode 之间的相位关系**，而不是全局量子态向量。相位差 `C(t) = |⟨a₀⟩ − ⟨a₁⟩|` 天然是 2-body 量——它只需要两个 mode 就能定义。

因此编译器将所有 N-qubit 门分解为局部 2-body PhaseStep，每步在 `dim(ℋ_2) = 2² × d²` 上求解：

```
执行代价：O(M × dim(ℋ_2)²)   而非   O(M × dim(ℋ_N)²)

加速比 = (dim(ℋ_N) / dim(ℋ_2))²
       = (2^(Nq-2) × d^(Nm-2))²

Nq=3, d=6：加速比 = (2¹ × 6¹)² = 144 倍
Nq=4, d=6：加速比 = (2² × 6²)² = 20,736 倍
```

全局 N-qubit 结构由**步骤序列**携带，而不是由仿真维度承载——这正如整数的值由二进制位序列表达，而不是靠"一个超大进制的单个数字"来表达。

```
3-qubit Toffoli                执行时间
─────────────────────────────────────────────────
传统仿真（DIM=1,728，全局）   ≈ 数小时
QCU 局部相位执行（DIM=144）   ≈ 数十秒（与 2-qubit 相当）
```

Layer 2 涌现指令（`SYNC_EMERGE`、`QCL_RUN`）是协议级操作，需要全局 qubit 上下文，此时才使用真实的 `dim(ℋ_N)`。

### 覆盖范围（全部通过测试）

| 层 | 指令 | 状态 |
|----|------|------|
| Layer 0 单量子比特 | X Y Z H S SDG T TDG SX RX RY RZ P U ID BARRIER RESET | ✅ |
| Layer 0 多量子比特 | CX CY CZ SWAP iSWAP ECR CCX CSWAP MCX MEAS | ✅ |
| Layer 0 判决指令 | PROJ_MEAS（投影测量）DISC(θ)（诱导判决） | ✅ |
| Layer 1 Phase 指令 | PHASE_SHIFT TRIM LOCK DRIVE_SET BOOST DISPERSIVE_WAIT FREE_EVOLVE | ✅ |
| Layer 2 Emerge 指令 | QCL_PCM QIM BOOST RUN SYNC_EMERGE PHASE_LOCK_WAIT PHASE_ANNEAL | ✅ |
| Q# 前端 | Bell / Toffoli / Fredkin / QFT / 旋转门 / Adjoint | ✅ |
| Cirq 前端 | Bell / Toffoli / 旋转门 / ZPow/XPow / to_cirq 双向 | ✅ |
| 噪声模型 | ideal / nisq / noisy / circuit-inferred 四档推导 | ✅ |

测试：`tests/test_isa_full.py` **65/65 PASS**（含 Cirq 5 项、噪声模型 7 项、PROJ_MEAS/DISC 5 项）；`tests/test_qsharp.py` **7/7 PASS**。

编译器优化 pass：合并相邻 `phase_shift`、相消清零、`noop` 剥离；CCX 原始 48 步 → 优化后 40 步。

#### PROJ_MEAS 与 DISC 判决指令

QCU 的物理输出是相位相干度 C，而不是经典比特。这两条指令负责把 C 值转换为量子算法可读的比特结果：

| 指令 | 作用 | IQPU 参数 |
|------|------|----------|
| `PROJ_MEAS` | 投影测量：高强度辨别协议，把 ⟨σz⟩ 推向 ±1 | eps_boost=8.0 |
| `DISC(θ)` | 诱导判决：C > θ → bit=0，C ≤ θ → bit=1 | 阈值 θ，默认 0.01 |

QASM 用法：

```qasm
proj_meas q[0] -> c[0];   // 投影测量
disc(0.05) q[0] -> c[0];  // 诱导判决，阈值 0.05
```

---

## 路线图

### 已完成
- `qcu/core/`：Lindblad RK4 求解器、相位调制、读出、纠缠度量
- `qcu_kdrv.sys`：Windows 内核驱动（ObReferenceObjectByName 方案）
- GPU 加速：cupy-cuda13x 双后端
- 工作负载：Shor 因式分解、哈希坍缩搜索、collapse_scan
- `qcu_lang`：三层 ISA + 编译器 + QASM / Qiskit / Q# / Cirq 前端 + 优化 pass
- 局部相位执行模型：N-qubit 电路在 DIM=144 下执行，无指数膨胀
- 噪声模型推导：`set_noise()` 注解 + 四档自动推导 IQPUConfig
- PROJ_MEAS / DISC 判决指令：C 值 → 经典比特的桥接层
- `qcu/gates/`：基础量子 benchmark 层（第一层 sanity check）
  - `deutsch.py`：QCU 原生 Deutsch 算法（100% 准确率，C 间隔 186.99）
    oracle 编码为 `boost_phase_trim`——架构设计时预留的腔相位注入接口，
    本阶段将其封装为正式 benchmark 管线

### 下一阶段

---

## 当前迁移状态

当前原型保存在：

- `../legacy/imported_single_file_prototypes/qcu_reconstructed.py`
- `../legacy/imported_single_file_prototypes/qcu_full_reconstructed.py`

后续将逐步拆分到 `core/`、`runtime/`、`io/`。
