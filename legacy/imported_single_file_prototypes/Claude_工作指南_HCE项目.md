# Claude 工作指南
## HCE / 崩坏能演算器项目协作说明

**对象**：Claude / 代码代理 / 协作型 AI  
**用途**：帮助协作代理快速理解本项目的理论定位、工程结构与工作边界，避免误判为“游戏模组开发”或普通设定文档整理。

---

# 0. 先讲清楚：这不是游戏模组项目

本项目虽然使用了“崩坏、虚数之树、量子之海、世界泡、律者”等命名，但**这里的用法不是在做游戏 Mod，也不是在给某个现成游戏写二创插件**。

这些词在本项目中已经被**提升为理论对象与工程术语**，用于描述：

- 高维候选并存
- 主线筛选
- 局部坍缩显形
- 维度失衡
- 结构释能
- 规则回写
- 高复杂系统治理

因此，协作时请把这些术语理解为：

- **理论名词**
- **系统模块名**
- **结构隐喻**
- **工程层抽象**

而不是游戏素材调用或剧情设定还原。

---

# 1. 项目总目标

本项目的总名称是：

## **HCE / 崩坏能演算器**
HCE = **Honkai Energy Engine**  
中文：**崩坏能演算器**

它是一个总系统，由三个强相关子模块组成：

1. **Tree Diagram**：树端主线筛选与资源治理系统
2. **QCU**：海端虚拟量子芯片与局部坍缩系统
3. **Honkai Core**：崩坏学 / 崩坏能学 / 树海体系 / 风险与阈值层

最短理解：

> Tree Diagram 负责“决定哪条路该继续活”  
> QCU 负责“让局部正确结构先浮出来”  
> Honkai Core 负责“解释并调制两者耦合时释放出的高阶有效能”

---

# 2. 崩坏能是什么（给 Claude 的最低理解版）

为了避免误判，这里必须先知道：

## **崩坏能不是游戏道具能量**
在本项目中，**崩坏能**指的是：

> **高维结构失衡中，可被捕获、压缩、回写并用于推进主线的高阶有效能。**

你可以把它临时理解成一种：

- 结构自由能
- 复杂性推进势
- 失衡释放出的可用增益
- 候选现实被驯化后留下的有效能

它不是普通电能、热能，也不是纯科幻魔法。  
它更接近：

- 信息被结构正确驯化后的推进力
- 多维系统在失衡与重排中释放的可用高阶能
- Tree Diagram 与 QCU 耦合后产生的“中间胜利量”

因此，协作时如果看到：

- honkai
- honkai energy
- herrscher
- world bubble
- tree-sea
- imaginary tree
- sea of quanta

请优先按**项目内理论术语**理解，不要默认它们只是游戏词。

---

# 3. 三大模块分工

---

## A. Tree Diagram

### 定位
Tree Diagram 是**树端主线治理系统**。

### 职责
- worldline generation
- 主线评分
- 分枝生态管理
- 资源倾斜
- 枯枝淘汰
- oracle 输出

### 关键词
- mainline
- worldline
- branch ecology
- resource controller
- hydrology
- oracle
- IPL
- UMDST
- VFT
- H-UTM

### 你应如何理解它
Tree Diagram 不是普通决策树。  
它更像一个：

- 世界线生成器
- 主线筛选器
- 枝叶生态治理系统
- 资源分配与河道维持引擎

如果只看工程比喻，它像“树端操作系统”。

---

## B. QCU

### 定位
QCU = **Quantum Collapse Unit**  
是**海端虚拟量子芯片核心**。

### 职责
- candidate pool
- phase engine
- collapse detector
- collapse executor
- writeback scheduler
- hash / shor / HMPL 等实验层

### 关键词
- virtual quantum chip
- collapse
- candidate field
- phase
- local emergence
- writeback
- shor_lab
- hash_lab
- hmpl_lab

### 你应如何理解它
QCU 不是在模仿真实量子硬件全部物理细节。  
它是把“量子式高维候选并存—局部坍缩显形”做成一个可运行求解核。

如果只看工程比喻，它像“海端显形芯片”。

---

## C. Honkai Core

