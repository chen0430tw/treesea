# Tree Diagram 决策分析使用指南

## 这是什么

Tree Diagram 的核心是一个数值多候选评估系统，它通过流体动力学模拟来搜索所有可能的路径（worldline），淘汰不可行的，留下得分最高的。

虽然它的内部使用气象/物理隐喻（网格、压力、水文），但它可以被用于**任何需要在多个候选方案中做选择的决策问题**——只要你能把问题编码成一个 ProblemSeed。

## 快速开始

### 1. 写一个 seed JSON 文件

```json
{
  "title": "你的决策问题标题",
  "target": "你想要达成的目标描述",
  "constraints": [
    "约束条件 1",
    "约束条件 2"
  ],
  "resources": {
    "budget": 0.60,
    "infrastructure": 0.70,
    "data_coverage": 0.50,
    "population_coupling": 0.40
  },
  "environment": {
    "field_noise": 0.30,
    "social_pressure": 0.50,
    "regulatory_friction": 0.25,
    "network_density": 0.60,
    "phase_instability": 0.35
  },
  "subject": {
    "output_power": 0.80,
    "control_precision": 0.70,
    "load_tolerance": 0.60,
    "aim_coupling": 0.85,
    "stress_level": 0.30,
    "phase_proximity": 0.50,
    "marginal_decay": 0.15,
    "instability_sensitivity": 0.25
  }
}
```

### 2. 跑 Tree Diagram

```bash
# 快速测试（~4秒，低分辨率）
python -m tree_diagram run --seed my_seed.json --profile quick --no-oracle --out result.json

# 正式计算（~10分钟，高分辨率）
python -m tree_diagram run --seed my_seed.json --profile default --no-oracle --out result.json
```

### 3. 看结果

结果 JSON 中最重要的字段：
- `top_results[0].family` — 胜出的候选家族
- `top_results[0].feasibility` — 可行性（0-1，越高越好）
- `top_results[0].stability` — 稳定性（0-1，越高越好）
- `top_results[0].risk` — 风险（0-1，越低越好）
- `oracle_summary.dominant_pressures` — 主导压力源
- `oracle_summary.inferred_goal` — 推断的目标轴

---

## Seed 参数编码指南

编码 seed 是整个流程中最关键也最困难的步骤。所有参数值域为 0.0 - 1.0。

### resources（你手上有什么）

| 参数 | 含义 | 编码指引 |
|------|------|----------|
| budget | 预算/资源充裕度 | 0.3=紧张, 0.6=适中, 0.9=充裕 |
| infrastructure | 基础设施成熟度 | 0.3=从零开始, 0.7=有现成工具链, 0.9=完善 |
| data_coverage | 信息/数据完备度 | 0.3=信息不足, 0.7=大部分已知, 0.9=完全掌握 |
| population_coupling | 用户/受众耦合度 | 0.3=无用户基础, 0.7=有社区, 0.9=强绑定 |

### environment（外部环境怎么样）

| 参数 | 含义 | 编码指引 | 阈值效应 |
|------|------|----------|----------|
| field_noise | 竞争/噪音程度 | 0.2=蓝海, 0.5=适中, 0.8=红海 | >0.3 触发 field_noise_elevated |
| social_pressure | 社会/舆论压力 | 0.2=无关注, 0.5=有讨论, 0.8=高压 | >0.5 触发 social_pressure_dominant |
| regulatory_friction | 合规/制度阻力 | 0.2=无管制, 0.5=有规范, 0.8=强监管 | >0.4 触发 regulatory_friction_present |
| network_density | 网络/生态密度 | 0.3=孤立, 0.6=有连接, 0.9=密集网络 | — |
| phase_instability | 市场/环境不稳定性 | 0.2=稳定, 0.5=波动, 0.8=剧变 | >0.35 触发 phase_instability_moderate |

### subject（你要做的事本身）

