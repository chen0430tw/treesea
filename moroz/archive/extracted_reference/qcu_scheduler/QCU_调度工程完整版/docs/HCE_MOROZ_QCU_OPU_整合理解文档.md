# HCE / MOROZ / QCU / OPU 整合理解文档

## 0. 文件目的

本文件用于把前面关于以下问题的讨论一次性整合：

- MOROZ 如何调度 QCU
- QCU 到底怎么调度
- OPU 在 QCU 里是什么定位
- 是否需要把 OPU 升级为全功能调度器
- QCU 是否需要虚拟主板 / bus / 虚拟内存
- 虚拟芯片是否需要指令集 / AVX
- QCU 并行或多核是否会更快
- 虚拟芯片的算力到底从何而来
- 虚拟芯片与虚拟机的区别

本文件目标是把这些概念从“零散聊天结论”收口成一个统一口径。

---

## 1. 总体结论

当前阶段最正确的系统关系是：

> **MOROZ 是前端压缩与总调度系统，QCU 是后端坍缩与显形设施，OPU 是 QCU 内部的治理核。**

三者关系不是谁吞掉谁，而是分层协作：

- **MOROZ** 决定哪些高价值候选簇值得进入 QCU
- **QCU 基础 scheduler** 决定这些簇进入后怎么排队、怎么执行
- **OPU** 决定运行过程中要不要 tighten / relax / gate / suppress，做资源、摩擦、质量三闭环治理

最短一句话：

> **MOROZ 决定让谁上场，QCU scheduler 决定怎么排队，OPU 决定打到一半要不要变阵。**

---

## 2. MOROZ 的定位

MOROZ 不是单一破解器，而是：

> **面向弱口令、模板口令与强先验候选空间的分层式密码恢复研究框架。**

它的核心思想不是对原始大空间做盲目硬扫，而是把问题拆成两段：

### 前端
- 候选建模
- 模板限域
- 搜索压缩
- 优先级排序
- frontier 压缩
- 质量观测

### 后端
- 对已经压缩过的高价值工作区做快速显影和局部坍缩

因此可以直接定成：

- **MOROZ 是总系统**
- **QCU 是核心武器**

也就是：

> **MOROZ 负责把搜索空间压窄；QCU 负责把高价值候选快速显影。**

---

## 3. MOROZ 如何调度 QCU

MOROZ 不应该把 QCU 硬封装进去，也不应该直接 import QCU 各种内部对象。

正确关系应为：

> **MOROZ 调度 QCU，而不是吞掉 QCU。**

### 正确流程

```text
MSCM
  ↓
K-Warehouse
  ↓
ISSC
  ↓
MOROZ Collapse Dispatcher
  ↓
QCU Backend
  ↓
CollapseResultBundle
  ↓
MOROZ Aggregator
```

### MOROZ 负责
- 候选建模
- 模板限域
- frontier 压缩
- 生成高价值 cluster
- 决定是否调用 QCU
- 决定给多少 budget
- 决定本地跑还是上 Slurm
- 决定 profile

### QCU 负责
- 真正做相位化显影
- 局部坍缩
- 读出
- 输出结果

### 推荐实现
MOROZ 内部应该有一个 **坍缩后端接口层**，例如：

```text
moroz/
├─ frontends/
│  ├─ mscm/
│  ├─ kwarehouse/
│  └─ issc/
├─ collapse/
│  ├─ backend_interface.py
│  ├─ dispatcher.py
│  ├─ qcu_adapter.py
│  └─ schemas.py
└─ runtime/
```

最关键的不是把 QCU 拷进 MOROZ，而是：

> **让 MOROZ 通过一个后端接口去调用 QCU 这个独立显影设施。**

---

## 4. QCU 的定位

QCU 不是普通函数堆，也不是一开始就要做成完整硬件模拟器。

当前阶段更准确的定义是：

> **专用坍缩运行时 / 专用显形后端 / 专用演算设施**

它的职责包括：

- 状态表示
- 相位调制
- 候选态并存
- 局部坍缩
- 读出
- trace 输出
- 结果回写支持

所以当前阶段 QCU 不是：
- 通用电脑模拟器
- 虚拟机
- 完整 PC 级硬件仿真器

而是：

> **一个专门为候选显形、坍缩和读出服务的运行环境。**

---

## 5. QCU 到底怎么调度

QCU 的“调度”要分层理解。

### 5.1 外部调度
由 MOROZ 或 HCE 负责，决定：

- 这批候选要不要进 QCU
- 进几个 cluster
- 每个 cluster 给多少预算
- 用什么 profile
- 本地、multiprocess 还是 Slurm

### 5.2 QCU 基础调度
由 QCU 自己的 scheduler 负责，决定：

- request ingress
- cluster 排序
- batch 拆分
- step window 切分
- readout / checkpoint 时机
- termination policy

