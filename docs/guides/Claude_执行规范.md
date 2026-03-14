# Claude_执行规范

## 0. 文件定位

本文件是当前阶段给 Claude 的**唯一执行规范**。  
它整合了：

- 工作指南
- 代码重构执行规范
- 源码迁移对照表

Claude 在 HCE 仓库内协作时，一律以本文件为准，不再分散查阅多份同类说明。

---

## 1. 项目本质

本项目虽然借用了“崩坏”“树海”“律者”“世界泡”等命名，但这里的语境是：

- 理论建模语言
- 系统架构命名
- 高维结构计算与复杂系统工程术语
- 分布式计算与超算部署项目

**不是：**

- 游戏模组开发
- 剧情解析
- 角色设定整理
- 二创百科

Claude 默认必须按**项目内部工程/理论定义**理解这些术语。

---

## 2. 四系统并列原则

HCE 仓库包含四套系统：

- Tree Diagram
- QCU
- Honkai Core
- HCE

其中：

- Tree Diagram 可独立运行
- QCU 可独立运行
- Honkai Core 可独立运行
- HCE 是集成运行时与桥接层

Claude 不得把项目理解成：

- “HCE 下面附带三个子模块”
- “只有进入 HCE 后其他模块才有意义”
- “Tree Diagram / QCU / Honkai Core 只是 HCE 的库”

正确理解是：

> 三核独立可运行，HCE 负责耦合，不负责垄断。

---

## 3. Tree Diagram 的正确口径

Tree Diagram 当前的参考源码基线，不是单一脚本，而是以下两个原型文件共同构成的**同一系统原型集合**：

- `tree_diagram_complete_mini_colab_v3_active.py`
- `tree_diagram_weather_oracle_v5_tuned.py`

这两个文件：

- 不是两个并列模式
- 不是两个独立项目
- 不是“主体 + 附属壳层”
- 而是 **同一个 Tree Diagram 系统的双原型基线**

其中：

- 前者更偏抽象骨架与最小闭环
- 后者更偏数值化、气象化、ensemble / oracle 化实现

Claude 在重构 Tree Diagram 时：

- 不允许只按 `mini_colab` 脚本重构
- 不允许把 `weather_oracle_v5_tuned.py` 误解成独立系统
- 必须把两者共同视为 Tree Diagram 的参考源码集合

---

## 4. 目标环境：超算 / 训练集群优先

Claude 必须默认本项目运行环境不是普通单机，而是：

- 天河级别超算
- 高性能训练集群
- Slurm 调度系统
- MPI / 多节点并行
- TUI 交互前端
- 批处理 / checkpoint / 日志归档 / 实验追踪

因此 Claude 在写代码、改结构、写文档时，应优先考虑：

- 是否适合批处理提交
- 是否适合多节点 / 多 rank
- 是否支持 checkpoint / resume
- 是否有独立 `configs/`, `jobs/`, `slurm/`, `mpi/`, `io/`, `runtime/`, `cli/`
- 输出是否写入统一的 `runs/`, `checkpoints/`, `logs/`, `results/`

---

## 5. 四系统职责边界

### 5.1 Tree Diagram
职责：
- problem seed 解析
- 背景推断
- group field 编码
- worldline 生成
- branch ecology 评估
- 资源裁决
- oracle 输出
- 数值实现层（包括 weather / oracle 化实现）接入

输入：
- problem seed
- constraints
- worldline config
- branch scoring config
- 数值实现层配置（包括 weather / oracle 相关配置）

输出：
- ranked worldlines
- branch ecology snapshot
- oracle output
- resource allocation summary

### 5.2 QCU
职责：
- 状态表示
- 相位调制
- 候选态并存
- 局部坍缩
- 读出
- solver trace
- 批量扫描
- 高维候选显形

### 5.3 Honkai Core
职责：
- 崩坏学建模
- 崩坏能学建模
- 阈值分析
- 风险评估
- 耦合模型
- 稳定化分析
- 世界泡判据
- 律者化 / 权限化判据

### 5.4 HCE
职责：
- Tree Diagram ↔ QCU ↔ Honkai Core 桥接
- 多阶段流水线
- integrated result merge
- checkpoint / fault tolerance
- TUI 前端
- 集群级作业封装

---

## 6. 代码重构最高原则

Claude 在任何重构任务中都必须遵守以下优先级：

1. 先保留可运行性
2. 再补入口与 I/O
3. 再拆模块
4. 最后再追求优雅

也就是说：

> 能跑、能提交、能恢复、能追踪，比“代码看起来更干净”更重要。

---

## 7. 原型文件处理原则

所有现有单文件原型，默认先放入：

`legacy/imported_single_file_prototypes/`

这些原型文件在完成完整迁移前，始终视为：

- 回退基线
- 行为参考实现
- 最小可运行备份

**不得直接删除原型文件。**

---

## 8. 标准分层

