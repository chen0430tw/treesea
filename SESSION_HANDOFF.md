# treesea Session Handoff

> 2026-04-14，最终更新

---

## 开发背景

treesea 是一个以崩坏学 / 崩坏能学 / 树海体系为理论框架的多系统 HPC 工程仓库。命名来自"虚数之树"（Tree）与"量子之海"（Sea）的耦合体系。

项目包含：
- **Tree Diagram** — 树端裁决系统（候选世界线生成、分支生态管理）
- **QCU** — 海端虚拟量子芯片（Lindblad 主方程 + 局部坍缩）
- **Honkai Core** — 崩坏能观测系统（E_H / G_H / D_H / Gamma_H 计量）
- **HCE** — 崩坏能演算器整机（Tree Diagram + QCU + Honkai Core 桥接）
- **OPU** — 光学处理单元
- **MOROZ** — 多尺度收缩系统（MSCM + K-Warehouse + ISSC）
- **CFPAI** — 计算金融规划 AI（反向 MOROZ + 链式搜索 + Tree Diagram 网格）
- **LASA** — 资金形态分层会计（TypeScript，资金语义分类引擎）

另有独立仓库：
- **Tensorearch** — 模型架构解剖工具（15 家族分类 + 8 命令 + v1.0.0 已发布）
- **URP** — 通用拟构扩展指令体系（Rust Runtime）

---

## 本次会话完成的事（2026-04-13~14）

### HCE 崩坏能演算器（从零到完成）

1. **Honkai Core 18 文件**：崩坏能估计、阈值分析、耦合建模、改写评估
2. **HCE 29 文件**：I/O 桥接、流水线控制、结果合并、checkpoint、容错、TUI
3. **QCU torch fused solver**：49x 加速（1329s→27s），cupy/torch 冲突修复
4. **注意力评分系统**：
   - 手工权重 32.1% → 三阶段重构 → Codex 语义坍缩 → 4 轮集群训练 → **90.7% top-1**
   - strategy_tags（22 种标签）消除候选语义不足
   - Tensorearch 审计：0 findings
5. **树形调度器**：参考 URP IRGraph，ComputeNode = PTE，_search_tree = 页表遍历
6. **实验场景**：崩坏能三态、御坂网络 20K、台湾能源、TMSR vs SMR、火星登陆、AGI 时间线、大智若愚对偶、芯片主权

### Tensorearch

1. **space 多家族分类**：4 轴 → 15 家族 + 14 扩展轴（Codex 主导）
2. **adapt 家族适配器**：`--adapter source` 源码自动分类 → 家族模板 → trace graph
3. **diagnose modular flow**：模块化收缩数 + 拓扑均匀度（Codex 主导）
4. **help 命令**
5. **H100 profiling 闭环**：TTS (GPT-SoVITS vs VITS)、Diffusion (U-Net/VAE/CLIP)、GNN (GCN/GAT/SAGE)、MNIST
6. **baseline_residual 修复**、**_RE_BIO 收紧**
7. **v1.0.0 发布**：tensorearch.exe 7MB，部署到 C:\cygwin64\bin\
8. **文档更新**：README 8 命令表 + 15 家族表 + CLI_USAGE space 文档

### CFPAI 计算金融规划 AI

1. **目录重构**：CFPAI_integrated_bundle → cfpai，扁平化，清除 GPT 临时命名
2. **补全 stub**：state_types、scoring、universe_builder、allocator、risk_budget、node_utility、propagation、scripts、tests
3. **市场数据加载器**：market_loader.py（pandas-datareader/yfinance 自动切换）
4. **单资产 cap 50%**：Sharpe 0.67 → 0.85，MaxDD -14% → -10%
5. **四灯风险信号**：green/yellow/red/purple（紫灯=黑天鹅级别）
6. **UTM 硬约束隔离**：cash_floor 和 max_single_weight 不被优化器覆盖
7. **上下行波动率拆分**：区分好的波动和坏的波动，Sharpe 0.85 → 1.66
8. **麦克斯韦妖**：非线性门控，Sharpe 1.66 → **1.82**
9. **三模式可选评分**：classic / updown_vol / maxwell_demon，预设 maxwell_demon
10. **真实数据验证**：NVDA+AMD+INTC+SMH+QQQ+TLT (2023-2026)
    - Ann Return 35.55%, Sharpe 1.82, MaxDD -14.42%
    - NVDA 持有 20% 时间，avg 权重 44%
11. **9 个 smoke tests 全过**

### LASA

- 解包到 D:\LASA，TypeScript 模块化版本
- 定位：CFPAI 的上游，资金语义分类 → CFPAI 资产配置

---

## 各系统当前状态

| 系统 | 目录 | 状态 |
|------|------|------|
| Tree Diagram | `tree_diagram/` | ✅ 完成 |
| QCU | `qcu/` | ✅ 完成 + torch fused 49x |
| OPU | `opu/` | ✅ 完成 |
| MOROZ | `moroz/` | ✅ 完成 |
| Honkai Core | `honkai_core/` | ✅ 本次完成 |
| HCE | `hce/` | ✅ 本次完成 (90.7% top-1) |
| CFPAI | `cfpai/` | ✅ 本次完成 (Sharpe 1.82) |
| LASA | `D:\LASA\` | 已解包，待集成 |
| Tensorearch | `D:\Tensorearch\` | ✅ v1.0.0 发布 |
| URP | `D:\URP\` | ✅ 已完成 |

---

## 下个会话要做的事

### CFPAI Phase 2
1. **API 层**：market_api / state_api / planning_api / tuning_api（4 文件）
2. **UTM 诊断**：dimension_matrix.py + diagnostics.py
3. **回测可视化**：plots.py（净值曲线、权重变化图）
4. **杠杆机制**：负权重（做空）、max_leverage 参数、LASA 标记借入资金
5. **衍生品定价**：期权不对称收益
6. **额外数据源**：宏观变量、新闻情绪、链上数据

### LASA 集成
1. LASA → CFPAI 接口：可支配+已实现+自由资产 → CFPAI 输入
2. CFPAI 杠杆部位 → LASA 标记为借入+受限+未实现
3. 循环加杠杆防护

### Tensorearch
1. PyPI 发布准备（Codex 已开始，pyproject.toml 需改版本号+加 scripts）
2. adapt 接更多家族的真实 profiling 数据

### HCE
1. 注意力评分剩余 4 个 MISS 需要领域专家通过 strategy_tags 解决（不应强行调权重）
2. Phase 4 Oracle 完整输出（世界线生态图、神谕化解释）

---

## 关键技术决策记录

- **PTE 树形调度**：HCE 的 ComputeNode 就是页表项，_search_tree 就是页表遍历（参考 URP IRGraph）
- **麦克斯韦妖**：CFPAI 的非线性门控，好分子放大坏分子压制（解决线性评分天花板）
- **Tensorearch 实战价值**：在 CFPAI 开发中发现 grid_builder 缺 gating_logic → 加 cap 50% → Sharpe +27%
- **CFPAI vs MOROZ**：反向关系。MOROZ 收缩（混沌→秩序），CFPAI 展开（秩序→可能性空间）
- **LASA vs CFPAI**：LASA 告诉你有多少钱能用，CFPAI 告诉你怎么用
- **训练过拟合警告**：不要强行让领域专业 MISS 通过通用权重，会破坏泛化