### 5.3 OPU 治理调度
由 OPU 负责，决定运行中的：

- tighten / relax
- gate_level
- suppress_evict
- quality alarm
- 资源/摩擦/质量纠偏

所以 QCU 的正确流程是：

```text
CollapseRequest
   ↓
RequestIngress
   ↓
ClusterScheduler
   ↓
CollapseScheduler
   ↓
OPU Governance
   ↓
Adjusted Plan
   ↓
QCU Runtime
   ↓
CollapseResultBundle
```

---

## 6. OPU 的正确定位

你现有的 `va100/opu` 明显是一颗：

> **治理型 OPU（governance core）**

它做的是：

- `observe(stats)`
- EMA ledger
- `decide()`
- Resource / Friction / Quality 三闭环
- 输出动作（actions）
- 通过 actuators 生效

这说明它不是：
- request parser
- queue manager
- cluster planner
- execution plan builder

它更像：

- 资源治理器
- 质量守门员
- 摩擦回收器
- 冷却 / 抖动 / gate 裁决器

所以结论很清楚：

> **OPU 不是弱，而是职责偏治理，不是完整执行调度器。**

---

## 7. 要不要把 OPU 升级为全功能调度器

不要。

更准确的路线是：

> **补一个基础 scheduler，让 OPU 站在 scheduler 上面做治理与纠偏。**

### 不建议的做法
- 把 OPU 强行改成 request ingress
- 把 OPU 强行改成 cluster planner
- 把 OPU 强行改成 queue manager
- 把 OPU 强行改成 batch splitter

### 推荐做法
分成两层：

#### 基础 scheduler
负责：
- 接请求
- 排 cluster
- 拆 batch / window
- 管 checkpoint / readout / terminate

#### OPU
负责：
- 资源治理
- 质量守门
- 摩擦回收
- 计划纠偏

一句话定版：

> **scheduler 管“怎么排”，OPU 管“值不值得这样排、资源该怎么给”。**

---

## 8. QCU 需要补什么模块

当前阶段，QCU 至少需要以下四层：

### `core/`
放算法：
- `state_repr.py`
- `phase_modulation.py`
- `collapse_operator.py`
- `readout.py`
- `lindblad_solver.py`

### `scheduler/`
放基础调度：
- `request_ingress.py`
- `cluster_scheduler.py`
- `collapse_scheduler.py`
- `termination_policy.py`

### `governance/`
放 OPU 桥接：
- `stats_adapter.py`
- `action_adapter.py`
- `opu_bridge.py`

### `runtime/`
放生命周期：
- `runner.py`
- `session.py`
- `checkpoint.py`

### `io/`
放契约：
- `collapse_request_schema.py`
- `collapse_plan_schema.py`
- `collapse_result_schema.py`

### `api/`
放调用接口：
- `local_api.py`
- `bundle_api.py`

### `cli/`
放人类和 SSH 调用入口：
- `run_local.py`
- `submit.py`
- `inspect.py`

---

## 9. QCU 是否需要 API

需要，但要分层。

### 当前阶段必须有的
1. **内部函数 API**
2. **Bundle API**
3. **CLI API**

### 当前阶段先不要急着做的
4. **网络微服务 API（REST / gRPC）**

最稳的路线是：

> **先做本地与文件契约型 API，不一上来做网络微服务。**

例如：
- `run_qcu(request_bundle, qcu_config) -> sea_output_bundle`
- `tree_candidates_to_qcu_input(tree_output_bundle, qcu_profile) -> qcu_input`
- `write_sea_output(sea_output_bundle, output_path)`

---

## 10. QCU 是否需要指令集

需要，但当前阶段更准确地说，是需要：

> **操作语义集（operation set）**

而不是一上来就做像 x86/ARM 那样完整的硬 ISA。

### 最合适的三层

#### 上层：任务指令
给 MOROZ / HCE / Agent 用，例如：
- `LOAD_CLUSTER`
- `SET_PROFILE`
- `RUN_COLLAPSE`
- `RUN_READOUT`
- `EXPORT_RESULT`

#### 中层：芯片操作指令
QCU 当前最该先有的，例如：
- `INIT_STATE`
- `APPLY_PHASE`
- `APPLY_COUPLING`
- `COLLAPSE_LOCAL`
- `READOUT_WINDOW`
- `CHECKPOINT`
- `TERMINATE_IF`
- `EMIT_RESULT`

#### 下层：数值核操作
以后才可能进一步细化，例如：
- 向量/矩阵推进
- SIMD/GPU kernel
- 稀疏更新

一句话定版：

> **需要“操作集”，不必先做“硬指令集”。**

---

## 11. QCU 是否需要 AVX / 指令集优化

### 11.1 AVX 不是必需条件
QCU 的框架层、调度层、I/O 层不要求 AVX 就能跑。

