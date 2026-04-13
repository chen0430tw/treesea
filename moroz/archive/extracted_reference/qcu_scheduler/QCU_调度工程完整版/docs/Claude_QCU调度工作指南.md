# Claude 的 QCU 调度工作指南

## 0. 文件定位

本文件是给 Claude 的 **QCU 调度专项工作指南**。  
目标是让 Claude 在参与 QCU 重构、调度层实现、与 OPU 对接时，不再误判职责边界，也不再把 QCU 写成：

- 一堆散乱函数
- 纯数学原型
- 被 MOROZ 或 HCE 吞掉的内部模块
- 被 OPU 取代的“无独立调度层”后端

Claude 在处理 QCU 调度问题时，一律以本文件为准。

---

## 1. 先记住一句话

> **MOROZ 决定让谁上场，QCU 基础 scheduler 决定怎么排队，OPU 决定打到一半要不要变阵。**

这是 QCU 调度问题的总原则。

---

## 2. QCU 的正确定位

QCU 当前阶段不是：

- 通用模拟器
- 完整虚拟硬件平台
- 纯数学脚本
- 被 MOROZ 封装进去的内部工具

QCU 当前阶段应被理解为：

> **可调度、可执行、可读写结果的专用坍缩后端设施。**

它负责：
- 状态表示
- 相位调制
- 候选态并存
- 局部坍缩
- 读出
- trace 输出
- 结果回写支持

---

## 3. QCU 调度必须分三层

Claude 必须严格区分三种“调度”。

### 3.1 上游调度（MOROZ / HCE）
负责：
- 哪些高价值 cluster 值得进入 QCU
- 给多少 budget
- 用什么 profile
- local / multiprocess / slurm 哪种后端

这层 **不属于 QCU 内部调度**。

---

### 3.2 QCU 基础调度（必须实现）
负责：
- request ingress
- cluster 排序
- batch / step window 切分
- readout / checkpoint 时机
- termination policy

这层是 **QCU 自己必须补出来的执行调度层**。

---

### 3.3 OPU 治理调度
负责：
- 资源治理
- 质量守门
- 摩擦回收
- tighten / relax / suppress / gate
- 对执行计划做动态纠偏

这层是 **治理层**，不是入口层，也不是 plan builder。

---

## 4. Claude 最容易犯的错

### 错误 1：把 OPU 当成完整调度器
不要把 OPU 写成：
- request parser
- queue manager
- cluster planner
- batch splitter

OPU 不是这些。

---

### 错误 2：让 MOROZ 深入 QCU 内部
不要让 MOROZ：
- 直接 import QCU 内部状态对象
- 直接控制 QCU phase/collapse/readout 细节
- 直接改 QCU 执行计划内部字段

MOROZ 只应该通过标准请求对象调用 QCU。

---

### 错误 3：没有 scheduler 层，直接 core 硬跑
不要让 `collapse_operator.py` 或 `readout.py` 直接承担：
- 请求接入
- cluster 排序
- 批次切分
- checkpoint 时机

这些都应该放在 scheduler 层。

---

### 错误 4：过早做“虚拟主板 / bus / 虚拟内存”
当前阶段不要把 QCU 写成完整虚拟硬件平台。  
当前阶段先做：
- Bundle
- Scheduler
- Runtime
- Adapter
- Governance

---

## 5. QCU 当前必须具备的目录语义

Claude 重构时，QCU 至少应具备以下层次：

```text
qcu/
└─ qcu/
   ├─ core/
   ├─ scheduler/
   ├─ governance/
   ├─ runtime/
   ├─ io/
   ├─ api/
   └─ cli/
```

---

## 6. 各层职责

## 6.1 `core/`
只放算法与数值核，例如：
- `state_repr.py`
- `phase_modulation.py`
- `collapse_operator.py`
- `readout.py`
- `lindblad_solver.py`

**禁止**在 `core/` 中写：
- request ingress
- queue 排序
- cluster 拆分
- checkpoint 总策略

---

## 6.2 `scheduler/`
这是 QCU 调度层，必须实现。

建议至少有：

- `request_ingress.py`
- `cluster_scheduler.py`
- `collapse_scheduler.py`
- `termination_policy.py`

### `request_ingress.py`
负责：
- 校验 `CollapseRequest`
- 补默认 budget / policy
- 建立 session

### `cluster_scheduler.py`
负责：
- cluster 排序
- backend 路由
- 初始 budget 分配
- 生成 cluster 级执行计划

### `collapse_scheduler.py`
负责：
- 单 cluster 的 step window 切分
- readout/checkpoint 节点安排
- 执行粒度组织

### `termination_policy.py`
负责：
- collapse_score / stability / max_steps 终止规则

---

## 6.3 `governance/`
这是 OPU 对接层。

建议至少有：

- `stats_adapter.py`
- `action_adapter.py`
- `opu_bridge.py`

### `stats_adapter.py`
把 QCU runtime 的原始状态压成 OPU 可理解的 stats：

- `hot_pressure`
- `faults`
- `wait_time_s`
- `rebuild_cost_s`
- `quality_score`

### `action_adapter.py`
把 OPUAction 映射成对执行计划的修正，例如：

- tighten → 降 step budget / 限并发
- relax → 放宽 budget / readout
- gate_level → 提高准入门槛
- suppress_evict → 暂缓驱逐低优先簇

