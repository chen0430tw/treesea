# CFPAI Agent 集成方案

## 文档目的

本文档用于定义 **Agent 如何接入 CFPAI**，并明确：

- Agent 应该放在哪一层
- Agent 与 CFPAI 主系统如何分工
- 工具层、服务层、核心层如何隔离
- 自然语言任务如何映射成规划、回测、调参与诊断操作
- 后续如何从研究型 Agent 逐步扩展到执行型 Agent

一句话原则：

> **CFPAI 负责算，Agent 负责问、调、看、下指令。**

---

## 1. 总体设计原则

CFPAI 本身是一个**计算金融规划系统**，主链为：

```text
状态表示 Φ
→ 反向 MOROZ 动态展开 R
→ 链式搜索 C
→ Tree Diagram 网格求值 T
→ 规划输出 Ψ
```

并由：

```text
UTM
```

作为正式调参与结构校准层。

因此，Agent 的正确接入方式，不是把对话逻辑塞进上述核心链路，而是：

> **把 Agent 放在外层，作为自然语言控制器与工具调度器。**

---

## 2. 三层结构

推荐采用三层结构：

```text
User
 ↓
Agent Layer
 ↓
Service / Tool Layer
 ↓
CFPAI Core
```

### 2.1 CFPAI Core
负责：

- 市场状态表示
- 动态锚定
- 反向 MOROZ 展开
- 链式搜索
- Tree Diagram 网格求值
- 风险预算
- 规划输出
- UTM 调参与回测

它回答的是：

- 市场当前处于什么状态
- 哪些路径值得继续跟踪
- 哪些资产该加权或减权
- 风险预算应收缩到多少
- 参数应如何调优

### 2.2 Service / Tool Layer
负责把核心能力封装成：

- 函数接口
- API 接口
- 工具调用入口
- 报告与诊断接口

它回答的是：

- 这个能力怎么被程序调用
- 自然语言意图怎么映射成具体执行任务
- 不同运行模式怎么被统一管理

### 2.3 Agent Layer
负责：

- 接收自然语言任务
- 识别用户意图
- 选择合适工具
- 调用服务层
- 汇总输出
- 生成解释
- 驱动后续动作

它回答的是：

- 用户想让我做什么
- 我应该跑哪个模式
- 输出应该如何组织
- 下一步是否需要调参、回测、诊断或生成报告

---

## 3. 推荐目录结构

建议在当前仓库上新增：

```text
CFPAI/
├─ cfpai/
│  ├─ service/
│  │  ├─ __init__.py
│  │  ├─ planning_service.py
│  │  ├─ backtest_service.py
│  │  ├─ tuning_service.py
│  │  ├─ diagnostics_service.py
│  │  └─ reporting_service.py
│  │
│  └─ api/
│
├─ agent/
│  ├─ __init__.py
│  ├─ orchestrator.py
│  ├─ router.py
│  ├─ memory.py
│  ├─ prompts/
│  │  ├─ planning_prompt.md
│  │  ├─ tuning_prompt.md
│  │  ├─ diagnostics_prompt.md
│  │  └─ reporting_prompt.md
│  │
│  └─ tools/
│     ├─ planning_tool.py
│     ├─ backtest_tool.py
│     ├─ tuning_tool.py
│     ├─ diagnostics_tool.py
│     └─ reporting_tool.py
│
└─ docs/
   └─ CFPAI_Agent_集成方案.md
```

---

## 4. 模块分工

## 4.1 `cfpai/service/`
这层是对核心引擎的“服务化封装”。

建议职责：

### `planning_service.py`
封装：

- 单次 planning
- 多资产 planning
- 最新权重与风险预算生成
- 最新路径输出

### `backtest_service.py`
封装：

- 单资产回测
- 多资产回测
- Stooq 数据快速回测
- UTM 调参前后对比回测

### `tuning_service.py`
封装：

- UTM 自动调参
- 搜索历史读取
- 最优参数加载
- 最佳 run 输出

### `diagnostics_service.py`
封装：

- 当前锚点解释
- 路径解释
- Tree Diagram 节点值解释
- 权重来源解释
- 风险预算解释

### `reporting_service.py`
封装：

- 结果摘要
- Markdown 报告
- CSV 导出
- 图表导出

---

## 4.2 `agent/tools/`
这是 Agent 真正使用的工具层。

### `planning_tool.py`
负责：