| 参数 | 含义 | 编码指引 |
|------|------|----------|
| output_power | 方案的输出能力/天花板 | 0.5=一般, 0.8=强, 0.95=顶级 |
| control_precision | 执行精度/可控性 | 0.5=粗略, 0.8=精确, 0.95=完全可控 |
| load_tolerance | 承压能力/容错 | 0.3=脆弱, 0.6=适中, 0.9=强韧 |
| aim_coupling | 目标与手段的耦合度 | 0.5=松散, 0.8=紧密, 0.95=完全对齐 |
| stress_level | 当前压力水平 | 0.2=轻松, 0.5=适中, 0.8=高压 |
| phase_proximity | 离临界点/转折点的距离 | 0.3=远, 0.6=接近, 0.9=临界 |
| marginal_decay | 边际衰减风险 | 0.1=低, 0.3=适中, 0.6=高 |
| instability_sensitivity | 对扰动的敏感度 | 0.2=钝感, 0.5=适中, 0.8=极敏感 |

---

## Hidden Variables（背景推演）

TD 会从你的 seed 参数自动计算 6 个隐藏变量，这些才是真正驱动结果的量：

```
latent_stress       = 0.4 * social_pressure + 0.3 * phase_instability + 0.3 * stress_level
resource_ceiling    = 0.35 * budget + 0.35 * infrastructure + 0.30 * data_coverage
coupling_depth      = 0.5 * population_coupling + 0.3 * network_density + 0.2 * aim_coupling
phase_edge_proximity = 0.5 * phase_instability + 0.3 * phase_proximity + 0.2 * field_noise
decay_risk          = 0.5 * marginal_decay + 0.3 * instability_sensitivity + 0.2 * (1 - load_tolerance)
control_capacity    = 0.5 * control_precision + 0.3 * output_power + 0.2 * (1 - regulatory_friction)
```

| 隐藏变量 | 决定什么 | 高值意味着 |
|----------|----------|------------|
| latent_stress | 系统内在压力 | 需要更保守的方案 |
| resource_ceiling | 资源上限 | <0.6 会触发 resource_constrained |
| coupling_depth | 耦合深度 | >0.7 会放大风险和机会 |
| phase_edge_proximity | 离相变边界的距离 | >0.5 触发核心矛盾 |
| decay_risk | 衰败风险 | >0.2 触发 decay_risk_nonzero |
| control_capacity | 控制能力 | >0.7 推断目标为 precision_upgrade |

---

## 候选家族含义

TD 内部使用 7 个候选家族，每个家族代表一类解决路径：

| 家族 | 隐喻 | 决策映射 |
|------|------|----------|
| **batch** | 批量处理、规模化、吞吐优先 | 低开销、直接、标准化方案 |
| **network** | 网络效应、连接、生态 | 依赖外部网络/社区的方案 |
| **phase** | 相变、突变、跨越式 | 高风险高回报的激进方案 |
| **electrical** | 精密控制、高功率 | 需要大量资源但精确可控的方案 |
| **ascetic** | 苦行、极简、低资源 | 最低成本的生存方案 |
| **hybrid** | 混合、多路径并行 | 组合多种策略的方案 |
| **composite** | 复合、多层结构 | 分阶段分层的复杂方案 |

**解读技巧**：
- Top 12 全是同一个家族 → 信号极强，方向明确
- 出现 2-3 个家族 → 有替代路径，需要进一步分析
- 家族分散 → 问题本身没有明确最优解，可能需要重新编码 seed

---

## 分辨率与交叉验证

Tree Diagram 有 4 个计算精度档位：

| Profile | 网格 | 步数 | 耗时 | 用途 |
|---------|------|------|------|------|
| quick | 32×24 | 30 | ~4秒 | 快速探方向 |
| default | 128×96 | 300 | ~10分钟 | 正式决策 |
| cluster | 512×384 | 1000 | ~90秒 (H100) | 高精度 |
| deep | 512×384 | 3000 | ~270秒 (H100) | 深度预测 |

