# HCE 与大模型 Agent / Claude Code SSH 接入规范

## 0. 文件目的

本文件用于明确 HCE 当前阶段中：

- 大模型 Agent 模块
- Claude Code 通过 SSH 远程操作

这两类能力应如何接入 HCE，以及它们在系统中的正确定位。

本文件的核心目标是防止两种常见错误：

1. 把 Agent 直接塞进树海内核，导致系统边界混乱  
2. 把 Claude Code SSH 当成 HCE 内部模块，而不是外部运维/开发方式

---

## 1. 总体结论

HCE 可以接入：

- **大模型 Agent 模块**
- **Claude Code 通过 SSH 的远程操作方式**

但两者的定位完全不同。

### 1.1 大模型 Agent 的定位
大模型 Agent 适合作为：

> **上层认知入口 / 策略编排层**

它负责：
- 把自然语言请求转成结构化任务
- 帮用户选运行模式
- 自动组装 RequestBundle
- 解释 Tree / Sea / HC 的结果
- 生成实验计划和报告摘要

它不应直接成为树海内核的一部分。

---

### 1.2 Claude Code SSH 的定位
Claude Code 通过 SSH 适合作为：

> **外部远程开发员 / 远程运维员 / 远程研究员**

它负责：
- 连接集群或超算节点
- 修改仓库文件
- 提交 `sbatch`
- 查看 `squeue / sacct`
- tail 日志
- 修改 config
- 做代码重构与调试

它不是 HCE 内部模块，而是一种**外部操作方式**。

---

## 2. 推荐三层结构

最稳的结构应该分成三层：

```text
人类 / Agent / Claude Code
           ↓
       HCE 入口层
           ↓
   Tree / QCU / HC 内核
```

### 2.1 外层：人类 / Agent / Claude Code
负责：
- 提需求
- 写配置
- 选模式
- 触发任务
- 看结果
- 改代码
- 远程运维

### 2.2 中层：HCE 入口层
负责：
- 接收 RequestBundle
- 校验模式与权限
- 选择 profile
- 调度 Tree / Sea / HC
- 归档结果
- 输出 FinalReportBundle

### 2.3 内层：Tree / QCU / HC
负责：
- 真正演算
- 真正裁决
- 真正显形
- 真正风险评估

---

## 3. 大模型 Agent 的正确接入方式

## 3.1 Agent 适合做什么

Agent 最适合做的事情包括：

- 自然语言 → RequestBundle
- 根据任务目标自动建议运行模式
- 自动生成 config
- 自动选择实验 profile
- 自动解释中间结果
- 输出自然语言报告
- 生成实验计划
- 生成后续执行建议

例如：

### 输入
“帮我对这个候选主线做树先海后再风险评估，预算限制在 4 节点以内。”

### Agent 输出
- `task_type`
- `mode = tree_then_sea_then_hc`
- `budget`
- `runtime_profile`
- `output_policy`

最终组装为 `RequestBundle` 交给 HCE。

---

## 3.2 Agent 不适合做什么

Agent 不应直接做以下事情：

- 直接改 Tree 的 branch score
- 直接修改 QCU 内部 collapse 状态
- 直接覆写 Honkai Core 的阈值裁决结果
- 绕过 HCE 入口层直接操作树海内核对象
- 在系统内部偷偷共享 Python 运行时对象

也就是说：

> **Agent 可以决定“怎么跑”，但不要直接参与“内部怎么算”。**

---

## 3.3 Agent 的正确位置

推荐位置：

```text
hce/
└─ hce/
   ├─ agents/
   │  ├─ request_planner.py
   │  ├─ bundle_builder.py
   │  ├─ result_interpreter.py
   │  └─ experiment_planner.py
   └─ bridges/
      └─ agent_gateway.py
```

### 推荐职责

#### `request_planner.py`
- 自然语言任务解释
- 模式建议
- 预算建议

#### `bundle_builder.py`
- 把 Agent 规划结果组装成 `RequestBundle`

#### `result_interpreter.py`
- 把 `TreeOutputBundle / SeaOutputBundle / HCReportBundle / FinalReportBundle` 转成自然语言解释

#### `experiment_planner.py`
- 生成实验批次计划
- 生成扫描方案建议

#### `agent_gateway.py`
- Agent 与 HCE 的统一桥接层
- 限制 Agent 的权限边界
- 确保 Agent 只触碰 Bundle，不触碰树海内核对象

---

## 4. Claude Code SSH 的正确接入方式

## 4.1 Claude Code SSH 适合做什么

Claude Code 通过 SSH 最适合做的事情包括：

- SSH 连接集群
- 打开仓库
- 改 Python 文件
- 改 YAML 配置
- 提交 `sbatch`
- 查看 `squeue / sacct / scontrol`
- 读取 logs / checkpoints / results
- 维护 Slurm 模板
- 重构仓库结构
- 修复运行错误

这非常适合 HCE 这种：

- 有大量目录骨架
- 需要不断重构
- 需要经常提交集群任务
- 需要看日志与结果
- 需要维护 Slurm / MPI / config

的项目。

---

## 4.2 Claude Code SSH 不应被设计成什么

Claude Code SSH 不应被设计成：

- HCE 内部包
- Tree/Sea/HC 计算内核的一部分
- 隐藏式自动控制器
- 直接写进 pipeline 的系统组件

它不是仓库里的“模块”，而是：

> **人类研究员的远程操作替身 / 外部开发与运维方式**

---