### 11.2 AVX 对热点数值核有帮助
尤其在：
- phase update
- collapse step
- 批量 readout
- 小到中型 CPU 版数值核

所以更准确的结论是：

> **AVX 不是入场券，但可以是 CPU 版 QCU 的重要加速器。**

建议路线：
- 基础版不要求 AVX
- CPU 加速版优先支持 AVX2
- 更高性能再考虑 AVX-512 / GPU / CUDA

---

## 12. QCU 并行或多核运行会不会更快

会，但不是线性变快，而且最值得并行的层次不是单个坍缩链内部。

### 最值得并行的层次

#### 第一优先：候选簇并行
不同 `candidate_cluster` 独立跑。

#### 第二优先：参数扫描并行
不同 profile / collapse policy / readout window 分开跑。

#### 第三优先：读出批次并行
一个 cluster 内多个 readout task 分开跑。

#### 第四优先：单链数值核并行
单个 cluster 内部 phase/collapse 核心再做多核/GPU 优化。

一句话定版：

> **QCU 最佳加速方式通常是“多簇并行显形”，而不是一开始就把单条显形链切得很碎去并行。**

---

## 13. 虚拟芯片是否需要虚拟主板 / bus / 虚拟内存

当前阶段不需要。

最短结论：

> **现在完全不用再写“虚拟主板 / bus / 虚拟内存”那一套。**

你当前真正需要的是：
- MOROZ → QCU 的请求/结果接口
- QCU 基础调度
- OPU 治理桥
- runtime
- Bundle I/O

而不是先做一台虚拟电脑。

### 什么时候它才有意义
只有当下面这些成立时，才值得进一步做“统一互连层”：

- QCU 操作集已经稳定
- 不只一个后端
- HCE 想进一步设施化
- 你真要做“虚拟芯片平台”

所以现在不要做：
- 虚拟主板
- bus
- 虚拟内存
- 全系统硬件语义

当前阶段只需：
- Bundle
- Scheduler
- Runtime
- Adapter
- Governance

---

## 14. 虚拟芯片的算力从何而来

虚拟芯片当然会烧宿主机资源。

最准确的说法是：

> **虚拟芯片的“智能”来自算法，虚拟芯片的“体力”来自宿主机。**

它不会凭空产生算力。  
真正提供资源的是：

- 宿主 CPU
- 宿主 RAM
- 宿主 GPU
- 宿主存储
- 宿主 I/O

QCU / Tree / HCE 的厉害之处，不是“无资源运行”，而是：

> **通过算法，把同样的宿主机资源用得更聪明。**

也就是：
- 少跑低价值分支
- 少做无意义展开
- 先显形高价值候选
- 早点停止
- 让资源更集中

一句话定版：

> **它们不产生新算力，只提高旧算力的命中率。**

---

## 15. 虚拟芯片和虚拟机是不是一样

不一样，但共享“虚拟化”思想。

### 虚拟机
目标是：

> **在宿主机上虚拟出一台完整通用电脑**

通常包含：
- 虚拟 CPU
- 虚拟内存
- 虚拟硬盘
- 虚拟网卡
- 操作系统

### 你这里说的虚拟主板 / 虚拟芯片
目标是：

> **在宿主机上虚拟出一套专用计算装置**

它更关心：
- 操作集
- 状态区
- 调度
- 数据通路
- 读出/回写
- 资源治理

一句话定版：

> **虚拟机像“电脑里的电脑”，虚拟芯片更像“电脑里的专用机关”。**

---

## 16. 真实开发顺序建议

按当前阶段，最合理的顺序是：

### 第一阶段
补齐 QCU 基础层：
- `request_ingress.py`
- `cluster_scheduler.py`
- `collapse_scheduler.py`
- `termination_policy.py`

### 第二阶段
补齐 OPU 桥接层：
- `stats_adapter.py`
- `action_adapter.py`
- `opu_bridge.py`

### 第三阶段
补齐 runtime：
- `runner.py`
- `session.py`
- `checkpoint.py`

### 第四阶段
补齐 I/O 与 API：
- `collapse_request_schema.py`
- `collapse_result_schema.py`
- `local_api.py`
- `bundle_api.py`

### 第五阶段
再考虑：
- 并行优化
- AVX/GPU 优化
- 更完整的操作集
- 更硬的“虚拟芯片平台”语义

---

## 17. 最终总收口

这整套讨论可以压成一句话：

> **MOROZ 负责把搜索空间压窄并决定哪些高价值候选簇值得进入 QCU，QCU 的基础 scheduler 负责把这些簇排成执行计划，OPU 作为治理核在运行过程中根据资源、摩擦和质量信号动态纠偏；QCU 当前应先做成可调度、可执行、可读写结果的专用坍缩后端，而不是过早做成完整虚拟硬件平台。**
