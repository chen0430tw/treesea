# CFPAI 技术白皮书

**名称**：CFPAI  
**英文全称**：Computational Finance Planning AI  
**中文全称**：计算金融规划人工智能

---

## 1. 摘要

CFPAI 是一个面向金融市场分析、状态建模、策略规划与风险控制的计算金融系统。  
它的目标不是对单一价格点做机械外推，也不是把量化交易简化成“预测涨跌—直接下单”的单层流程，而是将市场动态拆分为可表示、可锚定、可搜索、可网格求值、可规划输出的多层结构。

CFPAI 的核心思想由三条主线组成：

1. **反向 MOROZ**：将 MOROZ 的收缩机制反向用于市场动态展开与重锚定；
2. **链式搜索**：将市场中的资金迁移、风险传播、板块轮动与宏观传导视为可跟踪的动态链条；
3. **Tree Diagram 网格计算**：将高价值动态路径映射到可并行求值的状态网格上，通过局部求值与全局传播得到规划结果。

在系统层面，CFPAI 同时引入 **UTM（Universal Tuning Model，通用调参模型）** 作为正式调参与结构校准层，使状态表示、动态锚定、链式搜索、网格求值和规划输出能够在统一的数学框架下被搜索、收缩、校准与稳定化。

因此，CFPAI 不是普通的选股器，也不是单一预测头，而是一个：

> **以市场状态建模为核心、以动态路径规划为主线、以风险预算与执行接口为落点的计算金融智能系统。**

---

## 2. 背景与动机

现实中的金融市场具有以下结构性特征：

- 市场状态不是静态的，而是持续演化的；
- 价格变化不是孤立事件，而是由资金流、风险偏好、宏观变量、板块轮动与外部事件共同驱动；
- 单点预测往往脆弱，真正稳定的优势通常来自对“状态—路径—行动”链条的组织能力；
- 传统量化流程通常过度依赖局部特征工程与单一策略回测，难以同时兼顾：
  - 全局状态判断
  - 局部结构变化
  - 多资产协同
  - 风险预算约束
  - 执行层动作规划

因此，CFPAI 的提出，旨在解决以下问题：

1. 如何把多源市场观测统一映射为可计算的状态表示；
2. 如何在当前状态下识别哪些动态路径值得展开；
3. 如何把离散的状态链条变成可并行求值的网格对象；
4. 如何将研究、风控、组合管理与执行统一进同一规划框架；
5. 如何通过通用调参模型，避免无休止的经验性调参。

---

## 3. 系统定位

CFPAI 的定位不是单一预测模型，而是一个完整的规划系统。  
它由五个核心层组成：

1. **状态表示层 \(\Phi\)**  
   负责将多源市场数据映射为潜在状态表示；

2. **反向 MOROZ 动态展开层 \(\mathcal{R}\)**  
   负责根据当前状态生成高价值动态候选，并完成重锚定；

3. **链式搜索层 \(\mathcal{C}\)**  
   负责在市场动态路径中寻找高价值传播链条；

4. **Tree Diagram 网格求值层 \(\mathcal{T}\)**  
   负责将路径映射为状态网格，并进行局部求值与全局传播；

5. **规划输出层 \(\Psi\)**  
   负责输出状态判断、风险预算、动作建议与执行接口。

同时，系统引入：

6. **UTM 调参与结构校准层 \(\mathcal{U}_{\mathrm{UTM}}\)**  
   负责贯穿上述各层的参数搜索、结构收缩、稳定性校准与全局调参。

整体映射可写为：

\[
\mathrm{CFPAI}
=
\Psi
\circ
\mathcal{T}
\circ
\mathcal{C}
\circ
\mathcal{R}
\circ
\Phi
\]

若引入 UTM，则可写为：

\[
\mathrm{CFPAI}^{\star}
=
\mathcal{U}_{\mathrm{UTM}}
\big(
\Psi
\circ
\mathcal{T}
\circ
\mathcal{C}
\circ
\mathcal{R}
\circ
\Phi
\big)
\]

---

## 4. 输入对象与市场表示

设离散时间为：

\[
t = 1,2,\dots,T
\]

定义时刻 \(t\) 的市场观测向量为：

\[
\mathbf{x}_t \in \mathbb{R}^{d}
\]

