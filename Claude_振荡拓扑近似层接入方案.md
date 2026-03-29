# Claude 振荡拓扑近似层接入方案
## OTAL（Oscillatory Topology Approximation Layer）在 QCU 中的定位、职责与落地建议

**版本**：v1.0  
**作者**：430  
**对象**：Claude / 协作代码代理  
**用途**：指导将 **振荡拓扑近似层（OTAL）** 接入现有 QCU / IQPU 系统，使其作为 **快搜前层 / 候选成熟度筛选层 / 局部坍缩前筛层**，与现有 Lindblad + RK4 高保真验证层形成分层架构。  

---

# 0. 先讲清楚：这份文档解决什么问题

现有 QCU / IQPU 的主执行路径默认是：

```text
候选态 → Lindblad + RK4 → readout → 判定
```

这条路径的问题不是错误，而是**过重**。  
尤其对很多任务来说，系统真正需要的不是“高保真重建整条连续物理轨迹”，而是更快地知道：

- 哪些局部节点在收敛  
- 哪些区域相位正在对齐  
- 哪些候选更像主线  
- 哪些地方已经接近坍缩阈值  
- 哪些区域值得进一步送去高保真验证  

因此需要在 Lindblad + RK4 之前增加一个更轻的前置筛选层。  
这个层不是再调一次 RK4，而是直接换一种表示：

> **用随机拓扑节点 + 振荡指向数 + 邻域传播规则，快速近似连续高维演化的方向场与局部成熟度。**

这就是 **振荡拓扑近似层（OTAL）**。

---

# 1. OTAL 的正式定位

## 1.1 定义

**振荡拓扑近似层（Oscillatory Topology Approximation Layer, OTAL）**：  
一种位于 QCU 候选态池与局部坍缩层之间的离散近似层。它通过**随机拓扑节点、动态邻接关系、振荡指向数与局部传播规则**，在不完整求解全系统连续微分方程的前提下，快速估计：

- 方向场趋势
- 相位一致性
- 邻域收敛性
- 主线倾向
- 局部成熟度
- 坍缩候选热点

## 1.2 最短定义

> **OTAL 不是高保真求解器，而是 QCU 的快搜代理层。**

## 1.3 与 RK4 的关系

OTAL 不是 RK4 的严格数学等价物，也不应被实现为“另一种数值积分器”。  
它的正确定位是：

- **前置近似层**
- **快搜层**
- **方向判断层**
- **候选筛选层**

关系可写成：

\[
\boxed{
\text{QCU}
=
\text{候选态池}
\to
\text{OTAL}
\to
\text{局部坍缩层}
\to
\text{高保真 Lindblad/RK4 验证层}
}
\]

---

# 2. 为什么需要 OTAL

## 2.1 当前 RK4 路径的问题
现有路线默认让每个候选都经历：

- Lindblad 开放系统 RHS
- RK4 四次采样
- 读出
- 观测
- 可能还有纠缠/成熟度评估

这对于“只想先判断方向”的任务来说过重。

## 2.2 QCU 真正关心的不是完整轨迹
QCU 的核心价值本来就不是“把每条轨迹精确算完”，  
而是：

- 让正确结构先浮出来
- 让值得坍缩的区域先被发现
- 让主线趋势先显影

因此，QCU 比起“连续积分器”，更需要一个：

> **能快速判断“哪里在成形”的前筛层。**

## 2.3 振荡指向数已经提供了本体语言
你们并不是要随便找一个 heuristic。  
QCU 之所以能自然走到 OTAL，是因为已有的**振荡指向数体系**已经能表达：

- 周期性
- 指向性
- 相位差
- 动态几何轨迹
- 局部振荡模式

所以 OTAL 不是临时 patch，而是：

> **用自研数学母语重写快搜层。**

---

# 3. OTAL 的核心思想

OTAL 的核心思想是：

> **把“连续高维演化”在快搜阶段降阶为“图上的振荡传播与方向收敛”。**

具体来说，不再把系统看成必须时刻精确积分的整体，而是看成：

- 一组节点
- 一组边
- 每个节点携带一个振荡指向数
- 每条边携带一个耦合权重
- 局部区域通过邻域传播形成一致性或主线趋势

于是原本的连续演化问题：

\[
\frac{d\rho}{dt}=\mathcal{L}(\rho)
\]

在快搜阶段先被近似为：

\[
\boxed{
G_t=(V_t,E_t,\vec{D}(t),W_t)
}
\]

其中：

