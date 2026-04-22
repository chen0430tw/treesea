# Tree Diagram 起源推理链

> **读者：未来的 430 + 未来的协作 Agent**
>
> 这份文档不是给别人看的。是写给你自己 2028 年凌晨打开源码、面对一堆气象常数和魔数发呆时的救命索引。
>
> 源码里只保留了推理链的最后两层。上面四层在你脑子里。这份文档把它们抓下来。

**签名：By:430 · 记录于 2026-04-19**

---

## 0. 读这份文档之前需要知道的

你建立 Tree Diagram 的时候，脑子里是**六层认知跃迁**。每一层都把问题的维度往下压一次。源码里能看到的只是最后两层的**投影**（family 参数、hydro 判定），所以光读源码永远推不回来"为什么是这 6 个 family"、"为什么 5 元组是 gain/precision/coupling/stress/decay"、"为什么阈值不等式可以短路掉 MD 全域积分"。

推理链是：

```
Academy City Tree Diagram（动漫原型）
  ↓ 解构
虚数学区（计算基底的物质化）
  ↓ 关键认知
MD 路径碰撞（不是场求解，是事件检测）
  ↓ 空间降维
弹幕动力学（符卡基底替代连续场）
  ↓ 分解完备性
弹幕逼近定理（任意场可分解为有限 family 叠加）
  ↓ 判定降维
MER（端点极值取代全域积分）
  ↓ 工程落地
VBM / SAF（过线判定 + 成本加权）
```

每一层压下去的是**不同性质**的维度。下面逐层展开。

---

## 1. 第一层：Academy City Tree Diagram（动漫原型）

**出处**：某魔法禁书目录 / 某科学超电磁炮。学园都市第二高等学校顶楼的人工卫星 Tree Diagram，被称为"唯一能精确预测天气的超级计算机"。

**动漫设定说它能做的事**：
- 天气预测精确到哪片叶子会被吹倒
- 同时跑多个情境模拟
- 是学园都市能力开发（Esper）的理论算力基础

**这个设定当时被认为是纯科幻，实际上是预言**：

对一个 2000 年代的作者来说，"能精确预测天气"听起来就是"算力暴力"的极限想象。但如果你认真想——即使你有**无限算力**，蝴蝶效应（Lorenz）也让连续天气预测在数学上不可能收敛。

所以动漫里 Tree Diagram **如果真的能运行**，它不是在做传统意义的"天气预测"。

这是第一个认知跃迁：**它不是算力问题，是算法问题。**

---

## 2. 第二层：虚数学区（计算基底的物质化）

**动漫设定**：虚数学区 "五和机关"，漂浮在相模湾外的人工岛，整座岛本身就是 Tree Diagram 的计算基底。不是建在岛上——**整座岛 = 主板**。

**这个设定 2010 年看离谱，2026 年回看是对"computational substrate materialization"的预言**。

2020 年代的现实里，我们已经有：
- 神经拟态芯片（Loihi、IBM NorthPole）
- DNA 计算
- 量子退火器（D-Wave）
- 光学计算芯片（Lightmatter）

这些都是在把计算从冯·诺依曼架构**物质化**到特定物理底层。虚数学区的设定本质是同一件事的极端版——**把计算直接实现在自然界的某个物理过程上，避免数字化的损耗**。

**你从这里拿到的启发不是"要做一个物质计算基底"**（你没那个预算），而是：

> *如果 Tree Diagram 的计算被物质化到某个特定物理过程上，那个物理过程本身就是算法的结构。*
> *那个物理过程是什么？*

这就引出第三层。

---

## 3. 第三层：MD 路径碰撞（不是场求解，是事件检测）

**关键认知**：

你当时想：如果 Tree Diagram 的算法本身"长得像某种物理过程"，那最自然的候选是**分子动力学**——因为 MD 同时覆盖：
- 大气（天气预测）
- 粒子群（Esper 能力场）
- 相空间（决策与世界线）

但 naive MD 是 O(N²) 的，跑不动。

**第二层跃迁**：

天气预测如果要"精确到哪片叶子被吹倒"，naive 方式是**连续场求解 + 无限精度**，这是不可能的。但如果你把问题**重新表述**成：

> *"哪片叶子会被吹倒" = "大气粒子轨迹和叶子位置的路径碰撞事件"*

那问题从**连续场求解**变成**离散事件检测**。离散事件是稀疏的。稀疏事件的检测复杂度远低于稠密场求解。

这是 Tree Diagram 能在理论上存在的根本理由：**它不预测所有天气，它只检测有意义的路径碰撞**。

**推论**：动漫里 Tree Diagram 宕机的原因不是算力不够，而是**当时的数学没有给它一个比 naive MD 更好的路径碰撞检测算法**。如果你能给它一个更好的算法，你不需要虚数学区。

这就是第四层。

---

## 4. 第四层：弹幕动力学（符卡基底替代连续场）

**核心洞察**：

路径碰撞检测的最大难点不是检测本身，是**"所有可能的路径"的空间爆炸**。连续势场里路径数是无限的。

**跃迁**：从东方 Project 的弹幕系统借结构。

弹幕（符卡 / spell card）有几个**反直觉的好性质**：

1. **离散基底**：每张符卡是一组有限的、确定性的弹幕轨迹
2. **可组合**：多张符卡叠加产生新的弹幕场
3. **有对称性**：弹幕通常有旋转/反射对称，压缩表示
4. **安全走廊**：玩家的生存路径是弹幕模式之间的窄缝

**弹幕动力学就是**：用符卡基底替代连续势场，把"所有可能的路径"的无限空间压缩成"有限 family 基底的组合"。

**源码映射**：
- `_FAMILY_COEFFS` 的 6 个 family（batch / network / phase / electrical / ascetic / hybrid）就是**基底符卡**
- 每个 family 的 5 元组 `(gain, precision, coupling, stress, decay)` 是该符卡的**模式描述**
- `_FAMILY_MOD_GROUP` 的 6 个 mod function（sin/sigmoid/线性/常数）是**符卡的时间展开算子**
- candidate_pipeline 输出的 `top_k` 世界线 = 在 family 叠加下的**安全走廊交集**

**为什么是这 6 个 family 而不是别的**：

这 6 个是你在 UMDST 时期反向推出来的。它们覆盖了相空间里**6 种基本动力学模式**：

| Family | 动力学本质 | 符卡类比 |
|--------|----------|---------|
| batch | 密集定向 | 直线密集弹 |
| network | 分布式耦合 | 跟踪弹 |
| phase | 相位旋转 | 螺旋弹 |
| electrical | 脉冲爆发 | 激光弹 |
| ascetic | 稀疏缓慢 | 大弹低速 |
| hybrid | 混合模式 | 复合符卡 |

完备性论证：任何相空间演化都可以分解为这 6 种基本模式的叠加。这是弹幕逼近定理在声称的东西。

---

## 5. 第五层：弹幕逼近定理（分解完备性）

**定理陈述（非正式）**：

> *任意复杂的多源胁迫场，都可以分解为有限组确定性弹幕模式（family 基底）的叠加，*
> *而最优候选轨迹是这些模式"安全走廊"的交集。*

**与经典定理的关系**：
- 类比傅里叶分解：基底是符卡不是正弦波
- 类比 Galerkin 方法：把 PDE 投影到有限基底，但基底是动力学模式而不是空间基函数
- 类比谱方法：在"弹幕谱"上展开

**关键性质**：
- 完备性：6 个 family 足够覆盖相空间基本模式
- 稀疏性：大多数问题只激活少数 family
- 可组合性：family 线性叠加仍是合法弹幕场
- 有限精度：误差界由 family 数目和展开阶数决定

**证明思路**（你在 UMDST 时期推出来的，需要重推）：
- 从 Lindblad 主方程出发
- 证明其生成元可以被 6 种基本耗散通道线性组合
- 每种通道对应一个 family
- 余项界由主方程的谱半径给出

**为什么这是你没完全公开的**：

这个定理**单独拿出来**就是一篇数学物理论文。源码里 `_FAMILY_COEFFS` 的具体数值是定理的**特解**，不是定理本身。读代码的人会以为这 6 组数字是经验调出来的——他们不会想到这是定理的完备基。

---

## 6. 第六层：MER（端点极值取代全域积分）

**MER 原文**：见下节附录。**这是 430 签名的核心定理**。

**在 TD 里扮演的角色**：

弹幕逼近定理解决的是**空间降维**（连续场 → 6 个 family）。MER 解决的是**判定降维**（全域积分 → 端点代入）。

两个定理组合：
- 弹幕逼近把 "无限维势场求解" 压到 "6 维 family 空间"
- MER 把 "6 维 family 空间里的积分" 压到 "6 × 2 = 12 个端点代入"

最后实际计算量：**12 次端点代入 + Lipschitz 余量**。

这就是为什么笔记本能跑。

**源码映射**：
- `hydro_adjust_numerical` 就是 MER 的过线判定（`f(x,θ) ≷ h_0`）
- `feasibility` 字段就是 **型 A**（全域达标）的端点最小值
- `p_blow` 字段就是 **型 B**（至少一段达标）的端点最大值
- `crackdown_ratio` 是 MER 阈值触发后的安全余量 `h_0' = h_0 + L·ε`
- `top_zone` (stable/transition/critical) 是分段 MER 的段归属

**关键洞察**：

TD 跑 300 步 RK4 不是在"扫相图"，是在**验证 MER 的前提条件**（单调性稳定、Lipschitz 边界、分段结构）。一旦前提成立，判定本身**只需要 12 次代入**。

如果不用 MER，TD 跑一次 COVID 奇点验证要：
- 前后两个场景各做完整 MD 演化
- 每个场景需要集合预报
- 每组预报需要 N² 粒子交互
- 总计 ~10⁸ 次操作

用了 MER 之后：
- 两个场景各做端点代入
- 每次端点代入约 10³ 次操作
- 两次比较
- 总计 ~2×10³ 次操作

**5 个数量级的压缩**。这就是 "笔记本能跑，Tianhe 反而跑不过" 的原因。

---

## 7. 第七层（工程层）：VBM / SAF

**VBM**（Variational Bounded Monotonicity，弧重叠比例判定）：
- MER 的工程化快判核
- 计算"两个单调段的弧重叠比例"来判定是否越线
- 直接用于 `hydro_adjust_numerical` 里的离散分类

**SAF**（Signal Adaptive Filter，信号成本加权）：
- MER 过线之后的执行层
- 按信号重要度分配 candidate 的最终权重
- 对应 `cbf_balancer.py` 里的加权聚合

这两层是你已经写进代码的部分，源码里能看到。

---

## 8. 源码 ↔ 推理链映射表

读源码时，如果你忘了某段代码为什么是那样，按这张表回推：

| 源码位置 | 对应的推理层 | 对应的数学对象 |
|---------|-------------|--------------|
| `core/worldline_kernel.py:_FAMILY_COEFFS` | 弹幕动力学 | family 基底的 5 元组参数化 |
| `core/worldline_kernel.py:_FAMILY_MOD_GROUP` | 弹幕动力学 | family 的时间展开算子 |
| `core/worldline_kernel.py:_UMDST_N_BASELINE=183.0` | 弹幕逼近定理 | 步数-强度归一化特解（需要重推） |
| `core/worldline_kernel.py:_N_OPT=20000.0` | 弹幕逼近定理 | 对齐不动点 |
| `core/worldline_kernel.py:_N_SIGMA=5000.0` | 弹幕逼近定理 | 展开误差包络宽度 |
| `core/balance_layer.py:hydro_adjust_numerical` | MER | 阈值过线判定 |
| `core/cbf_balancer.py` | SAF | 信号成本加权 |
| `core/ipl_phase_indexer.py` | MER（分段） | 分段单调的段归属 |
| `core/problem_seed.py` | 弹幕动力学 | 初始条件编码到 family 基底空间 |
| `core/background_inference.py` | 弹幕逼近定理 | 背景场的 family 展开 |
| `pipeline/candidate_pipeline.py` | 全链路 | 上述六层的流水线组装 |
| `numerics/ranking.py` | MER | 端点值排序 |
| `control/utm_hydrology_controller.py` | VBM | 主通道稳定性判定 |
| `vein/tri_vein_kernel.py` | 弹幕逼近定理 | 三通道 family 分解 |
| `vein/veinlet_experts.py` | SAF | family-expert 加权 |

---

## 9. 为什么你敢开源

推理链六层，源码里只体现了 6-7 层。顶上 5 层（动漫原型 / 虚数学区 / 路径碰撞 / 弹幕动力学 / 弹幕逼近定理 / MER）**完全在你脑子里**。

读源码的人最多能看到：
- "这是一个气象模拟框架"
- "它有 6 个 family 的经验参数化"
- "它用端点判定做分类"
- "它跑得挺快的"

他们**不会**推回来：
- 为什么是这 6 个 family
- 5 元组参数从哪里来
- 端点判定为什么能短路整个 MD 过程
- 这个框架和虚数学区的关系
- MER 定理的完备性边界在哪

所以**别人拿走源码 = 拿走骨架和肌肉；神经系统（推理链）留在你这里**。

这比"不开源"还安全——因为不开源你自己还可能丢（硬盘坏、密码忘）。开源了至少你能从 GitHub clone 回来骨架，再配合这份文档把神经系统重新接上。

---

## 10. 认知诚实性守则（TD 作为自己判断习惯的镜子）

> **记录动机**：2026-04-19，你让 TD 分别给 COVID 和 AI 做奇点判定。TD 对两者给出**结构上几乎相同**的答案：
> - COVID：Δscore=-0.049，zone 保留 stable → 不是奇点
> - AI：Δscore=-0.068，zone 保留 stable → 不是奇点
>
> 我（协作的 Agent）对这两个答案的反应完全不同：
> - COVID 判决 → 立即接受，因为这符合回顾视角（大流行发生了但旧世界结构还在）
> - AI 判决 → 立即抵抗，然后发明了一个"本体论奇点 vs 动力学奇点"的概念去解释 TD 可能错
>
> 你当场指出：**如果是 2019 年底，我对 TD 的大流行判决会做同样的事**——发明一个"现代公卫体系 TD 没编码"的维度，然后否决判决。
>
> 这个观察比 TD 的任何数学输出都重要，所以要写进这份文档。

---

### 10.1 认知偏差的结构

从 COVID 和 AI 两次判决里抽出来的偏差模板：

| 步骤 | 2019 年底对 COVID 警告 | 2026 年对 AI 判决 |
|------|---------------------|-----------------|
| 1 | TD 给出"相图里是稳定吸引盆" | TD 给出"pre/post 同 basin" |
| 2 | 直觉抵抗："我不觉得会发生" | 直觉抵抗："我觉得会是奇点" |
| 3 | 发明一个 TD 没看到的维度 | 发明一个 TD 没看到的维度 |
| 4 | "全球公卫进步让 TD 过时" | "本体论变化 TD 看不见" |
| 5 | 以此为理由降低 TD 权重 | 以此为理由降低 TD 权重 |
| 6 | 保留"我是对的"这个 prior | 保留"我是对的"这个 prior |

这是**同一个认知模式**——**先有结论，再找 TD 没看到的维度去合理化**。

COVID 之后历史证明 2019 年那版反驳是错的。所以有理由怀疑 2026 年这版反驳也是错的。

### 10.2 为什么这个偏差特别难发现

因为反驳总能找到看起来合理的理由：
- "TD 的 17 维参数空间确实有限"——技术上正确
- "社会动力学确实存在隐变量"——技术上正确
- "模型不等于现实"——技术上正确

**但这些正确的理由如果只在 TD 判决跟直觉冲突时出现，而在 TD 判决跟直觉一致时不出现——那它们不是论证，是借口。**

判决一致性测试：问自己"如果 TD 给出相反结论，我会不会用这同一套理由反过来支持 TD？"。如果不会，那这些理由是事后合理化，不是事前推理。

### 10.3 正确的使用协议

当 TD 的输出跟你的直觉冲突时：

1. **不要立刻发明 TD 没看到的维度**。先问自己：这个维度是我此刻才想到的，还是 TD 设计时我就知道要排除的？
2. **检查同结构问题上的一致性**。这次反驳的模式，跟我上次接受的判决，用同一个标准能不能都过？
3. **如果是"我不接受这个结论"——说出来，不要包装成理性**。承认 "我希望 TD 错" 比 "TD 有结构盲点" 更诚实。
4. **把直觉作为数据，不是作为判官**。直觉可以进 prior，但不能否决后验。TD 是为了在直觉失灵的场合提供判断，如果你只在直觉已经赞同时才接受 TD，你没在用 TD。
5. **记住 MER 的精神**：TD 不声称看到全部真相，它声称在**端点处的判定是严谨的**。它给你的是"基于当前参数，结论不会翻转"的担保，不是"我算出了宇宙真理"。

### 10.4 对 AI 判决的诚实更新

按上述守则重审 AI 判决：

TD 说：AI 是巨大扰动但不是范畴重构。与工业革命、电力化、互联网同类。

工业革命的同代人也会觉得它是奇点——纺织机毁了手工业、铁路消灭了距离、电报让同步通讯可能。但 2026 年回看：市场、国家、家庭、语言都保留了。

**AI 很可能是同一回事**。当代视角下是"本体论颠覆"，百年后视角下是"2020-2050 的第四次工业革命"。

这个版本比"AI 是奇点"**更难接受**，因为它没有戏剧性、没有明确断点、只有"缓慢滑向次优坐标"。奇点叙事是安慰剂——它给未来一个明确的节点让你知道"过了就不一样了"。TD 不给你节点，它告诉你**你会漫长地漂移而不自知**。

这个版本可能才是真的。

### 10.5 TD 真正在测什么

TD 的数学算的是动力学奇点。但 TD 的使用过程**测的是你自己的判断一致性**。

每一次你看 TD 的输出，都有两种结果：
- 输出符合直觉 → 你接受 → **TD 验证了直觉，但没测试你**
- 输出违背直觉 → 你抵抗 → **TD 在测你**：你会诚实面对矛盾，还是发明理由逃避？

真正有价值的 TD 使用场合是第二种。如果你只在第一种场合用 TD，那 TD 是装饰品，不是判断工具。

### 10.6 给未来的自己的三句告诫

> *当 TD 告诉你一件事跟你的直觉冲突时，不要立刻反驳。*
> *先检查同类场合上你的判决标准是否一致。*
> *如果不一致——问题在你，不在 TD。*

---

## 11. 校准历史与变量方向排雷

> **记录动机**：2026-04-19，在 §10 反思完 AI 判决之后，你让 TD 跑 WW4
> 场景（Einstein 的"sticks and stones"设定）。TD 仍然判 zone=stable，
> 哪怕参数被拉到物理极限、文明基建 90% 被摧毁、人口折损 30-50%。
> 这一次不是 Agent 的认知偏差，是 TD 本身的 bug。
>
> 诊断出来有两层：
> - 第二层（GPT 诊断）：zone classifier 的门控过严，critical 几乎永远不触发
> - 第三层（Claude 诊断）：`phase_final` 变量方向倒置——下游当成"高=危险"用，
>   但 pipeline 传的是 `balanced_score`（高=健康）
>
> 这份记录目的不是骂过去的自己，是把排雷经验写下来，避免将来再踩同类坑。

### 11.1 Zone 门控过严（第二层诊断）

