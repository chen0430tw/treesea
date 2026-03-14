# Honkai Core

Honkai Core 是理论与阈值分析系统，负责崩坏学、崩坏能学、树海结构、阈值判据、风险分析与稳定化建模。

## 一句话定义

Honkai Core 是一个可独立运行的理论计算与风险评估系统，用于对崩坏、崩坏能、世界泡、律者化与主线重排进行建模和数值分析。

## 系统职责

- 崩坏能估计
- 阈值分析
- 风险分级
- 耦合建模
- 稳定化评估
- 世界泡自洽判定
- 律者化 / 权限化判定
- 结构重排与回写风险分析

## 输入

典型输入包括：

- scenario config
- threshold parameters
- energy model config
- coupling model config
- rewrite / stabilization parameters

配置文件通常位于：

- `configs/hc_default.yaml`
- `configs/hc_local_debug.yaml`
- `configs/hc_cluster.yaml`

## 输出

典型输出包括：

- energy estimate report
- threshold scan result
- risk surface
- stabilization recommendation
- herrscherization / rewrite assessment
- structured theory report

默认输出路径：

- `runs/honkai_core/`
- `logs/honkai_core/`
- `checkpoints/honkai_core/`
- `results/honkai_core/`

## 目录说明

- `honkai_core/theory/`：理论文档
- `honkai_core/models/`：数值模型
- `honkai_core/io/`：场景与报告 I/O
- `honkai_core/runtime/`：运行时
- `honkai_core/cli/`：命令入口
- `jobs/`：作业定义
- `slurm/`：Slurm 模板
- `mpi/`：MPI 启动脚本

## 本地运行

```bash
python -m honkai_core.cli.run_local --config configs/hc_local_debug.yaml
```

## 集群提交

```bash
python -m honkai_core.cli.submit --config configs/hc_cluster.yaml
```

或直接：

```bash
sbatch slurm/hc_single.sbatch
sbatch slurm/hc_scan.sbatch
```

## MPI 启动

```bash
bash mpi/mpirun_hc.sh
```

## 理论文档

核心理论文档位于：

- `honkai_core/theory/honkai_studies.md`
- `honkai_core/theory/honkai_energetics.md`
- `honkai_core/theory/imaginary_tree.md`
- `honkai_core/theory/sea_of_quanta.md`
- `honkai_core/theory/world_bubble.md`
- `honkai_core/theory/herrscher.md`
- `honkai_core/theory/threshold_and_risk.md`

## 当前状态

Honkai Core 不是纯文档目录，而是面向数值分析和集群运行的理论计算系统。  
后续将从理论稿逐步沉淀出 `energy_model.py`、`threshold_model.py`、`coupling_model.py` 与 `rewrite_model.py`。
