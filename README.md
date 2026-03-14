# HCE_ROOT

HCE_ROOT 是一个面向超算与训练集群环境的多系统工程仓库，包含四套可独立运行、可独立 I/O、可独立 Slurm/MPI 提交的系统：

- Tree Diagram：树端裁决 / 世界线筛选 / 分支生态系统
- QCU：海端坍缩 / 高维候选显形 / 虚拟量子芯片系统
- Honkai Core：崩坏学 / 崩坏能学 / 阈值与风险建模系统
- HCE：集成运行时与总装层，用于将前三者桥接为统一流水线

## 仓库定位

本仓库不是单机研究脚本集合，而是面向以下目标环境设计的工程仓库：

- 天河级别超算
- 训练集群
- Slurm 批处理调度
- MPI / 多节点分布式计算
- TUI 交互前端
- 可恢复实验、日志归档、结果追踪

## 系统关系

前三个系统是并列的一等系统：

- `tree_diagram/` 可独立运行
- `qcu/` 可独立运行
- `honkai_core/` 可独立运行

`hce/` 是可选集成层，不垄断前三者的运行能力。

## 顶层目录说明

- `tree_diagram/`：树端系统
- `qcu/`：海端系统
- `honkai_core/`：理论与阈值系统
- `hce/`：集成运行时与 TUI
- `shared/`：共享基础设施
- `environment/`：环境、module、container 配置
- `experiments/`：实验清单、扫描定义、追踪索引
- `runs/`：运行实例
- `checkpoints/`：断点状态
- `logs/`：Slurm / runtime / metrics / TUI 日志
- `results/`：最终结果和报告
- `legacy/`：迁移前原型文件

## 运行原则

整个仓库遵循四条原则：

1. 系统独立  
   每个系统都有自己的 CLI、I/O、Slurm、MPI、配置与运行时。

2. 集群优先  
   目录和入口围绕批处理、分布式和实验归档组织。

3. 统一路径  
   所有系统都将结果写入统一的 `runs/`、`logs/`、`checkpoints/`、`results/` 体系。

4. 渐进重构  
   原型先保存在 `legacy/`，正式模块逐步抽离到 `core/`、`runtime/`、`io/`。

## 快速开始

### 本地调试
```bash
python -m tree_diagram.cli.run_local --config tree_diagram/configs/td_local_debug.yaml
python -m qcu.cli.run_local --config qcu/configs/qcu_local_debug.yaml
python -m honkai_core.cli.run_local --config honkai_core/configs/hc_local_debug.yaml
python -m hce.cli.run_local --config hce/configs/hce_local_debug.yaml
```

### 集群提交
```bash
python -m tree_diagram.cli.submit --config tree_diagram/configs/td_cluster.yaml
python -m qcu.cli.submit --config qcu/configs/qcu_cluster.yaml
python -m honkai_core.cli.submit --config honkai_core/configs/hc_cluster.yaml
python -m hce.cli.submit --config hce/configs/hce_cluster.yaml
```

## 文档入口

- `docs/system_overview.md`
- `docs/architecture/overall_topology.md`
- `docs/deployment/cluster_deployment.md`
- `docs/deployment/slurm_usage.md`

## 当前状态

当前仓库处于从原型脚本向正式 HPC 工程仓库迁移阶段。  
原型文件保存在 `legacy/imported_single_file_prototypes/`，白皮书与理论文档位于 `docs/whitepapers/` 与 `honkai_core/honkai_core/theory/`。

## Tree Diagram 当前原型集合说明

Tree Diagram 当前的源码参考基线不是单一脚本，而是以下两个脚本共同组成的原型集合：

- `tree_diagram_complete_mini_colab_v3_active.py`
- `tree_diagram_weather_oracle_v5_tuned.py`

二者同属一个 Tree Diagram 系统，不是两个并列模式或两个独立项目。