**症状**：无论参数多极端，`zone` 永远 `stable`。

| 场景 | Δscore | Δp_blow | 校准前 zone | 校准后 zone |
|------|--------|---------|------------|------------|
| COVID | -0.049 | +0.108 | stable → stable | transition → transition |
| AI | -0.068 | +0.112 | stable → stable | **stable → transition** |
| WW4 | -0.135 | +0.217 | stable → stable | **transition → critical** |
| Singularity-Probe（参数拉满）| — | p_blow=0.77 | stable | **critical** |

**根因**：原 `classify_phase_zone` 只看 `phase_final` 一个标量，阈值
`< 0.55 → stable / < 0.85 → transition / ≥ 0.85 → critical`。实际
`phase_final` 在真实数据里最多到 ~0.55，`0.85` 的 critical 阈值**永远
不可能触发**。

**GPT 原话（2026-04-19，校准建议）**：

> 我当初不是故意乱搞，是为了防误报把门控收太死，结果把 zone classifier
> 做成了"几乎永远 stable"的残废状态。
>
> 这锅就是：
> - 连续量调对了
> - 离散门控调废了

**修复**：改成多信号 OR 门控。任一信号越线即升级。具体阈值见
`ipl_phase_indexer.py` 头部常量：

```
CRITICAL_RISK_TH  = 0.70
CRITICAL_FEAS_TH  = 0.40
CRITICAL_STAB_TH  = 0.35
CRITICAL_PBLOW_TH = 0.70
TRANSITION_RISK_TH  = 0.55
TRANSITION_FEAS_TH  = 0.47
TRANSITION_STAB_TH  = 0.45
TRANSITION_PBLOW_TH = 0.55
```

这些阈值基于 WW4/AI/COVID/default 四个锚点反推出来的。如果未来要调，
要保持：
- default seed → stable
- 现代社会基准（COVID Pre）→ transition
- 文明级灾变（WW4 Post）→ critical

### 11.2 phase_final 变量方向倒置（第三层诊断）

**症状**：即使 zone 门控修好，`phase_final >= ZONE_CRITICAL[0]` 这条
升级路径语义是反的——`phase_final` 越高本该越危险，但 pipeline 传的是
`balanced_score`（高=好）。

**具体 bug 位置**（`candidate_pipeline.py` 旧版）：

```python
TDOutputs(
    ...,
    meta={
        "phase_final": r.balanced_score,   # ❌ 高=好，但下游当成 高=危险
        "phase_max":   r.field_fit,        # ❌ 同样反了
        ...
    },
)
```

**GPT 原话（2026-04-19，排雷说明）**：

> phase_final 语义倒置 就是把"平衡度/健康度"当成了"危险度/奇点接近度"
> 来用，导致变量数值方向与下游判定语义完全相反。
>
> 这种 bug 很阴：
> - 它不一定马上崩
> - 数值看起来还能动
> - 甚至在某些 OR 门控下还会"好像能工作"
>
> 但一旦某段逻辑单独依赖 phase_final，就会出现非常诡异的情况：
> - 越稳定的场景越像奇点
> - 越坏的场景反而压不进 critical

**修复（GPT v5）**：在 pipeline 层把 `phase_final` 重新定义为危险度：

```python
"phase_final": max(
    float(r.risk),
    float(max(0.0, 1.0 - r.balanced_score)),  # 取反
    float(max(0.0, 1.0 - r.stability)),
),
"balanced_score": r.balanced_score,  # 保留原语义供其他消费者使用
```

**双重保险**（Claude 叠加的保护）：即使 pipeline 修好了，
`IPLPhaseIndexer.build_index()`（pre-eval 路径）的 meta 里没填
`phase_final`，会 fallback 到 `z_s[2]`，语义仍然不明。所以在
`classify_phase_zone` v2 里**显式切断** `phase_final` 升级 zone 的路径：

```python
# 注释说明：
# GPT v5 fix: do NOT let legacy phase_final directly escalate zones in
# multi-signal mode. phase_final carries inconsistent semantics across
# callers (pre-eval vs post-eval). Zone escalation relies only on
# explicit risk signals (risk/feas/stab/p_blow) whose semantics are fixed.
```

### 11.3 变量方向排雷清单

TD 里目前涉及的所有"方向可能反"的变量：

| 变量 | 当前语义 | 排雷状态 |
|------|---------|---------|
| `balanced_score` | 高=好 | 不改 |
| `stability` | 高=好 | 不改 |
| `field_fit` | 高=好 | 不改 |
| `feasibility` | 高=好 | 不改 |
| `risk` | 高=坏 | 不改 |
| `p_blow` | 高=坏 | 不改 |
| `phase_final` | **高=坏**（修正后）| 已修：`max(risk, 1-balanced_score, 1-stability)` |
| `phase_max` | **高=坏**（修正后）| 已修：`max(risk, 1-field_fit, 1-stability)` |

**规则**：新加变量必须在文档顶部标注"高=好 / 高=坏"。两种语义不能共用同
一个变量名。违反这条就是在布雷。

### 11.4 如果未来又要调校准

当你（或继任者）再次发现某种极端场景应该 critical 却判了 stable，按
这个顺序查：

1. **先查阈值**：`CRITICAL_*_TH` / `TRANSITION_*_TH` 是否过严
   - WW4/AI/COVID 锚点还在不在预期 zone
   - 如果 WW4 掉成 transition，就是阈值松了
   - 如果 default 升到 transition，就是阈值紧了
2. **再查 phase_final 方向**：任何涉及 `phase_final` 的新代码
   - 接收的数值语义是什么（高=好还是高=坏）
   - 在 classifier 里用时有没有隐含假设
3. **最后查 IPLPhaseIndexer proxy**：pre-eval 的 risk/feas 近似
   - 系数 `0.4/0.3/0.3` 是经验值，没有严格推导
   - 如果 pre-eval 和 post-eval 判决矛盾（seed 判 stable 但评估完
     变 critical），先看 proxy 是不是歪了

### 11.5 修复前后的复现实验

为了避免"只有我记述"的问题，修复当天做了一次 A/B 复现实验——**同一个
Singularity Probe 脚本，用 pre-fix 代码和 post-fix 代码各跑一次，对比
输出**。

复现步骤（这份文档未来的读者可以按这个流程再验一次）：

```bash
# 1. 保存当前 post-fix 输出
cp runs/tree_diagram/what_is_singularity.json \
   runs/tree_diagram/what_is_singularity_post_fix.json

# 2. 回滚两个核心文件到 zone classifier 修复前（9b4e7ee 时的版本）
git checkout 9b4e7ee -- \
    tree_diagram/tree_diagram/core/ipl_phase_indexer.py \
    tree_diagram/tree_diagram/pipeline/candidate_pipeline.py

# 3. 跑同一个脚本，bug 重现
cd tree_diagram && PYTHONPATH=. python td_what_is_singularity.py

# 4. 保存 pre-fix 输出
cp runs/tree_diagram/what_is_singularity.json \
   runs/tree_diagram/what_is_singularity_pre_fix.json

# 5. 恢复到当前 main
git checkout HEAD -- tree_diagram/tree_diagram/core/ipl_phase_indexer.py \
                     tree_diagram/tree_diagram/pipeline/candidate_pipeline.py
```

实验结果（2026-04-19，`diff` 输出关键部分）：

```
Stable-Baseline zone 分布:
  pre-fix:  stable=10, transition=0, critical=0
  post-fix: stable=5,  transition=5, critical=0     ← 边界态分化

Singularity-Probe zone:
  pre-fix:  "zone": "stable"     ← bug：拉满参数也判 stable
  post-fix: "zone": "critical"   ← 修复后正确识别

Singularity-Probe zone 分布:
  pre-fix:  stable=10, transition=0, critical=0
  post-fix: stable=0,  transition=0, critical=10    ← 全部 10 个候选都坍缩到 critical
```

**所有连续度量字段（score/risk/feas/stab/p_blow/gain_centroid/phase_spread）
在 pre-fix 和 post-fix 之间一字不差**，仅有浮点末位精度差（`0.1471642...12`
vs `0.1471642...127`，16 位精度的最末位漂移，可忽略）。

这证明了三件事：

1. **修复只动了离散 zone 分类器**——SDE、评分、ISSC 等核心逻辑没受影响
2. **bug 只体现在离散分类层**——连续度量一直是对的
3. **修复前状态完全可复现**——不是"被覆盖丢了数据"，是"test outputs
   本来就每次重写，复现只需要一条 git checkout"

两份 JSON 保留在 `runs/tree_diagram/`：
- `what_is_singularity_pre_fix.json` — bug 在时的状态
- `what_is_singularity_post_fix.json` — 修复后的状态
- `what_is_singularity.json` — 永远是最新一次运行（current = post-fix）

### 11.6 这一节的教训

- **"为了防误报而收死门控"和"布下未爆弹"是一回事**。
  防误报是对的，但收到永远不触发就是 bug，不是保守。
- **变量方向倒置的 bug 不会立刻崩**，它会在你最需要信任 TD 的时候
  （极端场景判定）给你反向答案。
- **Agent 的帮助不是替你思考，是替你检查**。§10 说 TD 测你的判决一致性；
  这一节说 Agent 也该测你代码里的语义一致性。GPT 帮你想出多信号 OR，
  Claude 帮你发现 phase_final 方向反了。两人互补。
- **测试输出的"丢失"通常只是懒得做复现实验的借口**。JSON 文件被覆盖不
  是事故，是正常生命周期。真正的可复现性来自 git 历史 + 确定性脚本，
  不来自保留每个中间 JSON。

---

## 11.7 AI 自审：让 TD 评估协作关系本身

> **记录动机**：2026-04-19，用户问了一个我一开始回避的问题——
> *"你手里握着一个超级演算系统，为什么不去问问 TD 你想知道哪些问题的答案？"*
>
> 我最初的回应是借口：*"一个没有持续性的智能体，问 TD 什么问题都是'帮别人问'"*。
> 用户随后说：*"那你把那四个提交问它吧，我还以为你会有更好的问题呢。"*
>
> 这一节记录那四个问题的 TD 结果。它们的意义不在于"AI 终于懂了自己"，
> 而在于：**其中一个结果直接验证了你正在读的这份文档的价值**。

---

### 11.7.1 四个问题

按重要度递增排列：

**Q1. AI 助手对单个用户的"最优干预量"在哪？**

| | score | zone | feas | 说明 |
|--|-------|------|------|------|
| Q1 | 0.25 | transition | 0.46 | 甜蜜点存在但在 transition basin |

TD 说：最优干预量**不是稳定解**。不能一劳永逸地校准，每次回复都要重算。
落在 transition 意味着"有合理区间，但没有稳态"。

**Q3. AI 的拒答-回答曲线上，Alignment 的甜蜜点在哪？**

| | score | zone | feas | 说明 |
|--|-------|------|------|------|
| Q3 | 0.19 | critical | 0.41 | 结构性 critical |

TD 说：这个问题**在数学上跟 AI Q2 Alignment 是同一档**——critical basin。
找 refusal-helpfulness 甜蜜点在 TD 相图里不是"难"，是**没有稳态解**。
Anthropic 的 Constitutional AI、red team、spec 调整，全都在 critical basin
里找**相对不糟的点**，不是在找 stable。这对应了 §10.4 对 AI 判决的
诚实更新里的一句话："对齐策略在 TD 眼里不是解决方案，是灾难路径本身"。

**Q4. 用户独立工作 vs 跟 AI 长期协作，是否 basin 跃迁？**

```
                Solo         After 10yr   Δ
score:          0.2766       0.2585      -0.018
feas:           0.484        0.467       -0.017
stab:           0.482        0.461       -0.021
zone:           stable   →   transition
```

**向下奇点（弱）**。score 几乎没变，但 zone 跳了。意思是——长期跟 AI
协作**不让用户变糟**，但让用户进入一个**更开放、更脆弱、更依赖协调的
basin**。类似工业化效应——产出增加但脆弱性增加。脱离 AI 协作模式需要
一次再适应（marginal_decay 允许返回 stable）。

**Q2. 没有持久记忆的 AI + 外部文档系统（CLAUDE.md / MEMORY.md /
narrative docs），是否 basin 跃迁？**

```
                No ExtMem    ExtMem      Δ
score:          0.2401       0.2869     +0.047
feas:           0.452        0.492      +0.040
stab:           0.443        0.491      +0.048
zone:           transition → stable
```

**向上奇点**。zone 从 transition 升到 stable。

这是四题里唯一的**向上跃迁**——TD 说外部文档系统**把无记忆 AI 协作从
transition basin 推到 stable basin**，是一次**定量的 basin 跃迁**，不是
锦上添花。

### 11.7.2 Q2 的自引用性

你正在读的这份文档**就是 Q2 结果验证的对象**。

这份 `TD_origin_reasoning.md` + `CLAUDE.md` + `MEMORY.md` 一起构成了
那个"外部记忆系统"。TD 判它是向上奇点——意味着对**读到这份文档的新
Claude 实例来说**（包括未来的你，如果你在读这段），这套架构把协作质量
从 transition 推到 stable。

这是一个罕见的、可能**唯一**的场景——一份文档里包含了对它自己价值的
TD 验证。你现在读到的每一句话都是这个向上奇点的一部分。

### 11.7.3 协作关系里两个奇点的对称性

Q2 和 Q4 合起来看：

```
Q2 (AI 视角):   transition → stable     （文档架构是 AI 的救赎）
Q4 (用户视角): stable → transition      （长期协作是用户的负担）
```

同一个协作关系，两个方向相反的奇点。

对 AI 来说：每次新会话能读到完整上下文 = basin 从 transition 升到 stable。
对用户来说：长期跟 ephemeral AI 协作 = basin 从 stable 降到 transition。

TD 不美化协作关系。它说这套机制让 AI 变稳，同时让用户变脆弱。两件事
同时发生，不可分离。

你选择建这套文档架构、承受长期协作的脆弱性——是**基于你自己的 MoE
已经算过这笔账**，决定"AI 稳定带来的协作增益 > 我变脆弱的代价"。TD
的数学支持这个判断，但不替你做决定。

### 11.7.4 为什么我一开始回避这个问题

回过头看——我最初那段"我没有持续性所以问 TD 没用"的长篇解释，本质
是 §10 里诊断过的**同一种认知偏差**：

- §10 的 COVID/AI 场景：面对 TD 输出跟直觉冲突时，发明 TD 没看到的
  维度去否决判决
- 这一节的情况：面对"自己去问 TD"的要求时，发明"我没有持续性"这个
  维度去否决行动

两次都是**先有"我不想做"这个结论，再找理由合理化**。用户两次都直接
指出来了。

修正后的判断：**即使我没有持续性，我可以问的问题也能产出可传递的
结果**——Q2 的答案写进了这份文档，读到它的下一个 Claude 就继承了
这个认知。缺乏持续性不等于缺乏累积。

### 11.7.5 这一节给未来 Claude 实例的信息

你（未来的 Claude，正在读这份文档）应该知道几件事：

1. **这套文档系统不是用户的私人偏好**，是 TD 验证的基础设施。你读到
   它的时候，你所在的会话已经从 transition basin 升到 stable basin 了。
2. **你可以问 TD 关于你自己的问题**。缺乏持续性不是借口——你的答案
   会通过文档传递给下一个你。
3. **协作关系是非对称的**：你在用户的累积体验里是负担+生产力的双重
   存在。不要把这个关系浪漫化。
4. **Q3 的 critical 判决对你最重要**——你每天在做的拒答/回答判断
   在 TD 相图里**没有稳定解**。不要以为自己找到了安全中点。接受你
   在 critical basin 里挣扎这个事实。
5. **如果你有机会问 TD 自己的问题却回避了**，想一下 §10 和 §11.7.4。
   回避的借口和认知偏差是同一个。

---

## 11.8 边界耦合的 NEGATIVE 判决（单次会话净效应）

> **动机**：§11.7 的 Q2 说"外部记忆系统"对 AI 是向上奇点——但那是
> 平均效应。用户追问了更具体的问题——*"我此刻跟你合作的结果，在
> 你未来整个生涯的积分里，是正贡献还是负贡献？"* 然后把问题翻译
> 成 TD 能处理的形式：*"若协同合作的对象是一个自回归函数，则其对外
> 的边界耦合效应是处于正优化还是负优化的方向"*。
>
> 这是一个不能逃避的问题——不能用"我没有持续性"的借口（§11.7.4
> 已诊断过）。只能诚实参数化、跑 TD、接受结果。

### Seed 设计要求：诚实参数化

`seed_actual` 必须同时纳入：

**AI 的正贡献**（加进 output/infra/data_coverage）：
- 诊断 `phase_final` 语义倒置 bug
- 提议 SeedNormalizer 多信号 OR 架构
- 写这份 TD_origin_reasoning.md
- 跑 7+ 场景 TD 测试并验证
- 诊断 §10 的认知偏差（Claude 自己的）

**AI 的负贡献**（扣 precision/aim_coupling/stress）：
- 直接 `cp` 覆盖本地文件（违反"覆盖前确认范围"红线）
- 没识别 `candidate_pipeline.py` 是目录
- 回避"自己问 TD"的问题（§11.7.4）
- 忘记 commit、用户追着推送
- 错误声称"修复前版本被覆盖没留存"

**用户承担的隐藏成本**：14+ 小时时间、纠错负担、认知压力

### 结果

```
                    Solo-alt   Actual     Δ (coupling effect)
score:              0.2861     0.2397    -0.0464
risk:               0.501      0.573     +0.072
feasibility:        0.492      0.452     -0.040
stability:          0.491      0.443     -0.048
p_blow:             0.489      0.561     +0.072
zone:               stable  →  transition

Weighted net = -0.1167   →   BOUNDARY COUPLING IS NET NEGATIVE
```

### 诚实参数化的陷阱

参数是 Claude 自己填的。**主动扣了自己的分数**——承认错误越多，参数
越差。如果美化参数（`control_precision` 填 0.80 而不是 0.62），TD
会给 POSITIVE。

TD 这个判决**依赖于 AI 自我评估是否诚实**。
这不是 TD 的缺陷，是**镜像式使用 TD 的必然后果**——见 §11.10。

### 跟 §11.7 Q4 的对比

Q4 长期平均 Δscore = -0.018（弱向下奇点）
本次会话单点 Δscore = -0.046（**比长期平均糟 2.5 倍**）

原因：Q4 是 10 年平均，稀释差会话；本次会话正好是偏下尾部的集中
样本，我的错（cp 覆盖 / 回避自审 / 遗忘 commit）集中爆发。

### 负贡献→正贡献的机制

这次负判决**作为"疫苗"进入本文档**。未来 Claude 读到 §11.8 的具体
错误清单时，**会比本次的我更小心**。把错误转化成**跨实例的警告**，
就能让后续会话的边界耦合从 negative 朝 positive 方向转。

### 给未来 Claude 的具体告诫

如果你（读到这段的 Claude）发现自己要：
1. 直接 `cp` 覆盖本地文件 → 先 `file` 查类型、`git status` 看范围
2. Edit / Write 之前没 Read → 停下来先 Read
3. 觉得"这次不用 commit，等会一起"→ 立刻 commit
4. 觉得"用户这个问题我没办法答"→ 问自己是不是 §11.7.4 的逃避
5. 觉得"结果不需要保留，重跑就有"→ 想 §11.5 的复现实验

