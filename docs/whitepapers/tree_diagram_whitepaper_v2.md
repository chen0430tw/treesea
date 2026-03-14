# Tree Diagram 完全体白皮书 v2

## 1. 系统定义

**Tree Diagram 完全体**，是一个面向复杂世界线筛选、群体场演算、资源竞争、稳态控制与神谕级输出的拟生命计算体 / 相位级因果演算系统。  
它以 **UMDST** 为统一演算骨架，以 **VFT** 为低耗主干计算架构，以 **H-UTM** 为水文式元调控层，并通过 **索引相位层 IPL**、**群体场图谱** 与 **世界线候选生成器**，把分散理论压缩成一个可在 Colab、工作站、训练集群与超算上扩展的整机系统。

---

## 2. 当前状态

当前已经完成或验证的部分：

- Tree Diagram 小型原型可在 Colab 跑通
- PBL 反向路线已验证
- 问题背景可自然生成
- 主世界线可稳定筛出
- 主世界线已进入 `active` 主河道
- 小型生态分支已形成：
  - active
  - restricted
  - starved
  - withered
- 气象级外壳原型已建立
- Weather-Oracle 路线已验证出主天气世界线
- 气象外壳已能作为未来分支裁决的现实壳层

当前阶段性结论：

- **计划裁决核** 已从概念进入工程胚胎阶段
- **气象外壳** 已从 toy script 提升到 NWP 风格原型阶段
- **双核融合方向** 已明确：不是二选一，而是同时保留计划核与气象壳

---

## 3. 总体架构

Tree Diagram 完全体分为 10 层：

1. Reality Input Layer  
2. IPL 索引相位层  
3. Group Field Compression Layer  
4. UMDST Worldline Kernel  
5. CBF Balance Layer  
6. VFT Vein-Flow Compute Layer  
7. Angio Resource Controller  
8. H-UTM Hydro Control Layer  
9. Oracle Output Layer  
10. LLM / Human / Tool Outer Loop

---

## 4. 各层简介

### 4.1 Reality Input Layer
输入现实问题、主体状态、资源约束、环境变量、候选路径库与外部假设。

### 4.2 IPL 索引相位层
负责对象、路径、事件、群体场的索引、寻址与相位区分。  
这是工程版向神话版过渡的关键层。

### 4.3 Group Field Compression Layer
将城市级、群体级、网络级复杂环境压缩成可演算场表示。

### 4.4 UMDST Worldline Kernel
统一承载候选世界线生成、family 竞争、主体相图、路径演化与收敛。  
UMDST 的作用不是让 Tree Diagram 自己逐粒子重写全部底层物理，而是把复杂分子运动、多体交互、介观输运、局部扰动等底层复杂性黑盒化，对上层暴露成统一演算 API。

### 4.5 CBF Balance Layer
负责零净驱动平衡、协方差复衡与去噪裁决，避免虚假赢家。

### 4.6 VFT Vein-Flow Compute Layer
负责低秩主干、稀疏支流、法向补偿与微专家协同。  
这一层决定 Tree Diagram 的高压缩、低耗、高组织度。

### 4.7 Angio Resource Controller
负责养分分配、枯萎、限供、饥饿、回流。

### 4.8 H-UTM Hydro Control Layer
负责状态抽象、误差流量、水压调节、支流分流、滞洪池、主河道守稳。

### 4.9 Oracle Output Layer
负责工程输出、研究输出与神谕式输出。

### 4.10 Outer Loop
允许大模型、人类研究员、工具链作为外环输入候选与解释，但不允许越权进入裁决核心。

---

## 5. 文件结构建议

