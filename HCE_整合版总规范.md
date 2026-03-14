# HCE 整合版总规范

## 0. 文件定位

本文件是当前阶段 **唯一的整合版总规范**。  
它一次性统一以下内容：

- 项目总体结构
- Tree / Sea / Honkai Core / HCE 的边界
- Tree Diagram 的正确原型口径
- 树海交互模式
- I/O 与 Bundle 设计
- 回写机制
- 双入口设计（标准 HPC + 学园都市风格入口）
- 学园都市风格要求
- 风格验收标准
- 仓库与运行路径设计
- 对 Claude 的执行口径

本文件的目标不是继续分裂文档，而是把前面有效结论一次性收口，作为当前阶段的**单一主规范**。

---

## 1. 总体结论

HCE 当前应被设计为一个 **四系统并列、统一 I/O 契约、标准 HPC 底层执行、上层可学园都市风格化呈现** 的工程系统。

四个系统分别是：

- **Tree Diagram**：树端系统
- **QCU**：海端系统
- **Honkai Core**：理论与风险评估系统
- **HCE**：集成运行时与调度系统

它们之间的关系不是父子依附关系，而是：

- Tree Diagram 可独立运行
- QCU 可独立运行
- Honkai Core 可独立运行
- HCE 负责把前三者桥接成整机流水线

也就是说：

> **三核独立可运行，HCE 负责耦合，不负责垄断。**

---

## 2. Tree Diagram 的正确口径

这是整个项目里必须钉死的一条。

Tree Diagram 当前的参考源码基线，不是单一脚本，而是以下两个原型文件共同构成的 **同一系统原型集合**：

- `tree_diagram_complete_mini_colab_v3_active.py`
- `tree_diagram_weather_oracle_v5_tuned.py`

这两个文件：

- 不是两个并列模式
- 不是两个独立项目
- 不是“主体 + 附属壳层”
- 而是 **同一个 Tree Diagram 系统的双原型基线**

因此，后续任何重构、迁移、README、Claude 协作都必须遵守：

> **Tree Diagram = 这两个 `.py` 文件共同构成的同一系统原型集合。**

其中：

- 前者更偏抽象骨架与最小闭环
- 后者更偏数值化、气象化、ensemble / oracle 化实现

但两者都属于 **同一个 Tree Diagram**。

---

## 3. 四系统职责边界

## 3.1 Tree Diagram（树）

Tree Diagram 是树端系统，负责：

- 接收问题与约束
- 生成 worldline / branch 候选
- 做主线筛选
- 做分支生态管理
- 输出排序后的候选集合
- 提供 oracle hint

Tree Diagram 的输出不是最终整机答案，而是：

> **候选主线集合 + 排名 + 分支状态 + 资源倾斜建议**

---

## 3.2 QCU（海）

QCU 是海端系统，负责：

- 接收树给出的候选
- 将候选抬到高维候选空间
- 执行相位调制
- 执行局部坍缩
- 执行读出
- 生成显形证据与稳定性指标

QCU 的输出不是全局主线，而是：

> **局部显形结果 + 读出证据 + 坍缩指标 + 稳定性信息**

---

## 3.3 Honkai Core

Honkai Core 是理论与风险评估系统，负责：

- 崩坏能估计
- 阈值判定
- 风险分析
- 规则改写 / 权限化评估
- 输出限幅、回写、终止建议

Honkai Core 不承担树海主计算，而承担：

> **理论评估与风险裁决层**

---

## 3.4 HCE

HCE 是集成运行时，负责：

- 接收外部任务
- 调度树、海、HC 的执行顺序
- 管理中间产物
- 控制回写策略
- 管理 checkpoint / 日志 / 结果归档
- 形成最终报告
- 提供 TUI 与 CLI

HCE 的本质不是吞掉其它系统，而是：

> **桥接、调度、回写、归档、汇总的整机运行时**

---

## 4. 最高交互原则

### 4.1 不共享内部对象，只交换显式 Bundle

树、海、HCE、HC 之间不应直接共享运行时内部对象。  
不要设计成：

- Tree 直接 import Sea 的内部类
- Sea 直接改 Tree 内存对象
- HCE 直接在不同 stage 之间乱传 Python 内部结构

正确方式是：

> **所有系统只通过 Bundle 和中间产物交互。**

这样做的好处：