- \(V_t\)：节点集合
- \(E_t\)：边集合
- \(\vec{D}(t)\)：节点上的振荡指向数
- \(W_t\)：动态权重 / 相位耦合矩阵

---

# 4. OTAL 的最小形式化定义

设拓扑图为：

\[
G=(V,E)
\]

其中：

- \(V=\{v_1,v_2,\dots,v_N\}\)
- \(E\subseteq V\times V\)

每个节点 \(v_i\) 关联一个振荡指向数：

\[
\vec{D}_i(t)=\vec{s}_i(t), \qquad \vec{s}_i(t+T_i)=\vec{s}_i(t)
\]

每条边 \((i,j)\) 具有动态边权：

\[
w_{ij}(t)
\]

则 OTAL 定义为：

\[
\boxed{
\mathcal{O}_{\mathrm{TA}}
=
\bigl(
G,\,
\{\vec{D}_i(t)\}_{i=1}^N,\,
W(t),\,
\mathcal{U},\,
\mathcal{C}
\bigr)
}
\]

其中：

- \(G\)：拓扑骨架
- \(\vec{D}_i(t)\)：节点振荡指向数
- \(W(t)\)：动态边权矩阵
- \(\mathcal{U}\)：局部更新规则
- \(\mathcal{C}\)：坍缩候选判据

---

# 5. OTAL 的工作流程

OTAL 在 QCU 中的工作流程建议为四步：

## 5.1 候选图构建
从现有候选态池中抽样或聚类生成拓扑节点。  
节点可代表：

- 候选态中心
- 相位峰值点
- 局部模式簇
- 子区域代理点

## 5.2 振荡赋值
为每个节点赋予：

- 初始振荡指向数
- 局部周期参数
- 相位偏置
- 邻域耦合强度

## 5.3 拓扑传播
通过邻域更新规则，快速观察：

- 哪些节点方向在拉齐
- 哪些局部子图相位开始集中
- 哪些区域发散
- 哪些区域收敛

## 5.4 候选坍缩标记
对局部区域计算成熟度，若超过阈值，则交给：

- QCU 局部坍缩层
- 或高保真 Lindblad/RK4 验证层

---

# 6. 更新规则建议

一个最小更新规则可以写成：

\[
\vec{D}_i(t+\Delta t)
=
(1-\lambda)\vec{D}_i(t)
+
\lambda
\sum_{j\in \mathcal{N}(i)}
\tilde w_{ij}(t)\,\vec{D}_j(t)
+
\eta_i(t)
\]

其中：

- \(\mathcal{N}(i)\)：节点 \(i\) 的邻域
- \(\tilde w_{ij}(t)\)：归一化边权
- \(\lambda\)：邻域耦合系数
- \(\eta_i(t)\)：局部扰动项

### 实现要求
Claude 不必一开始就实现所有复杂变体。  
第一版只需：

- 支持节点向量更新
- 支持边权更新
- 支持相位差和方向差的基本传播
- 支持扰动项可选开关

---

# 7. 坍缩候选判据建议

定义局部子图 \(U\subseteq V\) 的成熟度：

\[
M(U,t)
=
\alpha_1 A(U,t)
+
\alpha_2 P(U,t)
+
\alpha_3 S(U,t)
-
\alpha_4 R(U,t)
\]

其中：

- \(A(U,t)\)：振荡一致性
- \(P(U,t)\)：相位集中度
- \(S(U,t)\)：邻域支持强度
- \(R(U,t)\)：扰动/发散度

当：

\[
M(U,t)\ge \Theta_c
\]

则将该区域标记为：

- `collapse_candidate=True`
- 推入 QCU 局部坍缩队列
- 或进入高保真验证队列

---

# 8. Claude 的接入目标

Claude 在接入 OTAL 时，不应该直接改烂现有 RK4 路径，而应完成：

## 8.1 保留现有 Full Physics Mode
即：

- Lindblad + RK4 继续保留
- 不删原路线
- 不直接宣称 OTAL 等价替代 RK4

## 8.2 新增 Fast Search Mode
当 mode = `fast_search` 时：

- 优先走 OTAL
- 只把少量高成熟候选送进 Lindblad/RK4
- 不再对所有候选执行高保真演化

## 8.3 实现两层衔接
Claude 需要明确实现：

- OTAL 输出什么格式
- QCU collapse 层如何接收
- 哪些字段可直接复用（phase, maturity, candidate_id, local_score）
- 哪些候选被推入 full physics 验证层

---

# 9. 推荐代码目录