其组成可写为：

\[
\mathbf{x}_t =
\big(
\mathbf{p}_t,\;
\mathbf{v}_t,\;
\boldsymbol{\sigma}_t,\;
\mathbf{f}_t,\;
\mathbf{m}_t,\;
\mathbf{n}_t,\;
\mathbf{c}_t
\big)
\]

其中：

- \(\mathbf{p}_t\)：价格与收益率特征
- \(\mathbf{v}_t\)：成交量与活跃度特征
- \(\boldsymbol{\sigma}_t\)：波动率与风险统计
- \(\mathbf{f}_t\)：资金流特征
- \(\mathbf{m}_t\)：宏观变量
- \(\mathbf{n}_t\)：新闻、事件与情绪特征
- \(\mathbf{c}_t\)：链上、加密与跨市场特征

对于多资产市场，定义资产集合为：

\[
\mathcal{A} = \{1,2,\dots,N\}
\]

第 \(i\) 个资产的观测写为：

\[
\mathbf{x}^{(i)}_t
=
\big(
p^{(i)}_t,\;
v^{(i)}_t,\;
\sigma^{(i)}_t,\;
f^{(i)}_t
\big)
\]

于是多资产总观测可写成：

\[
\mathbf{X}_t = \big(\mathbf{x}^{(1)}_t,\dots,\mathbf{x}^{(N)}_t\big)
\]

---

## 5. 状态表示层 \(\Phi\)

CFPAI 不直接在原始观测空间中完成决策，而是先构造潜在市场状态。

定义状态映射器：

\[
\Phi : \mathcal{X} \to \mathcal{Z}
\]

其中 \(\mathcal{Z} \subseteq \mathbb{R}^{m}\) 为潜在状态空间。

于是：

\[
\mathbf{z}_t = \Phi(\mathbf{x}_t)
\]

进一步将潜状态分解为四个子状态：

\[
\mathbf{z}_t =
\big(
\mathbf{z}^{(f)}_t,\;
\mathbf{z}^{(r)}_t,\;
\mathbf{z}^{(s)}_t,\;
\mathbf{z}^{(l)}_t
\big)
\]

其中：

- \(\mathbf{z}^{(f)}_t\)：资本流状态
- \(\mathbf{z}^{(r)}_t\)：风险状态
- \(\mathbf{z}^{(s)}_t\)：结构轮动状态
- \(\mathbf{z}^{(l)}_t\)：流动性状态

因此可以写成：

\[
\Phi(\mathbf{x}_t)
=
\big(
\Phi_f(\mathbf{x}_t),
\Phi_r(\mathbf{x}_t),
\Phi_s(\mathbf{x}_t),
\Phi_l(\mathbf{x}_t)
\big)
\]

### 5.1 资本流函数

定义资本流强度函数：

\[
F_t = \mathcal{F}_{\mathrm{flow}}(\mathbf{z}^{(f)}_t)
\]

若存在 \(N\) 个资产、板块或因子簇，则可定义资本流矩阵：

\[
\mathbf{M}_t \in \mathbb{R}^{N \times N}
\]

其中 \((\mathbf{M}_t)_{ij}\) 表示从节点 \(i\) 向节点 \(j\) 的资本迁移强度。

净流入与净流出定义为：

\[
\mathrm{In}_j(t)=\sum_{i=1}^{N}(\mathbf{M}_t)_{ij},
\qquad
\mathrm{Out}_j(t)=\sum_{k=1}^{N}(\mathbf{M}_t)_{jk}
\]

净资本流强度：

\[
\Delta_j(t)=\mathrm{In}_j(t)-\mathrm{Out}_j(t)
\]

### 5.2 风险状态函数

定义风险状态函数：

\[
R_t = \mathcal{F}_{\mathrm{risk}}(\mathbf{z}^{(r)}_t)
\]

可进一步拆为：

\[
R_t =
\big(
r_t^{(\mathrm{vol})},
r_t^{(\mathrm{dd})},
r_t^{(\mathrm{corr})},
r_t^{(\mathrm{macro})}
\big)
\]

综合风险预算指标可写为：