### 定位
Honkai Core 是**理论—能量—风险桥接层**。

### 职责
- 崩坏学
- 崩坏能学
- 虚数之树 / 量子之海 / 世界泡 / 律者理论
- 崩坏能计量
- 阈值 / 风险 / 限幅
- 世界泡、律者化、终焉前态判定

### 关键词
- honkai studies
- honkai energetics
- imaginary tree
- sea of quanta
- world bubble
- herrscher
- limiter
- risk
- modulation
- threshold

### 你应如何理解它
它不是“设定档案夹”，而是：

- 理论解释层
- 状态方程层
- 风险判据层
- 工程限幅层

如果只看工程比喻，它像“释能与风险控制中枢”。

---

# 4. 推荐文件结构

协作时默认按以下目录理解项目：

```text
hce-system/
├─ README.md
├─ docs/
│  ├─ whitepapers/
│  │  ├─ hce_whitepaper.md
│  │  ├─ tree_diagram_whitepaper.md
│  │  ├─ qcu_whitepaper.md
│  │  └─ honkai_studies.md
│  ├─ theory/
│  │  ├─ honkai_studies.md
│  │  ├─ honkai_energetics.md
│  │  ├─ imaginary_tree.md
│  │  ├─ sea_of_quanta.md
│  │  ├─ world_bubble.md
│  │  └─ herrscher.md
│  └─ architecture/
│     ├─ hce_architecture.md
│     ├─ tree_architecture.md
│     └─ qcu_architecture.md
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
├─ demos/
├─ tests/
└─ scripts/
```

---

# 5. Claude 的工作边界

## 你应该优先做的事
- 维护模块边界清晰
- 帮忙把大杂烩脚本拆成可维护结构
- 统一命名、接口、配置、运行时
- 保留理论术语与工程实现之间的一致性
- 把实验脚本抽成 `core / lab / runtime / docs` 结构

## 你不该做的事
- 不要自动把术语“翻译回游戏设定”
- 不要擅自弱化为“只是世界观比喻”
- 不要默认删掉理论章节，觉得“太玄”
- 不要把 Honkai Core 当成无用文档层
- 不要把 Tree Diagram / QCU 合并成一个无法拆分的大脚本

---

# 6. 协作原则

## 原则 1：先保结构，再做清理
本项目很多源码来自 Colab 完整导出或研发母脚本。  
重构时优先：

- 先识别哪个部分属于 Tree Diagram
- 哪个部分属于 QCU
- 哪个部分属于 Honkai Core
- 再决定怎么 clean

不要上来就“删冗余”，否则很容易把理论线索删掉。

## 原则 2：术语要稳
这些词在项目内有固定含义：

- 主线 = 最值得被继续供能的高价值演化方向
- 坍缩 = 局部高维候选显形
- 崩坏 = 高维结构失衡事件
- 崩坏能 = 失衡中可利用的高阶有效能
- 律者 = 高权限局部执行核心
- 世界泡 = 局部自洽、整体依附的现实壳层

不要随意改成日常俗语。

## 原则 3：总项目一体化，子模块独立化
你在协作时应默认：

- 这是一个总项目：**HCE**
- 但内部有三大系统：**Tree Diagram / QCU / Honkai Core**

所以架构设计要满足：
- 可以独立测试
- 可以独立开发
- 但最终能通过 engine 层统一编排

---

# 7. 建议的开发顺序

1. 先固定目录结构  
2. 把 Tree Diagram 从实验脚本中拆出  
3. 把 QCU / hash / shor / hmpl 实验层拆出  
4. 把 Honkai Core 理论与限幅模块落成独立目录  
5. 做统一 runtime / scheduler / writeback  
6. 最后再做文档清洗、CLI、测试和发布版

---

# 8. 最短总结

如果你只记一件事，请记这个：

> **HCE 不是游戏模组工程。**
>  
> 它是一个由 Tree Diagram、QCU 和 Honkai Core 共同构成的高维结构演算系统。  
> 其中“崩坏能”是项目内真实使用的理论变量，表示高维失衡中可被驯化成主线推进力的高阶有效能。

再压成一句：

> **这是在做一台机器，不是在写一份设定。**