- 适合 Slurm / MPI / 多节点
- 易做 checkpoint
- 易追踪中间结果
- 易于跨语言重构
- 易于失败恢复
- 易于后续把某些模块独立部署

---

### 4.2 交互单位统一为 Bundle

统一交互单位如下：

- `RequestBundle`
- `TreeOutputBundle`
- `SeaOutputBundle`
- `HCReportBundle`
- `FinalReportBundle`

这样做的意义是：

- 易落盘
- 易恢复
- 易跨进程
- 易跨节点
- 易跨语言
- 易审计
- 易让 TUI / CLI 读写

---

### 4.3 回写先做弱回写

当前阶段不做：

- 海直接改树分数
- HC 直接改 Tree branch_state
- HCE 直接强制覆盖内部结构

当前阶段推荐：

> **弱回写 + writeback adapter**

也就是：
- 海只输出 feedback 建议
- HC 只输出裁决建议
- HCE 或 Tree 的 adapter 决定是否采纳

---

## 5. 推荐标准流水线

当前阶段推荐的一条标准流水线是：

```text
RequestBundle
   ↓
Tree Diagram
   ↓
TreeOutputBundle
   ↓
QCU
   ↓
SeaOutputBundle
   ↓
Honkai Core
   ↓
HCReportBundle
   ↓
HCE merge
   ↓
FinalReportBundle
```

这对应的模式名建议固定为：

`tree_then_sea_then_hc`

这是当前最稳的默认模式。

---

## 6. 允许的运行模式

系统必须支持以下模式，而不是只支持整机模式。

### 6.1 `tree_only`
只运行 Tree Diagram。

### 6.2 `sea_only`
只运行 QCU。

### 6.3 `hc_only`
只运行 Honkai Core。

### 6.4 `tree_then_sea`
树先筛选，再交海显形。

### 6.5 `tree_then_sea_then_hc`
树、海、HC 全流水线，当前推荐默认模式。

### 6.6 `sea_then_tree`
保留为未来扩展模式，当前阶段可以先不做。

---

## 7. Bundle 设计

## 7.1 RequestBundle

### 作用
整机入口任务描述。

### 最小字段
```json
{
  "request_id": "req_0001",
  "task_type": "worldline_search",
  "mode": "tree_then_sea_then_hc",
  "seed": {},
  "constraints": {},
  "budget": {},
  "runtime_profile": {},
  "output_policy": {},
  "metadata": {}
}
```

### 字段说明
- `request_id`：全局请求号
- `task_type`：任务类型
- `mode`：执行模式
- `seed`：问题种子
- `constraints`：约束
- `budget`：预算
- `runtime_profile`：运行资源配置
- `output_policy`：输出策略
- `metadata`：附加信息

---

## 7.2 TreeOutputBundle

### 作用
Tree Diagram 对外标准输出。

### 最小字段
```json
{
  "request_id": "req_0001",
  "tree_run_id": "td_0001",
  "candidate_set": [
    {
      "candidate_id": "cand_01",
      "worldline": {},
      "score": 0.91,
      "branch_state": "active",
      "resource_weight": 0.82
    }
  ],
  "ranking": [],
  "ecology_snapshot": {},
  "oracle_hint": {},
  "tree_metrics": {},
  "checkpoint_ref": "",
  "metadata": {}
}
```

### 关键输出
- `candidate_set`
- `ranking`
- `ecology_snapshot`
- `oracle_hint`
- `tree_metrics`
- `checkpoint_ref`

---

## 7.3 SeaOutputBundle

### 作用
QCU 对外标准输出。

### 最小字段
```json
{
  "request_id": "req_0001",
  "sea_run_id": "qcu_0001",
  "input_candidates": ["cand_01", "cand_02"],
  "collapse_results": [
    {
      "candidate_id": "cand_01",
      "collapse_score": 0.88,
      "readout": {},
      "phase_signature": {},
      "stability": 0.73
    }
  ],
  "sea_ranking": [],
  "solver_trace_ref": "",
  "sea_metrics": {},
  "checkpoint_ref": "",
  "metadata": {}
}
```

### 关键输出
- `input_candidates`
- `collapse_results`
- `sea_ranking`
- `solver_trace_ref`
- `sea_metrics`
- `checkpoint_ref`

---

## 7.4 HCReportBundle

### 作用
Honkai Core 风险与阈值评估输出。