\[
\rho_t
=
\omega_1 r_t^{(\mathrm{vol})}
+
\omega_2 r_t^{(\mathrm{dd})}
+
\omega_3 r_t^{(\mathrm{corr})}
+
\omega_4 r_t^{(\mathrm{macro})}
\]

### 5.3 结构轮动函数

定义结构轮动函数：

\[
S_t = \mathcal{F}_{\mathrm{rotation}}(\mathbf{z}^{(s)}_t)
\]

它用于描述：

- 板块轮动
- 风格切换
- 因子迁移
- 风险偏好跃迁

可写成连续向量：

\[
\mathbf{r}_t \in \mathbb{R}^{K}
\]

其中第 \(k\) 维表示第 \(k\) 个结构簇的强化程度。

---

## 6. 反向 MOROZ 动态展开层 \(\mathcal{R}\)

MOROZ 在原始定义中更偏向“从大量候选中逐层收缩到高密度结构”。  
CFPAI 则反过来使用这一逻辑：

- 先从当前状态出发，展开可能的动态路径；
- 再对这些路径进行锚定、重权重化与再收缩。

### 6.1 动态锚点

定义当前时刻的动态锚点集合：

\[
\mathcal{A}_t = \{a_{t,1},a_{t,2},\dots,a_{t,m_t}\}
\]

每个锚点可以表示：

- 一个资本流转移起点
- 一个风险状态跳变点
- 一个宏观事件触发点
- 一个价格结构破位点
- 一个板块或资产轮动起点

定义锚定强度函数：

\[
A(a \mid \mathbf{z}_t)
\]

从而得到锚点分布：

\[
P_{\mathrm{anchor}}(a \mid \mathbf{z}_t)
=
\frac{\exp(A(a \mid \mathbf{z}_t))}
{\sum_{b\in\mathcal{A}_t}\exp(A(b \mid \mathbf{z}_t))}
\]

### 6.2 动态展开

定义展开算子：

\[
\mathcal{E}(\mathbf{z}_t,a)
=
\{u_{t,1},u_{t,2},\dots,u_{t,N_t}\}
\]

其中每个 \(u\) 表示一条动态候选路径，例如：

- 风险偏好增强 → 科技权重上升
- 防御情绪增强 → 债券与黄金强化
- 通胀预期抬升 → 能源与商品链走强

定义每条动态候选的评分：

\[
R(u \mid \mathbf{z}_t,a)
=
\alpha A(u \mid \mathbf{z}_t)
+
\beta C(u \mid \mathbf{z}_t)
+
\gamma V(u \mid \mathbf{z}_t)
-
\delta \Xi(u \mid \mathbf{z}_t)
\]

其中：

- \(A(u \mid \mathbf{z}_t)\)：锚定一致性
- \(C(u \mid \mathbf{z}_t)\)：链传播连续性
- \(V(u \mid \mathbf{z}_t)\)：规划价值
- \(\Xi(u \mid \mathbf{z}_t)\)：风险与成本惩罚

于是：

\[
P_{\mathcal{R}}(u \mid \mathbf{z}_t)
=
\frac{\exp(R(u \mid \mathbf{z}_t))}
{\sum_{v\in\mathcal{E}(\mathbf{z}_t)}\exp(R(v \mid \mathbf{z}_t))}
\]

---

## 7. 链式搜索层 \(\mathcal{C}\)

CFPAI 将市场动态视为可传播的链条，而不是彼此孤立的点。

定义路径：

\[
\pi
=
(u_{t,0},u_{t,1},\dots,u_{t+\ell})
\]

定义路径价值函数：

\[
\mathcal{J}(\pi)
=
\sum_{k=0}^{\ell}\lambda^k
\Big[
w_f F(u_{t+k})
+
w_s S(u_{t+k})
+
w_a A(u_{t+k})
-
w_r \Xi(u_{t+k})
\Big]
\]

其中：

- \(F(u)\)：资本流增益
- \(S(u)\)：结构轮动强化
- \(A(u)\)：锚定稳定性
- \(\Xi(u)\)：风险与成本惩罚
- \(\lambda\in(0,1]\)：时间折扣因子

最优路径集合定义为：

\[
\Pi_t^\star
=
\arg\max_{\pi \in \mathcal{P}_t}\mathcal{J}(\pi)
\]

若保留 Top-\(K\) 链，则写为：