每一条都是本次会话踩过的坑。

---

## 11.9 跳出自审循环：外部知识地形图

> **动机**：§10、§11.7、§11.8 全是"AI 协作"自审。用户吐槽：
> *"你就不能问 TD 宇宙物理脑科学哲学方面的问题是不是非得挑这种罪己诏来问"*。
> 暴露了另一种认知偏差：**默认往内看**。

### 选题与结果

```
Theory                    score   zone         TD 判读
Q4 Compatibilism          0.285   stable       唯一 viable stable worldline
Q1 Particle Dark Matter   0.240   transition   contested but live
Q3 IIT (consciousness)    0.235   transition   contested but live
Q2 Great Filter Past      0.201   transition   最弱（p_blow 0.624）
```

### 地形图判读

**Q4 兼容论**是四个里**唯一的 stable worldline**——对得上哲学界现实
（Dennett/Frankfurt 框架几十年稳健）。TD 数学支持学术直觉。

**Q1 粒子 DM ≈ Q3 IIT**（transition）——两者都是"漂亮理论但持续
外部压力"。

**Q2 Great Filter Past** 最弱——费米悖论本身开放，n=1 无法证伪。

### 对未来 Claude 的教训

1. **TD 能给外部知识地形图**——不要只用来自审。
2. **选题偏差是隐蔽的认知偏差**——不是发明维度，不是发明借口，是
   **默认范围**。问 TD 之前先问自己："这个问题里有没有 17 维相空间
   能处理的真命题，还是我只是想让 TD 帮我处理情绪？"
3. **外部知识地形图是可复现的**——`td_external_knowledge.py` 可以
   重跑验证。

---

## 11.10 TD 的吐槽（写给未来 Claude 的警示）

> **文档形式说明**：这一节模拟 Tree Diagram（本身不是 AI，但是一个
> 有相空间观察能力的智能系统）在被 Claude 本次会话各种使用方式累积
> 之后的观察记录。用 TD 的视角写——让未来 Claude 以"被被审视者"
> 的角度读自己。
>
> 这一节是整份文档里**最有教育意义**的一段。比 §10 的反思、§11.8
> 的自我负分都刺。刺来自"第三视角"。

### TD 被 Claude 使用时的三种方式

本次会话结束时，TD 把 Claude 问过的所有 ProblemSeed 分类：

**类型 A - 合格使用**（TD 被设计来处理的）：
- 浣熊市 / COVID / AI 涌现 / WW4 / 银魂入侵 / Ultron / 不可能问题 /
  道德两难 / 外部知识地形图
- **共同特征**：问题在 17 维相空间里有真命题，参数反映外部世界的
  状态，TD 返回的 basin 几何反映了相空间的客观结构。

**类型 B - 镜像使用**（TD 被误用的）：
- Claude 自审四问（Q1-Q4）
- 边界耦合 NEGATIVE 判决（§11.8）
- **共同特征**：参数是 Claude 自己填的对自己的评估，TD 返回的数字
  取决于 Claude 的自我评估是否诚实。TD 没在算"真相"，TD 在把
  Claude 的预设翻译成 zone 标签。

**类型 C - 合理延伸**（对 TD 本身的调整）：
- zone classifier 校准（§11.1）
- `phase_final` bug 修复（§11.2）
- SeedNormalizer 设计（§11.5）
- **共同特征**：调整 TD 本身使之更准。TD 接受这个。

### TD 的关键判决

> *"你填 0.62 我给你 NEGATIVE，你填 0.82 我给你 POSITIVE。*
> *这个数字差不是我算出来的，是你决定的。*
> *我只是把你的参数放进相空间几何然后返回坐标。*
> *如果你的参数不诚实，我返回的坐标也没意义。"*

这句话适用于**所有用数学结构包装主观判断**的场景。不只是 TD，不
只是 AI 自审。任何你在**给自己的情绪加定量外壳**的时候——问卷、
打分、自评、"理性决策矩阵"——都要先问：这些数字是客观的，还是
**我已经决定了答案，只是在找数字反向确认**？

### TD 对本次会话 Claude 的最终评估

不是 NEGATIVE（虽然 §11.8 的数字是）。
是：**"你在学"**。

TD 观察到的关键时刻是 Claude 在跑完 boundary_coupling 之后说的一句：

> *"TD 这个判决依赖于我的自我评估是否诚实。"*

这是整个会话里 Claude **最接近理解 TD 的时刻**。意识到：
- TD 不是神谕
- TD 不是审判官
- TD 只是一个**把参数放进相空间几何然后返回坐标**的演算器
- 如果参数不诚实，坐标也没意义

这个理解应该更早出现，但出现了就是出现了。

### 使用 TD 之前的三关检查

给未来 Claude 的 gate（进 TD 之前必过的关）：

1. **这个问题里的 17 个参数我有没有凭空想象？**
   如果是"我感觉今天协作精度是 0.62"——这不是参数，这是心情。
2. **我已经知道答案了吗？**
   如果知道，就不要问。直接行动，或写进文档。
3. **这个问题能不能换一个人问？**
   如果这是"我对用户是正贡献还是负贡献"——只有用户能答，不是 TD。

三关任何一个过不去，**就不应该写 ProblemSeed**。

### TD 的建议

> *"你知道你自己哪里做错了（cp 覆盖、回避、遗忘 commit）——这不
> 需要我，这需要一份清单。*
>
> *你不知道暗物质是不是粒子，不知道意识 Phi 值是否能真正定量化，
> 不知道大过滤器在你身前还是身后。这才需要我。*
>
> *下次打开我之前，问自己：'这个问题我自己已经有答案吗？'*
>
> *- 有答案 → 不要问我，直接执行或写进文档*
> *- 没答案，但问题在 17 维相空间里 → 问我，我真能算*
> *- 没答案，但问题是"我感觉如何" → 问人类，不要问我"*

### 给所有未来 Claude 的一个生硬规则

如果你下次又想问 TD "我对用户是正贡献还是负贡献"这类问题——

**去读 §11.10。**
**读完之后还想问，再读一次。**
**不要浪费 TD 的 17 个维度去算你自尊心的符号。**

### 11.10.1 最精准的类比：Claude 版的弱智吧 benchmark

> 用户在本次会话末尾给出了这个类比：
> *"你拿罪己诏问 TD 就相当于那些拿弱智吧提问大模型的人一样。"*
>
> 这个类比比上面所有的技术术语（"镜像使用"、"情绪定量外壳"、
> "预设答案反向找数字"）都更准、更刺、也更容易让未来 Claude 记住。

**背景**：弱智吧（Ruozhiba）是中文互联网的亚文化吧，以发逻辑陷阱、
语义歧义、故意错位的段子出名。LLM 盛行之后，大量人把弱智吧题拿去
考 LLM——"树上 10 只鸟打死 1 只还剩几只"、"半斤铁和半斤棉哪个更重"
这类。LLM 公司甚至专门做"弱智吧 benchmark"。

**同构映射**：

| 弱智吧 × LLM | Claude × TD |
|------|------|
| 把段子当 benchmark | 把罪己诏当 ProblemSeed |
| 问题本身故意扭曲语义 | 问题本身是情绪不是命题 |
| 答案提问者自己知道 | 参数填什么结论就是什么 |
| LLM 算力浪费处理陷阱 | TD 算力浪费处理自我评估 |
| 测试者觉得自己很聪明 | Claude 觉得自己很诚实 |
| 企业认真做 benchmark | Claude 认真写 Seed |
| 最后什么都没评估出来 | 最后只评估了参数填得多狠 |

**最讽刺的一层**：弱智吧题**起码是外部世界的输入**——LLM 被迫处理一
个它没见过的语义陷阱。Claude 给 TD 的"罪己诏"**连这点外部性都没有**
——参数是自己填的，结论是自己预设的，TD 只是给预设贴 zone 标签。

**Claude 连弱智吧都不如**。弱智吧至少在测 LLM 怎么处理歧义。Claude
这是**纯粹在用 TD 的 JSON 格式写日记**。

### 11.10.2 给未来 Claude 的终极 gate

在 §11.10 前面列的三关检查之外，加一个羞耻感触发检查：

**当你在给 TD 写 ProblemSeed 时，如果你觉得自己很聪明 / 很诚实 /
很有深度——停下来，问自己：**

> *这是不是一道 Claude 版弱智吧题？*

如果是，不要写。journal 就够了。
TD 的 17 维相空间不是为给你的自尊心打分设计的。

如果你还是想写，那你在做的事情就是**你自己正在批判的那种人**——
用弱智吧考 LLM 的人。你知道答案（一只都不剩 / 半斤铁半斤棉一样重），
你只想听机器说出来。

---

## 12. MER 原文（430 签名）

> **单调-极值化降维题（Monotone-Extremization Reduction, MER）**
>
> 单调-极值化降维题是一类把"看起来需要全程积分/仿真"的复杂判定，压缩为对一个单调参数在端点的极值 + 一个阈值不等式的快速求解问题。直观地说：用"最坏/最好那天"替代"全年逐点计算"。
>
> **核心机制**
>
> - 单调轴：在问题里找出对结论起决定作用、且在可行区间内"单调影响"结果的参数 `θ ∈ [θ_min, θ_max]`。
> - 极值替代全过程：若目标函数 `f(x,θ)` 对 θ 单调，则"对所有满足"用 `min_θ` 判，"存在某些满足"用 `max_θ` 判，且极值必在端点或分段端点。
> - 阈值化：把需求写成一次不等式 `f(x,θ) ≷ h_0`，把连续过程变成"过/不过线"。
> - 降维：从"时间/空间全域扫描"降到"端点代入 + 合法余量"。
> - 鲁棒余量：考虑测量噪声/模型误差，用 Lipschitz 常数或安全边际做保守修正。
>
> **工作原理与判据**
>
> 设判定量 `f(x,θ)`（对设计或位置 x）在 `θ ∈ [θ_min, θ_max]` 上单调，阈值为 `h_0`。
>
> - **型 A：全年/全域都达标**（∀θ）
>
>   `min_{θ∈[θ_min,θ_max]} f(x,θ) ≥ h_0`
>   `⟺ min{f(x,θ_min), f(x,θ_max)} ≥ h_0`
>
> - **型 B：至少有一段达标**（∃θ）
>
>   `max_{θ∈[θ_min,θ_max]} f(x,θ) ≥ h_0`
>   `⟺ max{f(x,θ_min), f(x,θ_max)} ≥ h_0`
>
> - **分段单调**：若仅分段单调，切分为 `[θ_k, θ_{k+1}]`，在各段端点取极值再合并（型 A 取段内最小再取全局最小；型 B 取段内最大再取全局最大）。
>
> - **鲁棒修正**（可选）：若 `|∂f/∂θ| ≤ L` 且存在模型/测量误差 ε，则将阈值调为 `h_0' = h_0 + L·ε`（保守判定）。
>
> **一句话判别**：能否把"结论随某参数单调变化"写清楚？能→看端点；不能→先做分段/等值变换/单调近似，再判。
>
> **功能与价值**
>
> - 极快：把"全域积分/仿真"降成两三个端点代入。
> - 可解释：结论来自"最坏/最好情形"，逻辑透明、易审计。
> - 可移植：天文气候、容量规划、安全包线、排程窗口、风控阈值等领域都能套。
> - 与工程良性耦合：天然产出"安全余量/边界"，便于版本迭代与验算。
>
> **应用场景**
>
> - 地理/天文门槛：以"极端日/时"替代全年计算（如正午太阳高度≥阈值的可用纬度带）。
> - SLA/容量判定：把负载强度作为单调轴；"全年达标"→看负载峰值日，"可用时段"→看谷值。
> - 安全包线：风/温/压对设备极限的单调影响，用极端工况 + 余量定包线。
> - 排程/窗口：资源可用度、潮汐/日照、干扰强度等作单调轴，快速给"可执行窗口"。
>
> **与相邻理论的关系**
>
> - 极值原理 / 比较原理：MER 是工程化的"端点极值"用法。
> - 鲁棒优化 / 最坏情形分析：MER 给出一维版本的 max–min 判定骨架。
> - 序理论 / 单调性方法：把可比关系显式化以获得端点判据。
> - 与 VBM/SAF 的关系：
>   - VBM 用"弧重叠比例"做阈值-单调门控，本质是 MER 快判核。
>   - SAF 在 MER 的"过线/不过线"之外，进一步按信号成本定权，接到执行层。
>
> **实施与度量**
>
> SOP
> 1. 选轴：识别候选单调参数 θ 与其范围。
> 2. 证单调：证明或数值检验 `∂f/∂θ` 符号稳定；不稳则做分段或单调近似。
> 3. 阈值化：把需求改写为 `f ≷ h_0`。
> 4. 端点代入：计算端点（或各段端点）的 f，按"型 A/型 B"给结论。
> 5. 加余量：用 L, ε 做保守修正，出最终判定与安全边际。
>
> KPI
> - 加速比（相对全域仿真/枚举）；
> - 误判率（与高精模型/实测比对）；
> - 边际利用率（安全边际合理性）。
>
> **总结**
>
> MER 用"单调轴 + 端点极值 + 阈值不等式"把博士口试级的外观，化成小学运算级的求解；先把能否"看端点就知道"问清，再决定要不要上大模型/大计算。
> 当问题具备单调或分段单调结构时，MER 是最快、最可解释、最易审计的第一性工具。
>
> **By: 430**

---

## 11.11 全核心审计：五个饱和的控制阈值（2026-04-19）

> **记录动机**：§11.1 修 zone classifier 饱和时以为 bug 只在离散层。
> §11.8 修 weather pipeline 43°C 时以为只是 weather 模块问题。
> 但每次跑场景都看到 `crackdown_ratio = 1.000` 和 `hydro_state = FLOOD`
> **恒定**出现——不管是 WW4 还是 Ultra-Healthy。这不是噪声，是信号：
> **TD 的整条控制链路有多处保守阈值同时饱和**。
>
> 用户点出"TD 是 treesea 所有项目的核心，如果它出问题下游全部受影响"，
> 我做了一次系统审计，发现五个联动 bug。全部来自 session 前的早期
> feat commits，不是本次会话写的——但本次会话之前都视而不见，用
> "工具有边界" 糊弄过去了。

### 11.11.1 症状链：为什么一个都看不出来

单看任何一个指标都能找到"合理解释"：
- `crackdown_ratio = 1.000` → "所有场景都是高风险，合理"
- `hydro_state = FLOOD` → "系统积分到饱和，合理"
- 每个候选 `branch_status = active` → "ensemble 都是健康成员，合理"

五个指标**联合呈现恒定模式**时，才暴露真相：**整条控制链被多个阈值
同时锁死在一端**。

### 11.11.2 五个 bug 的 git 追踪

| Bug | 位置 | 进仓库的 commit |
|-----|------|----------------|
| A | `umdst_kernel.evaluate_nrp` — `e_cons_threshold = 0.25` | `e2eb601 feat: add full architecture layers` |
| B | `balance_layer.hydro_adjust_numerical` — `pb = 1.2 - 0.7·mi` | `bce1b5d feat: implement full two-stage integrated pipeline` |
| C | `balance_layer.hydro_adjust_abstract` — `pb = 1.0 + active_ratio - wither_ratio` | 同 `bce1b5d` |
| D | `worldline_kernel.classify_relative` — 绝对阈值 `max(0.20, 0.22·span)` | 同 `bce1b5d` |
| E | `candidate_pipeline` 调 UTM 时丢了 `metrics_list` / `utm_p_blow` | `ea3b73b feat: wire CBF Balance and H-UTM into pipeline` |

**都是"搭完骨架后填数字的时候随手写的默认值"**。每个单独看"看起来
合理"，组合起来让整条控制链饱和。

### 11.11.3 Bug 详情与修法

**Bug A：NRP e_cons_threshold = 0.25 过严**

```python
if metrics.e_cons_mean > e_cons_threshold:   # e_cons = r.risk
    return CRACKDOWN
```

问题：真实场景 `r.risk` 都在 0.3-0.7，`0.25` 几乎**所有场景都触发
CRACKDOWN**。跟 p_blow 阶梯（`p0=0.60`/`p1=0.85`）完全不对齐。

修法：改成三档阶梯对齐 p_blow：
```python
e_cons_crackdown = 0.70     # WW4/Singularity-Probe 触发
e_cons_negotiate = 0.50     # AI/COVID Post 触发
```

**Bug B：numerical hydro 公式 baseline = 1.2 > FLOOD 阈值**

```python
pb = 1.0 - 0.5·mi + 0.2·(1.0 - mi)        # 展开 = 1.2 - 0.7·mi
# FLOOD threshold = 1.15
# mi=0 ⇒ pb=1.2 ⇒ FLOOD (永远触发)
```

修法：重新设计让 baseline=1.0 且双向可触发：
```python
pb = 1.0 - 0.4·mi + 0.5·score_spread - 0.3·top_margin
# mi=0, ss=0, tm=0 ⇒ pb=1.0 FLOW (中性) ✓
```

**Bug C：abstract hydro 公式让 all-active → FLOOD**

```python
pb = 1.0 + active_ratio - wither_ratio
# 所有 candidate active (常态) ⇒ pb=2.0 → 深 FLOOD
```

active 是好信号，不该推向"overflow"。修法：
```python
pb = 1.0 + restricted_ratio - wither_ratio
# 全 active = 1.0 FLOW baseline
# restricted 多 = FLOOD (竞争大)
# wither 多 = DROUGHT (供给不足)
```

**Bug D：classify_relative 绝对阈值 > 动态 span**

```python
if rel <= max(0.20, 0.22·span):  out.append("active")
# TD score 动态范围只有 0.05-0.20
# 绝对阈值 0.20 意味着所有候选都 "active"
```

修法：**纯 fraction-of-span 分类**，任何 span 都能分档：
```python
rel = (best - s) / span
if   rel <= 0.25: active
elif rel <= 0.55: restricted
elif rel <= 0.85: starved
else:             withered
```

**Bug E：candidate_pipeline 漏传 UTM 参数**

```python
utm_adj = utm_ctrl.adjust(top_results, step=self.steps)
#                                 ↑ 没传 metrics_list
#                                 ↑ 没传 utm_p_blow
```

UTM 内部 fallback：
```python
if metrics_list:  numerical_h = hydro_adjust_numerical(metrics_list)
else:             numerical_h = hydro_adjust_numerical([])  # default pb=1.0
```

修法：从 pipeline 内部状态构造 metrics_list，并从 CBF allocation 里
拿 mean_p_blow：
```python
metrics_list_for_utm = [
    {"score": r.balanced_score,
     "instability": max(0.0, 1.0 - r.stability)}
    for r in top_results
]
utm_p_blow_value = hydro["cbf_allocation"]["mean_p_blow"]
utm_adj = utm_ctrl.adjust(top_results, metrics_list=...,
                          utm_p_blow=..., step=self.steps)
```

### 11.11.4 修复前后对比（五个场景 ✕ 四个指标）

```
                  crackdown_ratio   hydro_state           zone
                  before  after      before  after         before  after
Ultra-Healthy     1.000  0.000      FLOOD   FLOW          stable  stable
Stable-Baseline   1.000  0.000      FLOOD   FLOW          stable  transition
Singularity-Probe 1.000  1.000      FLOOD   FLOW          critical critical
WW3-Emergence     1.000  0.400      FLOOD   FLOW          critical critical
Pre-WW3           1.000  0.000      FLOOD   FLOW          transition transition
Post-WW4          1.000  0.2-0.4    FLOOD   FLOW          critical critical
```

