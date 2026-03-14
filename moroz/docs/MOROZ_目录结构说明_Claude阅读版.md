# MOROZ 目录结构说明（Claude 阅读版）

## 文档目的

本文档用于把 `MOROZ_package_v5` 当前的目录结构，转换成更适合 Claude 或其他接手者快速阅读的说明版。

它回答的问题不是“某个理论是什么”，而是：

- 这个包里每一层文件是干什么的
- 哪些是正式文档
- 哪些是源码骨架
- 哪些是原始上传参考
- 下一步应该从哪里开始接手

---

## 顶层

```text
MOROZ_package_v5/
```

### `README.md`
总包说明。  
作用：

- 告诉接手者这是什么包
- 说明包里分成源码骨架、文档、原始上传参考三层
- 给出后续迁移方向

### `MANIFEST.json`
清单文件。  
作用：

- 记录当前包里包含了哪些关键内容
- 方便快速核对是否漏文件

---

## `docs/`

这是**正式文档层**，不是源码。

### `docs/api/`
#### `MOROZ_API.md`
MOROZ 总系统 API 说明。  
作用：

- 定义 MOROZ 暴露什么接口
- 说明它不是 QCU 内核 API
- 适合给接手者先理解系统入口

### `docs/whitepaper/`
#### `MOROZ_技术白皮书_扩展版.md`
当前保留的唯一白皮书版本。  
作用：

- 给出 MOROZ 的正式定义
- 包含 MSCM / K-Warehouse / ISSC / HCE 的理论框架
- 是理解系统定位的主文档

### `docs/architecture/`
#### `repo_structure.md`
仓库结构规划说明。  
作用：

- 定义 MOROZ、QCU、HCE、contracts 的边界
- 说明目录为什么这样切
- 是工程拆分的主参考

#### `Claude_工作指南与协作规范.md`
专门给 Claude 的协作文档。  
作用：

- 告诉 Claude 不能乱改系统定义
- 告诉它先对位迁移，再重构
- 告诉它哪些是核心边界，哪些是参考上传包

### `docs/narrative/`
#### `MOROZ_传说叙事抽象文档.md`
抽象总结前面关于 MOROZ 传说感的演绎。

#### `MOROZ_神秘感品牌叙事计划书_合法公开版.md`
偏品牌叙事与对外语气控制。

#### `MOROZ_神秘感与传说叙事整合文档.md`
把上面两类叙事合并后的统一版本。  
作用：

- 给后续 README、海报、控制台文案、品牌说明用

---

## `archive/`

这是**原始参考层**，不是正式工程目录。

### `archive/uploads/`
这里放你上传的原始材料。

#### `MOROZ代码.txt`
最重要的文本参考源之一。  
作用：

- 包含你前面贴给我的 MOROZ 理论、命名、定义、结构、算法思路
- 后续很多骨架就是按这个拆出来的

#### `MOROZ_API.md`
原始上传版 API 文档参考。

#### `MOROZ_技术白皮书.md`
原始上传版白皮书参考。  
注意：

- 正式保留版本在 `docs/whitepaper/` 里是“扩展版”
- 这里这个更像原始参考底稿

#### `HCE_complete_integrated_with_agent_ssh.zip`
你上传的 HCE 相关源码压缩包。  
作用：

- 后续应对位拆到 `moroz/hce/`

#### `QCU_调度工程完整版压缩包.zip`
你上传的 QCU 相关源码压缩包。  
作用：

- 后续应对位拆到 `qcu/runtime/` 和 `qcu/opu/`

### `archive/extracted_reference/`
目前是预留目录。  
作用：

- 以后可以把上传 zip 解出来放这里做“原始参考展开层”
- 不建议直接把这里当正式工程目录

---

## `moroz/`

这是**MOROZ 主系统骨架层**。

### `moroz/__init__.py`
包入口。

### `moroz/contracts/`
这是**边界层**，很重要。

#### `types.py`
定义核心对象，比如：

- `FrontierCandidate`
- `CollapseCandidate`

#### `request.py`
定义：

- `BudgetSpec`
- `StopPolicy`
- `CollapseRequest`

#### `result.py`
定义：

- `RuntimeStats`
- `CollapseResult`

#### `serialization.py`
定义对象序列化 / 反序列化。  
作用：

- 让 MOROZ 与 backend、CLI、Agent 之间说同一种对象语言

### `moroz/adapters/`
这是**翻译层**，负责把 MOROZ 前端接到 QCU。

#### `qcu_mapping_rules.py`
放 feature → QCU 参数/提示 的映射规则

#### `request_mapper.py`
把 `CollapseRequest` 转成 runtime 可吃的 `RuntimeConfig`