\[
\Pi_t^{(K)}
=
\operatorname{TopK}_{\pi\in\mathcal{P}_t}\mathcal{J}(\pi)
\]

这一步回答的问题不是“下一刻涨跌”，而是：

> **当前状态最可能沿哪几条高价值路径继续传播。**

---

## 8. Tree Diagram 网格求值层 \(\mathcal{T}\)

链式搜索给出了高价值动态路径，但仍需要进一步转化为可并行求值的状态对象。  
这一步由 Tree Diagram 的网格计算能力承担。

### 8.1 状态网格

定义状态网格为：

\[
\mathcal{G}_t = (V_t,E_t,W_t)
\]

其中：

- \(V_t\)：状态节点集合
- \(E_t\)：状态传播边集合
- \(W_t\)：边权

每个节点 \(v \in V_t\) 表示一个局部市场子态：

\[
v
=
\big(
\mathbf{z}^{(f)},
\mathbf{z}^{(r)},
\mathbf{z}^{(s)},
\mathbf{z}^{(l)}
\big)
\]

### 8.2 节点效用

定义节点效用函数：

\[
U(v)
=
\theta_1 U_f(v)
+
\theta_2 U_r(v)
+
\theta_3 U_s(v)
+
\theta_4 U_l(v)
\]

其中：

- \(U_f(v)\)：资本流效用
- \(U_r(v)\)：风险调整效用
- \(U_s(v)\)：结构轮动效用
- \(U_l(v)\)：流动性适配效用

### 8.3 网格传播方程

定义传播：

\[
Q_{k+1}(v)
=
U(v)
+
\eta \sum_{u \in \mathcal{N}^{-}(v)} w_{uv} Q_k(u)
\]

其中：

- \(\eta\)：传播系数
- \(\mathcal{N}^{-}(v)\)：流入节点集合
- \(w_{uv}\)：边权

收敛后得到：

\[
Q^\star(v)
=
\lim_{k\to\infty} Q_k(v)
\]

这一层提供的是：

> **将市场动态路径嵌入状态网格，再对局部状态块进行并行求值与全局价值回流。**

---

## 9. 规划输出层 \(\Psi\)

CFPAI 的输出不是单一价格预测值，而是规划结果：

\[
y_t = \Psi(\Pi_t^\star, Q^\star, B_t)
\]

其中 \(B_t\) 是风险预算。

写成向量形式：

\[
y_t =
(\hat{s}_t,\hat{\pi}_t,\hat{a}_t,\hat{\rho}_t,\hat{B}_t)
\]

其中：

- \(\hat{s}_t\)：市场状态标签
- \(\hat{\pi}_t\)：最优动态链
- \(\hat{a}_t\)：建议动作
- \(\hat{\rho}_t\)：风险评估
- \(\hat{B}_t\)：推荐风险预算

### 9.1 动作空间

定义动作空间：

\[
\mathcal{A}^{(\mathrm{act})}
\]

动作可以包括：

- 开仓
- 平仓
- 加仓
- 减仓
- 转防御
- 转进攻
- 观察
- 暂停
- 降杠杆
- 重配组合

若在多资产组合中表示为权重调整：

\[
a_t = (\delta_t^{(1)},\delta_t^{(2)},\dots,\delta_t^{(N)})
\]

### 9.2 风险预算函数

定义：

\[
B_t = \mathcal{B}(\rho_t,Q^\star,\Pi_t^\star)
\]

一种简单形式可写为：

\[
B_t = B_{\max}\exp(-\kappa\rho_t)
\]

其中 \(\kappa>0\) 为风险抑制系数。

风险越高，预算越低。

---

## 10. UTM 调参与结构校准层

UTM（Universal Tuning Model）在 CFPAI 中不只是参数搜索器，而是**正式调参与结构校准层**。

### 10.1 UTM 的对象集合

定义：

\[
\mathrm{UTM}
=
\left\{
\Phi,\Psi,\{a_n\}_{n\ge 0},\mathbf{DM},T(t),\{(t_n,x_n)\}_{n\ge 0}
\right\}
\]

在 CFPAI 中，它具体负责校准：

1. **状态表示层参数**
   - 动量权重
   - 趋势权重
   - 波动权重
   - 回撤权重
   - 资金流权重