### 最小字段
```json
{
  "request_id": "req_0001",
  "hc_run_id": "hc_0001",
  "energy_estimate": {},
  "threshold_assessment": {},
  "risk_assessment": {},
  "rewrite_assessment": {},
  "recommendation": {},
  "metadata": {}
}
```

### 关键输出
- `energy_estimate`
- `threshold_assessment`
- `risk_assessment`
- `rewrite_assessment`
- `recommendation`

---

## 7.5 FinalReportBundle

### 作用
HCE 最终汇总输出。

### 最小字段
```json
{
  "request_id": "req_0001",
  "tree_ref": "td_0001",
  "sea_ref": "qcu_0001",
  "hc_ref": "hc_0001",
  "final_selection": {},
  "final_ranking": [],
  "energy_summary": {},
  "risk_summary": {},
  "artifacts": {},
  "metadata": {}
}
```

### 关键输出
- `tree_ref`
- `sea_ref`
- `hc_ref`
- `final_selection`
- `final_ranking`
- `energy_summary`
- `risk_summary`
- `artifacts`

---

## 8. 回写机制

### 8.1 弱回写格式

建议统一成一个 feedback 对象：

```json
{
  "candidate_id": "cand_01",
  "feedback": {
    "confidence_boost": 0.12,
    "stability_penalty": 0.08,
    "phase_hint": "focus_local",
    "recommend_branch_state": "active"
  }
}
```

### 8.2 回写控制点

回写不应分散在各模块内部，而应集中到：

- `hce/integration/writeback_adapter.py`

由它负责：

- 读取 SeaOutputBundle 的反馈
- 读取 HCReportBundle 的建议
- 决定是否回写
- 记录采纳与拒绝原因
- 输出 writeback trace

### 8.3 当前阶段不做强回写

当前阶段先不做：

- 海直接改 Tree 内部分数
- HC 直接改 Tree 内部状态
- 自动循环多轮更新

因为这会导致：
- 难追踪
- 难回滚
- 难 checkpoint
- 难定位边界

---

## 9. 文件格式约定

### 9.1 配置文件
统一使用 **YAML**。

用途：
- cluster profile
- runtime config
- task config
- output policy

### 9.2 Bundle 文件
统一使用 **JSON**。

用途：
- RequestBundle
- TreeOutputBundle
- SeaOutputBundle
- HCReportBundle
- FinalReportBundle

### 9.3 事件流与日志
统一使用 **JSONL**。

用途：
- runtime events
- step trace
- metrics stream
- TUI tail

---

## 10. 项目结构设计

## 10.1 顶层结构

```text
HCE_ROOT/
├─ docs/
├─ tree_diagram/
├─ qcu/
├─ honkai_core/
├─ hce/
├─ shared/
├─ environment/
├─ experiments/
├─ runs/
├─ checkpoints/
├─ logs/
├─ results/
└─ legacy/
```

---

## 10.2 Tree Diagram 结构

```text
tree_diagram/
├─ README.md
├─ pyproject.toml
├─ tree_diagram/
│  ├─ source_basis/
│  ├─ abstracts/
│  ├─ numerics/
│  ├─ pipeline/
│  ├─ io/
│  ├─ runtime/
│  ├─ cli/
│  └─ distributed/
├─ configs/
├─ jobs/
├─ slurm/
├─ mpi/
├─ tests/
└─ examples/
```

### 语义说明
- `source_basis/`：明确两个原型文件共同作为源码基线
- `abstracts/`：seed / background / group field / worldline / ecology
- `numerics/`：weather state / dynamics / forcing / ensemble / ranking
- `pipeline/`：把抽象层与数值层接成 Tree Diagram 主流程

---

## 10.3 QCU 结构

```text
qcu/
├─ README.md
├─ pyproject.toml
├─ qcu/
│  ├─ core/
│  ├─ io/
│  ├─ runtime/
│  ├─ cli/
│  ├─ distributed/
│  └─ workloads/
├─ configs/
├─ jobs/
├─ slurm/
├─ mpi/
├─ tests/
└─ examples/
```

---

## 10.4 Honkai Core 结构

```text
honkai_core/
├─ README.md
├─ pyproject.toml
├─ honkai_core/
│  ├─ theory/
│  ├─ models/
│  ├─ io/
│  ├─ runtime/
│  └─ cli/
├─ configs/
├─ jobs/
├─ slurm/
├─ mpi/
├─ tests/
└─ examples/
```

---

## 10.5 HCE 结构

