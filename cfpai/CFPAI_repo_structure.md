# CFPAI 仓库结构说明

## 文档目的

本文档用于定义 CFPAI 的推荐文件结构、模块边界与后续工程拆分原则。  
目标是避免把状态表示、动态锚定、路径搜索、网格求值、规划输出和 UTM 调参全部混写成单个巨文件。

---

## 1. 顶层结构

```text
CFPAI/
├─ docs/
├─ configs/
├─ data/
├─ outputs/
├─ runs/
├─ scripts/
├─ tests/
├─ cfpai/
│  ├─ api/
│  ├─ contracts/
│  ├─ data/
│  ├─ features/
│  ├─ state/
│  ├─ reverse_moroz/
│  ├─ chain_search/
│  ├─ tree_diagram/
│  ├─ planner/
│  ├─ utm/
│  ├─ backtest/
│  ├─ interfaces/
│  └─ utils/
└─ archive/
```

---

## 2. docs/

### `docs/`
放正式文档：

- `CFPAI_技术白皮书.md`
- `CFPAI_API.md`
- `CFPAI_repo_structure.md`
- `Claude_CFPAI_工作指南.md`

---

## 3. configs/

### `configs/`
放配置：

```text
configs/
├─ toy/
├─ benchmark/
├─ multiasset/
├─ utm/
└─ production/
```

建议内容：

- 特征开关
- 风险预算参数
- Tree Diagram 网格参数
- UTM 搜索空间
- 回测参数
- 输出模式

---

## 4. data/

### `data/`
放原始或中间数据：

```text
data/
├─ raw/
├─ processed/
├─ stooq/
└─ snapshots/
```

---

## 5. outputs/ 与 runs/

### `outputs/`
放：
- 图表
- 汇总 CSV
- 报告 md

### `runs/`
放：
- 实验 run
- checkpoints
- logs
- tuned params
- diagnostics

---

## 6. cfpai 核心包结构

### `cfpai/contracts/`
定义边界对象。

建议文件：

```text
cfpai/contracts/
├─ market_types.py
├─ state_types.py
├─ path_types.py
├─ grid_types.py
└─ planning_types.py
```

### `cfpai/data/`
负责数据源接入。

建议文件：

```text
cfpai/data/
├─ csv_loader.py
├─ stooq_loader.py
├─ aligner.py
└─ universe_builder.py
```

### `cfpai/features/`
负责特征构造。

建议文件：

```text
cfpai/features/
├─ price_features.py
├─ flow_features.py
├─ risk_features.py
├─ rotation_features.py
└─ feature_pipeline.py
```

### `cfpai/state/`
负责状态表示层 \(\Phi\)。

建议文件：

```text
cfpai/state/
├─ encoder.py
├─ flow_state.py
├─ risk_state.py
├─ rotation_state.py
└─ liquidity_state.py
```

### `cfpai/reverse_moroz/`
负责动态锚定与反向 MOROZ 展开。

建议文件：

```text
cfpai/reverse_moroz/
├─ anchors.py
├─ expansion.py
├─ scoring.py
└─ filters.py
```

### `cfpai/chain_search/`
负责路径搜索。

建议文件：

```text
cfpai/chain_search/
├─ path_builder.py
├─ scoring.py
├─ transition_rules.py
└─ topk.py
```

### `cfpai/tree_diagram/`
负责网格求值。

建议文件：

```text
cfpai/tree_diagram/
├─ grid_builder.py
├─ node_utility.py
├─ propagation.py
├─ engines.py
└─ result_aggregator.py
```

### `cfpai/planner/`
负责输出动作、仓位、预算。

建议文件：

```text
cfpai/planner/
├─ action_space.py
├─ risk_budget.py
├─ allocator.py
└─ output_mapper.py
```

### `cfpai/utm/`
负责 UTM 调参与结构校准。

建议文件：

```text
cfpai/utm/
├─ search_space.py
├─ contraction.py
├─ dimension_matrix.py
├─ tuner.py
└─ diagnostics.py
```

### `cfpai/backtest/`
负责回测与评估。

建议文件：

```text
cfpai/backtest/
├─ engine.py
├─ metrics.py
├─ report.py
└─ plots.py
```

### `cfpai/api/`
负责高层调用接口。

建议文件：

```text
cfpai/api/
├─ market_api.py
├─ state_api.py
├─ planning_api.py
└─ tuning_api.py
```

---

## 7. 模块边界原则

### 原则 1：状态表示与动态展开分离
- `state/` 只负责表征市场状态
- `reverse_moroz/` 只负责从状态出发做动态锚定与展开

### 原则 2：链式搜索与网格求值分离
- `chain_search/` 只负责找路径
- `tree_diagram/` 只负责对路径映射的状态网格做求值

### 原则 3：规划输出与回测分离
- `planner/` 只负责生成动作和预算
- `backtest/` 只负责评估

### 原则 4：UTM 不吞掉主系统
- `utm/` 是调参与结构校准层
- 不是主系统本体
- 不能把状态表示、路径搜索、网格求值逻辑硬塞进 `utm/`

---

## 8. 推荐的最小 pipeline 文件

```text
cfpai/
├─ pipeline.py
├─ multiasset_pipeline.py
└─ tuning_pipeline.py
```

### `pipeline.py`
单资产主链

### `multiasset_pipeline.py`
多资产主链

### `tuning_pipeline.py`
UTM 自动调参主链

---

## 9. 当前阶段推荐优先级

### Priority A
1. `data/stooq_loader.py`
2. `features/feature_pipeline.py`
3. `state/encoder.py`
4. `reverse_moroz/anchors.py`
5. `chain_search/path_builder.py`
6. `tree_diagram/grid_builder.py`
7. `planner/output_mapper.py`

### Priority B
8. `utm/tuner.py`
9. `backtest/engine.py`
10. `backtest/report.py`

### Priority C
11. 实时化接口
12. 更高阶 Tree Diagram 引擎
13. 可视化 dashboard

---

## 10. 一句话总结

CFPAI 的仓库结构应该体现它的系统本质：

> **状态表示、动态锚定、路径搜索、网格求值、规划输出与 UTM 调参必须分层清晰，不能混成一个量化脚本仓库。**