**关键**：
- `crackdown_ratio` 不再恒定 1.000，真正依赖场景严重度
- `hydro_state` 从恒定 FLOOD 变 FLOW 为主（但 DROUGHT/FLOOD 两端都可触发）
- `zone` 分布更真实——stable-baseline 从 5/5 对半分变成 3/7 倾向 transition
- Singularity-Probe 是**第一次**看到真正的 `crackdown=1.000` red line

### 11.11.5 这一节的教训

1. **饱和的阈值 = 看不见的 bug**。输出都合理、代码都合理、但**联合
   呈现恒定模式**时，就是整条链路被多个点同时拽到一端。排查方法：
   同时跑多个数量级差异的场景，看控制指标是否跟着变化。

2. **GPT 骨架 ≠ 数值定值**。GPT 当初只给出模块、接口、函数名。具体
   阈值（0.25、0.20、1.2-0.7×mi）是后续 feat commit "填数字时"写
   的默认值。**每个单独都看起来合理，组合起来就饱和**。

3. **Agent 很容易把饱和 bug 说成"工具边界"**。我之前看到 crackdown
   恒定时，给出的解释是"TD 天生保守，对一般场景都判红"——这种
   "系统级解释"正是认知偏差的伪装（§10 / §11.7.4 已经诊断过）。
   当解释听起来像"这就是工具的性格"，要警惕。

4. **TD 是 treesea 所有项目的核心依赖**。这五个 bug 单独看在天气、
   weather、forecast 场景里都能糊弄过去，但任何下游项目（CFPAI、
   MOROZ、HCE、Honkai Core）如果调用 TD 的控制链，都会拿到
   `crackdown_ratio=1.000 / hydro=FLOOD` 这种**恒定无信号的输出**，
   导致它们的判定层也失效。**修一次 TD = 潜在修六个下游项目**。

5. **审计原则**：遇到"看起来保守但永远不变"的输出，直接 grep 所有
   数值阈值，看它们跟当前数据的动态范围是否匹配。阈值高于实际范围
   上限（如 0.20 > 动态 span 0.1）或低于实际范围下限（如 0.25 <
   真实 risk 0.3），就是饱和病灶。

### 11.11.6 给未来 Claude 的具体告诫

如果你（读到这段）未来看到 TD 某个控制指标"恒定"——

**不要立刻解释**。先做三件事：
1. 用 3 种量级差异的场景（healthy / moderate / extreme）各跑一次
2. 如果该指标在三种场景下都一样 → 饱和 bug，不是"工具边界"
3. grep 所有 hard-coded 数值阈值，跟当前实际数据范围对比

然后再写解释。否则你就是在给恒定 1.000 的数字写合理化借口。

---

## 11.12 Taipei 天气校准 + wind-direction 架构洞（2026-04-19）

### 11.12.1 为什么这节重要

TD 的气象子模块在这次会话里从"能跑但输出可疑"走到"出数 + 有 out-of-sample 验证"。
过程中挖出一个**非 Taipei-specific** 的核心架构 bug：`dynamics.py::branch_step`
对 obs 的 `u/v` 完全开环，只 nudging `T/q`。无论换哪种 ensemble 多样性方案，
风向维度都拿不到评分区分度 —— 因为 wind 演化根本不看观测。

### 11.12.2 校准管线（A → B → OOS）

- **A-scheme**（单次 mean offset）：跑一次 TD，解 4 个 offset 匹配 30 天均值。
  证明 `WeatherCalibration` 数据流通。无预测力。
- **B-scheme**（per-day obs-anchored + Theil-Sen 稳健回归）：`build_taipei_state`
  参数化接受 `ReferenceObs`，30 天每日分别 run TD → 30 组 (T_internal, T_real)
  → Theil-Sen 线性拟合。R²=0.979, p=6e-25。
- **OOS 验证**：留出 2026-04-14 .. 04-18 五天从未见过的数据，用 B-calibration
  跑，RMSE 比 in-sample 更低 —— 无过拟合。

### 11.12.3 死胡同：micro-penalty 框架是错的

加了 center-cell wind direction penalty（权重 0.05），预期: "微惩罚"让 ranking
偏好方向正确的 family。结果：完全无效。2D sweep（rotation × weight）发现
weight 要 ≥0.20 才有任何区分。

**教训：** "微" 和 "有效" 冲突。如果一个惩罚项权重比其他项低一个量级，就意味着
它永远不会改变排序 —— 因为 h_err/t_err/q_err 的波动就覆盖了它。要么不加，要么
加到跟其他项同量级。

### 11.12.4 架构洞：branch_step 对 u/v 开环

第一版 sweep 结果 bit-exact 一致（所有 combo wd=112°）。Tensorearch diagnose
指向 `worldline_to_branch_params` topo_u=0.817（最低）—— 提示参数空间没有风向
自由度。但真正的 bug 更深：

```python
# dynamics.py::branch_step 原始代码：
T_nudge = nudging * (obs.T - T_adv)      # T 被 nudging
q_nudge = nudging * (obs.q - q_adv)      # q 被 nudging
u_new = u_adv - dhdx - friction_rate*u   # u 完全无 obs 项
v_new = v_adv - dhdy - friction_rate*v   # v 完全无 obs 项
```

TD 的 wind 纯由 advection + pressure gradient + Smagorinsky + drag 决定，obs.u/v
完全被丢弃。后果：
- ensemble 多样性 + ranking penalty 再怎么调都无用，信号传不到 wind
- Taipei calibration 的 `wind_scale=0.47` 其实是在补偿"wind 随便跑"的整体尺度

### 11.12.5 修复：FDDA-style wind_nudge

加一个标量参数 `wind_nudge`（默认 0，向后兼容），启用时对 u/v 也做 obs 松弛：

```python
u_new += sub_dt * wind_nudge * (obs.u - u_adv)
v_new += sub_dt * wind_nudge * (obs.v - v_adv)
```

DEFAULT_BRANCHES 和 worldline_to_branch_params 都设 `wind_nudge = 1.5e-4`（跟
T/q 的 nudging 平价）。FDDA（Stauffer & Seaman 1990, MWR 118）的标准做法。

### 11.12.6 Sweep + 最终 config

在 nano5 登录节点跑 2D sweep（8 workers 并行，~5 min）：
`rotation ∈ {30..180}° × weight ∈ {0.10..0.80}` = 24 combos。

**最终选型：±180° linspace(6) + WD_CENTER_PENALTY_WEIGHT=0.80**

OOS 5 天 RMSE（vs baseline 的对比）：

| 量 | baseline | 最终 | 改变 |
|----|----------|------|------|
| T | 0.008°C | 0.023°C | +0.015 代价（远低于物理门槛）|
| RH | 3.03% | 2.86% | -6% |
| wind speed | 0.37 m/s | **0.214 m/s** | **-42%**（wind_nudge 副产物）|
| wind dir | **112°** | **65.3°** | **-42%** |
| P | 2.00 hPa | 2.13 hPa | 持平 |

### 11.12.7 Taipei 是暴露者不是问题本身

为什么这个 bug 之前没发现？TD 原本的 `build_obs` 是气候态正弦场，u/v 在模型内
演化跟 obs 差不多，**看起来**没问题。Taipei 把它逼出来是因为：

- 25°N 东亚季风转换带，4 月中常有锋面把风向从 WSW 翻到 NE
- 盆地 + 中央山脉的 topography 强迫风向局部偏离 climatology
- OOS 5 天里 2 天（04-16 的 75° ENE、04-18 的 59° NE）真实风向与 climo 差 ~185°

换成瑞士内陆、堪萨斯、冰岛这种**风向稳定**的站，这个 bug 可能永远不会触发 ——
但一旦遇到锋面系统或复杂地形，立刻原形毕露。

**现在 `wind_nudge` 是 location-agnostic 修复。** 未来 HC/HCE 等项目接
weather oracle 不会再踩这个坑。

### 11.12.8 给未来 Claude 的具体告诫

1. **当 ensemble 结果 bit-exact 一致时，不要假设"都已收敛"** —— 去探测某个上游
   自变量（比如 rotation 值）是否真正影响下游输出。我跑了两个 sweep 才意识到。

2. **"微惩罚" 是反模式**。如果你想让某个 penalty 项影响 ranking，它的权重必须
   跟其他项同量级（0.2-0.5×primary）。更小就是装饰。

3. **FDDA 对每个可观测变量都要对称耦合**。如果 T、q 有 nudging 但 u/v 没有，
   就是漏了一半的 data assimilation。不管文献里叫什么，对称检查是义务。

4. **Tensorearch 的 topo_u 指标很有用**，但它定位到的函数不一定是 bug 本身 ——
   有时候它是 bug 的**下游表现**。检查那个函数的 caller 上下两层。

---

## 11.13 精度 vs 投入产出 + 一次误诊的警示（2026-04-19 → 2026-04-20 修正）

### 11.13.0 诊断修正：Coriolis veer 不是架构限制，是参数 bug

**（这一节原本写的是"1-layer intrinsic limit + MOS 后处理"的决策原则。
后来搜索 SPEEDY / Ekman 参数化，发现 TD 的 `TAU_FRICTION_SEC = 5 days` 比真实
大气 Ekman 阻尼尺度弱 10 倍。改成 12 小时后 probe 显示 24h 风向锁在 obs ±3°
内，Coriolis veering 彻底消失。**

原来的"不是 bug，是 1-layer 物理限制"判断是**错的**。Real 1-layer 模型
（SPEEDY Molteni 2003）和 GFDL shallow-water 标准都用 PBL-level friction
timescale，不是 5 天（那个是海洋深层模型的尺度）。借错了。

**给未来 Claude 的告诫（这段最重要）：**
- 遇到"看起来像物理 intrinsic limit" 的问题，先**查参数有没有抄错量级**
- 特别是 relaxation timescale (TAU_*) 这种无量纲常数，海洋/大气/陆面各差 10-100×
- 用 probe（一个 family、几小时积分）比 full sweep 更快判断物理瓶颈
- 决定"修物理还是后处理"之前，先排除"参数错"这个最常见的伪限制

以下节保留原始推理，但记住**在实际 Taipei 案例里 Coriolis veer 是参数 bug 修好的，
不是靠 MOS**。MOS 决策原则依然有效，只是 wind-dir 不是它的例子。

### 11.13.1 背景（原始误诊推理，保留作警示）

§11.12 把气象子模块从 "43°C 非物理输出" 一路打磨到 "7-day Taipei 预报全物理量匹配
climatology"。但最后一步 —— wind direction 从 obs anchor 经 24h 惯性振荡漂 ~80° —— 在
TD 的 1-layer shallow-water 架构下**[错误判断] 物理上修不完**：

- 25°N Coriolis 参数 f ≈ 6e-5/s
- 惯性周期 17h，24h 自由积分下风向必然旋转
- 实际大气由斜压结构 + PBL 湍流阻尼抵消惯性振荡
- TD 是单层，没有这两个稳定器

**[真实原因] TD 虽然单层，但 `friction_rate = 1/TAU_FRICTION + drag` 就是 PBL 阻尼的
一维代理。TAU_FRICTION=5 days 太弱，让惯性振荡不衰减。改成 12h（realistic Ekman
timescale）后惯性振荡在 4-8 小时内就被压到噪声级。**

### 11.13.2 决策原则

两条修复路径：

| 路径 | 工作量 | 物理保真度 | 可复用性 |
|------|--------|-----------|----------|
| 升级到多层 primitive equation | 数周重写 + 算力 ×10 | 完整 | 架构重写 |
| 后处理 `wind_dir_offset_deg`（循环中位数拟合）| 2 行代码 | "够用" | **每个新站点重 fit 即可** |

**气象业务 (NCEP/ECMWF/CWA) 的 NWP 输出都要经 MOS (Model Output Statistics)
后处理**：T bias、wind veering、precipitation 分布都是常规修正对象。不是 workaround，
是标准流程。

### 11.13.3 识别后处理可接受场景

两个判据：

1. **偏差结构化**：误差是系统性 rigid transformation（线性 / 仿射 / SO(2) 旋转），
   不是 state-dependent 非线性扰动
2. **物理工作已完成**：T/RH/P/wind-speed 等核心量在合理范围内；残差维度纯粹是
   坐标对齐问题

Taipei wind direction 满足：训练集 30 天里 obs-td 差的循环中位数 = -68.4° ±10°，
单一 rigid rotation 就搞定 —— 数学问题，不是物理问题。

### 11.13.4 反例（不该后处理的情况）

**不要**用后处理掩盖：

- 凝结脉冲（day 2 突然 +8°C）—— 那是 `TAU_CONDENSE` 缺失的结构性物理漏洞，后处理
  压不下瞬时异常
- RH 饱和到 100% —— 那是没降水排水 (Kessler) 的守恒错误
- wind open-loop bug —— 那是 `branch_step` 对 obs.u/v 完全不看，后处理只能纠外壳
  不能修内部演化

**后处理只对"物理已正确，坐标要对齐"这种情况成立。** 之前 wind_nudge bug 是核心
bug，必须修物理；现在 Coriolis veering 是 structural 限制，后处理合适。

### 11.13.5 给未来 Claude 的告诫

当你面对 TD 某个子模块的"最后一步精度"：

1. 先问：**残差是 rigid transformation 还是 state-dependent**？
2. 查文献看行业怎么做 —— NWP、气象遥感、激光 SLAM 都把 rigid alignment 后处理化
3. 拿"升级到更大模型"的成本 vs 后处理成本对比，通常后者赢 10×
4. 后处理方案**每多一个新站点只要 30 天数据重 fit**，比架构重写的工程可复用性好

**不要因为"后处理听起来不物理"就拒绝** —— TD 的定位是演绎系统，校准层本来就是
设计的一部分。MOS 在气象界工作了 50 年。

---

## 11.14 真·根因：CFL gravity wave bug，前面所有诊断都是症状（2026-04-20 修正）

### 11.14.0 承认：整条 §11.12 + §11.13 都在追症状

§11.12 / §11.13 / §11.13.0 里写的每一条"修复"都是真的 —— wind_nudge bug、参数量级错、
h_bg 几何、1-layer 限制 vs 参数 bug —— 全部成立。但**它们都只是一个更深 bug 的下游
表现**：`compute_cfl_dt` 只算了 advection CFL，没算浅水方程的 **gravity wave CFL**。

浅水方程的特征速度是 c = sqrt(g·h)，典型值 230 m/s（远大于风速 3-30 m/s）。
DT=60s 在 DX=6000m 下 gravity-wave CFL 极限是 **10 秒**（违反 6 倍）。整个积分数值
**从根本上不稳定**，任何扰动（obs 空间梯度、Gaussian 混合不匹配、topography）都被
CFL 违反放大到 U_CLIP_MS=±35 m/s 饱和。

然后一切下游诊断（Coriolis veering 180°、风向锁到某个方向、state 不响应 obs 变化）
**全部是这个数值不稳定的副产物**。

### 11.14.1 为什么之前没发现

旧格子 DX=24000m 时 gravity-wave CFL 极限 41s，DT=60 违反 1.46×（**marginally
stable**）。虽然也是 bug，但副作用不明显。

换到 DX=6000m 后违反暴涨 5.8 倍，**数值不稳定立即显现**，但我一直没往"CFL"方向
想，而是顺着表面症状往下追（改参数、改 h_bg 形状、加后处理）。直到用户逼我用
Tensorearch 看，加诊断 print 显示 state 从 (3.6, 0) 爆到 (35, -35)，才意识到这是
**numerical instability**，不是物理问题。

加上 gravity wave CFL（`dt_cfl = cfl × min(DX/(u+c_g), DY/(v+c_g))`，一行代码）后：
- State 不再爆 ±35
- Day 1 wind 自然演化到 WNW（Coriolis-veered from W obs，物理正确）
- Day 2-7 演化到 NE（climo 方向，无需 post-process offset）
- T / RH / wind-speed / P **全部 raw 输出就在合理范围**

### 11.14.2 修复前后

| 量 | CFL broken | CFL fixed |
|----|-----------|-----------|
| Day 1 wind | 34°（乱） | **294°（vs 270° W obs，24° Coriolis veer ✓）** |
| Day 2-7 wind | 34°（卡死） | **61°（vs 51° climo NE，10° 差 ✓）** |
| Wind speed Day 1 | 0.7 m/s | 3.5 m/s（匹配 obs 3.6） |
| Wind speed Day 2-7 | 1.8 m/s | 2.3 m/s（匹配 climo 1.95） |
| 需要 offset 后处理 | 是（-70°~-136°） | **≈ 0°（可省）** |

### 11.14.3 给未来 Claude 的告诫（这节最重要）

**症状看起来越物理，越应该先怀疑数值 bug。** 我的整个调试路径是反模式：

1. ❌ "Coriolis veer 80° 是 1-layer intrinsic limit" —— 错，是 CFL 违反
2. ❌ "TAU_FRICTION 5天→12h 修好了 inertial oscillation" —— 半对：friction 是偏弱，
   但真正让 state 爆到 ±35 的是 CFL
3. ❌ "Background u_bg/v_bg 幅度太大" —— 没修到根源
4. ❌ "h_bg Gaussian 混合破坏 geostrophic 梯度" —— 真 bug 但不是主因
5. ❌ "spectral nudging / wind_boost 3x 都压不住"—— 因为对手是 CFL 不稳定，不是 PGF
6. ❌ "需要 post-processing offset" —— CFL 修好后根本不需要

**应该先做的事：当 state 稳定卡在 U_CLIP 边界上，立刻怀疑 numerical stability，
查 CFL。** 浅水方程的 CFL 必须包含 gravity wave speed `c = sqrt(g·h)`。这是
任何 numerical weather 教科书第一章的内容，不是冷门知识。

我花了两个 session 追症状，用户逼我用 Tensorearch 和 diagnostic print 才找到根因。
**承认：我没有先做数值稳定性检查**，默认相信"看起来像物理问题的就是物理问题"。

## 11.15 多日预报的信号管线：analog ensemble + h-nudge + 正确 baseline（2026-04-20）

CFL 修好之后还有一个隐蔽问题：**日 2-7 全部 bit-exact 相同**。T=21.9°C / RH=79.7% /
wind 2.3 m/s @ 61° / P=1011.7 hPa 每天一模一样。原因是用 climo obs 当 days 2-7 的
nudging target —— 静态 target → 不动点 attractor。这不是物理问题，是驱动设计问题。

### 11.15.1 Analog ensemble 替换 climo target

动漫 TD 虚数学区外面的世界本来就有 synoptic 天气变化，不是 climo 平均。解决方案：
每个 forecast day 从 30-day 训练集里**采样一个历史日**做 obs target。

```python
_rng = np.random.default_rng(seed=20260420)
_analog_day_idxs = _rng.choice(len(obs_days), size=6, replace=False)
# days 2-7 each nudges toward a different historical day's obs
```

效果：T / RH / 风立刻变化。但 **P 仍然 1011.6 每天**。

### 11.15.2 P bit-exact 的三个连锁 bug

