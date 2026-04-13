# treesea Session Handoff

> 2026-04-13，更新

---

## 仓库位置

`D:\treesea` — GitHub: chen0430tw/treesea

## 七系统当前状态

| 系统 | 目录 | 文件数 | 状态 |
|------|------|--------|------|
| **Tree Diagram** | `tree_diagram/` | 95 .py | ✅ 开发完成，集群测试过 |
| **QCU** | `qcu/` | 77 .py | ✅ 开发完成，新增 torch fused solver (49x 加速) |
| **OPU** | `opu/` | 11 .py | ✅ 从 APT-Transformer 迁入 |
| **MOROZ** | `moroz/` | 60 .py | ✅ core + HCE + scheduler + QCU core |
| **Honkai Core** | `honkai_core/` | 18 .py | ✅ **本次完成**，全部实现 |
| **HCE** | `hce/` | 29 .py | ✅ **本次完成**，全部实现 |

## 本次会话完成的事（2026-04-13）

### Honkai Core — 从 placeholder 到完整实现（18 文件）

**io/**
- `risk_schema.py` — 7 个 dataclass：RiskEntry, RiskSurface, EnergyEstimate, ThresholdAssessment, RewriteAssessment, Recommendation, HCReportBundle
- `threshold_schema.py` — ThresholdScanPoint + ThresholdScanResult
- `scenario_loader.py` — ScenarioConfig + CandidateSpec + YAML/JSON 加载
- `energy_report_writer.py` — Bundle/JSONL/文本摘要落盘

**models/**
- `energy_model.py` — 崩坏能估计 (G_H, D_H, Γ_H, ρ_H, 增益/稳态/衰竭判定)
- `threshold_model.py` — 阈值分析 (成熟度 M(U_i), 越限判定, 参数扫描)
- `coupling_model.py` — 树海耦合 (耦合强度, 能量传递, 共振, 稳定性)
- `rewrite_model.py` — 改写评估 (风险加权, 稳定化代价, 行动建议)

**runtime + cli/**
- `runner.py` — HonkaiCoreRunner: 4 步流水线 → HCReportBundle
- CLI: run_local / submit / inspect 三入口

### HCE — 从 placeholder 到完整实现（29 文件）

**io/** — RequestBundle, FinalReportBundle, PipelineConfig (6 种运行模式)
**bridges/** — TD/QCU/HC 三系统 I/O 桥接 + 弱回写 feedback
**integration/** — TD→QCU, QCU→HC 阶段桥接, PipelineController, ResultMerger
**runtime/** — HCERunner, CheckpointManager, FaultToleranceHandler, Launcher
**cli/** — run_local / submit / inspect + TUI 入口
**tui/** — 5 面板: 主菜单 / 状态总览 / 任务提交 / 队列状态 / 结果浏览

### QCU — torch fused Lindblad solver（新增）

- `qcu/core/lindblad_torch.py` — FusedLindbladSolver
  - collapse operators 堆成 batch tensor，用 torch.bmm 替代 Python for 循环
  - 参考 FlashMLA 设计：减少 Python↔GPU 搬运次数
- `qcu/core/iqpu_runtime.py` — 新增 `run_qcl_v6_fused()` 方法
- `qcu/runtime/runner.py` — 自动检测 torch+CUDA → 启用 fused solver

**性能对比 (d=4, Nq=3, Nm=3, 12 candidates, RTX 3070):**

| 版本 | QCU 耗时 | 加速比 |
|------|---------|--------|
| cupy 原版 (full_physics) | 1329s | 1x |
| cupy fast_search | 426s | 3.1x |
| **torch fused** | **27s** | **49x** |

d=6 torch fused: 728s（可跑，CPU 原版根本跑不完）

### 整机流水线验证

- Tree Diagram → QCU → Honkai Core → HCE Merge 全链路跑通
- 场景: Misaka Network Synchronization Crisis (20000 Sisters, 3 Factions)
- d=4: 29s 完成, d=6: 730s 完成
- 崩坏能观测: 3 场景（稳态/增益/临界）+ 耦合强度阈值扫描

### 集群同步状态

- nano5 上 tree_diagram/ 与本地完全一致
- honkai_core/ 和 hce/ 的新代码尚未同步到集群