- 调用 planning service
- 接收自然语言参数映射结果
- 输出结构化 planning 结果

建议接口：

```python
def run_planning(
    symbols: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    mode: str = "multiasset",
    config: dict | None = None,
) -> dict:
    ...
```

### `backtest_tool.py`
负责：

- 跑回测
- 返回绩效摘要
- 保存输出路径

建议接口：

```python
def run_backtest(
    symbols: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    use_utm: bool = False,
    config: dict | None = None,
) -> dict:
    ...
```

### `tuning_tool.py`
负责：

- 启动 UTM 调参
- 读取收缩历史
- 输出最优参数

建议接口：

```python
def run_tuning(
    symbols: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    generations: int = 6,
    population: int = 12,
    elite_k: int = 4,
    seed: int = 430,
) -> dict:
    ...
```

### `diagnostics_tool.py`
负责：

- 解释最近一次运行
- 给出锚点、路径、权重与预算来源

建议接口：

```python
def explain_latest_run(run_dir: str) -> dict:
    ...
```

### `reporting_tool.py`
负责：

- 把运行结果组织成 Markdown / JSON / 图表摘要

建议接口：

```python
def build_report(run_dir: str, format: str = "markdown") -> str:
    ...
```

---

## 5. Agent 的职责边界

Agent 需要做的事：

1. 识别用户意图
2. 解析用户给定的约束
3. 选择正确工具
4. 调用工具
5. 组织结果
6. 生成解释
7. 决定是否需要下一步动作

Agent 不应该做的事：

1. 不直接改写 CFPAI 核心算法
2. 不直接穿透到 `state/`、`tree_diagram/` 等内部模块随意改参数
3. 不绕过服务层和工具层
4. 不把聊天逻辑塞进核心包
5. 不把调参逻辑写死在 prompt 里

---

## 6. 自然语言到工具调用的映射

CFPAI Agent 应支持把自然语言任务映射成工具调用。

### 6.1 研究型指令
例如：

- “帮我看一下过去 10 年默认资产池的多资产回测”
- “比较 UTM 调参前后差异”
- “把最新 regime 路径和资产权重列出来”

映射为：

- `backtest_tool.run_backtest(...)`
- `tuning_tool.run_tuning(...)`
- `diagnostics_tool.explain_latest_run(...)`

### 6.2 规划型指令
例如：

- “现在跑一次 planning”
- “用默认资产池给出今天的风险预算和权重”
- “看当前最值得跟踪的三条路径”

映射为：

- `planning_tool.run_planning(...)`

### 6.3 调参型指令
例如：

- “再用 UTM 搜一轮”
- “只优化回撤和 Sharpe”
- “把 generations 提高到 12”

映射为：

- `tuning_tool.run_tuning(...)`
- 并调整目标函数与搜索配置

### 6.4 诊断型指令
例如：

- “为什么这次偏向 TLT 和 GLD”
- “哪一个锚点触发了当前路径”
- “Tree Diagram 哪些节点得分最高”

映射为：

- `diagnostics_tool.explain_latest_run(...)`

---

## 7. 推荐的 Orchestrator 逻辑

建议在 `agent/orchestrator.py` 中实现一个简单调度器。

### 输入
- 用户自然语言
- 上下文
- 最近运行记录
- 当前配置

### 输出
- 选中的工具
- 结构化参数
- 工具执行结果
- 解释文本

### 简化流程

```text
User Request
    ↓
Intent Router
    ↓
Argument Mapper
    ↓
Tool Selection
    ↓
Service Call
    ↓
Result Parser
    ↓
Agent Explanation
```

---

## 8. Router 的推荐分类

可以把用户请求先分成五类：

1. `planning`
2. `backtest`
3. `tuning`
4. `diagnostics`
5. `reporting`

例如：

```python
def classify_intent(text: str) -> str:
    ...
```

映射逻辑大致如下：

- 含 “权重 / 风险预算 / 现在怎么看” → `planning`
- 含 “回测 / 历史 / 表现 / 跑一下过去” → `backtest`
- 含 “调参 / UTM / 搜索 / generations” → `tuning`
- 含 “为什么 / 解释 / 哪个锚点 / 哪条路径” → `diagnostics`
- 含 “整理 / 输出文档 / 报告” → `reporting`

---

## 9. Memory 的作用

Agent 可以有轻量 memory，用来记住：