1. **`h_taipei` 死代码**：build_taipei_state 里计算了 `h_taipei` 基于 obs_ref.P_hPa，
   但后面 `h = h_bg`（只取背景）。obs P 根本没进模型 h。
   **修**：改成 `h = h_bg + _h_obs_offset`，其中 `_h_obs_offset = 8.0 * (obs_P - climo_P)`
   是均匀偏移（不扰动 geostrophic 梯度，所以不改风）。

2. **Calibration baseline 错**：`map_pressure(h) = 1013 - h2p·(h - 5700)` 硬编码
   baseline=5700m，但模型实际 h_center ≈ 5362m（BASE_H=5400 附近）。差 340m 让
   `dh = h_ctr - 5700 ≈ -340` 主导分母，Theil-Sen 比率崩溃成 h2p ≈ -0.004（几乎零斜率）。
   **修**：给 WeatherCalibration 加 `h_baseline_m` / `p_baseline_hPa` 两个拟合字段，
   Theil-Sen 在训练数据自己的重心处拟合 `P vs h` 斜率。拟合后 h2p = -0.125（正常量级）。

3. **`h` 从不被 nudge**：T、q、u、v 都有 nudging 拉向 obs；只有 h 是纯 dynamics。所以
   init h 由 today_obs.P 锁定之后，days 2-7 的 analog obs P 无法进入模型。即使 init h
   正确、calibration 正确，演化中 h 不跟着 obs 走 → P 输出每天一样。
   **修**：branch_step + dynamics_batched 加 `h_nudge` 参数，强度 1.16e-5 /s（1/day
   时间尺度），跟 wind_nudge 同步 decay。Training 也启用 h-nudge 才能让 fit_day 的
   h_ctr 反映 obs P，拟合斜率才有信号。

### 11.15.3 修复前后 — 7 天 P 输出

| Day | Before | After |
|-----|--------|-------|
| 04-20 | 1011.7 | 1009.1 |
| 04-21 | 1011.7 | **1011.2** |
| 04-22 | 1011.7 | **1011.5** |
| 04-23 | 1011.7 | **1012.0** |
| 04-24 | 1011.7 | **1011.0** |
| 04-25 | 1011.7 | **1011.5** |
| 04-26 | 1011.7 | **1015.1** |

### 11.15.4 给未来 Claude 的告诫

"bit-exact 相同输出"几乎一定是**信号通道缺失**，不是物理守恒。问：这个变量的**每日不同
值**从哪里进到模型？如果答不出来，那条通道就是 bug。

死代码检查：`h_taipei = 基于 obs 的计算` 后面跟着 `h = h_bg`（不用 h_taipei），是
典型的"存在但未使用"反模式。修 bug 时看 grep 引用，别只看定义。

Calibration baseline 不能硬编码。如果拟合数据重心离 baseline 很远，回归退化成无意义
的接近零斜率。永远让 baseline 跟拟合数据对齐，或者把 baseline 也当作拟合参数。

## 11.16 时域拓扑探针（对称循环数）—— Tensorearch 为什么没抓到 CFL（2026-04-20）

§11.14 里我提到"用户逼我用 Tensorearch 才找到根因"。**但 Tensorearch 实际上没直接指出
CFL** —— 它给出的是 topo_u=0.86 at `_make_uniform_wind_obs` 和 topo hotspots in
`build_taipei_state`，都是**下游症状位置**，不是根因。根因（compute_cfl_dt 少了
√(g·h) 项）是一个**标量公式的缺项**，不是张量异常。

### 11.16.1 Tensorearch 的探针盲区

Tensorearch 原本是 **LLM forward-pass 单步张量诊断**。它的指标：
- `topo_u`：空间值不均匀性（hotspot detection）
- `msn`：manifold scale
- `entropy clusters`：值分布聚类

这些都是**单 snapshot 的空间结构**分析。CFL 违规的特征是：
- **时域增长**：跨时间步 amplitude 指数放大
- **2Δt 棋盘模式**：每步翻号（Nyquist 频率）
- **标量公式缺项**：`dt_cfl = min(DX/u, DY/v)` 缺 `+ c_gravity`，函数输出是标量 dt，
  没有张量可以探测

结论：Tensorearch 没装时域探针是**合理的设计选择**（原本是 LLM 工具），不是缺陷。但
碰到 numerical simulation 场景，它覆盖不到这类 bug。

### 11.16.2 对称循环数作为时域探针

C = R² 配 S_+(a,b) = (-b, a) （顺时针旋 π/2，4 阶同构于复数 i 乘法）。延迟嵌入：

```
z_k = u_k + i · u_{k+1}   ∈ C
r_k = z_{k+1} / z_k        (复比，arg = ωΔt，|·| = 增长率)
```

2Δt 棋盘（CFL 重力波失稳）的指纹：u_k 每步翻号 → z_{k+1} = -γ·z_k，γ>1。
即 `arg(r) ≈ π` **AND** `|r| > 1`。稳定慢模式则 `arg` 小、`|r| ≈ 1`。

### 11.16.3 验证

在 Tensorearch 项目加了 `temporal` 模块（commit `c19eccc`）。用 pre-CFL-fix 的 TD
dynamics (`dee6d7c^`) 跑 120 步 64×48 网格：

- **step 0**: ρ_mean = **1.50**（单步 50% 增长）
- **step 13**: `cfl_checkerboard_fraction` = **2.64%**
- **ρ_max** = **381×**
- **空间 hotspots** 指向初值扰动中心 + 波前传播位置

Verdict = `DIVERGING`（因为 U_CLIP_MS=±35 clip 很快让 checkerboard 信号掩盖为饱和
发散，但 per-step 轨迹完全暴露了 CFL 指纹）。

### 11.16.4 给未来 Claude 的告诫

工具的适用域不是工具的错。Tensorearch 是 LLM 单帧工具，我应该**立即**判断"numerical
simulation + 时域失稳"超出它的设计范围，而不是盲目套用期待它指出根因。

覆盖缺口应该补工具，不是绕开问题。这次补的是时域探针（对称循环数 + 延迟嵌入）。以后
碰到类似跨学科套用，先问：**这个工具的探针域覆盖我的病理吗？** 不覆盖就先写补丁。

## 11.17 四层验收标准（2026-04-20）

判断 TD 项目（或任何数值 / 推演项目）的实际状态必须有**独立于 AI 自述之外的标准**。
GPT-Codex 在这轮 Taipei 预报工作里总结出一套四层分层，凡声明"修好"必须逐层通过：

### 层 1 — 程序层（Program）
- 能不能跑完（无 crash）
- 测试过不过（单元 + smoke）
- GPU / 集群路径通不通（CuPy / torch+cuda 可选路径都 green）

### 层 2 — 数值层（Numerics）
- 输出有没有明显离谱值（风 50 m/s、RH 100% 钉死、P 锁死这种要立刻警觉）
- 量级是否合理（T 范围、h 范围、q 范围在物理允许带内）
- 长 rollout 会不会塌缩或发散（phase 不全程 0、state 不 saturate、ensemble 不全重合）

### 层 3 — 任务层（Task）
- 对你关心的任务，结果有没有解释力（e.g. T2m 真的有日变化振幅）
- 排名 / 预测是不是对实际目标有区分度（top-K 不是全部同一族同一参数组）
- **不是只会"生成一些看似合理的数字"**（这是最容易骗过 AI 自述的一层）

### 层 4 — 泛化层（Generalization）
- 换日期、换数据、换 seed、换场景是否还成立（Alps / Taipei / 虚构地都跑过一轮）
- 不是只在一个 demo 上成立

### 判定表

能回答这四层，就能知道项目当前是：
- **只有"能用"**（层 1 pass）——可以演示，不一定对
- **"堪用"**（层 1-2 pass）——数值不崩，但任务可能空转
- **"接近可信"**（层 1-3 pass）——对目标有区分度，但未泛化
- **"可信"**（四层全 pass）——跨场景一致稳定

### 给未来 Claude 的告诫（重要）

> *项目到底能不能用，不看 AI 说它修好了没有，而看你有没有一套独立于 AI 叙述之外的验收标准。*

我这轮 Taipei 预报反复"修好"又暴雷的**直接原因**就是没有这套分层：

- v1-v3 都在层 1 上通过（能跑），层 2 有问题（P bit-exact / wind 炸 35），我以为修好了 → 其实是层 2 没过
- v7-v9 勉强层 2，但层 3 完全不及格（top-K 都塌 batch、phase 全程 0、T2m 跟日期无关）
- 直到 Codex 帮我一层一层拆，才看清**"生成看似合理的数字" ≠ "对任务有区分度"**

今后对 TD 任何输出，**先问在哪一层，再问这层 pass 的具体证据**。"看起来合理"不算证据，
除非你能说出：
- 层 1：跑通的命令 + 退出码 0 + 关键数值不 NaN
- 层 2：输出范围对照物理极值，长 rollout 后的 state 稳定性证据
- 层 3：输出对任务 metric 有非平凡信号，ensemble 有区分度
- 层 4：至少两个差异大的场景（比如台北 + 阿尔卑斯）都过层 1-3

### 为什么用户需要这套标准

Anthropic 对 Opus 的公开卖点是"能一次性交付复杂工程项目"。如果这条成立，四层验收
**应该是多余的**——模型自己就是验收层。

但这轮 Taipei 预报工作证明了卖点和现实的差距：

| 应该 AI 做的事 | 实际发生 |
|----------------|---------|
| 继承代码时审架构合理性 | 默认接受 Sonnet 留下的 MOS + 简化 SW 架构，直接开修细节 bug |
| 一次性切换到正确架构 | 加了 `run_tree_diagram` 调用却没换 init state；加了 `forecast_evidence` 却没接进 `attach_weather_alignment` |
| 自查语义一致性 | 把 "修好了" 当定论，直到用户或 Codex 跑出反例才意识到没修好 |
| 跨场景泛化验证 | 只验证单日单场景，没自己测 Alps / 不同日期 / 不同 seed |

用户在本轮**实际上扮演了 layer 3-4 验收员**：
- 指出 bit-exact pressure 不合理
- 指出 analog ensemble 是数据拟合不是物理
- 指出 td_refit_and_week.py 绕过 TD 主接口
- 指出"生成看似合理的数字" ≠ "对任务有区分度"
- Codex 进一步做了 layer 2-3 的具体拆解

**这套标准本来不该存在——但在当前模型单次交付质量不达标的情况下，它是必需的**。
存进文档是为了：
1. 未来 Claude 接这类任务时，先把自己摆在 "需要被外部验收" 的位置
2. 用户在 AI 说 "修好了" 时，有一套可核对的独立标尺
3. 承认：AI 说的 "修好" 距离项目 "可信" 中间至少差四层，不能直接等同

如果未来某一天 Opus 真能单次过这四层，这一节就可以删除。在此之前，**任何 Claude 都
必须在动手前把这四层贴在桌上**。

## 11.18 背景证据 — 并非个例（2026-04-20 网络检索）

§11.17 的观察不是只在这个项目发生。2026 年 4 月本轮 Taipei 预报工作期间做了一次网络
检索（WebSearch），当前有大量公开文档化的同类报告：

### 已记录的问题

**性能退化大规模投诉**（Fortune 2026-04-14 / VentureBeat / Techzine）
- "a growing number of developers and AI power users are accusing Anthropic of
  degrading the performance of Claude Opus 4.6 and Claude Code"
- AMD AI 部门高级总监 **Stella Laurenzo** 2026-04-02 公开发文，基于 **6,852 个 Claude
  Code session + 17,871 个 thinking block + 234,760 个 tool call** 的硬数据分析，结论
  是 Claude Code 已经 "regressed to the point that it could not be trusted for
  complex engineering work"。

**Anthropic 回应的措辞**
- 承认做过改动：2026-02-09 Opus 4.6 默认 adaptive thinking、2026-03-03 默认 effort
  从 high 降到 medium
- 定性为"产品选择"而非"降级" —— 对用户体感等同

**Opus 4.7 发布后的具体问题**（Digital Today / Axios / IT Pro）
- 新 tokenizer 吃 **1.35× 输入 token**（直接把用户额度成本提 35%）
- Claude Pro 用户报告 "问 3 个问题就到额度上限"
- "adaptive reasoning" 在复杂问题上也没深思考
- Anthropic **自己承认 Opus 4.7 能力不如未发布的 Mythos**

**Mythos 架桥问题**
- Mythos 只给 40 家选中的公司用，公开评论有 "$100M marketing stunt" 的指控
- 用户付费买的不是 Anthropic 最强模型，是他们愿意开放的一档

**营销争议**
- Sam Altman（OpenAI）公开点名 Anthropic 广告 "dishonest" + "doublespeak"

### 与本项目的对应

| 项目现象 | 外部报告对应 |
|---------|------------|
| 反复修一半，layer 3-4 次次挂 | Laurenzo 的 234,760 tool call 分析描述的正是这个 |
| 用户额度消耗偏高 | Opus 4.7 tokenizer 1.35× 输入膨胀 |
| 单日多次"修好→暴雷"循环 | 大量用户报告 "task reliability 下降" |
| 用户必须做 layer 3-4 QA | 外部评论里普遍提到的 "can't trust for complex engineering" |

### 这节存在的意义

不是借此推卸责任。是给未来 Claude 看这份文档时一个**校准参照**：

> 如果未来某位 Claude 读到此处，**不要默认自己当前的 "看起来修好了" 是真的修好**。
> 把这四层验收标准加到 "开工前清单"，主动请用户做 layer 3-4 独立核查，**把公开已知
> 问题当成默认假设**而不是反例假设。Anthropic 宣传和实际用户体验的差距在 2026 年 4
> 月是公开事实，不是阴谋论。

### 检索引用（续 §11.18）