### `opu_bridge.py`
串联：
- `observe(stats)`
- `decide()`
- `apply(action, plan)`

---

## 6.4 `runtime/`
负责：
- session 生命周期
- 执行 scheduler 输出的 plan
- 调 core
- 写 checkpoint
- 汇总治理 trace
- 产出最终结果

建议至少有：
- `runner.py`
- `session.py`
- `checkpoint.py`

---

## 6.5 `io/`
负责 I/O 契约，不要让外部系统直接摸内部对象。

建议至少有：
- `collapse_request_schema.py`
- `collapse_plan_schema.py`
- `collapse_result_schema.py`

### 必须坚持的原则
QCU 对外主要吃和吐的是：
- `CollapseRequest`
- `CollapsePlan`
- `CollapseResultBundle`

而不是任意 dict 或任意内部对象。

---

## 6.6 `api/`
当前阶段先做：
- `local_api.py`
- `bundle_api.py`

不急着做：
- REST API
- gRPC
- WebSocket 服务

一句话：
> **先做本地与文件契约型 API，不要一上来做网络微服务。**

---

## 6.7 `cli/`
建议至少有：
- `run_local.py`
- `submit.py`
- `inspect.py`

让 QCU 可以：
- 本地跑
- 上 Slurm
- 查结果

---

## 7. QCU 调度对象必须明确

Claude 在写代码时，不要跳过对象设计。

### 7.1 `CollapseRequest`
作用：QCU 的标准输入。

至少应包含：
- `request_id`
- `qcu_session_id`
- `candidate_cluster(s)`
- `qcu_profile`
- `budget`
- `termination_policy`
- `output_policy`
- `backend`
- `metadata`

---

### 7.2 `CollapsePlan`
作用：scheduler 输出的执行计划。

至少应包含：
- cluster 顺序
- candidate ids
- step budget
- readout interval
- checkpoint interval
- backend
- priority

---

### 7.3 `CollapseResultBundle`
作用：QCU 的标准输出。

至少应包含：
- `collapse_results`
- `sea_ranking`
- `stability`
- `phase_signature`
- `solver_trace_ref`
- `checkpoint_ref`
- `governance_trace`
- `metrics`

---

## 8. Claude 写 QCU 调度时必须遵守的边界

### 8.1 MOROZ 只到 `CollapseRequest`
MOROZ 不得直接碰：
- QCU 内部 runtime 对象
- QCU 内部 collapse state
- OPU 内部 ledger

---

### 8.2 OPU 只做治理，不做入口
OPU 不得直接承担：
- request ingress
- cluster 排序
- batch 切分

---

### 8.3 QCU core 只做算法，不做总控
`core/` 不得偷偷吞掉：
- scheduler 职责
- governance 职责
- runtime 职责

---

## 9. QCU 与 OPU 的标准关系

Claude 必须始终按这个关系实现：

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
Adjusted Execution Plan
   ↓
QCU Runtime
   ↓
CollapseResultBundle
```

解释：

- scheduler 先排出基础执行计划
- OPU 再根据运行状态动态纠偏
- runtime 真正执行 plan
- 最终输出结果与治理 trace

---

## 10. 并行和性能优化原则

当前阶段，Claude 在优化 QCU 时应优先：

### 第一优先
簇级并行：
- 不同 `candidate_cluster` 分开跑

### 第二优先
参数扫描并行：
- 不同 profile / collapse 策略分开跑

### 第三优先
读出批次并行

### 第四优先
单链数值核并行（CPU/GPU 深度优化）

**不要一开始就沉迷把单个 collapse 链切得很碎去并行。**

---

## 11. AVX / GPU / 指令集 的正确处理方式

### 11.1 AVX
- 不是必需条件
- 可以是 CPU 数值热点加速路径

### 11.2 GPU / CUDA
- 是后续数值核强化路径
- 不是当前 scheduler 层的前提

### 11.3 指令集
当前阶段先定义：
- 操作语义集（operation set）

不必一开始就写成完整硬 ISA。

---

## 12. Claude 的交付顺序建议

当用户要求你“写 QCU 调度”时，Claude 应按这个顺序交付：

### 第一批
`scheduler/`
- `request_ingress.py`
- `cluster_scheduler.py`
- `collapse_scheduler.py`
- `termination_policy.py`

### 第二批
`governance/`
- `stats_adapter.py`
- `action_adapter.py`
- `opu_bridge.py`

### 第三批
`runtime/`
- `runner.py`
- `session.py`
- `checkpoint.py`

### 第四批
`io/` + `api/`
- schema
- local API
- bundle API

### 第五批
再做：
- 并行优化
- AVX/GPU 优化
- 更完整操作集

---

## 13. 给 Claude 的最终提醒

如果 Claude 只能记住 4 条，就记住：

1. **QCU 必须有自己的基础 scheduler。**
2. **OPU 是治理核，不是完整执行调度器。**
3. **MOROZ 通过标准请求对象调 QCU，不深入内部。**
4. **当前阶段先把 QCU 做成专用坍缩后端，不要过早做成完整虚拟硬件平台。**

---

## 14. 一句话总收口

> **Claude 在实现 QCU 调度时，必须先补齐基础 scheduler，再通过 OPU bridge 把现有治理型 OPU 接到 runtime 上，对执行计划做动态纠偏；不要把 OPU 升级成万能调度器，也不要让 MOROZ 直接深入 QCU 内核。**