- 最近一次使用的资产池
- 最近一次运行的时间区间
- 最近一次 UTM 参数配置
- 最近一次输出目录
- 最近一次最优参数文件

例如：

```text
memory/
- last_symbols
- last_start
- last_end
- last_run_dir
- last_best_params
```

这样用户说：

- “再跑一轮”
- “用刚刚那组参数”
- “把前面的结果解释一下”

Agent 就能接上，而不用每次重问全部上下文。

---

## 10. 推荐的最小可用版本（MVP）

第一阶段不做“自动交易 Agent”，只做：

### 10.1 Research Agent
负责：
- 回测
- 调参
- 结果摘要
- 报告生成

### 10.2 Planning Agent
负责：
- 最新状态规划
- 资产权重
- 风险预算
- 路径输出

### 10.3 Diagnostics Agent
负责：
- 解释结果
- 解释路径
- 解释预算与权重来源

也就是说，第一阶段 Agent 的主要角色是：

> **研究与规划控制器**

而不是：
> **直接自动下单的执行代理**

---

## 11. 为什么不建议一开始就做执行型 Agent

原因很简单：

1. 当前 CFPAI 还处于结构验证和原型推进阶段；
2. 自动执行会引入：
   - 账户接口
   - 下单安全
   - 滑点
   - 成本
   - 失败重试
   - 风险上限
3. 这些复杂度会把主系统开发节奏拖慢。

因此，推荐路径是：

### Stage 1
研究 / 回测 / 规划 / 诊断 Agent

### Stage 2
模拟执行 Agent

### Stage 3
真实执行 Agent（如果未来有需要）

---

## 12. Service vs Tool vs Agent 的边界

### Service
回答：
- “核心系统怎么被程序调用”

### Tool
回答：
- “Agent 应该调用哪个功能”

### Agent
回答：
- “用户这句话到底想让我做什么”

三个层次一定要分开。

如果把它们混在一起，就会出现：

- 核心系统被对话逻辑污染
- 工具接口难以测试
- Agent prompt 和主系统实现耦合
- 后期难以替换模型或执行方式

---

## 13. 推荐的最小文件清单

建议最少先新增这些文件：

```text
cfpai/service/planning_service.py
cfpai/service/backtest_service.py
cfpai/service/tuning_service.py
cfpai/service/diagnostics_service.py

agent/orchestrator.py
agent/router.py
agent/memory.py

agent/tools/planning_tool.py
agent/tools/backtest_tool.py
agent/tools/tuning_tool.py
agent/tools/diagnostics_tool.py
agent/tools/reporting_tool.py
```

---

## 14. 一句话工作流示例

### 例 1：用户问
> “现在默认资产池跑一次 planning，给我最新权重和风险预算”

执行：

1. router 识别为 `planning`
2. planning tool 调 `planning_service`
3. CFPAI Core 生成输出
4. Agent 解释：
   - 当前状态
   - 主要路径
   - 权重
   - 风险预算

### 例 2：用户问
> “用 UTM 再调一轮，多看 Sharpe 和回撤”

执行：

1. router 识别为 `tuning`
2. tuning tool 调 `tuning_service`
3. UTM 跑搜索
4. Agent 输出：
   - 最优参数
   - 收缩历史
   - 调参结果摘要

### 例 3：用户问
> “为什么这次偏向债券和黄金”

执行：

1. router 识别为 `diagnostics`
2. diagnostics tool 调 `diagnostics_service`
3. 从最近 run 中取：
   - anchors
   - paths
   - grid values
   - risk budget
4. Agent 生成可读解释

---

## 15. 最终结论

CFPAI 的 Agent 集成原则可以压成一句话：

> **把 Agent 放在外层，作为自然语言控制器与工具调度器；把 Service 作为核心能力封装层；把 CFPAI Core 保持为独立、可测试、可复用的规划引擎。**

因此，最佳分层是：

- **CFPAI Core**：负责算
- **Service / Tool Layer**：负责调
- **Agent Layer**：负责理解用户并组织结果

这条分层能保证：

1. 系统边界清晰  
2. 工程结构可扩展  
3. 后续能平滑从研究型 Agent 扩展到执行型 Agent  
4. 不会把 CFPAI 退化成一个“会聊天的量化脚本”

---

## 16. 最短总结版

> **Agent 的正确导入方式，不是塞进 CFPAI 内核，而是作为外层控制器，通过工具层和服务层调度 CFPAI 的规划、回测、调参与诊断能力。**
