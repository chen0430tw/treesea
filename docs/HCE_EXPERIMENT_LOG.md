# HCE 崩坏能演算器实验记录

> 2026-04-13，首次全流水线测试

---

## 实验环境

| 项目 | 本地 | 集群 |
|------|------|------|
| GPU | RTX 3070 Laptop 8GB | 2x H100 80GB |
| CPU | i7 laptop | Xeon (login node) |
| Python | 3.13 | 3.12 |
| torch | 2.11.0+cu130 | 2.6.0+cu124 |
| cupy | 14.0.1 (cuda13x) | 14.0.1 |
| QCU solver | torch fused (lindblad_torch.py) | torch fused |

---

## 实验 1: 崩坏能三态观测

**目的**：验证 Honkai Core 能正确区分稳态/增益/临界三种崩坏能状态

**配置**：纯 Honkai Core，无 QCU/TD

| 场景 | 候选数 | coupling | E_H | Γ_H | ρ_H | state | action |
|------|--------|----------|-----|-----|-----|-------|--------|
| 稳态（树海低冲突） | 4 | 0.5 | 0.0000 | 0.0516 | 0.0000 | depletion | proceed |
| 增益（树海高冲突） | 5 | 0.8 | 6.0010 | 29.99 | 6.0010 | gain | limit |
| 临界（律者化风险） | 3 | 0.95 | 12.951 | 785.9 | 25.902 | gain | contain |

**结论**：
- 低冲突 → G_H < D_H → depletion，安全放行
- 高冲突 → G_H >> D_H → gain，限制回写
- 极端冲突 → ρ_H=25.9 超过阈值 10.0 → breach(honkai)，封锁回写
- 律者化风险 >0.88 的候选被正确标记

**耗时**：<1s

---

## 实验 2: 大智若愚对偶性

**目的**：验证"大智若愚 = 大愚若智"在坍缩后是否成立

**配置**：
- seed: Wisdom-Foolishness Duality
- QCU: d=4, Nq=3, Nm=3, 2 factions x 4 candidates
- 两个 faction 用完全对称的 QCU 参数

**结果**：
```
da_zhi_ruo_yu (wisdom hidden)  : C_end = 0.019863
da_yu_ruo_zhi (foolish crowned): C_end = 0.019863
divergence = 0.000000
symmetry ratio = 1.0000
```

**结论**：对偶成立。相同 QCU 参数 → 相同坍缩结果。"智"和"愚"是观测者投影，底层结构不可区分。E_H=9.60, Γ_H=5.08 (gain)，悖论本身在释能。

**耗时**：28s

---

## 实验 3: 御坂网络同步危机

**目的**：20000 Sisters, 3 Factions 的大规模并行场景（白皮书验收标准 A）

**配置**：
- seed: Misaka Network Synchronization Crisis
- QCU: d=4, 3 factions x 4 candidates = 12 candidates
- Faction A: standard sisters (10032-19999)
- Faction B: will of the network
- Faction C: third season clones (20001-)

**QCU 坍缩结果（d=4）**：
| Faction | avg C_end | best C_end | 最佳候选 |
|---------|-----------|------------|----------|
| A | 0.020722 | 0.014707 | sister_10003 |
| B | 0.007202 | 0.003588 | sister_10005 |
| C | 0.001364 | 0.000287 | sister_10009 |

**QCU 坍缩结果（d=6）**：
| Faction | avg C_end | best C_end | 最佳候选 |
|---------|-----------|------------|----------|
| A | 0.008266 | 0.007201 | sister_10003 |
| B | 0.007218 | 0.007060 | sister_10004 |
| C | 0.008001 | 0.007698 | sister_10008 |

**Honkai Core**：E_H=17.62, Γ_H=8.41, breach=True(honkai), action=contain, 12/12 critical

**发现**：d=4 和 d=6 的赢家不同（d=4: Faction C, d=6: Faction B）。高维空间的坍缩动力学和低维不同。

**耗时**：
| 配置 | RTX 3070 | H100 |
|------|----------|------|
| d=4 fused | 27s | 18s |
| d=6 fused | 744s | 271s |

---

## 实验 4: 台湾 2030 能源转型

**目的**：实际决策问题——5 种能源策略的最优排名

**配置**：
- seed: Taiwan 2030 Energy Grid Transition
- 5 策略 x 2 变体 = 10 candidates
- tree_score: 专家赋值（手动模式）
- herrscher_risk: 按单点故障风险赋值

**排名结果**：
| # | 策略 | composite | tree |
|---|------|-----------|------|
| 1 | D: balanced_diverse | 0.9027 | 0.85 |
| 2 | D: fortress_island | 0.8842 | 0.82 |
| 3 | B: nuke_2units | 0.8725 | 0.80 |
| 4 | B: nuke_3units | 0.8422 | 0.75 |
| 5 | A: govt_base | 0.7822 | 0.65 |
| 9 | E: drift_lng | 0.6038 | 0.35 |
| 10 | E: drift_coal | 0.5734 | 0.30 |

**结论**：Resilience-First（均衡多元化）胜出。Status quo 排最后。

**耗时**：24s

---

## 实验 5: TMSR vs SMR 核能路线

**目的**：中科院钍基熔盐堆 vs 玲龙一号 SMR 哪个更有前景

**数据来源**：WebSearch（2026-04 最新公开资料）
- TMSR-LF1: 2025 年实现钍铀转换（全球首次），10MW 研究堆 2026 破土
- ACP100 玲龙一号: 2026 上半年商业运营，全球首座陆基 SMR