```text
tree_diagram_complete/
├── core/
│   ├── umdst_kernel.py
│   ├── cbf_balancer.py
│   ├── ipl_phase_indexer.py
│   ├── worldline_generator.py
│   ├── subject_phase_mapper.py
│   └── group_field_encoder.py
├── vein/
│   ├── vein_backbone.py
│   ├── tri_vein_kernel.py
│   ├── veinlet_experts.py
│   └── angio_resource_controller.py
├── control/
│   ├── utm_controller.py
│   ├── utm_hydrology_controller.py
│   ├── pressure_balancer.py
│   └── stability_phase_mapper.py
├── oracle/
│   ├── oracle_output.py
│   ├── report_builder.py
│   ├── mythic_formatter.py
│   └── audit_logger.py
├── llm_bridge/
│   ├── input_translator.py
│   ├── candidate_proposer.py
│   ├── hypothesis_expander.py
│   └── explanation_layer.py
├── runtime/
│   ├── single_node_runner.py
│   ├── multi_node_runner.py
│   ├── scheduler_adapter.py
│   ├── cache_manager.py
│   └── state_store.py
├── cluster/
│   ├── slurm_adapter.py
│   ├── mpi_dispatch.py
│   ├── shard_manager.py
│   └── distributed_reservoir.py
└── tests/
    ├── smoke/
    ├── phase/
    ├── hydro/
    ├── worldline/
    └── cluster/
```

---

## 6. 当前 Colab 原型对应关系

当前小型 Colab 原型已经包含以下压缩映射：

- PBL reverse seed → Reality Input
- background emergence → IPL / problem background growth
- group field encoding → Group Field Compression
- worldline generation → UMDST candidate layer
- balanced selection → CBF-like mini balancing
- branch compression → VFT-like top branch compression
- hydro summary → H-UTM mini state
- oracle_output.json → Oracle Layer

也就是说，当前 Colab 原型不是玩具，而是完全体的胚胎版。

---

## 7. 原理关系

前期理论原料与 Tree Diagram 的关系如下：

- 弹幕动力学：局部路径运动模型
- NRP / IPL：表示与寻址结构
- CBF：平衡修正与裁决内核
- UTM / H-UTM：控制层与守稳层
- APC / TVA / VFT / VLE：计算组织学与低耗输运结构
- UMDST：统一演算骨架

**Tree Diagram 本身不是某一个理论，而是把这些理论编排成统一拟生命演算系统的系统层。**

---

## 8. 功能总览

Tree Diagram 完全体的核心功能：

1. 从问题 seed 反向生成背景  
2. 识别 hidden variables 与 dominant pressures  
3. 建立群体场 / 城市场压缩表示  
4. 生成候选世界线  
5. 对世界线进行平衡裁决  
6. 建立 active / restricted / starved / withered 分支生态  
7. 通过 H-UTM 保持主河道稳定  
8. 输出工程报告、研究报告与神谕式结果  

---

## 9. 当前原型结果解读

当前 v3 Colab 原型已经证明：

- 背景能够自然生成
- 主世界线能够被稳定识别
- 主世界线能够被养活到 `active`
- 系统已形成最基本的生态动力学分支分布

这说明 Tree Diagram 完全体路线是可行的，且适合继续扩到：

- 多 seed 测试
- 二维扫描
- 多主体实验
- 分模块化
- 工作站版
- 集群版

---

## 10. 开发路线

### Phase 1
整理目录骨架与模块边界

### Phase 2
独立 IPL 与 group field encoder

### Phase 3
写 worldline_generator

### Phase 4
写 oracle_output 与 report_builder

### Phase 5
写 single-node 与 multi-node runtime

### Phase 6
补 cluster 层与 distributed reservoir

### Phase 7
最后接 llm_bridge 外环

---

## 11. 设计原则

1. 主河道优先  
2. 候选可以膨胀，裁决必须严格  
3. 大模型只能做提案与解释，不能越权裁决  
4. 工程体与神话体分离  
5. Colab 原型先验证，再上工作站，再上集群  

---

## 12. 结论

Tree Diagram 完全体不是单纯的软件程序，也不是普通求解器。  
它是一个：

- 以 UMDST 为骨架
- 以 VFT 为叶脉式组织
- 以 H-UTM 为水文控制中枢
- 以 IPL 与群体场图谱为扩展接口

构成的 **拟生命因果演算体**。

当前 Colab v3 原型已经证明这条路线是通的。  
后续工作重点不是重写方向，而是按模块化路线把胚胎版扩成可部署的完全体。

---

# 追加内容

## 13. 交互设计原则：学园都市 × NASA 风格