#### `result_adapter.py`
把 QCU runtime 的结果转回 `CollapseResult`

### `moroz/backends/`
这是**后端接口层**。

#### `base.py`
定义 backend 抽象接口

#### `qcu_backend.py`
把 MOROZ 接到 QCU runtime 的最小骨架

### `moroz/core/`
这是**算法核心层**。

#### `types.py`
定义：

- `SourceToken`
- `Candidate`
- `FeatureWeights`
- `ScoreBreakdown`
- `SearchMetrics`

#### `mscm.py`
MSCM 骨架。  
作用：

- 组织 source pool
- 统一打分
- 输出候选权重

#### `k_warehouse.py`
K-Warehouse 骨架。  
作用：

- best-first / top-k / upper bound / gate
- 候选压缩与优先搜索

#### `metrics.py`
统计层。  
作用：

- entropy
- top-q coverage
- retention ratio
- effective throughput

#### `issc.py`
ISSC 骨架。  
作用：

- 对 ranked 候选做收缩统计封装
- 输出 collapse stats

#### `moroz_core.py`
MOROZ-Core 主入口。  
作用：

- 串起 MSCM → K-Warehouse → ISSC

### `moroz/hce/`
这是**运行层骨架**。

#### `moroz_hce.py`
MOROZ-HCE 骨架。  
作用：

- run_id
- run_dir
- shard
- checkpoint
- summary
- global top 合并

### `moroz/examples/`
示例层。

#### `demo_sources.py`
示例 source 占位文件

#### `run_moroz_core_demo.py`
最小 MOROZ-Core demo

#### `run_moroz_hce_demo.py`
最小 MOROZ-HCE demo

### `moroz/tests/`
测试骨架。

#### `test_mscm.py`
MSCM 最小测试

#### `test_k_warehouse.py`
K-Warehouse 最小测试

#### `test_issc.py`
ISSC 最小测试

### `moroz/configs/`
配置层。

#### `core/demo_small.json`
core demo 配置

#### `hce/local_run.json`
HCE 本地运行配置

#### `sources/toy_cat.json`
toy cat 示例源配置

### `moroz/runs/`
运行目录预留。  
作用：

- 以后给 run 产物、checkpoint、summary 用

---

## `qcu/`

这是**QCU 骨架层**，目前还是 stub 级，不是上传包里的真实 runtime 全量拆分版。

### `qcu/__init__.py`
QCU 包入口

### `qcu/runtime/`
真实坍缩设施应该放这里，目前是最小骨架。

#### `state.py`
定义 runtime state

#### `qcu_runner.py`
当前最小 QCU runner。  
作用：

- 吃 `RuntimeConfig`
- 模拟 collapse score
- 调 OPU
- 输出 runtime result

### `qcu/opu/`
QCU 内部治理层骨架。

#### `controller.py`
定义：

- `ControlAction`
- `OPUController`

#### `policies.py`
默认 OPU policy

#### `signals.py`
一些简单 signal 函数

#### `governance.py`
治理入口占位

### `qcu/profiles/`
不同模式的 profile 参数占位。

#### `toy.py`
toy profile

#### `benchmark.py`
benchmark profile

#### `real.py`
real profile

---

## 当前这个包的本质

这不是完整成品仓库，而是：

### 1. 文档层
告诉你 MOROZ 是什么、边界怎么切、后续怎么协作

### 2. 骨架层
先把：

- contracts
- adapters
- backends
- core
- hce
- qcu runtime / opu / profiles

这些关键位置占住

### 3. 原始参考层
保留你上传的：

- QCU zip
- HCE zip
- MOROZ 理论文档

这样后续 Claude 或其他 Agent 不会从零乱猜，而是可以**对位迁移**。

---

## 现在最该做的事

如果给 Claude 接手，最合理的顺序是：

### 第一步
先看：

- `docs/whitepaper/MOROZ_技术白皮书_扩展版.md`
- `docs/architecture/repo_structure.md`
- `docs/architecture/Claude_工作指南与协作规范.md`
- `archive/uploads/MOROZ代码.txt`

### 第二步
从：

- `archive/uploads/QCU_调度工程完整版压缩包.zip`

把真实 QCU 源码拆出来，对位迁移到：

- `qcu/runtime/`
- `qcu/opu/`
- `qcu/profiles/`

### 第三步
从：

- `archive/uploads/HCE_complete_integrated_with_agent_ssh.zip`

把真实 HCE 调度层拆出来，对位迁移到：

- `moroz/hce/`

### 第四步
用 adapter 和 contracts 把：

- MOROZ-Core
- QCU runtime
- HCE

三者真正接成完整链路。
