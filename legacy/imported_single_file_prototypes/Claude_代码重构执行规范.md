# Claude 代码重构执行规范
## HCE / 崩坏能演算器项目源码整理与重构规范

**对象**：Claude / 代码代理 / 协作型 AI  
**用途**：指导协作代理对 HCE（崩坏能演算器）项目进行源码考古、结构拆分、模块清理与发布版重构。  
**适用范围**：Colab 母脚本、Jupyter Notebook、单文件研发档案、实验脚本、理论文档与运行时整合。

---

# 0. 总原则

本项目不是普通应用开发，也不是游戏模组工程。  
它是一个由 **Tree Diagram / QCU / Honkai Core** 三大系统构成的高维结构演算项目。

因此重构时必须遵守以下总原则：

1. **先保结构，再做清理**
2. **先分层，再抽象**
3. **先考古，再发布**
4. **理论名词不随意删除或降格**
5. **总项目一体化，子模块独立化**

如果你只记一句：

> **不要把研发母脚本当垃圾代码清扫；先把它当考古现场。**

---

# 1. 重构目标

重构的目标不是“把代码改漂亮”这么简单，而是同时完成四件事：

## 1.1 结构恢复
把 Colab / Notebook / 单文件混合源码恢复成：

- Tree Diagram 子系统
- QCU 子系统
- Honkai Core 子系统
- Engine / Runtime 统一编排层

## 1.2 语义保真
确保以下术语在代码与文档中保持稳定含义：

- 主线
- 坍缩
- 崩坏
- 崩坏能
- 树端 / 海端
- 世界泡
- 律者
- Oracle
- 限幅 / 风险 / 阈值

## 1.3 工程可维护
重构后应支持：

- 模块独立测试
- 清晰导入关系
- 独立运行 labs
- Runtime 总控
- 文档自动对照

## 1.4 发布准备
最终重构结果应能支持：

- clean source tree
- docs 对齐
- CLI / runtime 入口
- tests
- 后续硬件 / SoC 架构映射

---

# 2. 输入源类型与处理优先级

本项目常见输入源有三类：

## 2.1 Colab / Notebook 完整导出
特点：
- 可能包含多轮迭代
- 同类类定义重复出现
- 中间夹实验日志、print 输出、可视化
- 代码顺序不代表最终模块边界

处理原则：
- 先定位“最后一版完整实现”
- 再定位“早期但有价值的实验分支”
- 不要一上来就按出现顺序切文件

## 2.2 单文件研发母脚本
特点：
- 多项目拼接
- 旧版函数残留
- 实验段和正式段混写
- 注释可能缺失

处理原则：
- 先做主题分区
- 再做模块抽取
- 原档必须保留 archive 版

## 2.3 白皮书 / 理论文档
特点：
- 包含术语、模块定位、边界定义
- 是代码分层的重要语义依据

处理原则：
- 代码重构必须参考理论文档
- 不可只凭程序结构猜含义

---

# 3. 目录规范

默认按以下目录重构：

```text
hce-system/
├─ README.md
├─ docs/
│  ├─ whitepapers/
│  ├─ theory/
│  └─ architecture/
│
├─ tree_diagram/
│  ├─ core/
│  ├─ oracle/
│  ├─ ecology/
│  ├─ hydrology/
│  ├─ experiments/
│  └─ README.md
│
├─ qcu/
│  ├─ core/
│  ├─ collapse/
│  ├─ shor_lab/
│  ├─ hash_lab/
│  ├─ hmpl_lab/
│  ├─ runtime/
│  └─ README.md
│
├─ honkai_core/
│  ├─ energetics/
│  ├─ modulation/
│  ├─ limiter/
│  ├─ risk/
│  ├─ worldbubble/
│  ├─ herrscher/
│  └─ README.md
│
├─ engine/
│  ├─ runtime/
│  ├─ scheduler/
│  ├─ writeback/
│  ├─ orchestration/
│  └─ README.md
│
├─ archive/
├─ demos/
├─ tests/
└─ scripts/
```

---

# 4. 模块识别规则

---

## 4.1 Tree Diagram 识别规则

看到以下关键词、类或逻辑，应优先归入 `tree_diagram/`：

- worldline
- mainline
- ecology
- withered / starved / active / restricted
- oracle
- hydrology
- IPL
- UMDST
- VFT
- H-UTM
- balance / branch / resource controller

### 典型归属
- 世界线生成器
- 主线评分器
- 分支生态模拟器
- 资源分配器
- 神谕输出层

---

## 4.2 QCU 识别规则

看到以下关键词、类或逻辑，应优先归入 `qcu/`：

- candidate pool
- collapse
- phase engine
- local emergence
- IQPU / QCU
- shor
- hash
- prefix zero
- reverse hash
- collision
- hmpl
- local readout
- writeback scheduler

### 典型归属
- 虚拟量子芯片核心类
- 候选态池
- 局部坍缩检测器
- 显形执行器
- Hash / Shor / HMPL 实验层

---

## 4.3 Honkai Core 识别规则

看到以下关键词、类或逻辑，应优先归入 `honkai_core/`：

- honkai energy
- energetics
- limiter
- threshold
- risk
- herrscher
- world bubble
- imaginary tree
- sea of quanta
- modulation
- gain / loss / density
- end-state / terminal / collapse risk

### 典型归属
- 崩坏能状态方程
- 增益 / 消耗计量
- 限幅器
- 风险监测器
- 律者化阈值判定
- 世界泡与终焉前态逻辑

---

# 5. 重构流程

---

## Phase 1：原档冻结

### 必做
- 把原始 `.py` / `.ipynb` 原样放进 `archive/`
- 文件名保留原始来源与日期
- 绝不直接在 archive 上改

