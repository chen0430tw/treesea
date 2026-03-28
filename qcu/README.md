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

- `qcu/core/`：核心求解模块
- `qcu/io/`：状态与结果 I/O
- `qcu/runtime/`：运行时
- `qcu/cli/`：命令入口
- `qcu/distributed/`：分布式执行
- `qcu/workloads/`：任务类型，如 factorization / hash_search / collapse_scan
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

## 当前迁移状态

当前原型保存在：

- `../legacy/imported_single_file_prototypes/qcu_reconstructed.py`
- `../legacy/imported_single_file_prototypes/qcu_full_reconstructed.py`

后续将逐步拆分到 `core/`、`runtime/`、`io/`。