```text
qcu/
├─ core/
├─ otal/
│  ├─ graph_state.py
│  ├─ oscillatory_direction.py
│  ├─ topology_update.py
│  ├─ maturity_score.py
│  ├─ candidate_filter.py
│  └─ README.md
├─ collapse/
├─ readout/
├─ runtime/
└─ benchmarks/
```

---

# 10. 推荐模块职责

## `graph_state.py`
定义：

- 节点表示
- 边表示
- 邻接矩阵 / 稀疏图结构
- OTALState 数据结构

## `oscillatory_direction.py`
定义：

- 振荡指向数表示
- 相位差计算
- 振荡周期参数
- 节点初始化规则

## `topology_update.py`
定义：

- 邻域传播更新
- 边权重更新
- 扰动项
- 图状态推进

## `maturity_score.py`
定义：

- 一致性
- 相位集中度
- 邻域支持
- 扰动惩罚
- 总成熟度公式

## `candidate_filter.py`
定义：

- 坍缩候选筛选
- Top-k 热点提取
- 推入 collapse 队列或 full physics 队列

---

# 11. 推荐数据结构

Claude 第一版可直接采用 dataclass：

```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class OTALNode:
    node_id: int
    direction: complex
    phase: float
    period: float
    local_score: float = 0.0

@dataclass
class OTALEdge:
    src: int
    dst: int
    weight: float

@dataclass
class OTALState:
    nodes: List[OTALNode]
    edges: List[OTALEdge]
    t: float
```

注意：  
第一版不需要一开始就过度复杂化，重点是先跑通：

- 节点更新
- 成熟度评分
- 候选筛选

---

# 12. 需要做的 benchmark

Claude 接入 OTAL 后，必须至少做三组 benchmark：

## 12.1 RK4-only vs OTAL + RK4
比较：

- 总时长
- 候选筛选效率
- 末态 / 命中率 / 主线清晰度

## 12.2 OTAL-only 快搜效果
比较：

- 是否能较快识别热点
- 是否能给出合理的 collapse candidate 排序
- 是否有明显 phase / direction clustering

## 12.3 稀疏图 vs 稠密图
比较：

- 图更新成本
- 候选成熟度收敛速度
- 是否出现过拟合式伪峰

---

# 13. 不要犯的错误

1. **不要把 OTAL 写成另一套 RK4**
   - 它不是数值积分器的替代实现
   - 它是拓扑快搜代理层

2. **不要直接删除原 Lindblad / RK4 路径**
   - 原路线必须保留为 high-fidelity validation

3. **不要把振荡指向数弱化成普通 phase label**
   - 它不是随便附个角度
   - 它是项目内正式的数学变量

4. **不要一开始就过度做复杂图神经网络**
   - 第一版先做轻量、可解释、可 benchmark 的近似层

5. **不要把 OTAL 当作游戏世界观模块**
   - 它是 QCU 的正式快搜层，不是设定附录

---

# 14. Claude 必须交付的输出

每次 OTAL 接入迭代后，Claude 输出必须包含：

1. 新增了哪些文件  
2. OTAL 在 runtime 中的接入点  
3. OTAL 输出到 collapse / full physics 的数据结构  
4. benchmark 数据  
5. 与原 Lindblad/RK4 的关系说明  
6. 是否保持了“振荡指向数”术语语义一致  

推荐模板：

```text
本次 OTAL 接入完成：
- 新增 qcu/otal/graph_state.py
- 新增 qcu/otal/topology_update.py
- 新增 qcu/otal/maturity_score.py
- runtime 支持 mode="fast_search_otal"

接入关系：
- 候选态池 -> OTAL -> collapse queue
- Top-k collapse candidate -> full physics validation

benchmark：
- RK4-only: 25.1s
- OTAL + RK4: 8.4s
- OTAL-only prefilter: 1.9s

说明：
- 保留原 Lindblad + RK4 路线
- OTAL 作为前置快搜层，不宣称数学等价替代
- 振荡指向数语义保持不变
```

---

# 15. 最终总结

Claude 接入振荡拓扑近似层时，必须把它理解为：

> **QCU 的快搜代理层，而不是另一种更快的 RK4。**

它的职责不是精确重建完整连续轨迹，而是低成本回答：

- 哪些方向已经足够清楚  
- 哪些局部节点在收敛  
- 哪些区域更像主线  
- 哪些地方值得坍缩  
- 哪些候选值得再交给高保真 solver  

如果把整件事压成一句最核心的话：

> **OTAL 的任务不是把曲线画得更准，而是尽快判断哪里已经不必再画整条曲线。**
