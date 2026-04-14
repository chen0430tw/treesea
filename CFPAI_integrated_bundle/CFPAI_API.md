# CFPAI API 说明

**名称**：CFPAI  
**英文全称**：Computational Finance Planning AI  
**中文全称**：计算金融规划人工智能

---

## 1. 设计目标

CFPAI 的 API 不是单纯暴露一个“预测涨跌”的函数，而是围绕完整规划链路设计：

1. 输入市场多源数据  
2. 生成状态表示  
3. 做动态锚定与反向 MOROZ 展开  
4. 做链式路径搜索  
5. 做 Tree Diagram 网格求值  
6. 输出规划结果、风险预算与动作接口

因此，CFPAI 的 API 更像**规划系统接口**，而不是单头预测器接口。

---

## 2. 核心对象

### 2.1 MarketObservation
表示单时刻市场观测。

```python
@dataclass
class MarketObservation:
    timestamp: str
    features: dict[str, float]
    meta: dict[str, Any] = field(default_factory=dict)
```

### 2.2 AssetObservation
表示单资产单时刻观测。

```python
@dataclass
class AssetObservation:
    symbol: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    extra_features: dict[str, float] = field(default_factory=dict)
```

### 2.3 MarketState
状态表示层输出对象。

```python
@dataclass
class MarketState:
    timestamp: str
    flow_state: dict[str, float]
    risk_state: dict[str, float]
    rotation_state: dict[str, float]
    liquidity_state: dict[str, float]
    latent_vector: list[float]
    meta: dict[str, Any] = field(default_factory=dict)
```

### 2.4 DynamicAnchor
动态锚点对象。

```python
@dataclass
class DynamicAnchor:
    anchor_id: str
    anchor_type: str
    score: float
    description: str
    meta: dict[str, Any] = field(default_factory=dict)
```

### 2.5 DynamicPath
链式搜索输出路径对象。

```python
@dataclass
class DynamicPath:
    path_id: str
    nodes: list[str]
    score: float
    horizon: int
    risk_penalty: float
    meta: dict[str, Any] = field(default_factory=dict)
```

### 2.6 GridNodeValue
Tree Diagram 网格求值节点对象。

```python
@dataclass
class GridNodeValue:
    node_id: str
    utility: float
    propagated_value: float
    meta: dict[str, Any] = field(default_factory=dict)
```

### 2.7 PlanningOutput
最终规划输出对象。

```python
@dataclass
class PlanningOutput:
    timestamp: str
    market_label: str
    selected_paths: list[str]
    risk_budget: float
    actions: dict[str, float]
    diagnostics: dict[str, Any] = field(default_factory=dict)
```

---

## 3. 核心接口

## 3.1 数据接口

### `load_market_data`
读取市场数据。

```python
def load_market_data(source: str, config: dict) -> pd.DataFrame:
    ...
```

支持：
- 本地 CSV
- Stooq
- 其他外部数据源适配器

### `build_features`
构建特征。

```python
def build_features(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    ...
```

输出：
- momentum
- trend_gap
- volatility
- drawdown
- volume_z
- 其他可扩展特征

---

## 3.2 状态表示层接口

### `encode_state`
状态表示层 \(\Phi\)

```python
def encode_state(features: pd.DataFrame, config: dict) -> list[MarketState]:
    ...
```

输入：
- 市场特征表

输出：
- `MarketState` 列表

---

## 3.3 反向 MOROZ 接口

### `detect_anchors`
识别动态锚点。

```python
def detect_anchors(states: list[MarketState], config: dict) -> list[DynamicAnchor]:
    ...
```

### `expand_reverse_moroz`
执行反向 MOROZ 动态展开。

```python
def expand_reverse_moroz(
    state: MarketState,
    anchors: list[DynamicAnchor],
    config: dict
) -> list[dict]:
    ...
```

输出为动态候选对象列表。

---

## 3.4 链式搜索接口

### `search_paths`
执行链式路径搜索。

```python
def search_paths(
    state: MarketState,
    candidates: list[dict],
    config: dict
) -> list[DynamicPath]:
    ...
```

支持：
- Top-K path
- horizon 限制
- persistence bonus
- regime transition penalty

---

## 3.5 Tree Diagram 网格接口

### `build_grid`
构造状态网格。

```python
def build_grid(
    state: MarketState,
    paths: list[DynamicPath],
    config: dict
) -> dict:
    ...
```

### `evaluate_grid`
执行 Tree Diagram 风格网格求值。

```python
def evaluate_grid(grid: dict, config: dict) -> list[GridNodeValue]:
    ...
```

这一层应允许不同求值引擎：

- Local CPU engine
- GPU engine
- Cluster engine
- Tree Diagram high-performance engine

---

## 3.6 规划输出接口

### `plan_actions`
根据路径与网格价值输出规划结果。

```python
def plan_actions(
    state: MarketState,
    paths: list[DynamicPath],
    grid_values: list[GridNodeValue],
    config: dict
) -> PlanningOutput:
    ...
```

输出内容包括：

- 市场状态标签
- 选中路径
- 风险预算
- 动作建议
- 组合权重
- 防御/进攻模式切换

---

## 3.7 UTM 调参接口

### `tune_with_utm`
用 UTM 风格调参。

```python
def tune_with_utm(
    train_data: pd.DataFrame,
    val_data: pd.DataFrame,
    search_space: dict,
    config: dict
) -> dict:
    ...
```

输出：
- 最优参数
- 收缩序列
- 搜索历史
- 最优实验摘要

---

## 4. 高层流水线接口

### `run_cfpai_pipeline`

```python
def run_cfpai_pipeline(
    market_df: pd.DataFrame,
    config: dict
) -> PlanningOutput:
    ...
```

内部应串起：

```text
load/build features
    ↓
encode_state
    ↓
detect_anchors
    ↓
expand_reverse_moroz
    ↓
search_paths
    ↓
build_grid / evaluate_grid
    ↓
plan_actions
```

---

## 5. 多资产接口

### `run_multiasset_pipeline`

```python
def run_multiasset_pipeline(
    asset_dfs: dict[str, pd.DataFrame],
    config: dict
) -> PlanningOutput:
    ...
```

支持：
- 多资产状态表示
- 资本流矩阵
- 板块轮动
- 多资产权重输出

---

## 6. 回测接口

### `backtest_cfpai`

```python
def backtest_cfpai(
    market_df: pd.DataFrame,
    config: dict
) -> dict:
    ...
```

返回：
- 信号序列
- 权重序列
- 组合收益
- 回撤
- Sharpe
- turnover
- cost
- 报告摘要

---

## 7. 推荐目录映射

```text
cfpai/
├─ data/
├─ features/
├─ state/
├─ reverse_moroz/
├─ chain_search/
├─ tree_diagram/
├─ planner/
├─ utm/
├─ backtest/
└─ api/
```

API 文件建议位置：

```text
cfpai/api/
├─ contracts.py
├─ market_api.py
├─ state_api.py
├─ planning_api.py
└─ tuning_api.py
```

---

## 8. 最小调用样例

```python
from cfpai.pipeline import run_cfpai_pipeline
import pandas as pd

df = pd.read_csv("spy.csv")
result = run_cfpai_pipeline(df, config={"mode": "toy"})

print(result.market_label)
print(result.risk_budget)
print(result.actions)
```

---

## 9. 一句话总结

CFPAI API 的本质不是“给一个价格预测值”，而是：

> **给一套从市场状态、动态锚定、链式路径、网格求值到规划动作的完整接口。**
