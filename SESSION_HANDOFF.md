# treesea Session Handoff

> 2026-04-13，最终更新

---

## 仓库位置

`D:\treesea` — GitHub: chen0430tw/treesea

## 七系统当前状态

| 系统 | 目录 | 状态 |
|------|------|------|
| **Tree Diagram** | `tree_diagram/` | ✅ 开发完成 |
| **QCU** | `qcu/` | ✅ torch fused solver (49x 加速) |
| **OPU** | `opu/` | ✅ 从 APT-Transformer 迁入 |
| **MOROZ** | `moroz/` | ✅ core + HCE + scheduler |
| **Honkai Core** | `honkai_core/` | ✅ 本次完成 |
| **HCE** | `hce/` | ✅ 本次完成 |

## 本次会话完成的事（2026-04-13）

### 1. Honkai Core 完整实现（18 文件）

- io/: HCReportBundle, RiskEntry, EnergyEstimate, ThresholdAssessment, ThresholdScanResult, ScenarioConfig
- models/: energy_model (G_H/D_H/Gamma_H), threshold_model, coupling_model, rewrite_model
- runtime/: HonkaiCoreRunner 4 步流水线
- cli/: run_local, submit, inspect

### 2. HCE 完整实现（29 文件）

- io/: RequestBundle, FinalReportBundle, PipelineConfig (6 模式)
- bridges/: TD/QCU/HC I/O 桥接 + 弱回写
- integration/: PipelineController, ResultMerger, candidate_attention
- runtime/: HCERunner, CheckpointManager, FaultToleranceHandler, Launcher
- cli/: run_local, submit, inspect + TUI 入口
- tui/: 5 面板

### 3. QCU torch fused Lindblad solver

- lindblad_torch.py: torch.bmm batched matmul
- 49x 加速 (d=4: 1329s → 27s)
- cupy/torch CUDA context 冲突已修
- complex64 全链路适配（登录节点兼容）

### 4. 注意力评分系统 (candidate_attention.py)

**v1 → v2 重写（Codex 协助优化）：**
- 三阶段架构：AFFINITY → CONSTRAINT → NORMALIZE
- 语义坍缩：TD 特征 → 4 主轴 (survival/race/coordination/institution)
- 候选身份语义：从 label 提取 joint/nasa/spacex 等标签
- 可解释 breakdown 输出
- Tensorearch 审计：0 findings

### 5. 实际场景测试

| 场景 | 结果 | 耗时 |
|------|------|------|
| 崩坏能三态观测 | 稳态/增益/临界 正确区分 | <1s |
| 大智若愚对偶性 | symmetry=1.0 对偶成立 | 28s |
| 御坂网络同步危机 | Faction C 最佳桥接 | 29s (d=4) |
| 台湾能源转型 | balanced_diverse #1 | 24s |
| 火星登陆预测 | SpaceX+NASA joint 2033 #1 | 22s |
| TMSR vs SMR 核能 | SMR 批量化 #1, Hybrid #3 | 24s |
| AGI 时间线 | China state-backed 2035 #1 | 36s |

### 6. 集群验证

- nano5 H100: Honkai Core 通过, HCE 整机 d=4 通过 (21s), d=6 通过 (276s)
- complex64 全链路适配解决登录节点内存限制

### 7. Tensorearch diagnose 功能优化

- _logic_labels 保守化（module 级不做全文搜索）
- shell strengths 去重
- derived_parameter_fallback 改成邻近检测
- shell/python entropy_clusters 结构统一
- _score_mutations 扩大变量名集合
