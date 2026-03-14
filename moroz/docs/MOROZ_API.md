# MOROZ API 说明

## 概述

MOROZ 的 API 只负责**总系统编排、前端压缩、任务投递、结果汇总**。  
它不是 QCU 内核 API，也不是 OPU runtime API。

一句话：

> MOROZ API 管“送什么进去、拿什么回来、怎么组织流程”，不管 QCU 内部怎么坍缩。

---

## 设计原则

1. **MOROZ 只暴露系统级接口**
2. **QCU / OPU 细节不直接泄漏到 MOROZ 外层**
3. **前端候选与后端坍缩解耦**
4. **toy / benchmark / real 模式统一走同一套 API 语义**
5. **请求对象稳定，后端实现可替换**

---

## API 分层

MOROZ API 推荐分成四组：

- 配置与构建
- 候选压缩
- 坍缩任务投递
- 结果与诊断

---

## 1. 配置与构建 API

### `MOROZConfig`

用于定义 MOROZ 总运行配置。

```python
@dataclass
class MOROZConfig:
    profile: str
    max_len: int
    frontier_size: int = 50
    search_budget: int = 10000
    collapse_backend: str = "qcu"
    mapping_policy: str = "default"
    diagnostics_level: int = 1
    trace_enabled: bool = False
```

字段说明：

- `profile`：运行档位，如 `toy`、`benchmark`、`real`
- `max_len`：候选最大长度
- `frontier_size`：送入后端坍缩的候选数量
- `search_budget`：前端搜索预算
- `collapse_backend`：后端名称，默认 `qcu`
- `mapping_policy`：frontier 到后端参数空间的映射规则
- `diagnostics_level`：诊断等级
- `trace_enabled`：是否启用 trace

---

### `build_moroz(config: MOROZConfig) -> MOROZSystem`

构造 MOROZ 系统对象。

```python
system = build_moroz(config)
```

返回值：

- `MOROZSystem`

---

## 2. 候选压缩 API

### `ingest_sources(...)`

导入候选源。

```python
system.ingest_sources(
    common_tokens=[...],
    personal_tokens=[...],
    domain_tokens=[...],
    context_tokens=[...],
    external_tokens=[...],
)
```

作用：

- 将常用词、个人线索、domain 线索、上下文词等注册进 MOROZ
- 交给 MSCM 做统一建模

---

### `build_candidates() -> list[FrontierCandidate]`

构建基础候选池。

```python
pool = system.build_candidates()
```

返回值：

- 候选对象列表

说明：

- 这里输出的是**前端候选**
- 还不是 QCU runtime 的内部对象

---

### `rank_candidates() -> list[FrontierCandidate]`

对候选做静态排序。

```python
ranked = system.rank_candidates()
```

作用：

- 调用 MSCM + K-Warehouse 的前端评分与优先搜索逻辑
- 输出已经排序好的前端候选

---

### `build_frontier(top_n: int | None = None) -> list[FrontierCandidate]`

生成 frontier。

```python
frontier = system.build_frontier(top_n=50)
```

作用：

- 从前端候选里截取高价值工作区
- 作为后端坍缩输入

如果 `top_n` 为空，则默认使用配置中的 `frontier_size`

---

## 3. 坍缩任务投递 API

### `make_request(frontier: list[FrontierCandidate]) -> CollapseRequest`

把 frontier 封装为标准任务请求。

```python
req = system.make_request(frontier)
```

返回对象：

- `CollapseRequest`

作用：

- 统一 MOROZ -> QCU 的请求格式
- 便于本地、benchmark、集群三种模式共用

---

### `submit(req: CollapseRequest) -> CollapseResult`

提交给后端坍缩引擎。

```python
result = system.submit(req)
```

作用：

- 将请求送入指定 backend
- backend 可能是：
  - toy qcu
  - benchmark qcu
  - real qcu
  - mock backend

返回：

- `CollapseResult`

---

### `run() -> CollapseResult`

一键跑完整流程。

```python
result = system.run()
```

完整流程：

1. ingest sources
2. build candidates
3. rank candidates
4. build frontier
5. make request
6. submit to backend
7. aggregate result

这是 MOROZ 最推荐的总入口。

---

## 4. 结果与诊断 API

### `get_frontier() -> list[FrontierCandidate]`