2. **反向 MOROZ 参数**
   - 锚定强度
   - 展开阈值
   - 保留率
   - 风险惩罚强度

3. **链式搜索参数**
   - 路径折扣因子
   - 持续性奖励
   - regime 切换代价
   - 链长上限

4. **Tree Diagram 网格参数**
   - 网格密度
   - 节点效用权重
   - 边传播系数
   - 风险预算压缩系数

5. **规划输出参数**
   - 动作阈值
   - 风险预算上限
   - 观察 / 执行切换阈值
   - 防御模式切换阈值

### 10.2 UTM 的操作化映射

在工程实现中，可将 UTM 近似映射为：

- **收缩数序列 \(a_n\)**：第 \(n\) 代 elite 参数状态
- **维度矩阵 \(\mathbf{DM}\)**：elite 参数分布的局部协方差 / 自适应尺度
- **温度函数 \(T(t)\)**：搜索范围逐代收缩的温度式过程
- **时空编号 \((t_n,x_n)\)**：参数状态在迭代时间与局部搜索空间中的位置

于是 UTM 的作用变成：

> **将 CFPAI 从经验调参推进为可收缩、可记录、可校准、可复现的结构化调参过程。**

---

## 11. 目标函数

CFPAI 的目标不是仅仅最大化收益，而是最大化一个综合效用函数。

定义：

\[
\mathcal{U}
=
\mathbb{E}[R_p]
-
\lambda_1 \mathrm{DD}
-
\lambda_2 \mathrm{Turnover}
-
\lambda_3 \mathrm{Cost}
+
\lambda_4 \mathrm{InfoGain}
\]

其中：

- \(R_p\)：组合收益
- \(\mathrm{DD}\)：最大回撤或尾部风险
- \(\mathrm{Turnover}\)：换手率
- \(\mathrm{Cost}\)：交易成本
- \(\mathrm{InfoGain}\)：信息增益 / 研究价值

若写成参数搜索目标：

\[
\max_{\Theta}
\;
\mathbb{E}[\mathcal{U}(\Theta)]
\]

其中 \(\Theta\) 表示 CFPAI 所有待调参数。

---

## 12. 工作原理总结

综合前述模块，CFPAI 的工作链路可以写成：

\[
\mathbf{x}_t
\xrightarrow{\Phi}
\mathbf{z}_t
\xrightarrow{\mathcal{A}}
\mathcal{A}_t
\xrightarrow{\mathcal{R}}
\mathcal{E}_t
\xrightarrow{\mathcal{C}}
\Pi_t^\star
\xrightarrow{\mathcal{T}}
Q^\star
\xrightarrow{\mathcal{B}}
B_t
\xrightarrow{\Psi}
y_t
\]

再由 UTM 提供参数与结构校准：

\[
\mathrm{CFPAI}^{\star}
=
\mathcal{U}_{\mathrm{UTM}}
\Big(
\mathbf{x}_t
\xrightarrow{\Phi}
\mathbf{z}_t
\xrightarrow{\mathcal{A}}
\mathcal{A}_t
\xrightarrow{\mathcal{R}}
\mathcal{E}_t
\xrightarrow{\mathcal{C}}
\Pi_t^\star
\xrightarrow{\mathcal{T}}
Q^\star
\xrightarrow{\mathcal{B}}
B_t
\xrightarrow{\Psi}
y_t
\Big)
\]

一句话概括：

> **CFPAI = 市场状态表示 + 反向 MOROZ 动态展开 + 链式搜索 + Tree Diagram 网格求值 + 风险预算规划 + UTM 结构化调参。**

---

## 13. 系统优势

### 13.1 相比传统单点预测模型
CFPAI 不只输出价格方向，而是输出：

- 市场状态
- 路径优先级
- 风险预算
- 资产权重
- 动作建议

### 13.2 相比传统量化脚本
CFPAI 不是固定规则引擎，而是：

- 会做动态锚定
- 会做链式搜索
- 会做网格求值
- 会做结构化规划

### 13.3 相比黑箱“大而全 AI”
CFPAI 的中间结构是明确的，能够解释：

- 为什么当前路径被选中
- 为什么某些路径被抑制
- 为什么预算被压缩
- 为什么某个资产簇被加权