重构时默认采用下列分层：

- `core/`：核心算法与业务逻辑
- `io/`：输入输出协议、schema、载入与写出逻辑
- `runtime/`：运行时控制、checkpoint、恢复逻辑
- `cli/`：本地运行、提交作业、结果查看等入口
- `distributed/`：MPI / 分片 / reduction / pipeline 分布式支持
- `slurm/`：`.sbatch` 模板、提交包装脚本、集群 profile
- `mpi/`：`mpirun_*.sh`、rank 布局说明

不要把：
- 业务逻辑塞进 `cli/`
- I/O 写死在 `core/`
- Slurm 模板散落到 `scripts/`
- checkpoint 到处乱写

---

## 9. 必须保证的最小入口

四个系统都必须逐步具备以下入口：

### 本地入口
`python -m <system>.cli.run_local --config ...`

### 提交入口
`python -m <system>.cli.submit --config ...`

### 查看入口
`python -m <system>.cli.inspect --run-id ...`

---

## 10. I/O 规则

每个系统都要有自己的输入输出 schema，不要互相偷读内部对象。

### Tree Diagram
- worldline / oracle / feedback schema

### QCU
- state / readout / scan / sea output schema

### Honkai Core
- threshold / risk / energy schema

### HCE
- pipeline / bridge / final report schema

默认输出路径统一为：

- `runs/<system>/`
- `checkpoints/<system>/`
- `logs/<system>/`
- `results/<system>/`

---

## 11. Slurm / MPI 规则

### Slurm
- 每个系统有自己的 `slurm/`
- 至少保留单节点模板与多节点/扫描模板
- 不要把分区、节点数、time 等硬编码进 Python

### MPI
- 先做 adapter，再做深度并行
- Tree Diagram：worldline / candidate shard
- QCU：state / operator / scan shard
- Honkai Core：scenario / threshold grid scan
- HCE：pipeline stage / result merge

---

## 12. 兼容性要求

每次重构后，至少保证以下一种成立：

- 保留旧脚本直接可运行
- 或提供 wrapper 兼容入口
- 或明确给出新旧路径映射与命令迁移说明

不能只改代码，不说明怎么继续跑。

---

## 13. 最小测试要求

### Tree Diagram
- 读一个 seed
- 生成少量 worldline
- 输出一个 oracle 结果

### QCU
- 初始化一个小状态
- 跑一次 collapse / readout
- 输出 trace

### Honkai Core
- 读一个 scenario
- 输出一个阈值 / 风险报告

### HCE
- 用假数据串联 TD → QCU → HC
- 合并结果
- 写 integrated report

---

## 14. 推荐重构顺序

1. 建目录骨架  
2. 建 README / 占位文件  
3. 补 `run_local.py` / `submit.py` / `inspect.py`  
4. 建 schema / loader / writer  
5. 补 `.sbatch` 与 `mpirun_*.sh`  
6. 从 legacy 抽函数进正式模块  
7. 最后做 HCE 集成与 TUI

---

## 15. 文件级迁移对照

### 15.1 Tree Diagram
共同基线：
- `legacy/imported_single_file_prototypes/tree_diagram_complete_mini_colab_v3_active.py`
- `legacy/imported_single_file_prototypes/tree_diagram_weather_oracle_v5_tuned.py`

迁移目标：
- 抽象层：`problem_seed.py`, `background_inference.py`, `group_field.py`, `worldline_kernel.py`, `branch_ecology.py`, `balance_layer.py`, `resource_controller.py`, `oracle_output.py`
- 数值层：`weather_state.py`, `dynamics.py`, `forcing.py`, `ensemble.py`, `ranking.py`

### 15.2 QCU
共同基线：
- `legacy/imported_single_file_prototypes/qcu_reconstructed.py`
- `legacy/imported_single_file_prototypes/qcu_full_reconstructed.py`

迁移目标：
- `state_repr.py`
- `phase_modulation.py`
- `collapse_operator.py`
- `readout.py`
- `writeback.py`
- `lindblad_solver.py`
- `entanglement_metrics.py`
- `iqpu_runtime.py`

### 15.3 Honkai Core
主要从理论稿和白皮书中抽模型：
- `energy_model.py`
- `threshold_model.py`
- `coupling_model.py`
- `rewrite_model.py`

### 15.4 HCE
主要从白皮书与三系统 I/O 关系建立桥接层：
- `td_qcu_bridge.py`
- `hc_bridge.py`
- `result_merge.py`
- `pipeline_controller.py`
- `writeback_adapter.py`

---

## 16. 最重要的一句话

如果 Claude 只能记住一条原则，就记住这句：

> 这是一个面向超算/训练集群的四系统工程项目，不是游戏设定整理；三套核心系统必须保持独立运行能力，HCE 只负责集成，不负责垄断；Tree Diagram 当前以两个原型脚本共同作为同一系统的参考源码基线。