## 4.3 Claude Code SSH 的正确定位

更准确地说，Claude Code SSH 是：

- 外部开发代理
- 外部运维代理
- 外部实验提交代理
- 外部调试代理

也就是说，它在 HCE 体系中的位置是：

```text
Claude Code (SSH)
      ↓
操作仓库 / CLI / Slurm
      ↓
HCE / Tree / QCU / HC
```

而不是：

```text
HCE 内核
└─ Claude Code module
```

这个差别必须严格保持。

---

## 5. Agent 与 Claude Code SSH 的差异

## 5.1 Agent 的本质
Agent 是：

> **认知入口与策略层**

它更像“会思考和解释的中枢助手”。

### 典型功能
- NL → Bundle
- 自动建议模式
- 自动解释结果
- 实验规划

---

## 5.2 Claude Code SSH 的本质
Claude Code SSH 是：

> **远程操作与开发层**

它更像“会改代码、提作业、看日志的远程研究员”。

### 典型功能
- 改仓库
- SSH 上集群
- 提交任务
- 查队列
- 修复代码
- 改配置

---

## 5.3 两者不能混成一个东西

不要把：

- Agent 的自然语言编排能力
- Claude Code 的远程仓库操作能力

混成一个模糊的“大模型自动做一切”。

在 HCE 里必须明确：

- Agent 主要作用于 **任务层**
- Claude Code SSH 主要作用于 **仓库与集群操作层**

---

## 6. 推荐交互拓扑

## 6.1 Agent 接入拓扑

```text
用户自然语言
      ↓
Agent
      ↓
RequestBundle
      ↓
HCE
      ↓
Tree / QCU / HC
      ↓
FinalReportBundle
      ↓
Agent 解释结果
      ↓
用户
```

### 说明
Agent 在这里承担：
- 任务解释
- Bundle 构造
- 结果解释

但不直接碰树海内核。

---

## 6.2 Claude Code SSH 接入拓扑

```text
Claude Code (SSH)
      ↓
编辑仓库 / 提交 Slurm / 查日志
      ↓
HCE CLI / Tree CLI / QCU CLI / HC CLI
      ↓
Slurm / MPI / 集群
      ↓
results / logs / checkpoints
```

### 说明
Claude Code 只是外部使用者的一种强化形态，不是系统内核。

---

## 6.3 两者共同存在时的总拓扑

```text
人类 / Agent / Claude Code
           ↓
       HCE 入口层
           ↓
   Tree / QCU / HC 内核
```

这就是当前最稳的总体结构。

---

## 7. Bundle 视角下的接入规则

## 7.1 Agent 可以读写什么
Agent 可以：

- 读 `RequestBundle`
- 写 `RequestBundle`
- 读 `TreeOutputBundle`
- 读 `SeaOutputBundle`
- 读 `HCReportBundle`
- 读 `FinalReportBundle`

Agent 不应直接读写：

- Tree 内部运行时对象
- QCU 内部状态对象
- HC 内部判据对象
- HCE runtime 内部调度对象

---

## 7.2 Claude Code SSH 可以碰什么
Claude Code SSH 可以碰：

- 仓库文件
- 配置文件
- Slurm 模板
- CLI
- 日志
- 检查点
- 结果文件

但它碰到这些，是因为它是**外部操作员**，不是系统在运行时主动把它纳入内核。

---

## 8. 与双入口设计的关系

HCE 之前已经确定采用双入口：

- **底层：标准 HPC 入口**
- **上层：学园都市风格入口**

那么 Agent 和 Claude Code SSH 应该这样接：

## 8.1 Agent
更适合接到 **学园都市风格入口 / HCE 入口层**

因为它天然适合做：
- 任务解释
- 模式编排
- 结果解释
- 设施化交互

所以 Agent 更像：

> **高层语义入口的增强器**

---

## 8.2 Claude Code SSH
更适合接到 **标准 HPC 入口 / 仓库操作层**

因为它天然适合做：
- 提交 `sbatch`
- 看 `squeue`
- 改 `.py`
- 改 `.yaml`
- tail logs

所以 Claude Code 更像：

> **底层工程与运维入口的强化执行员**

---

## 9. 学园都市风格下的命名建议

如果要把 Agent 纳入学园都市风格叙事层，推荐称呼：

- Agent：研究指挥层 / 认知辅助层 / 实验规划层
- Claude Code SSH：外部研究员终端 / 远程维护终端 / 实验执行终端

不建议直接写成：
- AI assistant module
- ssh automation bot

因为那样会把风格拉回普通工程工具。

---

## 10. 当前阶段推荐实施方式

## 10.1 Agent 模块
当前阶段可以先只做：

- RequestBundle 生成
- 模式推荐
- 结果解释

先别让它直接做：
- 自动强回写
- 自动改阈值
- 自动绕过裁决层

---

## 10.2 Claude Code SSH
当前阶段把它视为：

- 远程改仓库
- 远程提交作业
- 远程看日志
- 远程修问题

就够了。  
不要把它纳入 HCE 内部 runtime 设计。

---

## 11. 最终结论

一句话压缩：

> **大模型 Agent 适合作为 HCE 上层认知入口与策略编排层；Claude Code 通过 SSH 适合作为外部远程开发与运维执行员；二者都可以接入 HCE，但都不应直接成为树海内核的一部分。**

再压短一点：

- **Agent 决定怎么跑**
- **Claude Code 帮你远程把它跑起来**
- **Tree / QCU / HC 负责真正演算**