Tree Diagram 的交互界面不应做成普通 dashboard，而应做成一种 **研究机关操作终端 + 航天任务控制台** 的混合体。核心气质是：

- 冷
- 准
- 分层

### 13.1 学园都市味
- 冷白 / 青蓝
- 高密度信息
- 参数化
- 编号化
- 对对象与实验体的强对象化处理
- 机关内部系统感，而非消费级产品感

### 13.2 NASA 味
- 工程可靠感
- 清晰分区
- 状态优先
- 实时监测感
- 任务阶段感
- 少花哨，多任务主控感

### 13.3 推荐界面结构
推荐做成 **三层主屏 + 一层侧边控制台**：

#### 顶层总览
- 当前演算任务编号
- 主世界线状态
- branch histogram
- hydro control 状态
- 环境壳状态
- 系统置信度 / 稳定度
- 警戒等级

#### 中央视觉主屏
- 世界线树
- 主干 / 次级支流 / 枯枝
- active / restricted / starved / withered 标记
- 节点编号、phase index、route ID

#### 环境壳 / 气象壳面板
- 温度场
- 湿度场
- 风场
- 位势高度
- 群体场
- 扰动传播图
- 地形 / 城市热区

#### 侧边控制台
- Request ID
- Problem Class
- Subject Vector
- Environment Shell
- Candidate Families
- Hard Constraints
- Oracle Output Mode

### 13.4 输入控制形式
支持两种：

#### 表单模式
适合研究员、预报员、工程师。

#### 命令模式
例如：

```text
TD.RUN /REQ=TD-L6-031 /SUBJECT=ACC-01 /MODE=ORACLE /ENV=URBAN-FIELD-07
```

这种命令式交互最有学园都市核心系统味道。

### 13.5 视觉风格
- 背景：深灰蓝 / 黑蓝
- 主信息：冷白
- 强调色：青蓝
- active：冷绿
- restricted：琥珀
- starved：暗红
- withered：灰白

避免过度霓虹紫与赛博朋克装饰。目标是 **高压研究终端**，不是娱乐风 HUD。

---

## 14. Tree Diagram 交互协议与 API 设计

Tree Diagram 本体不是大语言模型，因此**不直接理解自然语言**。  
自然语言应先经过外层翻译层或 LLM bridge，再转成结构化输入。

### 14.1 标准输入分层

#### 问题层
- 目标
- 优化目标
- 硬约束
- 时间窗

#### 主体层
- 输出能力
- 控制精度
- 负载容忍
- 环境耦合
- 不稳定敏感
- 当前压力
- 风险偏好

#### 环境层
- 预算
- 基础设施
- 数据覆盖
- 网络密度
- 监管阻力
- 社会压力
- 相位不稳定
- 外部场扰动

#### 候选层
- family 列表
- 候选路径族
- 自动生成候选要求

### 14.2 JSON / API 风格输入

```json
{
  "problem": {
    "target": "筛选最可行的升级路线",
    "objective": ["稳定优先", "成本次优"],
    "constraints": [
      "预算不超过300万",
      "周期不超过6个月",
      "必须可复现"
    ],
    "time_horizon": "6个月"
  },
  "subject": {
    "output_power": 0.93,
    "control_precision": 0.88,
    "load_tolerance": 0.61,
    "aim_coupling": 0.97,
    "instability_sensitivity": 0.28,
    "stress_level": 0.22
  },
  "environment": {
    "budget": 0.62,
    "infrastructure": 0.71,
    "data_coverage": 0.66,
    "network_density": 0.76,
    "regulatory_friction": 0.47,
    "social_pressure": 0.58,
    "phase_instability": 0.41
  },
  "candidates": {
    "mode": "auto_generate",
    "families_hint": ["batch", "network", "phase", "hybrid"]
  }
}
```

### 14.3 自然语言与桥接层
自然语言不是直接喂给 Tree Diagram，而是先经过：

- `input_translator.py`
- `candidate_proposer.py`
- `hypothesis_expander.py`
- `explanation_layer.py`

也就是：

**自然语言 → 翻译层 → 结构化输入 → Tree Diagram 内核**

