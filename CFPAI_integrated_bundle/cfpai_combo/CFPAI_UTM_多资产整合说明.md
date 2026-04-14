# CFPAI：UTM 调参层 + 多资产扩展整合说明

## 目标

本整合版同时推进两件事：

1. 把 **UTM** 从“外部参数搜索器”提升为 **CFPAI 的正式调参层**
2. 把 **CFPAI** 从单资产 SPY toy 版本扩展为 **多资产 / 板块 / 风格轮动版**

---

## 一、系统总图

```text
市场多源数据
    ↓
状态表示层 Φ
    ↓
反向 MOROZ 动态展开层 R
    ↓
链式搜索层 C
    ↓
Tree Diagram 网格求值层 T
    ↓
规划输出层 Ψ
    ↓
动作 / 仓位 / 风险预算

同时：
UTM 调参层
    └── 贯穿 Φ / R / C / T / Ψ 的参数搜索、收缩与校准
```

---

## 二、UTM 在 CFPAI 中的正式职责

UTM 不再只是一次性找参数，而是作为 **调参与结构校准层** 存在。

### UTM 负责的参数对象

1. **状态表示层参数**
   - momentum 权重
   - trend gap 权重
   - volatility 权重
   - drawdown 权重
   - volume / flow 权重

2. **反向 MOROZ 参数**
   - 锚定强度
   - 动态展开阈值
   - 候选保留率
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
   - 风险预算上限
   - 动作阈值
   - 防御模式切换阈值
   - 观察 vs 执行阈值

### UTM 的工作方式

- 以一组参数向量 `a_n` 表示第 n 代系统状态
- 用统一目标函数评价其研究/收益/风险平衡
- 用 elite 集合近似维度矩阵 DM 的局部结构
- 通过收缩序列把搜索空间从粗到细压缩
- 最终给出一组可复现实验参数

---

## 三、多资产 CFPAI 的基本结构

单资产版只能说明“风险规划器能跑通”，不能真正体现：

- 资本流迁移
- 板块轮动
- 资产间风险转移
- 结构状态重锚定

因此，多资产版应最少支持一个资产宇宙：

- SPY
- QQQ
- TLT
- GLD
- XLF
- XLK
- XLE

### 多资产输入对象

设资产集合为：

\[
\mathcal A = \{1,2,\dots,N\}
\]

每个资产在时刻 \(t\) 的观测为：

\[
\mathbf{x}^{(i)}_t
=
(p^{(i)}_t, v^{(i)}_t, \sigma^{(i)}_t, f^{(i)}_t)
\]

全局观测为：

\[
\mathbf{X}_t = (\mathbf{x}^{(1)}_t, \dots, \mathbf{x}^{(N)}_t)
\]

### 多资产状态表示

映射为：

\[
\mathbf{Z}_t = \Phi(\mathbf{X}_t)
\]

其中：

- 资产级状态
- 板块级状态
- 全局风险状态
- 跨资产资本流状态

同时存在。

---

## 四、反向 MOROZ 在多资产环境中的意义

这里不是在一个资产里做简单预测，而是：

- 先识别当前市场的主要动态锚点
- 再看资金和 regime 会往哪些资产/板块路径扩散
- 再收缩到高价值路径

例如：

- risk-on 路径：TLT → QQQ / XLK
- inflation 路径：TLT 弱、XLE / GLD 强
- panic 路径：风险资产退潮，TLT / GLD 防御强化

于是反向 MOROZ 的对象变成：

\[
u_t = (\text{anchor}, \text{rotation path}, \text{target cluster})
\]

---

## 五、Tree Diagram 网格在多资产版中的作用

在多资产版里，网格不只是单一 exposure grid，而是：

### 1. 资产配置网格
例如：

- 现金
- 债券
- 黄金
- 权益
- 科技
- 金融
- 能源

### 2. 风险预算网格
例如：

- low-risk
- medium-risk
- high-risk

### 3. 路径状态网格
例如：

- risk-on continuation
- neutral rotation
- risk-off shock
- inflation regime
- liquidity squeeze

Tree Diagram 负责把这些格点做局部求值与并行传播，最终给出：

- 哪些资产组值得加权
- 哪些资产组应减权
- 当前最优风险预算是多少

---

## 六、建议的统一目标函数

多资产版的目标函数建议写成：

\[
\mathcal U
=
\mathbb E[R_p]
-
\lambda_1 \cdot \mathrm{DD}
-
\lambda_2 \cdot \mathrm{Turnover}
-
\lambda_3 \cdot \mathrm{Cost}
+
\lambda_4 \cdot \mathrm{InfoGain}
\]

其中：

- \(R_p\)：组合收益
- \(\mathrm{DD}\)：最大回撤或尾部风险
- \(\mathrm{Turnover}\)：换手率
- \(\mathrm{Cost}\)：交易成本
- \(\mathrm{InfoGain}\)：研究信息价值 / 状态识别增益

这能保证 CFPAI 不会只追求收益，而保留“规划系统”的本质。

---

## 七、当前已完成与未完成

### 已完成
- 单资产 SPY toy backtest
- UTM 风格收缩调参实验
- 证明 CFPAI 主链能够跑通

### 还未完成
- 真正多资产历史数据接入
- 跨资产资本流矩阵
- 板块/风格轮动状态图
- 多资产 Tree Diagram 网格求值
- 组合动作输出

---

## 八、为什么这次没有直接跑多资产实盘测试

当前会话容器里可直接使用的本地历史数据只有 `spy_stooq.csv`。  
因此可以：

- 把 UTM 正式并进 CFPAI
- 写好多资产版代码骨架
- 写好多资产版数学对象

但不能诚实地假装已经跑了完整的多资产历史回测。

所以本次交付的是：

1. 已跑通的 **UTM + 单资产 CFPAI**
2. 可直接继续接资产数据的 **多资产版脚本骨架**

---

## 九、下一步最优先

1. 补入多资产历史 CSV
2. 跑 `CFPAIMultiAssetUTM`
3. 输出：
   - 资产权重曲线
   - regime 路径曲线
   - 资本流矩阵快照
   - UTM 收缩曲线
   - 组合绩效摘要