**必须用两个精度交叉验证**：
1. 先跑 quick 看大方向
2. 再跑 default 确认信号稳健性
3. 如果 quick 中的家族在 default 中消失 → 那是低分辨率伪影，不可信
4. 如果两者一致 → 信号强，可以直接用

**实际案例**：Distrike 开源策略分析中，ascetic 家族在 quick (#11, #12) 出现但在 default 中完全消失，证明"极简苦行"路线只是低分辨率幻觉。

---

## 结合大模型使用（推荐流程）

单独使用 Tree Diagram 的门槛较高（需要理解参数语义和家族映射）。推荐与大模型（Claude / GPT 等）协同使用：

```
1. 向大模型描述你的决策问题（自然语言）
2. 让大模型先给出直觉判断（作为对照基线）
3. 让大模型把问题编码成 seed JSON
4. 跑 TD（quick + default）
5. 让大模型解读 TD 结果，映射回具体选项
6. 如果 TD 与直觉矛盾 → 以 TD 为准，重新审视假设
```

### 为什么要先让大模型给直觉判断？

不是为了让大模型做决定，而是为了建立一个可以被 TD 挑战的基线。如果 TD 结果和直觉一致，说明直觉可靠；如果矛盾，说明直觉中有被忽略的变量——这才是 TD 最有价值的时刻。

### 实际案例

| 步骤 | Distrike 开源策略 |
|------|-------------------|
| 1. 问题 | "Distrike 应该全开源还是 Open Core 还是闭源？" |
| 2. 大模型直觉 | "推荐 Open Core（核心开源 + 高级功能闭源）" |
| 3. 编码 seed | budget=0.30, social_pressure=0.72, resource_ceiling=0.432... |
| 4. TD 计算 | batch 家族 12/12 霸榜, resource_ceiling 触发 resource_constrained |
| 5. 解读 | resource_ceiling=0.432 杀死 Open Core（无法维护双代码库） |
| 6. 结论 | 推翻直觉，改为 MIT 全开源 + 速度护城河 |

**大模型的直觉错误不是因为"不知道"资源约束，而是在推理中没给它足够的权重。TD 的数学结构不允许任何变量被忽略。**

---

## 常见问题

### Q: seed 参数怎么定？感觉很主观

确实主观，这是 TD 最大的局限。建议：
- 不要纠结精确到小数点后两位，0.70 和 0.75 的区别不大
- 关注是否会越过阈值（如 social_pressure 在 0.5 附近的区别很大）
- 如果不确定，跑两次：一次用乐观参数，一次用悲观参数，看结论是否一致

### Q: 为什么所有结果都是 batch？

batch 是"默认赢家"——当问题没有极端约束时，低开销高吞吐的方案通常胜出。如果你期望看到 network 或 phase 家族，检查你的 seed 是否准确反映了问题的复杂度。

### Q: TD 给出的分数绝对值很低（如 0.27），是不是说明不可行？

不是。分数反映的是"在所有 worldline 中的相对排名"，不是"成功概率"。0.27 的方案只要是 Top 1 就是最优解。关注分数差距和 risk 值比关注绝对分数更有意义。

### Q: quick 和 default 结论不一致怎么办？

以 default 为准。quick 只有 23K 计算量，可能产生伪影。如果条件允许，再跑 cluster profile 做第三次确认。

### Q: 可以用来做哪些决策？

任何"在 N 个候选方案中选一个"的问题：
- 技术选型（语言、框架、架构）
- 商业策略（开源、定价、市场）
- 资源分配（团队、预算、时间）
- 风险评估（投资、安全、合规）

不适合的问题：
- 纯数值优化（用数学规划工具更合适）
- 是/否二元判断（seed 编码过度）
- 已有明确答案的问题（不需要模拟）