返回最近一次 frontier。

```python
frontier = system.get_frontier()
```

---

### `get_result() -> CollapseResult | None`

返回最近一次坍缩结果。

```python
result = system.get_result()
```

---

### `get_stats() -> dict`

返回 MOROZ 侧统计。

```python
stats = system.get_stats()
```

建议包含：

- candidate_count
- frontier_size
- search_elapsed_sec
- collapse_elapsed_sec
- total_elapsed_sec
- retention_ratio
- entropy
- top_q_coverage

---

### `explain_candidate(text: str) -> dict`

解释某个候选为何在前端被排到当前位置。

```python
explain = system.explain_candidate("catcloudmimi")
```

建议输出：

- source layers
- static features
- template tags
- base score
- frontier membership
- collapse result（如果存在）

---

### `export_summary(path: str) -> None`

导出运行摘要。

```python
system.export_summary("outputs/run_summary.json")
```

---

## 核心对象

### `FrontierCandidate`

MOROZ 前端输出给后端的标准候选对象。

```python
@dataclass
class FrontierCandidate:
    text: str
    base_score: float
    source_layers: list[str]
    features: dict[str, float]
    template_tags: list[str]
    provenance: dict[str, Any]
    meta: dict[str, Any]
```

---

### `CollapseRequest`

MOROZ 发给后端的标准请求。

```python
@dataclass
class CollapseRequest:
    request_id: str
    task_id: str
    profile: str
    candidates: list[FrontierCandidate]
    budget: dict[str, Any]
    mapping_policy: str
    stop_policy: dict[str, Any]
    meta: dict[str, Any]
```

---

### `CollapseResult`

后端回写给 MOROZ 的标准结果。

```python
@dataclass
class CollapseResult:
    request_id: str
    status: str
    ranked: list[CollapseCandidate]
    runtime_stats: dict[str, Any]
    stop_reason: str
    diagnostics: dict[str, Any]
    meta: dict[str, Any]
```

---

## 推荐的 `MOROZSystem` 接口草图

```python
class MOROZSystem:
    def ingest_sources(self, **kwargs) -> None: ...
    def build_candidates(self) -> list[FrontierCandidate]: ...
    def rank_candidates(self) -> list[FrontierCandidate]: ...
    def build_frontier(self, top_n: int | None = None) -> list[FrontierCandidate]: ...
    def make_request(self, frontier: list[FrontierCandidate]) -> CollapseRequest: ...
    def submit(self, req: CollapseRequest) -> CollapseResult: ...
    def run(self) -> CollapseResult: ...
    def get_frontier(self) -> list[FrontierCandidate]: ...
    def get_result(self) -> CollapseResult | None: ...
    def get_stats(self) -> dict: ...
    def explain_candidate(self, text: str) -> dict: ...
    def export_summary(self, path: str) -> None: ...
```

---

## 最小调用示例

```python
config = MOROZConfig(
    profile="benchmark",
    max_len=3,
    frontier_size=50,
    search_budget=10000,
    collapse_backend="qcu",
)

system = build_moroz(config)

system.ingest_sources(
    common_tokens=["cat", "kitty", "kitten"],
    personal_tokens=["mimi", "luna"],
    domain_tokens=["cloud", "mail"],
    context_tokens=["photo", "home"],
)

result = system.run()

print(result.status)
print(result.ranked[:5])
```

---

## MOROZ API 不做什么

MOROZ API 不负责：

- 不直接暴露 QCU 内部物理参数
- 不直接暴露 OPU runtime 控制细节
- 不做真实验证器接口
- 不把 toy benchmark 逻辑硬写成正式 API
- 不替代 QCU 内核

---

## 版本模式建议

建议 MOROZ API 支持三种模式，但保持相同语义：

### `toy`
- 快速试验
- 缩配后端
- 小词表

### `benchmark`
- 方法对照
- 稳定指标
- 可复现

### `real`
- 真实后端
- 完整 pipeline
- 系统级统计

三种模式都应保持：

- `build_frontier()`
- `make_request()`
- `submit()`
- `run()`

这些入口名称不变。

---

## 一句话总结

> MOROZ API 的职责，是把“候选建模 -> frontier 压缩 -> 坍缩请求 -> 结果汇总”这条链路标准化；它是总系统 API，不是 QCU 内核 API。