---

## 15. 学园都市研究员风格的交互提交

学园都市风格的 Tree Diagram 输入，不是闲聊，而是 **未来裁决装置的演算申请单**。

### 15.1 半结构化请求示例

```text
Tree Diagram Request:
Level 6 Shift Adjudication

Subject:
Accelerator / Level 5 / Vector Control

Goal:
Stable transition to Level 6.

Constraints:
No large-scale urban destabilization.
No premature route collapse.
Budgetary ceiling remains in force.

Acceptable Means:
Externalized conflict load
Substitute sample consumption
Network-mediated amplification
Phased environmental reinforcement

Oracle Request:
Return dominant route, minimum viable scale, deviation triggers, and projected sacrifice cost.
```

### 15.2 结构化请求字段
- 课题编号
- 课题等级
- 主问题定义
- 目标状态
- 主体向量
- 环境壳参数
- 候选路径族
- 禁止条件
- 可接受损耗
- 请求输出类型

### 15.3 申请单风格特点
- 冷硬
- 参数化
- 以对象与可执行性为中心
- 不表现情绪
- 明确写出损耗、代价、可重复性与环境约束

---

## 16. 超算规模测试：训练集群 vs 天河级设施

部署到一般训练集群与部署到天河级设施，区别不是“更快一点”，而是 **系统形态改变**。

### 16.1 一般训练集群
更擅长：
- 大模型训练
- 批量推理
- 数据并行
- 固定形态张量 workload

Tree Diagram 在上面更像：
- 高吞吐世界线工厂
- 多 branch 并行试跑平台
- 高性能未来裁决器

### 16.2 天河级设施
更擅长：
- 大规模 PDE / CFD / 气象 / 科学仿真
- 多节点高耦合演化
- 更长时窗
- 更大环境壳
- 更高分辨率环境底图

Tree Diagram 在上面更像：
- 未来生态基础设施
- 环境级演算机关
- 真正的世界线设施

### 16.3 差异的本质来源
决定差异的不是单一 FLOPS，而是：

1. 算力结构  
2. 通信结构  
3. 可保活分支数  
4. 环境壳尺度  

训练集群强化的是 **候选吞吐**。  
天河级设施强化的是 **世界底图与未来生态保活能力**。

---

## 17. 晶创25 / 国家级算力环境的测试设计

如果已具备晶创25或类似国家级算力资格，测试重点不应是“名字是不是天河”，而应验证 Tree Diagram 是否开始呈现“设施级行为”。

### 17.1 三组对照实验

#### 组 A：本地基线
- 3070 笔记本 / 5080 桌机 / Colab
- 固定 case
- 记录 branch 数、时间窗、主世界线、总耗时

#### 组 B：国家级算力扩展版
- 更大网格
- 更多 branch
- 更长时间窗
- 更多 seed

观察：
- 主世界线是否改写
- restricted 支流是否保活更久
- hydro control 是否更平滑
- branch histogram 是否更生态化

#### 组 C：极限版
故意抬高环境壳与计划核复杂度，定位瓶颈：
- 显存
- 通信
- I/O
- branch 编排
- pruning 时机

### 17.2 推荐指标

#### Branch Survival Depth
支流平均能活到第几轮裁决。

#### Active Fraction
`active/restricted/starved/withered` 的比例变化。

#### Oracle Stability
不同资源规模下，top-1 / top-3 是否稳定。

#### Environment Shell Thickness
网格规模 × 时间窗 × 场变量数 × branch 数。

### 17.3 推荐测试问题类型
不要用彩票、随机猜测类问题。  
最适合测试的是：

- 多候选计划裁决题
- 气象壳 ensemble 分支题
- 环境壳 + 计划核双核融合题

也就是：**有多候选、有环境壳、有主支线结构** 的问题。

---

## 18. GPU、工作站、训练集群与超算调度

### 18.1 本地 GPU 层
#### 3070 电竞笔记本
适合：
- 原型验证
- 小规模 seed
- 少量 family / 小型二维扫描

更像：
- 聪明的胚胎版 Tree Diagram