**排名结果**：
| # | 策略 | composite | tree | year |
|---|------|-----------|------|------|
| 1 | SMR 批量生产 | 0.9199 | 0.88 | 2028+ |
| 2 | SMR AI 数据中心 | 0.9022 | 0.85 | - |
| 3 | Hybrid: SMR→TMSR | 0.8839 | 0.82 | 2035 |
| 5 | TMSR 稳步路线 | 0.8122 | 0.70 | 2040 |
| 8 | TMSR 加速跳步 | 0.6640 | 0.45 | 2032 |

**结论**：短期 SMR 胜，长期 TMSR 有价值，最优解是 Hybrid。TMSR 跳步最危险。

**耗时**：24s

---

## 实验 6: 火星登陆预测

**目的**：预测人类首次登陆火星的时间和执行者

**数据来源**：WebSearch（SpaceX Starship, NASA Artemis II, China Tianwen）

**配置**（全自动模式，注意力评分 v2 + 语义坍缩）：
- 9 candidates: SpaceX x3, NASA x2, China x2, Joint x1, Never x1
- seed: competition=0.75, tech_readiness=0.35, turbulence=0.35

**排名结果**：
| # | 场景 | composite | tree | year |
|---|------|-----------|------|------|
| 1 | SpaceX+NASA joint | 0.96 | 0.95 | 2033 |
| 2 | SpaceX crew (realistic) | - | - | 2035 |
| 3 | SpaceX cargo | - | - | 2029 |
| 8 | Musk dream 2031 | - | 0.10 | 2031 |
| 9 | Never | - | 0.10 | 2050+ |

**赢家 breakdown**：
- institution_axis: 0.6406
- execution_axis: 0.6001
- coordination_axis: 0.2328

**结论**：联合方案排第一（机构能力 + 执行力 + 协同）。Musk 的 2031 和"永远上不去"都排末尾。四项关键技术（轨道加油、火星 EDL、生命保障、ISRU）均为 0% 验证。

**耗时**：22s

---

## 实验 7: AGI 时间线预测

**目的**：预测 AGI 到达时间和领跑者

**配置**（全自动模式）：
- 11 candidates: OpenAI x2, Anthropic x2, Google x2, China x2, Open-source x1, Pessimist x2
- seed: competition=0.90, tech_readiness=0.45, commercial_motivation=0.95

**排名结果**：
| # | 场景 | composite | tree | year |
|---|------|-----------|------|------|
| 1 | China state-backed | 0.9624 | 0.95 | 2035 |
| 2 | China DeepSeek/Qwen | 0.8002 | 0.68 | 2031 |
| 3 | No AGI before 2040 | 0.4777 | 0.14 | 2040 |
| 4 | Open-source collective | 0.4742 | 0.14 | 2032 |
| 5 | Anthropic safe AGI | 0.4741 | 0.14 | 2032 |
| 11 | Altman claim 2027 | 0.4540 | 0.10 | 2027 |

**赢家 breakdown**：
- execution_axis: 0.4737
- institution_axis: 0.3183

**崩坏能状态**：E_H=0.0, Γ_H=0.40, state=depletion — 消耗大于产出，尚无突破性释能

**结论**：国家支持路线 + 长期耐心排第一。CEO 声称的激进时间表排最后。Safety/alignment 15%/10% solved 是真正瓶颈。

**耗时**：36s

---

## QCU solver 性能基准

| 配置 | 求解器 | QCU 耗时 | 加速比 |
|------|--------|----------|--------|
| d=4 cupy full_physics | Python loop | 1329s | 1x |
| d=4 cupy fast_search | Python loop | 426s | 3.1x |
| d=4 torch fused (3070) | batched matmul | 27s | **49x** |
| d=4 torch fused (H100) | batched matmul | 18s | 74x |
| d=6 torch fused (3070) | batched matmul | 744s | - |
| d=6 torch fused (H100) | batched matmul | 271s | - |

---

## 注意力评分演进

| 版本 | 问题 | 修复 |
|------|------|------|
| v1 无注意力 | 所有候选 tree_score 相同 | 加入 attention_map |
| v1 attention_map | 梯度流（sigmoid 排序） | 加入门控打断 |
| v1 + 门控 | 33 规则 + 10 门控混杂，不可解释 | 重写为三阶段 |
| v2 三阶段 | seed 参数不传导 | 注入 seed_environment |
| v2 + 语义坍缩 (Codex) | QCU 参数不携带策略语义 | 从 label 提取身份语义 |

**最终架构**：
```
TD features → 坍缩为 4 主轴 (survival/race/coordination/institution)
候选 params → 原始特征 + 身份语义 → 坍缩为潜变量
AFFINITY (按主轴分组) → CONSTRAINT (硬约束) → NORMALIZE (softmax)
输出: tree_score + attention_breakdown (可解释)
```

**Tensorearch 审计**：0 findings, assessment = no_major_logic_smells_detected

---

## 已知限制

1. Tree Diagram 的 oracle 输出对不同 seed 区分度不够（field_snapshot 来自内部气象模拟，不直接反映 seed.environment）
2. QCU 物理参数不携带策略语义，需要从 label 补偿
3. d=6 在本地 RTX 3070 需要 12 分钟，d=8 可能需要集群
4. 注意力权重目前是手工设定，未来应该用数据驱动学习
5. composite_score = 0.6 * tree + 0.4 * (1 - C_end) 的权重是固定的