```text
hce/
├─ README.md
├─ pyproject.toml
├─ hce/
│  ├─ integration/
│  ├─ bridges/
│  ├─ io/
│  ├─ runtime/
│  ├─ cli/
│  └─ tui/
├─ configs/
├─ jobs/
├─ slurm/
├─ mpi/
├─ tests/
└─ examples/
```

---

## 11. I/O 文件落位

### Tree Diagram
- `tree_diagram/io/request_schema.py`
- `tree_diagram/io/tree_output_schema.py`
- `tree_diagram/io/feedback_schema.py`

### QCU
- `qcu/io/state_io.py`
- `qcu/io/sea_output_schema.py`
- `qcu/io/readout_schema.py`

### Honkai Core
- `honkai_core/io/scenario_loader.py`
- `honkai_core/io/risk_schema.py`
- `honkai_core/io/energy_report_writer.py`

### HCE
- `hce/io/request_bundle.py`
- `hce/io/pipeline_schema.py`
- `hce/io/final_report_schema.py`

### HCE integration
- `hce/integration/td_qcu_bridge.py`
- `hce/integration/hc_bridge.py`
- `hce/integration/result_merge.py`
- `hce/integration/writeback_adapter.py`

---

## 12. 运行入口设计

每个系统都必须有三类入口：

### 本地运行
```bash
python -m <system>.cli.run_local --config ...
```

### 集群提交
```bash
python -m <system>.cli.submit --config ...
```

### 结果查看
```bash
python -m <system>.cli.inspect --run-id ...
```

---

## 13. 标准 HPC 底层与学园都市风格上层

### 13.1 底层：标准 HPC 入口
底层继续保留真实的 HPC/集群操作方式，例如：

- `sbatch`
- `srun`
- `squeue`
- `sacct`
- `scontrol`

以及项目内部的工程命令，例如：

- `python -m tree_diagram.cli.submit --config ...`
- `python -m qcu.cli.submit --config ...`
- `python -m honkai_core.cli.submit --config ...`
- `python -m hce.cli.submit --config ...`

这一层的职责是：

- 提交真实作业
- 查询真实作业状态
- 提供底层调试路径
- 保证与超算/训练集群的兼容性

### 13.2 上层：学园都市风格入口
上层不取代 HPC，而是将相同的底层行为重新包装为：

- 学园都市式设施操作
- 中央演算机关式交互
- 更有权限层次感与实验机关气质的入口

例如，上层入口可以表现为：

- 提交演算任务
- 启动树端裁决
- 调用海端显形
- 发起阈值监察
- 申请主线回写
- 查询实验档案
- 切换观测态
- 执行降级

但其内部真正做的事情仍然是：

- 选择配置
- 选择 profile
- 组装 RequestBundle
- 生成或选择 sbatch
- 调用 `sbatch`
- 查询 `squeue / sacct`
- 聚合 logs / results

### 13.3 一句话总结

> **标准 Slurm 是执行内核，学园都市风格入口是语义外壳。**

---

## 14. 学园都市风格要求

HCE 的学园都市风格不应理解为“动漫化”，而应理解为：

> **一个冷静、层级分明、具有城市级实验机关气质的高权限科研演算系统。**

关键词如下：

- 城市级科研基础设施
- 高权限实验系统
- 分级访问
- 机关编号
- 冷静而危险
- 精确而克制
- 观测、裁决、显形、回写、阈值、收容、降级

### 14.1 设施化称呼
推荐对外称呼：

- Tree Diagram：树端裁决设施 / 主线筛选阵列
- QCU：海端显形设施 / 局部坍缩读出机关
- Honkai Core：阈值监察层 / 崩坏能评估机关 / 风险裁决层
- HCE：中央演算中枢 / 整机调度机关

### 14.2 权限层级
建议至少区分四层：

- 观测权限
- 研究员权限
- 高级实验员权限
- 裁决 / 管制权限

### 14.3 实验编号
显示层建议优先使用：

- `TD-EX-0421`
- `QCU-COLLAPSE-07`
- `HC-RISK-A3`
- `HCE-LINK-02`

### 14.4 风险提示风格
推荐用：

- 阈值通报
- 风险裁决
- 回写审查
- 封存建议
- 降级建议
- 观测态维持

而不是只停留在普通的 warning / error 级提示。

---

## 15. 风格验收标准