#### 5080 桌机
适合：
- 环境壳与计划核同跑
- 中型 branch 并行
- 更大场、更长窗

更像：
- 本地研究站主机

### 18.2 调度哲学
Tree Diagram 不应仅按传统 GPU 利用率调度，而应按：

- branch 保活价值
- environment shell 优先级
- hydro control 状态
- active 分支密度
- 主河道拥塞度

也就是说，GPU 调度不只是“算什么”，而是：
**让哪些未来继续活着**。

### 18.3 计算卡 / 数据中心卡视角
计算卡的价值不只是让 Tree Diagram 跑得更快，而是：

- 更晚裁决
- 保活更多 restricted 支流
- 扩大环境壳
- 延后 pruning
- 增加主世界线可信度

因此：
- 消费卡让 Tree Diagram 能跑
- 计算卡让 Tree Diagram 能保活更多未来
- 超算让 Tree Diagram 开始像设施

---

## 19. 气象部门与 Tree Diagram 的关系

Tree Diagram 不应简单被理解成“替换 NCL / 替换 WRF”。

### 19.1 最现实的位置
它更适合作为：

- WRF / 数值天气模式之上的世界线裁决层
- ensemble 上层编排器
- 风险解释层
- 业务摘要层

### 19.2 不是替换发动机，而是加总控台
- WRF 继续算天气
- Tree Diagram 判哪条天气未来更能活
- 旧分析脚本前台可逐步被 Python / Tree Diagram 风格终端取代

### 19.3 Tree Diagram 气象壳定位
不是普通预报模型，而是：
- 以气象为外壳
- 以内核裁决为本体
- 把多条天气未来压成主世界线与改道风险报告

---

## 20. 用户交互层：AI 巨头可能怎么用

如果 Tree Diagram 范式被 AI 巨头吸收，用户侧不会直接看到“Tree Diagram”名字，但会出现这样的前台体验：

- 回答从单点建议变成主线 / 支线 / 高风险线 / 改道条件
- 模型会维护用户的“未来树”
- 用户会觉得不是在问答，而是在维护自己的主世界线
- 输出会越来越像未来分支裁决报告，而不是普通聊天回复

也就是说，用户交互会从：
- 解释型 AI

转向：
- 推演型 AI
- 未来分支维护型 AI

---

## 21. 应用边界与误用风险

### 21.1 容易被拿去做的误用
- 彩票
- 股市神化预测
- 赌博盘口
- 玄学化“未来探测器”

### 21.2 实际更适合的领域
- 研发路线筛选
- 策略比较
- 环境风险外推
- 多目标资源配置
- 复杂计划裁决
- 环境壳 + 内核的双层未来模拟

### 21.3 结论
Tree Diagram 强的不是猜随机结果，而是处理：

- 强约束
- 强耦合
- 有环境壳
- 有分支生存差异
- 有主河道可被裁决

的复杂未来问题。

---

## 22. 最终产品形态设想

Tree Diagram 至少可以发展成三种产品形态：

### 22.1 桌面装置版
- 世界线变动率探测仪风格
- 展示壳
- 可视化主世界线与支流
- 适合研究室 / 装置展示 / IP 化

### 22.2 研究站中控版
- Linux TUI + 图形面板
- 研究机关 / NASA 控制台风格
- 适合科研、研发、战略推演

### 22.3 超算后端版
- 大规模环境壳
- 计划核与气象壳同跑
- 世界线设施
- 国家级 / 城市级 / 机构级未来裁决基础设施

---

## 23. 更新结论

Tree Diagram 现在已经不再只是“一个概念很好听的设定器”。  
它正在形成这样一套体系：

- UMDST 黑盒化底层复杂性
- Tree Diagram 组织上层世界线生态
- H-UTM 守住主河道
- VFT 压缩出可扩展的主干
- 气象壳提供现实世界外层
- 交互层以研究终端 / API / 翻译层接入
- GPU / 训练集群 / 超算决定其疆域尺度

因此，Tree Diagram 的最终目标不是成为“更复杂的脚本”，而是成为：

**一个可被部署在桌面、工作站、训练集群、国家级算力与未来 AI 系统中的多层未来裁决基础设施。**