### 命名建议
- `archive/colab_untitled2_raw.py`
- `archive/colab_Untitled4_raw.ipynb`

---

## Phase 2：源码考古

### 必做
- 扫描所有类、函数、入口运行块
- 识别重复实现
- 标出“最后一版完整实现”
- 标出“早期但有价值实验段”

### 产出
- `docs/architecture/source_map.md`

其中至少包含：

- 哪些单元属于 Tree Diagram
- 哪些单元属于 QCU
- 哪些单元属于 Honkai Core
- 哪些是实验 runner
- 哪些是旧版残留

---

## Phase 3：核心抽取

### 目标
先抽出最小可运行核心，而不是一次性做完整清理。

### 顺序建议
1. `qcu/core/`
2. `tree_diagram/core/`
3. `honkai_core/energetics/`
4. `engine/runtime/`

### 注意
- 抽核心时，保留原始注释语气和关键命名
- 不要先“改成更通用的名字”
- 先保证可追溯，再谈美化

---

## Phase 4：实验层拆分

### QCU labs
- `qcu/shor_lab/`
- `qcu/hash_lab/`
- `qcu/hmpl_lab/`

### Tree experiments
- `tree_diagram/experiments/`

### 规则
- 实验脚本可重复，但要按主题拆目录
- 所有 notebook 风格 demo 都不放进 `core/`

---

## Phase 5：统一运行时

当三大系统边界稳定后，开始做 `engine/`：

- runtime
- scheduler
- writeback
- orchestration

目标是把：

- Tree 主线裁决
- QCU 坍缩显形
- Honkai 能量调制

统一到同一套编排流程里。

---

## Phase 6：发布版清理

只在最后一步做：

- 命名统一
- API 收敛
- CLI 入口
- 文档补齐
- tests 补齐
- 依赖整理

不要把这一步提前。

---

# 6. 命名规范

---

## 6.1 保留项目内核心术语

这些术语不要擅自弱化或“改成正常词”：

- `mainline`
- `collapse`
- `honkai_energy`
- `imaginary_tree`
- `sea_of_quanta`
- `worldbubble`
- `herrscher`
- `oracle`

原因：这些词在项目内不是装饰，而是固定技术语义。

---

## 6.2 Python 命名建议

### 类
- `TreeDiagramEngine`
- `MainlineScorer`
- `QCUConfig`
- `CollapseScheduler`
- `HonkaiEnergyMeter`
- `HerrscherRiskModel`

### 模块
- `tree_runtime.py`
- `candidate_pool.py`
- `collapse_detector.py`
- `energy_gain_loss.py`
- `worldbubble_state.py`

### 常量
- `THETA_COLLAPSE`
- `THETA_HERRSCHER`
- `MAX_HONKAI_DENSITY`
- `MAINLINE_PRIORITY_CAP`

---

# 7. 文档对齐规范

代码重构时必须同步维护文档映射。

## 必要对应关系
- `tree_diagram/core/` ↔ `tree_diagram_whitepaper.md`
- `qcu/core/` ↔ `qcu_whitepaper.md`
- `honkai_core/` ↔ `honkai_studies.md`, `honkai_energetics.md`
- `engine/` ↔ `hce_whitepaper.md`

## 规则
- 理论文档里的模块名，如果代码里实现了，应尽量一一映射
- 代码里的重要类，如果进入核心层，文档里应能解释它属于哪一层

---

# 8. 绝对不要做的事

1. **不要把理论层整个删掉**
   - Honkai Core 不是“设定文件夹”

2. **不要把 Tree Diagram 和 QCU 糊成一个大脚本**
   - 它们是强耦合，但必须可独立演化

3. **不要先做“优雅抽象”再做结构恢复**
   - 先恢复，再优雅

4. **不要按文件顺序盲目切分**
   - Notebook / Colab 文件顺序常常是研发过程顺序，不等于模块顺序

5. **不要自动把术语翻译回游戏语境**
   - 项目内它们是技术术语

6. **不要默认删掉重复定义**
   - 先判断哪个是最终版，哪个是实验版

---

# 9. 最小交付标准

如果 Claude 要提交一个“可接受的重构结果”，最少应包含：

## 代码
- `tree_diagram/core/` 最小核心
- `qcu/core/` 最小核心
- `honkai_core/energetics/` 最小核心
- `engine/runtime/` 最小入口

## 文档
- `docs/architecture/source_map.md`
- 每个子模块一个 `README.md`

## 运行
- 至少一个 Tree Diagram demo
- 至少一个 QCU demo
- 至少一个 HCE 联合 demo

---

# 10. 推荐输出格式

当 Claude 完成一次重构任务时，输出应包含：

1. **改动摘要**
2. **新增目录/文件**
3. **从哪个原档抽出来**
4. **保留了哪些旧命名**
5. **哪些仍是 TODO**
6. **是否影响理论术语一致性**
7. **最小运行说明**

推荐模板：

```text
本次重构完成：
- 从 archive/colab_untitled2_raw.py 抽出 qcu/core/qcu_core.py
- 从 archive/colab_Untitled4_raw.ipynb 抽出 qcu/hash_lab/hash_reverse_lab.py
- 新增 docs/architecture/source_map.md

保留术语：
- QCU
- collapse
- mainline
- honkai_energy

未完成：
- engine/writeback 尚未统一
- honkai_core/risk 仍需补阈值模型
```

---

# 11. 最短总结

如果你只记最后一句，请记：

> **HCE 的代码重构不是“把脚本变干净”，而是把一台已经在研发中显形的机器，从母脚本和实验残骸里重新挖出来。**

再压成更短一句：

> **先考古，后模块化；先保结构，后美化。**