HCE 的学园都市风格不是靠文案装饰验收，而是靠系统是否能自然承载具有学园都市式规模感与实验机关感的任务来验收。

当前阶段建议把以下两类任务写成 **风格验收标准**。

### 15.1 验收标准 A：2 万御坂妹妹并行个体模拟

系统必须能够自然支持一种“学园都市式大规模并行实验对象”场景。

风格验收示例：

- 以 **2 万御坂妹妹** 为并行个体群
- Tree Diagram 负责个体分组、主线筛选、群体状态分枝管理
- QCU 负责局部显形、同步扰动、局部候选读出
- Honkai Core 负责阈值、群体风险与结构偏转评估
- HCE 负责实验中枢级调度、日志、归档与裁决记录

这里的重点不是二创内容，而是：

> **系统能否自然承载“大规模编号化个体群 + 精确分组 + 演算调度 + 阈值管制”的学园都市式实验场景。**

### 15.2 验收标准 B：大气分子运动模拟

系统必须能够自然支持一种“城市级 / 科学级大规模数值实验”场景。

风格验收示例：

- 大气分子运动模拟
- Tree Diagram 负责候选流场、宏观主线、分支筛选
- QCU 负责局部显形、高维候选扰动、微局部读出
- Honkai Core 负责阈值、能量、风险与结构稳定性评估
- HCE 负责中枢调度与综合报告

这里的重点是：

> **系统既要能承载学园都市式大规模编号实验对象，也要能承载硬科学规模的大气分子运动模拟。**

### 15.3 为什么这两个验收标准必须同时存在

只做“2 万御坂妹妹”会让系统容易滑向设定展示。  
只做“大气分子运动模拟”又会让系统容易退回普通 HPC 平台。

两者同时存在，才说明系统真正达到你要的风格：

- 既有学园都市式编号实验对象与研究机关感
- 又有硬核科学设施与超算级演算感

这才是 **学园都市 + NASA / 超算中心** 的混合气质。

---

## 16. 落盘路径统一规则

所有系统统一写入以下顶层路径：

- `runs/<system>/`
- `checkpoints/<system>/`
- `logs/<system>/`
- `results/<system>/`

其中：

### `runs/`
按 request_id / run_id 存运行实例目录。

### `checkpoints/`
按系统和 run_id 存恢复点。

### `logs/`
存 Slurm 输出、runtime 事件、metrics JSONL。

### `results/`
存最终 Bundle、报告、导出摘要。

---

## 17. 对 Claude 的统一口径

后续任何 Claude 协作都必须默认遵守：

### 17.1
本项目虽然借用了“崩坏”“树海”“律者”“世界泡”等命名，但这里的语境是：

- 理论建模语言
- 系统架构命名
- 高维结构计算与复杂系统工程术语
- 分布式计算与超算部署项目

而不是：
- 游戏模组开发
- 剧情解析
- 角色设定整理
- 二创百科

### 17.2
Tree Diagram 不是单一原型脚本，而是两个 `.py` 共同构成的同一系统原型集合。

### 17.3
树、海、HCE 之间不共享内部对象，只交换 Bundle。

### 17.4
HCE 是桥接层，不垄断 Tree / QCU / HC 的独立运行能力。

### 17.5
第一版只实现单向流水线，不做复杂强耦合。

### 17.6
先保兼容、先保可跑、先保集群可用，再做模块化和风格化。

---

## 18. 当前阶段一次性实现边界

当前阶段最合理的一次性实现范围是：

### 必做
- 四系统目录骨架
- Tree Diagram 双原型基线口径
- Bundle 设计
- 单向标准流水线
- 弱回写
- 双入口设计
- 学园都市风格要求
- 风格验收标准
- 统一落盘路径
- CLI 占位入口
- Slurm / MPI / TUI 占位结构

### 暂不做
- 强回写
- 多轮在线闭环
- 复杂 RPC
- 跨 stage 隐式状态共享
- 过早性能优化
- 过早多语言拆分

---

## 19. 一句话总收口

这套完整设计可以压成一句话：

> **HCE 当前应被实现为一个四系统并列、Tree Diagram 双原型共同取材、树海之间以 Bundle 契约交互、HCE 负责桥接与弱回写控制、底层使用标准 HPC 执行、上层提供学园都市风格入口、并以“2 万御坂妹妹并行个体模拟”和“大气分子运动模拟”作为风格验收标准的 HPC 工程系统。**