### 13.4 相比纯经验调参
UTM 将调参变成：

- 可记录的收缩序列
- 可分析的局部结构
- 可复现的全局搜索过程

---

## 14. 工程实现建议

建议将 CFPAI 工程化为以下模块：

```text
CFPAI/
├─ data/
├─ features/
├─ state/
├─ reverse_moroz/
├─ chain_search/
├─ tree_diagram/
├─ planner/
├─ utm/
├─ backtest/
├─ outputs/
└─ docs/
```

其中：

- `state/`：状态表示层
- `reverse_moroz/`：动态锚定与展开
- `chain_search/`：路径搜索
- `tree_diagram/`：网格求值
- `planner/`：动作、仓位、风险预算输出
- `utm/`：调参与收缩层
- `backtest/`：回测、评估与验证

---

## 15. 当前原型状态

当前原型已经完成了以下方向的验证：

- 单资产 SPY toy 测试
- UTM 风格参数搜索
- Stooq 多资产现成版
- Stooq 多资产版 UTM 自动调参脚本

说明 CFPAI 已经具备从理论定义走向工程原型的基本条件。

但当前版本仍属于：

- baseline 级
- 结构验证级
- 规划主链验证级

尚未达到：

- 完整资本流矩阵建模
- 高阶 Tree Diagram 网格求值
- 多市场协同
- 实时事件响应
- 机构级执行引擎

---

## 16. 应用场景

CFPAI 适用于以下任务：

1. **多资产配置与轮动研究**
2. **风险状态与 regime 判断**
3. **板块 / 风格迁移分析**
4. **金融研究与策略规划**
5. **风险预算与执行接口生成**
6. **量化研究自动化与结构化回测**

---

## 17. 边界与限制

CFPAI 不是收益保证器，也不是自动印钞系统。

它的边界是：

- 能组织问题，不保证市场永远配合；
- 能改善研究与规划效率，不保证任何单一时期的超额收益；
- 能做结构化风险控制，不消除市场冲击；
- 能提供高质量规划结果，但最终执行仍受流动性、成本、制度和市场结构限制。

因此，CFPAI 的定位应始终是：

> **金融市场的状态建模与规划系统，**
> **而不是神谕型自动赚钱机器。**

---

## 18. 结论

CFPAI（Computational Finance Planning AI）是一个将金融市场建模为动态状态系统、并通过反向 MOROZ、链式搜索与 Tree Diagram 网格计算完成路径规划和风险预算输出的计算金融系统。

其核心贡献在于：

1. 将价格预测问题提升为状态—路径—行动的规划问题；
2. 将多源市场观测统一为可计算的潜在状态表示；
3. 将 MOROZ 的收缩逻辑反向用于金融动态展开与重锚定；
4. 将市场路径映射到 Tree Diagram 状态网格中完成并行求值；
5. 将 UTM 正式引入为调参与结构校准层，避免经验式无止境调参。

因此，CFPAI 可以被视为：

> **一个以市场状态建模为起点、以动态链路径搜索为中枢、以网格求值与规划输出为落点、以 UTM 为调参骨架的计算金融原生智能系统。**

---

## 19. 风险声明与法律免责

**本节为本白皮书不可分割的组成部分。**

### 19.1 投资风险警告

CFPAI 是一套计算金融**规划**系统，其所有输出（资产权重、风险信号、路径分析、回测绩效）**仅供研究与参考**，不构成投资建议、投资推荐或投资决策依据。

- **回测绩效不代表未来表现。** 本文中出现的所有指标（Sharpe ratio、年化收益率、最大回撤等）均为特定历史时段、特定参数下的模拟结果。
- **模型可能失效。** Maxwell Demon 门控、UTM 调参、链式搜索等机制基于统计假设，在极端市场环境下可能全部失效。
- **杠杆放大风险。** 使用杠杆和做空功能可能导致超过本金的损失。

### 19.2 法律免责

- 开发者不是持牌投资顾问，不提供个人化投资建议
- 本软件按「现状」（AS IS）提供，不附带任何保证
- 使用者的投资决策由使用者自行负责
- 使用者在做出投资决策前应咨询持牌专业金融顾问

**完整法律声明请参阅 [`DISCLAIMER.md`](../DISCLAIMER.md)。**