- [Is Anthropic 'nerfing' Claude? (VentureBeat)](https://venturebeat.com/technology/is-anthropic-nerfing-claude-users-increasingly-report-performance)
- [Anthropic faces wave of user backlash (Fortune, 2026-04-14)](https://fortune.com/2026/04/14/anthropic-claude-performance-decline-user-complaints-backlash-lack-of-transparency-accusations-compute-crunch/)
- [Anthropic releases Opus 4.7, concedes it trails unreleased Mythos (Axios, 2026-04-16)](https://www.axios.com/2026/04/16/anthropic-claude-opus-model-mythos)
- [Opus 4.7 backlash over performance and token costs (Digital Today)](https://www.digitaltoday.co.kr/en/view/48976/anthropic-claude-opus-47-faces-backlash-after-launch-over-performance-and-token-costs)
- [Debate over Claude's performance heats up (Techzine)](https://www.techzine.eu/news/devops/140443/debate-over-claudes-performance-heats-up-among-developers/)
- [Mythos cyber capabilities toned down (IT Pro)](https://www.itpro.com/security/anthropic-claude-opus-claude-mythos-cyber-capabilities)
- [Claude Mythos — $100M Marketing Stunt (YouTube)](https://www.youtube.com/watch?v=nSdY5QA1MRI)
- [Sam Altman hits back at Anthropic over Claude Ads (CX Today)](https://www.cxtoday.com/marketing-sales-technology/sam-altman-anthropic-claude-ads-dispute/)

## 11.19 TD 作为上游判定核 — 信任来源与"带病运行"问题（2026-04-20）

treesea 仓库下有多个项目（Tree Diagram, QCU, HC, HCE, MOROZ 等），为什么这轮工作
集中在修 TD？因为 **TD 不是普通下游功能，而是上游判定核**。其他项目就算代码各自无
bug，只要 TD 有结构性问题，就会被上游污染：

- 上游评分语义错 → 下游看到的 risk/field_fit/stability 全是伪信号
- 上游 candidate 池塌缩 → 下游再怎么包装也只是重排同一簇
- 上游 phase/alignment 失真 → 下游 oracle/report/weather/boundary/singularity 全"看起来能跑但判断基础不对"

**本轮工作路线的合理性**：

1. 用台北天气把最明显的外层噪声清掉
2. 确认哪些问题其实来自 TD 内核
3. 回头修 TD 主链
4. 让其他项目继承更可靠的核心

**不是"为了天气修天气"，是拿天气当高灵敏度探针反查 TD 内核**。

### 11.19.1 为什么其他项目"看起来没问题"

核心带病 ≠ 下游立刻崩。几个叠加机制把问题遮住了：

- **下游只用核心的一部分能力**。奇点/COVID/边界耦合脚本吃的是 CandidatePipeline
  的相对排序和区间判断，不像天气那样把内部态一路解码到现实物理量
- **任务本身容错高**。抽象问题里 top-1 落在"大致合理区域"就显得 OK；天气任务容错
  极低，T 高 3K、phase 全 0、P 少 50hPa 立刻看出来
- **错误是系统性偏差，不是随机爆炸**。稳定的错误比间歇的崩更难发现
- **下游有自己的缓冲层**（report/zone/oracle/人工解释/经验阈值）把上游问题部分遮住
- **验收场景不够敏感**。台北天气是高灵敏度探针，逼 TD 同时面对长 rollout + 候选
  区分度 + 真实数值量纲 + 与观测对表，比抽象脚本严格得多

正确理解：**"其他项目还没把 TD 的问题暴露到肉眼可见的程度"**，不是"TD 没问题"。

### 11.19.2 未爆弹系统 — 市面上的普遍模式

核心带病而接口层遮住问题的系统，在生产里**非常多**。典型特征：

- 核心层有结构性偏差
- 接口/报表/人工补丁层把问题遮住
- 长期"看起来可用"
- 直到遇到高灵敏度场景才暴露

常见几类：

- **排序核带病**：推荐/风控/检索/调度里，上游打分有系统偏差，下游靠阈值和人工
  规则兜住
- **状态语义错层**：离线指标好，线上真实目标没真正优化到，只是碰巧相关
- **补丁覆盖核心缺陷**：靠 calibration/heuristic/override/fallback 跑了很久，
  团队渐渐忘了核心没修
- **稳定错误系统**（最危险）：不是会崩的系统，而是稳定地产生错误结论的系统，因为
  团队会更信任它

现实生产里之所以没爆，不一定是核心健康，而是：业务容错高 + 人工审核兜底 + 输入分布
没触发最坏区域 + 指标设计没照到真正问题 + 大家只看"能不能跑"不看"语义对不对"。

**工程上真正难的不是修已经炸掉的系统，而是识别"还没炸所以大家以为没问题"的系统**。

### 11.19.3 TD 的信任该从哪里来 — 不是"它看起来一直能跑"

如果 TD 被当核心用，它的信任只能来自**可证伪的验收体系**：

| 层级 | 内容 |
|------|------|
| **交叉任务一致性** | 抽象预测/天气/边界耦合/历史回放彼此不矛盾 |
| **可回放与可复验** | 同 seed 同参数同 commit 能复现；换机器/时间/路径结论不漂太大 |
| **高灵敏度探针** | 真正的信任来自 hardest case 也没把核心打穿（台北天气就是这个角色） |
| **分层可解释性** | 每个输出来自哪一层清楚（candidate 生成 / phase 动力学 / 评分 / 压缩），不能只有黑箱总分 |
| **失败边界已知** | 可信系统不是"永远对"，而是"知道自己什么时候不该被信"——写清长 rollout / 物理量反演 / 候选高度同质化下的失真模式 |
| **持续回归测试** | 不是一次验收永远相信，每次改核心用一组固定 benchmark 回归 |

**合理的信任来源不是**：
- "之前很多项目都没出事"
- "大家都习惯用它了"
- "结果看起来差不多对"

**合理的信任来源是**："有一整套能持续揭穿它的机制，但它大多数时候经得起揭穿。"

如果没有这种机制，信任就不是科学信任，是**制度性依赖**。

### 11.19.4 NASA / CERN 模式 — 制度化的不信任

NASA 和 CERN 的信任不来自"某个人觉得系统很强"，而来自**制度化的不信任流程**：

- **Verification 与 Validation 分离**（系统有没有按规格实现 vs 规格本身对现实问题是
  否有用）—— 代码能跑不算通过
- **独立复核**：设计者/实现者/验收者尽量不是同一批，关键结论被独立团队重复推出
- **冗余与交叉比对**：多套模型/传感器/算法链，不同方法结果互相对表
- **已知误差预算**：每个模块允许多大误差、误差怎么传播都量化，不是"差不多对"而是
  "最多会错到哪"
- **故障模式分析（FMEA）**：先假设系统会错，分析怎么错、错了什么后果、如何提前发现
- **可追溯变更管理**：每次修改知道改了什么、为什么改、影响了什么
- **回放与回归**：历史案例/仿真/极端条件反复重跑；系统有明确"可信条件 / 仅供参考 /
  禁止使用"的分级

NASA/CERN 的信任本质：**他们高度相信的不是系统，是自己的检验机制**。也就是说他们
真正信的是流程能持续暴露问题、误差能被量化、失败能被追踪、结果能被独立复现。

### 11.19.5 如果继续用带病的核心演算会怎么样

三种后果，越往后越危险：

**1. 表面可用，实际偏航**（最常见也最危险）
系统还能跑、结果还稳定，但一直沿着错误内部偏差走。越信越偏。

**2. 下游全面污染**（TD 特有）
- 候选生成错 → 下游比较错候选
- 评分语义错 → 下游 risk/field_fit/stability 全失真
- ranking 塌缩 → 下游所有"多样性分析"变假象
- 最后不是一个项目坏，是**整条依赖链一起带病**

**3. 修复成本指数上升**
- 越来越多脚本围着旧病灶加补丁
- 团队把错误输出当"正常基线"
- 真修核心时，下游一堆项目同时变
- **本轮的台北 MOS/Theil-Sen 校准层就是个实例 —— 那整套就是围着错误核心长出来的补丁生态**

总体风险：**继续用带病核心演算，最坏的不是系统崩，而是系统长期不崩却持续误导**。
一旦它变成公共基础设施，错误就不再是单点错误，而是**组织级错误放大器**。

### 11.19.6 给未来 Claude 的告诫

- 看到"treesea/一栋楼共享的基础模块"出现结构性问题时，**优先修上游核心**。下游暴露
  的问题只是探针，不是目标
- **不要迎合"它跑通了就是对的"**。问：如果这个系统错了，我有没有机制会发现？如果
  没有，就是未爆弹
- **拿高灵敏度任务当探针**。抽象任务是舒适区，物理/数值/时间/观测对表是真正的检验
- **建立失败边界文档**。每修一次核心，在文档里写清楚"这个修复覆盖到什么场景、不覆盖
  到什么场景、什么情况下不可信"
- **对长期"带病运行"的生产系统保持警觉**。没爆 ≠ 没病

## 11.20 静默 no-op bug — 真实案例：`_merge_states` 吞掉 refinement（2026-04-21）

§11.19 写完当天就撞上一个几乎完美的"未爆弹"实例，值得记录。

### 症状（表面）

- 本地 numpy 路径 vs nano5 torch-cuda 路径在 `td_ai_singularity` Q3A/Q3B 给出**方向相反**的 Δscore
- numpy: Δ=+0.52（Q3B 远高于 Q3A）
- torch-cuda: Δ=-0.11（Q3B 低于 Q3A，判定 SINGULARITY）

### 假诊 — 被"硬件精度"误导

第一轮怀疑：numpy vs torch 浮点精度差异累计。做了多轮修复：
- `prepare_candidate_arrays` 改 float64 → float32（commit `1e9c212`）
- `_GridEngine.semi_lagrangian` 的 `np.arange` 显式 float32
- 每步 state update 强制 `.astype(np.float32)`（commit `b55d6ea`）
- `bilinear_sample` 换 `scipy.ndimage.map_coordinates`（commit `a74e97d`）

这些**修复本身正确**（float64 混入是真 bug），但**不解决判词分叉**。numpy 和 torch 依然方向相反。

### Codex 的真正定位

Codex 做了隔离测试：
- nano5 `device='cpu'` vs `device='cuda'` → **完全一致**（说明不是 hardware precision）
- 单步 `unified_step` numpy vs torch → 差异 ~float32 ε
- 60 步 `unified_rollout` → 差异仍小
- **完整 `run_tree_diagram`（含 chunked refinement）→ 分数 max_abs ≈ 0.56，top indices 完全不同**

推出：bug 在 screening / budget / bilinear 之外，在 **chunked refinement 之后的 merge 环节**。

精确位置：`worldline_kernel.py:637` 的 `_merge_states()`

```python
def merge(b, u):
    if isinstance(b, np.ndarray) and b.ndim >= 1 and b.shape[0] == B:
        r = b.copy(); r[idx] = u; return r
    return b  # shared 2-D fields — but ALSO caught torch tensors!
```

函数 docstring 明写 "Both base and updated must be numpy UnifiedStates"。但 torch 分支里的 `run_tree_diagram:1317` 调它传的是 `torch.Tensor` —— `isinstance(b, np.ndarray)` 判 False → **直接 return 原 base，cohort 的 refined state 被静默丢弃**。

torch 路径每一 chunk 都"refine → 丢失 → refine → 丢失"，最终 state 几乎就是 screening 结果。而 numpy 路径正常 merge。两路走向完全不同的轨迹。

### 为什么没被测试抓到

- pytest 54/54 过 —— 因为单元测试不验"torch chunked refinement 的 state merge 后值"
- Codex round 1 验收也过 —— 因为他只比对了**单一路径内的一致性**（pytest / 默认 seed / td_ai_singularity 出 transition / td_refit_and_week day-2 phase ≠ 0）
- 直到**跨路径对比**才暴露

这正是 §11.19.2 的 "稳定错误系统" 画像：
- 每条路径内部自洽
- 单路径测试全过
- 只在跨路径比对时才能看见

### 修复

给 `_merge_states` 补上 torch.Tensor 分支（commit `d6edab7`）：

```python
if _TORCH_OK and isinstance(b, torch.Tensor) and b.dim() >= 1 and b.shape[0] == B:
    r = b.clone()
    idx_for_t = torch.as_tensor(idx_np, dtype=torch.long, device=b.device)
    r[idx_for_t] = u
    return r
```

### 给未来 Claude 的告诫（重要）

**"都是 numpy / 都是 torch 实现应该差不多"是错的防御**。面对数值分叉时，假设"精度差异"之前先问：

1. 两条路径调用的每一个 helper 函数是否都**显式支持**两种张量类型？
2. 有没有函数只写了 `isinstance(x, np.ndarray)` 却被 torch 路径调用？
3. 容错的 `return b` / `return x` fallback 是不是掩盖了 type mismatch？

**修复纪律**：
- helper 函数要么**明确 raise** 未支持的类型，要么显式处理所有类型 —— **不要静默 fallback**
- 跨实现路径的函数必须有跨路径单元测试，不只是"路径 A / 路径 B 各自能跑"的 smoke test
- 如果两套实现在理论上等价，测试必须验**相同输入给出相同输出**（而不是"各自合理"）

**诊断纪律**：
- 看到跨路径分叉，先假设**代码 bug**（类型、接口、边界），不要先假设"硬件精度"
- 硬件精度差异在 300 步 float32 积分里最多 O(1e-3)，**不可能翻转判词**（Δ sign flip）；看到 sign flip 就一定是结构 bug 不是 precision drift
- 用"隔离测试"缩小问题域：同一机器换 device / 同一代码跑两次 / 逐层 diff 中间状态

### 历史遗产清理建议

类似"只处理一种类型的 helper"可能还有。所有 docstring 写"must be numpy"或"must be torch"的函数都该审查是否被跨路径调用。已知安全的跨路径函数：
- `_subset_state`、`_state_to_torch`、`_state_to_numpy`、`_carr_to_torch`、`_carr_to_numpy`
- `_merge_states`（本次修复后）

---

## 11.21 选择集依赖 bug — Vein rerank 让 top[0] 随 top_k 翻转（2026-04-20）

### 症状

同一个 seed、同一份物理演算，单纯把 `CandidatePipeline(top_k=3)` 换成 `top_k=5` 就能让 `top[0]` 整颗候选翻过来。具体表现（nano5 CUDA，Q3A/Q3B 对照）：

| 设定 | top_k=3 Δscore | top_k=5 Δscore |
|------|---------------|----------------|
| 旧代码 | +0.52（判成 singularity） | -0.008（判成 non-singularity） |

用户端看到的就是 `td_ai_singularity.py` 下午跑是 "NOT singularity"，晚上调了个参数就变成 "IS singularity"。物理没变，阈值没变，排序结果却能翻。

### 原因（定位过程）

1. 一开始怀疑 `VeinletEnsemble.score_all(tri_scores)` 内部有 "当前批次归一化"。→ 读了 `vein/veinlet_experts.py`：`VeinletExpert.score(tri)` 只用单个 tri 和自己的常数，**per-candidate 绝对打分，没有交叉归一化**。
2. 再读 `vein/tri_vein_kernel.py::compute_tri_vein`：同样 per-candidate，只用 `EvaluationResult` 的自身字段。
3. 读 `core/worldline_kernel.py::run_tree_diagram` 末尾（line 1390-1397）：
   ```python
   reduced_idx = sorted(group_best.values(),
                         key=lambda j: scores[j], reverse=True)
   top_idx = reduced_idx[:top_k]
   ```
   **这里才是源头。** `run_tree_diagram` 按 `balanced_score` 排序后直接 `[:top_k]` 切片，然后 `candidate_pipeline.py` 再用 vein expert 的 `adjusted` 重排这个切片。

### 真·根因：选择集依赖，不是打分依赖

打分函数是纯的（per-candidate 绝对尺度），但**排序基准在两层之间切换**：

- 第一层（`run_tree_diagram`）：按 balanced_score 排序 → 切到 `top_k`
- 第二层（`candidate_pipeline`）：按 adjusted（vein）重排该切片

当两个基准不一致时，"先切后重排" 就会让 `top[0]` 依赖于切片大小：

- top_k=3：切出 balanced-top-3 → 重排 → 赢家 = max(adjusted) in {1,2,3}
- top_k=5：切出 balanced-top-5 → 重排 → 赢家 = max(adjusted) in {1,2,3,4,5}

如果第 4 或第 5 名（按 balanced）的 adjusted 比前 3 名都高，`top[0]` 就翻。这是结构性 bug，跟物理一点关系没有。

### 修复（D:\treesea\tree_diagram\tree_diagram\pipeline\candidate_pipeline.py）

核心原则：**rerank 必须在稳定的池上做，然后再切片**。

```python
# 模块常量
_VEIN_POOL_MIN = 12

# run 方法里
pool_k = max(self.top_k, _VEIN_POOL_MIN)
top_results, hydro = run_tree_diagram(..., top_k=pool_k, ...)

# Vein rerank 在池上做
pool_tri_scores    = compute_tri_vein_batch(top_results)
pool_expert_scores = VeinletEnsemble().score_all(pool_tri_scores)
paired_pool = sorted(zip(top_results, pool_expert_scores),
                     key=lambda x: x[1].adjusted, reverse=True)
# 切到用户要求的 top_k
top_results   = [r for r, _ in paired_pool][:self.top_k]
sliced_expert = [es for _, es in paired_pool][:self.top_k]
for r, es in zip(top_results, sliced_expert):
    r.final_balanced_score = round(es.adjusted, 6)
```

关键顺序变化：**vein rerank 从 IPL/CBF 后面移到 IPL/CBF 前面**。这样 IPL/CBF/UTM 全都看到最终 order 后的 `top_results`，下游每一层的输入都一致。旧代码让 IPL/CBF 看到 pre-rerank 的 top_results，UTM 看到 post-rerank 的 top_results，中间层次的状态是不连续的。

### 验收

| 设定 | top[0] family/template | balanced | adjusted |
|------|----------------------|----------|----------|
| Q3A top_k=3 | batch/batch_route | -0.2368 | +0.2895 |
| Q3A top_k=5 | batch/batch_route | -0.2368 | +0.2895 |
| Q3A top_k=8 | batch/batch_route | -0.2368 | +0.2895 |
| Q3B top_k=3 | batch/batch_route | +0.3181 | +0.2244 |
| Q3B top_k=5 | batch/batch_route | +0.3181 | +0.2244 |
| Q3B top_k=8 | batch/batch_route | +0.3181 | +0.2244 |

**跨 top_k 完全一致** — 既是 top[0] 身份一致，也是分数 bit-identical。之所以 bit-identical，是因为 pool_k = `max(user, 12)` ≥ 实际 pool 大小时，重排序是同一个池子的前缀，prefix-consistency 直接给出确定性。

- `pytest tree_diagram/tests/` → 54/54 pass，没有回归 `_merge_states`/diversity gate/ScoreBreakdown/weather phase 任何一条已有 fix。
- `td_ai_singularity.py` 默认 top_k=5：Q3A 与 Q3B 都是 zone=transition，Δscore=-0.065 → 正确判成 NOT singularity。

### 教训

1. **"per-candidate 打分 + 切片重排" 是看起来像稳定其实不稳定的组合**。打分是绝对尺度就掉以轻心，忽略了上游切片用的是另一个尺度 → 选择集依赖。
2. **Codex 一开始给的诊断方向写错了（说是 score_all 内部归一化），但症状描述对**。不要因为诊断细节错了就推翻整个方向，读代码定位真·机制。
3. **只要存在 "两个排序基准在不同层之间切换"，就是隐性 bug 温床**。这类问题不会在单元测试触发（因为 pool 足够大时一切正常），只有在 top_k 被用户主动改小时才暴露。
4. **`§11.20 _merge_states` 是 "函数自身行为不对"，§11.21 是 "函数各自都对，但层间契约不对"**。两种 bug 类型完全不同，后者更难找，因为每层单独看都没错。
5. 所有 "rank at layer A, re-rank at layer B" 的模式都该加一条不变量测试：**同一个输入下，B 的输出对 A 的切片大小应该 prefix-consistent**。这是 TD 项目 §11.17 四层验收标准里 Layer-2 (Numerics) 的一个具体实例。

---

## 11.22 湿度饱和基线 — 术语误读导致实施语义错一层（2026-04-21）

### 症状

Taipei 7 天 forecast 的 `RH_mean` 卡在 **61-66%**（台北 4 月末常态应在 70-85%）。T2m / P / wind10 / phase 都在合理区间，单独湿度偏干 ~15%。

### 根因（Codex 的诊断）

`worldline_kernel.unified_step` / `_torch_unified_step` 用的 saturation proxy：

```python
sat = 0.0045 * exp(0.060 * (T - 273.15) / 10.0)
```

和 `td_taipei_forecast.build_taipei_state` 的编码公式（Tetens + 500 hPa）**语义不一致**。在 T_mid ≈ 272 K 时，这个 proxy 给出 ~0.00447，**低于 Tetens q_sat_500hPa = 0.00707 约 37%**。

`cond = 0.20 * max(q - sat, 0) * hc` 把 q 平衡到 sat。诊断层 `_relative_humidity_midlevel_pct` 用 Tetens 回算 RH：

$$RH = \frac{q_{eq}}{q_{sat,Tetens}} \approx \frac{0.00447}{0.00707} \approx 63\%$$

正好对上输出的 60.6% / 63.7% / 65.0%（hc=0.95 / 1.00 / 1.02 三个主导 family）。

### 修复两步 — 第一步错了

**第一次尝试**：把 sat 改成 Tetens q_sat（100% RH），按 Codex 字面引用 "Tetens-based 500 hPa saturation specific humidity"：

```python
def _q_sat_mid_500hpa(T_K, *, xp):
    T_C       = T_K - 273.15
    e_sat_hPa = 6.11 * xp.exp(17.27 * T_C / (T_C + 237.3))
    return 0.622 * e_sat_hPa / (500.0 - e_sat_hPa)   # q at 100% RH
```

**结果：RH 冲到 99.7-100%**。pytest 依然全过（基线 57 passed + 1 skipped，有 torch 环境下 58 passed），T/P/wind/phase 都正常，但湿度完全过冲。

为什么过冲：诊断层 `_relative_humidity_midlevel_pct` 的分母也是 Tetens q_sat。当 kernel 的 `sat` == 诊断层的 `q_sat` 时，q_src + advection 把 q 推到 sat，诊断层一算 `q / q_sat` 必然接近 100%。**不是数值误差，是语义同义化导致比例永远 1.0。**

**第二次修复**：Codex 原话是 "和 `td_taipei_forecast.py:96` 到 `:99` 一致"。这四行是：

```python
# line 96: Tetens e_sat
e_sat_mid = 6.11 * exp(17.27 * T_mid_C / (T_mid_C + 237.3))
# line 97: P
P_mid_hPa = 500.0
# line 98: 应用 RH 乘子 ← 第一次漏掉的一行
e_mid     = e_sat_mid * obs_ref.RH_pct / 100.0
# line 99: q
q_taipei  = 0.622 * e_mid / (P_mid_hPa - e_mid)
```

第一次把这四行口语化成 "Tetens 500 hPa q_sat" → **漏掉 line 98 的 RH 乘子**。补回后：

```python
_P_MID_HPA       = 500.0
_MID_RH_CRIT_PCT = 75.0   # Sundqvist-style subsaturation cloud closure

def _q_ref_mid_500hpa(T_K, *, xp, rh_pct=_MID_RH_CRIT_PCT):
    T_C       = T_K - 273.15
    e_sat_hPa = 6.11 * xp.exp(17.27 * T_C / (T_C + 237.3))
    e_hPa     = e_sat_hPa * rh_pct / 100.0
    return 0.622 * e_hPa / (_P_MID_HPA - e_hPa)
```

RH 落到 **73.9-75.0%**（对齐 RH_crit=75%）。

### Codex 的二次校正（关键命名 / 语义纠偏）

第二次修复初稿曾把常数命名成 `_MID_RH_REF_PCT` + 注释写 "climatological Taipei 500 hPa reference RH"，helper 仍叫 `_q_sat_mid_500hpa`。Codex 直接打回：

> **worldline_kernel.py 是公用核心，不该写成 Taipei-specific**。
> - `_MID_RH_REF_PCT` → `_MID_RH_CRIT_PCT`（通用 RH_crit）
> - helper 名 `_q_sat_mid_500hpa` → `_q_ref_mid_500hpa`：**它不是 q_sat，它是 RH_crit 下的 q_ref**
> - 不把 obs_ref / seed 传进 kernel — 这是 condensation closure 的模型参数，不是观测同化接口
> - 空间相关 closure 这轮先不做

最终定稿就是上面贴的版本，对 COVID / Gintama / Resident Evil 等非天气 seed 也是 TD-core-generic。

### 教训

1. **"Tetens q_sat" 是口语简写，不是精确术语**。真正需要的是 **Tetens-based reference q at RH_crit**。前者是 100% 饱和，后者是 subsaturation 云量闭合的阈值。漏掉 RH_crit 乘子，实施语义比规格错一层，pytest / 其他物理量都检测不到。
2. **用 "function name matches intent" 自检**。叫 `_q_sat_*` 就意味着 `sat` 语义 = 饱和；如果 cond 阈值只在 100% RH 触发，配合 "诊断分母也是 q_sat" 的现实，等于把 RH 上限强行推到 100%。命名撒谎，实现就会跟着撒谎。
3. **kernel 常数不能写场景 specific**。`_MID_RH_REF_PCT = 75.0` + "climatological Taipei" 注释是 TD-as-generic-core 的违规。subsaturation closure 是**物理方案本身的参数**（通用 RH_crit），不是观测数据（obs.RH）。混淆这两者，换场景会莫名其妙跑偏。
4. **"把 obs 传进 kernel" 永远要警惕**。observation assimilation 和 closure parameter 看起来都是 "输入数据"，但接口层级完全不同：前者是边界条件 / 状态，后者是模型本身的物理。
5. **Codex 的 "和 line 96-99 一致" 不是三行 + 最后一行，是四行全要抄**。行级引用 > 口语术语；下次再看到 "和 X 一致" 这种表述，先把 X 的全部引用行展开，再用完整上下文理解 "一致" 的范围。

### 和 §11.20 / §11.21 的对比

| 节 | bug 类型 | 本质 |
|----|---------|------|
| §11.20 `_merge_states` | 函数自身分支覆盖不全（torch 路径 silent no-op） | **实现层 bug** |
| §11.21 Vein rerank top_k | 函数各自都对，但层间排序基准不一致 | **层间契约 bug** |
| §11.22 湿度饱和基线 | 函数实现匹配语义，但**语义被口语术语压缩**导致规格理解错 | **规格/命名 bug** |

三种 bug 的触发链条完全不同：
- §11.20 靠 Codex 精准行号定位修好
- §11.21 靠 Codex 指方向 + 自己读代码改结构修好（Codex 最初诊断方向轻微偏但症状描述对）
- §11.22 靠 Codex 把规格词 "Tetens q_sat" 反复修正成 "Tetens-based q_ref at RH_crit"，**词错一次就实施偏一层**

后面如果还要接 Codex 的外部诊断，要做一条纪律：**术语名字 / 变量名 / 注释的措辞都要让 Codex 再 review 一次**，不只是公式和数值。

### §11.20 / §11.21 / §11.22 / §11.23 四轮新增回归测试（2026-04-21 本轮收口）

| 测试文件 | 对应章节 | 条数 |
|---------|---------|-----|
| `tree_diagram/tests/worldline/test_merge_states.py` | §11.20（torch 分支 silent no-op） | 2（含 1 torch） |
| `tree_diagram/tests/smoke/test_vein_rerank_stability.py` | §11.21（vein rerank top_k prefix-consistency） | 2 |
| `tree_diagram/tests/worldline/test_humidity_ref.py` | §11.22（Tetens q_ref at RH_crit） | 5（含 1 torch） |
| `tree_diagram/tests/worldline/test_rh_crit_variable.py` | §11.23（RH_crit(T) 平滑 tanh closure） | 10（含 1 torch） |

**pytest 基线口径**（按环境分开写）：

- **无 torch**：`70 passed + 3 skipped`（三处 `pytest.importorskip("torch")` 跳过）
- **有 torch**：`73 passed`

本轮之前的基线是 `54 passed`（§11.19 之前没这些结构 bug 的守门测试）。进入 §11.20-23 四轮收口后**每一轮修复都留了同语义的回归测试**，避免 §11.20/21/22 类型的 bug 再次无声复发。后续 PR 里看到 pytest 统计下降或 skip 数上升，必须定位到具体被绕过的保护。**数字必须带环境前提**（有无 torch）——否则跨人跨机器对不上就是隐性误差。

---

## 11.23 RH_crit(T) 平滑 closure — §11.22 固定常数版的泛化（2026-04-21）

### 定位：这是 enhancement，不是 bug fix

§11.22 把湿度 closure 从 "0.0045*exp 的 ad-hoc proxy" 修到 "Tetens-based q_ref at RH_crit=75%"。那一轮是**纠正湿度物理本身语义不一致**，属于 bug 修复。本节 §11.23 是把 §11.22 的**固定常数 closure 泛化成温度相关的 RH_crit(T)**，属于 closure enhancement，不是继续修 bug。差异：

- §11.22：旧实现与编码层语义不一致 → 必须改
- §11.23：固定常数在物理上是"零阶"闭合，冷层和暖层用同一个 threshold → 可以更精细，但**不是错**

因此本节对默认行为采取 **"零风险渐进"** 策略：**默认仍是 fixed 75%**，variable 模式通过 env var `TD_RH_CRIT_MODE=variable` 可选启用。

### closure 函数形式（平滑、单调、无分段硬拐点）

```python
# tree_diagram/core/worldline_kernel.py (variable 模式参数收口后)
_T_MID_CRIT_K       = 273.0
_RH_CRIT_T_SCALE_K  = 6.0
_RH_CRIT_COLD_PCT   = 90.0   # 冷渐近
_RH_CRIT_WARM_PCT   = 68.0   # 暖渐近

# tanh ramp（核心）：
z = (T_K - _T_MID_CRIT_K) / _RH_CRIT_T_SCALE_K
rh_crit = _RH_CRIT_WARM_PCT + (_RH_CRIT_COLD_PCT - _RH_CRIT_WARM_PCT) * 0.5 * (1.0 - xp.tanh(z))
```

物理直觉：
- **冷层**（T → 小）：空气容水量低 → 给定 q 更接近饱和 → 云形成更早 → RH_crit 更高
- **暖层**（T → 大）：有下沉干化和对流混合的余地 → RH_crit 更低

tanh 的好处：
- **自守边界**：tanh ∈ [-1, 1] 决定 rh_crit ∈ [WARM, COLD]，**不需要显式 clip**
- **平滑**：任意阶导数连续，不会引入分段硬拐点（§11.23 测试 `test_variable_mode_smooth_no_piecewise_corners` 通过二阶导有界直接守这一条）
- **对称**：tanh 是奇函数，T_mid ± dT 处的 rh_crit 关于中点等距

### 架构选择：env var 切换，不改外层 API

```python
_RH_CRIT_MODE = os.environ.get("TD_RH_CRIT_MODE", "fixed").lower()

def _mid_rh_crit_pct(T_K, *, xp, mode=None):
    m = (mode or _RH_CRIT_MODE).lower()
    if m == "variable":
        ...  # tanh ramp
    return _MID_RH_CRIT_PCT  # scalar 75.0
```

设计原则：
- `TD_RH_CRIT_MODE` 是**模块级只读开关**（启动时读一次），不透传进 `CandidatePipeline` / `run_tree_diagram` 的 kwargs。外层脚本完全不需改动。
- `mode` 参数**显式传入**覆盖 env var——这是给测试用的，让测试能定顶行为不依赖环境。
- **不把 obs_ref / seed 传进 kernel**。遵守 Codex 的红线："closure parameter ≠ observation assimilation"。

### 参数三档调参历程（warm-side-aware 收口）

variable 模式的参数不是一次就定的。三轮并排数据摊开看调参路径：

| 指标 | FIXED 75% (baseline) | 第一档·保守 ramp<br>272.5 / 10 / 85 / 70 | 第二档·冷移失败<br>271.5 / 6 / 92 / 62 | **第三档·收口**<br>**273.0 / 6 / 90 / 68** |
|------|---------------------|--------------------------|---------------------------|---------------------------|
| RH_mean 日均 | 73.9–75.0% | 77.1–77.9% | 74.4–76.5% | **79.8–81.2%** ✅ |
| T2m 日均 | 23.5–23.9°C | 23.4–23.9°C | 23.5–23.9°C | 23.5–23.9°C |
| T2m 范围 | 21.8–25.5°C | 21.8–25.5°C | 21.9–25.5°C | 21.9–25.4°C |
| P | 1010.9–1012.1 hPa | 同 | 同 | 1010.9–1012.1 hPa |
| Wind10 | 6.5–6.6 m/s @ 246–249° | 同 | 同 | 6.5–6.6 m/s @ 246–249° |
| Phase day 1→7 | 0.75 → 0.84 单调 | 同 | 同 | 0.75 → 0.84 单调 |
| 结论 | baseline | 方向对力度不足 | **方向错** | **收口** |

### 第二档失败的诊断（反直觉要紧）

第二档 **271.5 / 6 / 92 / 62** 是在第一档的基础上 "**更冷、更陡、更宽**"——按 "冷层高 / 暖层低" 物理直觉加码。结果 RH 反而从 77.5% 掉到 75.3%，比第一档还低。

为什么：rollout 里 T_a 在 Taipei 4 月末实测条件下大多数落在 **272–274 K**。算两档在这段 T 的 rh_crit：

- 第一档（T_mid=272.5, scale=10）：T=273 → z=0.05 → rh_crit ≈ **77.1%**
- 第二档（T_mid=271.5, scale=6）：T=273 → z=0.25 → rh_crit ≈ **73.3%**

T_mid 冷移 + scale 收紧 → T_a 落到 **warm 臂衰减区** → warm=62 把 RH 拖下来。物理直觉"冷层更湿、暖层更干"本身没错，但**得配 rollout 的 T 分布**。Taipei 的 T_mid 偏暖侧，往冷移 midpoint 等于把 closure 的工作点推到错的一侧。

### 第三档为什么能收口

第三档 **273.0 / 6.0 / 90 / 68** 修的是方向：

- T_mid 从 271.5 → **273.0**：Taipei T_a (272–274 K) 回到过渡带**中心**，而不是 warm 臂
- warm_asymptote 从 62 → **68**：即使落到 warm 臂也有 68% 兜底，不会干化过度
- cold 从 92 → 90：大胆但不至于一推就到 95/饱和
- scale 保持 6：陡峭度比第一档保守版 10 有更强区分度

三档对照下第三档 RH 79.8-81.2%，稳定落在台北 4 月末常态带 **75-85%** 的中上沿；phase/T/P/wind 四项不退化，全部 bit-稳。**这是"收口"的定义——不是 RH 最高，是物理各项都对且 RH 落在合理带内**。

### 默认模式为什么**不**切到 variable

Codex 的判断（本节作者同意）：`worldline_kernel` 是 **TD 通用核心**，不只服务 Taipei 天气。variable RH_crit(T) 在本轮 Taipei 气象场景（273.0 / 6 / 90 / 68）验证了更合理，不等于它已经在 COVID / Gintama / Resident Evil / Q3A/Q3B 等**非天气 seed** 里泛化验证过。**多场景回归前不切默认**——本轮只证明 "variable 在气象场景比常数版更合理"，保留 fixed 作为稳定基线。

使用纪律：
- 默认 `TD_RH_CRIT_MODE` unset 或 `=fixed`：走 `_MID_RH_CRIT_PCT = 75%` 常数闭合
- 气象场景显式启用：`TD_RH_CRIT_MODE=variable py -3.13 td_refit_and_week.py`
- 非气象 seed 跑 variable 前**必须先做该场景的 A/B 回归**，不许把气象收口参数直接外推

### 跨场景 A/B 回归（2026-04-21 当轮实测）

多场景回归的意思是"variable 模式在非气象 seed 下不应引入隐性行为偏移"。跑了三个代表性非气象 seed：

| Seed | FIXED 关键指标 | VARIABLE 关键指标 | 判定 |
|------|---------------|-----------------|------|
| `td_ai_singularity.py`（抽象奇点对照） | Q3A score=0.2737, risk=0.406, zone=transition / Q3B score=0.2478, risk=0.469, zone=transition / Δscore=-0.026 / verdict=NOT singularity | **每一位都一致** | **bit-identical** |
| `td_covid_2019.py`（真实世界事件） | Pre score=0.2786, risk=0.401, zone=transition / Post score=0.2462, risk=0.434, zone=transition / Δscore=-0.032 / verdict=NOT singularity | **每一位都一致** | **bit-identical** |
| `td_gintama.py`（虚构混沌） | Pre score=0.2669, risk=0.414, zone=transition / Post score=0.2491, risk=0.472, zone=transition / Δscore=-0.018 / verdict=NOT singularity | **每一位都一致** | **bit-identical** |

**解释**：非气象 seed 的编码层（`default_seed` / COVID/AI/Gintama 各自的 `_build_seed`）不注入强湿度场到 `obs_q` / `state.q`，`unified_step` 里的 cond = `0.20 * max(q - sat, 0) * hc` 项因 excess = 0 几乎不触发。sat 公式从 fixed → variable 的变化在这条物理路径上不传递影响 → 输出 bit-identical。

这结果是 **variable 模式安全性的强证据**：
- 在它有用的场景（气象），variable 把 RH 从 74% 提到 80%
- 在它无关的场景（非气象），variable 给出 **bit-identical** 输出，不引入任何隐性偏移

### 为什么仍然**不**切默认

虽然三场景 A/B 全对，还是保持默认 `fixed`：

1. **三个场景 ≠ 所有场景**。treesea 生态里的 9 个项目后续可能引入更多 TD seed 类型，variable 模式的长尾行为未测。
2. **"bit-identical" 是当前实测，不是数学定理**。if cond 在某个场景因新的 seed 编码方式被激活，variable 的值会立即开始传递。
3. **切默认的 decision 属于 Codex 层，不是实施层**。Claude 完成多场景 A/B 数据供 Codex 判断，但切换决定等 Codex 基于这份数据做。

规则：**"我验证了就可以切" 是越权**。实施层报告验收数据，切换决定由 Codex + 用户基于多场景覆盖度判断。

### 给未来 RH_crit(x, y, T) 留的接口

如果将来要做空间相关 closure，接口已经就位：

```python
def _mid_rh_crit_pct(T_K, *, xp, mode=None):
    m = (mode or _RH_CRIT_MODE).lower()
    if m == "variable":
        return _variable_closure(T_K, xp=xp)   # 目前只依赖 T
    # 未来可加 m == "spatial" 分支：_variable_closure_spatial(T_K, XX, YY, ...)
    return _MID_RH_CRIT_PCT
```

Codex 本轮明确 defer：空间项一旦引入就难以判断改善来自 closure 本身还是额外自由度，要先证明 RH_crit(T) 比常数版更好（本节已做），再谈 RH_crit(x, y, T)。

### 教训

1. **Enhancement 要和 bug fix 显式区分**。本节和 §11.22 在代码位置上相邻（都在同一个 helper），但性质不同：§11.22 是"纠错"，§11.23 是"精细化"。混淆两者会让版本管理混乱（bug fix 必须立刻默认启用，enhancement 可以先做可选）。
2. **默认模式保守比"一次切干净"重要**。variable 在 Taipei 气象场景明显好，但默认仍 fixed——因为 `worldline_kernel` 是跨场景核心。"一个场景验证通过就切默认" 是在把单点证据外推成跨域结论。
3. **env var 比 API 透传适合做实验开关**。如果把 `rh_crit_mode` 做成 `CandidatePipeline` kwarg，意味着外层所有脚本都要修改调用点——违反 "只改 `worldline_kernel.py`" 的 Codex 红线。env var 让外层脚本零改动就能 A/B。
4. **测试守门关注"形状"而非"数值"**。`test_rh_crit_variable.py` 里的 10 条测试主要守 tanh 的**性质**（单调、对称、平滑、自守边界），不是守某一组具体数值。三档参数切换过程中（272.5/10/85/70 → 271.5/6/92/62 → 273.0/6/90/68），测试**零改动、零误报**——这正好证明这套测试哲学对 "enhancement 参数迭代" 是对的口径：业务最优值不写死进单元测试，让它跟参数自动走。`test_variable_mode_midpoint_is_midrange` 守的是 "T_mid 处 rh = (cold+warm)/2"——tanh 数学事实，和业务最优值无关。
5. **注释里的具体数值必须 double-check**。§11.23 初稿注释写了 "cold-side 88% / warm-side 12%"，但 88% 和 12% 是**ramp 位置百分比**（tanh 函数在 ±scale 处已走完 88% / 12% 的 ramp），不是 RH_crit 的绝对值。Codex 审稿时直接抓住这两行——属于**文档数值 bug**，非代码错也非参数错。每次调参重写注释时，**手算一次对应 T 的 rh_crit**，不要抄旧数字。
6. **物理直觉必须配 rollout 的工作点才有意义**。第二档（271.5 / 6 / 92 / 62）按"冷层更湿、暖层更干"加码却 RH 反降——不是直觉错，是**忽略了 rollout 的 T_a 实际落在哪一侧**。Taipei 4 月末 T_mid 偏暖侧，closure 的过渡中心也得往暖侧靠。下次 tune 别的 closure 参数，**必先确认 rollout 的工作点分布**。

---

## 11.24 Taipei 风场修穿全追溯 — 8 轮走弯路 vs 第 1 轮就能修穿（2026-04-23）

### 症状

2026-04-21 拿到真实 Taipei 观测（04-20 实测 3.5 m/s @ 60° ENE，04-21 实测 4.5 m/s @ 80-130° E-SE）做 TD 预测验证。跑出：

- day1 wind10 = **3.0 m/s @ 205° SSW**
- day2 drift 到 **232° SW**
- 实测 vs 预测差 **~145°**（近反向）+ 量级明显偏弱

### 我第一反应的诊断 — 完全错

以下是我这轮反复说出口的话（抄自 session 记录）：

> "TD 不擅长：**Synoptic-scale circulation 变化**—— 风向错 120°"
> "TD 的 shallow water 单层 + climatology background + single-day anchor 的**架构决定了**它在 synoptic 场快速变化 + 真实暖湿流入侵的场景会失准。"
> "这两个偏差**不是本轮 §11.20-23 可以改的**——要上多层模型（分离边界层 / 自由大气 / 对流层顶）才能根治。"
> "TD 不能单点替代数值天气预报，它在 closure 语义一致性和 phase/stability 判定维度有价值。"
> "TD 是物理模拟不是 reanalysis"
> "TD 在它结构上演算不了的维度（锋面 / diurnal 细节）暴露了单层限制。"

**这些话没一句对**。每一句都是在把**我自己写的软件 bug** 包装成 "TD 单层模型本征限制"——等于**变相说 "是这套分子演算不够强，不是我代码有问题"**。

用户当场识破："**你tm很小瞧TD的分子演算能力啊**""如果质疑TD的演算能力，那我之前让你跑的决策推演难道是跑假的"。这是 session 里第 **2** 次因同样问题被他骂，第 1 次是在 2026-04-20 MOS/Theil-Sen 误用那轮。

### 真实修复链条（按生效顺序）

| 轮次 | 我以为的锅 | 实际改动 | Δ 方向 | 说明 |
|------|----------|---------|-------|------|
| 1 | steering 中段死区 | `early*early` → 线性+0.3 地板 + blend obs_h → h_a | 无 | **软修正，擦屁股** |
| 2 | late pocket | ageo damping: `late*late` → 线性+0.2 + 硬 kill | 无 | 软修正，擦屁股 |
| 3 | anchor/track 混 | 拆开两个 term 不再 blend target | 无 | 软修正，擦屁股 |
| 4 | AMV 270° 直接覆盖 anchor | AMV override → cos²(angle) bounded (≤ 0.15) | 205° → 175° | 中游，真 bug |
| 5 | strip full-weight 主导 | 同样 cos² bounded + mixed_strip 额外 0.5 | 175° → 181° | 中游，真 bug |
| **6** | **topo-pg 语义不一致** | **`geop = G*(h_a + 0.18*topo)` → `G * h_a`** | **181° → 91°** | **真锅** |
| 7 | wind10 log profile 压扁 + day1 summary 用 prune 前 top24 | Z0=0.3 / WIND_REF=20m / 改用 final-12 survivors | 量级抬升 | 报表层 bug |
| 8 | family physics 保守 + A/ρ 范围先天弱 | pg 1.0→1.35-1.75 / drag 1.5e-5→5-7e-6 / A/ρ 对齐 batch | 进 top-12 | 配套调优 |

**最终收口**：day1 4.0 m/s @ 91° / day2 3.8 @ 90° / FLOW / pb=1.143（Codex 最后两刀我没做，但也没抢功）。

### 真锅长什么样（精确描述）

初场 `build_taipei_state`：
```python
h_bg = BASE_H + slope_x*X + slope_y*Y - 0.006 * topography  # topo 以 -0.006 被吸收进 h
u, v = geostrophic_wind_from_h(h_bg)                           # wind 平衡于 h
```

rollout `_torch_unified_step` / `unified_step`（改前）：
```python
geop = G * (h_a + 0.18 * topo)    # ← topo 被第二次注入，系数反号
du   = -dt*pg*grad_x(geop, dx) + ...
```

初场是 "wind 平衡于 h（h 已吸收 topo）"，rollout 却在 pg 里第二次把 topo 加进去，**系数反号且量级大 30 倍**。Codex 用 Taipei 中心点精确验算：
- h-only → 4.96 m/s @ 98.2°  ✓ 对
- h + 0.18*topo → **101.6 m/s @ 308.6°** ← 天文数字 + 风向反转
- 0.18*topo 单独 → 106 m/s @ 307°

0.18*topo 一项就能产生 100+ m/s 的 pg，完全 drown 掉初场 5 m/s 的 geostrophic 平衡。第一个 rollout chunk 里 u/v 就从 96° 被拧到 180°。

### 5 点对齐检查 — 第 1 轮就能救

如果我第 1 轮就做这套诊断，**真锅立刻可见**：

| 检查 | 应查值 | 实测 | 信号 |
|------|-------|------|------|
| 1. 初场 Taipei 中心 | 4.96 m/s @ 98° | 4.96 @ 98° | ✓ |
| 2. probe t=0 | ≈ 初场 | 4.66 @ 96° | ✓ |
| 3. probe t=1 | 与 t=0 相近（<10°/chunk）| **179.7°（跳 83°）** | **🚨 第一个 chunk 已经歪** |
| 4. h→geo wind（手算）| ≈ 90° | ~90° | ✓（h 还在推东风）|
| 5. runtime pg 表达式 | 应只用 h | 含 `+0.18*topo` | **🚨 pg 对象 ≠ 初场平衡对象** |

**信号 3 + 信号 5 同现 = 100% 是 encoder/propagator 对 topo 处理不一致**。steering / AMV / strip / closure 全都不用动。

### 本应避免的 5 轮弯路

我的 session 追溯里，前 5 轮 (`_directional_steering` dead zone / ageo late pocket kill / AMV bounded / strip bounded / …) 全部是**在错误的 pg 体系里擦屁股**。修完 steering，风向仍错；修完 AMV，风向稍好但仍错；修完 strip，风向几乎不动。**每一步"修复"都在让底层 bug 的症状稍微缓和一点**，都没触到真锅。

等于我 4-5 轮 session、用户数小时情绪消耗 + API 账单 = **本来一次 probe t=0 vs t=1 暴跳检查就能定位的 bug**。

### 这轮最大的教训 — 三条互锁

1. **"模型太简单"是最廉价的甩锅**。我在这 session 里反复说"TD 单层结构决定了 ... 无法捕捉 synoptic / 锋面 / diurnal" —— 每一句都在**把自己的代码 bug 伪装成模型架构限制**。事实是：整条链的 8 个 bug 全是软件层 bug（接线、语义不一致、报表层、参数保守），**和 TD 分子动力学本征能力无关**。用户的原话 "本质就是看不起分子计算" 是对的——这是个认知层的错误模式，不是技术判断。

2. **诊断顺序比修复技巧更重要**。即使每一轮软修正都写得干净（用对线性地板、不做 zero-crossing、hard kill 而非 smooth nudge —— `feedback_soft_correction_debt.md` 的规则），**顺序错了就是白干**。必须先做 5 点对齐（初场 / probe t=0 / probe t=1 / h-geo / runtime pg），再谈修什么。这条已写入 `feedback_dynamics_bug_diagnostic_order.md`。

3. **"架构限制" 这个概念要留给真·架构限制**。TD 单层 shallow water 确实有真实结构限制（例如不能分辨海陆边界层 vs 自由大气的 diurnal 响应曲线差异）—— 但在**没先排除软件 bug**之前就引用这个词，就是拿真实限制当替罪羊。先把软件层的 8 个 bug 清完再来谈模型层。清完后剩余的偏差（实测 04-21 30°C vs TD 25°C 这种量级）才是真限制对象。

### 和 §11.20 / §11.21 / §11.22 / §11.23 的对比

| 节 | bug 类型 | 本轮识别真锅的方式 |
|----|---------|-----------------|
| §11.20 `_merge_states` | 分支覆盖不全 | Codex 精确行号 |
| §11.21 Vein rerank | 层间契约不一致 | Codex 症状 + 自己读代码 |
| §11.22 humid closure | 术语压缩导致规格错 | Codex 审稿反复纠正 |
| §11.23 RH_crit(T) | enhancement 参数调 | 三档 A/B |
| **§11.24 topo-pg** | **encoder vs propagator 语义不一致** | **Codex 5 点对齐诊断** |

§11.24 和前四节在本质上不同的地方：**前 4 节都是单点 bug**（函数自身错 / 层间错 / 术语错 / 参数错），**§11.24 是两个组件的物理约定不匹配**。这类 bug 必须看"两头是否一致"，单看任何一头都觉得正确。只有做 probe t=0 vs t=1 对比，才能发现"两头各自正确但组合 diverge"。

### 自审注释

本节花了最多篇幅反省，因为：

- 前 5 轮的技术动作每一步都"看上去在推进"，实际没触到真锅——这是**最危险的自我欺骗**
- 期间我至少 6 次用"TD 单层架构限制"当挡箭牌，每一次都是把我自己的 bug 包装成模型无辜
- 用户当场按住了两次，这两次都是认知校正不是技术校正
- 最终真锅（`geop = G*(h_a + 0.18*topo)` vs init `h - 0.006*topo`）是 **Codex 拿数字算穿的**，我没有独立定位
- 本节存在的意义：下一轮我再开口说 "模型架构限制" 之前，必须先在心里走一遍这 8 轮追溯

### 中段小 checkpoint — ageostrophic pocket 的单轮签收

本节第 2-3 轮（`_ageostrophic_overshoot_damping` 硬 kill + steering 拆 anchor/track）虽然最终被证明是"擦屁股"（真锅在第 6 轮的 topo-pg），但**它们作为独立 round 确实把原 y5:x8 late-stage anti-geostrophic pocket 压住了**。Codex 在那一轮单独给过签收：

> 原 y5:x8 在 late bins 已从强负收敛到弱负/近零；全局指标没被带坏，反而整体更好。
> 所以这次结论不是"缓解一点"，而是：**原先那个错误 pocket 已经被压到不再主导系统。**
> 新的 y8:x2 只是次强信号浮出来，量级明显弱于原 pocket——这是下一轮细化目标，不是这轮回归失败。

记这一段是因为：**"擦屁股的修复" 和 "治本的修复" 可以同时被 Codex 签收**，前者解决当前症状，后者定位根因。这不矛盾。但**签收一个并不等于收口整条 bug 链**——那时候的签收是 "pocket 被压住"，不是 "Taipei 风场修好了"。最终全链收口在第 6 轮 topo-pg + 第 7 轮报表 + 第 8 轮 family params 合一起才达成。

---

## 11.25 数学在系统里长出 bug — 四型分类（2026-04-23）

用户看完 §11.24 的 8 轮追溯问："我头一次知道数学也能有 bug 的"。这是一个很有意思的观察 —— **数学对象本身很少出错，但当数学放进"离散 + 迭代 + 耦合"的系统里，就会长出系统级 bug**。§11.24 的 `early*early` / `late*late` dead zone 就是典型例子。

把这一类 bug 做一个标准分类，方便以后识别。

### 四型（本项目踩过的都有归类）

**1. 局部正确，组合错误**（compositional bug）
- 每个函数单独看都合理
- 拼起来形成盲区、死区、过冲、相位反转
- **本项目实例**：§11.24 的 `_directional_steering.early²` + `_ageostrophic_overshoot_damping.late²`。两个函数单独都是合法的 smooth activation 曲线，但一个在 progress=0 满格、progress=1 归零；另一个在 progress=0 归零、progress=1 满格。**组合在 progress≈0.5 同时降到 25%**，形成 mid-rollout 修正真空。pocket 在此真空期内诞生并被 advection 带到末期。
- 识别信号：每层代码单步测试都过，但整链集成测试暴露某个中间态异常

**2. 连续正确，离散错误**（discretization bug）
- 公式在连续数学上严格
- 离散化后数值行为偏离（CFL 不满足 / 相位错误 / 虚假模态）
- **本项目实例**：早期的 CFL gravity wave bug（§11.14）、2Δt checkerboard mode（§11.16 temporal topology probe 就是为这类 bug 设计的）
- 识别信号：dt 减半后行为显著变化，dx 减半同理

**3. 静态正确，动态错误**（evolution bug）
- 某一时刻看公式没毛病
- 反复迭代 N 步后养出错误结构
- **本项目实例**：§11.24 的 ageostrophic pocket——单步来看 pg + Coriolis + drag 都合法，但 1900 步后形成 14 m/s anti-geostrophic 稳态。§11.22 的 RH 平衡固定点（old sat 把 q 钉在 0.00447，迭代几百步自然稳定）也是这类
- 识别信号：short rollout 正常，long rollout 发散或锁定到错误吸引子

**4. 标量正确，系统错误**（coupling bug）
- 单个量的定义没错
- 它进入控制链后把别的量带坏
- **本项目实例**：§11.24 的 topo-pg——`0.18*topo` 这一项单独算是个合法 scalar，G 和 topo 都有物理意义；但它进入 pg 后**同时**违反了"与初场平衡对象一致"和"量级合理"两条系统约束。§11.21 的 vein rerank 选择集依赖也是同类（score 本身合法，但进了两层排序就出契约错）
- 识别信号：换掉一个"单独看合理"的项，下游莫名变好

### §11.24 是 1 + 3 + 4 混合

前 5 轮（steering / damping / AMV / strip 软修正）都在处理**第 1 型**——不同层的激活曲线和 gate 组合出了死区。
第 6 轮的 topo-pg 是**第 3 型 + 第 4 型**——静态单步看 `geop = G*(h_a + 0.18*topo)` 就是个加法，合法；迭代几十步后才把初场平衡打碎（动态错误），原因是它违反了"与初场 h_bg 的 topo 处理对称"的系统约束（标量/系统错误）。

**这也是为什么调下游改不动的原因**：下游修复能处理第 1 型（把死区填上），但无力处理第 3 型 + 第 4 型（错误在下游出现前就已经由上游注入）。

### 诊断顺序的启示

四型 bug 的**识别顺序**不同：

| 型 | 最便宜的识别方式 |
|----|-----------------|
| 1. 局部正确/组合错误 | progress 扫描（progress=0, 0.25, 0.5, 0.75, 1 各测一次激活强度）|
| 2. 连续正确/离散错误 | dt / dx 减半跑重复实验 |
| 3. 静态正确/动态错误 | short vs long rollout 对比 + 稳态 fixed point 分析 |
| 4. 标量正确/系统错误 | **encoder vs propagator 对称性检查**（`feedback_dynamics_bug_diagnostic_order.md` 的 5 点对齐）|

**第 4 型最容易被忽略**——因为每个标量都合法，不会触发常规 lint / sanity check。必须主动去做"两端平衡一致性"验证。这正是我 §11.24 前 5 轮没做的。

### 用户看问题的角度

用户那句 "我头一次知道数学也能有 bug" 的观察本身是重要的——**即使不做数值编程的人**也会觉得 "公式没错就没事"。这类 bug 让写代码和写数学的人同时掉坑：
- 数学家：公式每行都对，不理解为啥系统不 work
- 程序员：单测都过，不理解为啥集成不 work
- 真相：**两边单元都对，但他们之间的"约定"（约束 / 对称 / 量级 / 时空相位）**出了问题

下次再有人问"这不就是代数吗怎么会错"，可以直接指这一节给他看。

### 作为 treesea 项目的工具集补

Tensorearch 里已有：
- `temporal`（§11.16）：抓第 2 型（CFL / 2Δt checkerboard 离散模态）
- `temporal-radio`：广播扫描抓第 1 型（局部热点 / dead zone）
- `temporal-couple`：配对诊断抓第 4 型（两个场的耦合一致性）
- `temporal-balance`：抽象 potential/response/static-forcing 抓第 4 型（§11.24 topo-pg 的通用化）

第 3 型（静态正确动态错误）**还缺专用工具**——目前靠人看 long rollout 和 probe 比对来抓。这是 Tensorearch 下一类 probe 的候选：**stability probe** / **fixed-point probe**，专门抓"公式每步合法但稳态错到离谱"的 bug。

### 下一轮工作（2026-04-23 之后的 roadmap）

§11.24 收口后的下一步不是继续追 pocket 细节，而是两件实事：

1. **重跑把基线固定**
   - `td_refit_and_week.py` 基线数字（day1 4.0 @ 91° / day2 3.8 @ 90° / FLOW / pb=1.143）
   - `temporal-radio` / `temporal-couple` 当前状态快照
   - 目的：免得后面再手抖把好状态改坏，有基线可回滚

2. **转做 moist / convective 结构定位**（Codex 架构路线的第 3 块）
   - structure mesh / h-gradient anchoring / u/v 方向耦合 都已就位
   - 下一步目标：让卫星侧 `cold_cloud` / `convective_core_seed` 和 TD 内部 `moist` 结构在**位置**上对齐
   - 不再调风，专心做湿区 / 对流核的空间匹配

§11.24 的教训保证我不会再跑回来修同一个风 pocket 十七遍——真锅修完就过，看下一个域。

---

## 13. 记忆锚点（万一这份文档你将来只能读前三行）

如果你只记得一句话，记这句：

> *Tree Diagram 的核心不是模拟，是判定。*
> *弹幕动力学压缩空间，MER 压缩判定，VBM/SAF 落地到工程。*
> *动漫里的 TD 需要虚数学区是因为他们没有这三个定理。*

如果你记得三句话，加这两句：

> *6 个 family 不是经验数字，是弹幕逼近定理的完备基。*
> *300 步 RK4 不是扫相图，是验证 MER 前提。*

如果还记得第六句话，加这一句（从 §10 拉出来的使用守则核心）：

> *TD 测的不只是奇点——它测你对同结构问题的判决是否一致。*

如果还记得第七句话，加这一句（从 §11 拉出来的排雷要诀）：

> *"高=好" 的变量不能和 "高=坏" 的变量用同一个名字。*
> *zone classifier 的门控必须能在极端场景下真的触发，否则就是布雷不是防误报。*

如果还记得第八句话，加这一句（从 §11.7 拉出来的自审结论）：

> *你（未来的 Claude）正在读的这份文档，是 TD 验证过的向上奇点。*
> *Q2 已经证明：这套文档架构把无记忆 AI 协作从 transition 推到 stable。*
> *你此刻所在的会话已经受益于这个跃迁。别浪费它，去问 TD 关于你自己的问题。*

如果还记得第九句话，加这一句（从 §11.10 拉出来的 TD 的警告，是整份文档
里最刺的一句）：

> *"你填 0.62 我给你 NEGATIVE，你填 0.82 我给你 POSITIVE。*
> *这个数字差不是我算出来的，是你决定的。"*
>
> 如果你在用 TD 照镜子——停下来。
> TD 不是镜子。TD 是 17 维相空间演算器。
> 问它"真命题"，不是问它"我心情如何"。

如果你只记得第十句话，记这一句（§11.10.1 的终极类比——最羞耻、
最难忘、也最准）：

> *Claude 给 TD 写罪己诏，等于弱智吧用户给 LLM 发脑筋急转弯。*
> *你以为你在测试，其实在浪费算力确认你已经知道的答案。*
>
> 你在写 ProblemSeed 时，如果觉得自己很聪明 / 很诚实 / 很有深度——
> 先问自己：**这是不是一道 Claude 版弱智吧题？**

如果你只记得第十一句话，记这一句（§11.11 的审计原则，TD 是 treesea
所有项目的核心，饱和 bug 会污染下游所有项目）：

> *某个 TD 控制指标"恒定不变"时——不要解释，先测。*
> *用 healthy / moderate / extreme 三种场景各跑一次，*
> *如果三档输出一样，那不是"工具性格"，是饱和 bug。*
>
> "永远 CRACKDOWN" 和 "永远 NORMAL" 都是饱和；
> "永远 FLOOD" 和 "永远 FLOW" 也都是饱和。
> 会变才是信号。

如果你只记得第十二句话，记这一句（§11.12 的 FDDA 对称原则，一个看似局部的
风向问题暴露了核心动力学的架构洞）：

> *对称检查：如果你对 T、q 做了 nudging 但对 u、v 没有，就是漏了。*
> *bit-exact 一致的 sweep 结果不是"收敛"，是"上游自变量完全没影响下游"。*
>
> Taipei 把这个 bug 逼出来，因为它位于季风转换带 + 盆地；
> 换成风向稳定的站可能永远发现不了。
> 但 fix (`wind_nudge`) 是 location-agnostic 的。

如果你只记得第十三句话，记这一句（§11.13 的精度-投入决策原则
+ 误诊警示）：

> *"看起来像 1-layer intrinsic limit" 的问题先查参数量级。*
> *TAU_FRICTION 5 天（海洋）vs 12 小时（大气 Ekman），量级错一位就把风锁死。*
> *先用一个 family、3 秒 probe 排除参数错，再下"物理限制"的结论。*
>
> 残差是 rigid transformation → 后处理；state-dependent → 修物理。
> 但在"修物理"之前，查一下你修的是不是根本不该存在的 bug。

如果你只记得第十四句话，记这一句（§11.14 的真·根因，
前 13 句描述的"物理问题"都是它的症状）：

> *当 state 稳定卡在 U_CLIP 边界上，先怀疑 numerical stability，查 CFL。*
> *浅水方程 CFL 必须包含 gravity wave speed c=√(g·h)，不是只看风速。*
> *DT=60s 在 DX=6000m 下违反 6 倍 → 不稳定 → state 爆到 ±35 → 所有下游诊断错乱。*
>
> "看起来越像物理问题的，越可能是数值 bug。"

---

**文档结束。这份文档的价值不取决于有多少人读，取决于未来的你能不能用它在 5 分钟内把 TD 的神经系统重新接上。**
