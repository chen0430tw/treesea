# HCE

HCE 是集成运行时与总装层，用于把 Tree Diagram、QCU、Honkai Core 三套独立系统桥接成统一流水线。

## 一句话定义

HCE 是一个可独立提交和运行的集成系统，用于执行 Tree Diagram → QCU → Honkai Core 的耦合计算、结果合并与总装调度。

## 系统职责

- 跨系统 I/O 桥接
- 多阶段流水线控制
- 集成结果合并
- checkpoint / fault tolerance
- 集群级作业封装
- TUI 前端

## 上游系统

HCE 不替代以下系统，而是耦合它们：

- Tree Diagram
- QCU
- Honkai Core

三者都可以独立运行；HCE 仅在需要整机耦合时使用。

## 输入

典型输入包括：

- Tree Diagram 输出或配置
- QCU 输出或配置
- Honkai Core 输出或配置
- pipeline config
- bridge config
- run manifest

配置文件通常位于：

- `configs/hce_default.yaml`
- `configs/hce_local_debug.yaml`
- `configs/hce_cluster.yaml`

## 输出

典型输出包括：

- integrated pipeline result
- merged report
- inter-stage trace
- bridge I/O record
- checkpoint bundle
- final HCE report

默认输出路径：

- `runs/hce/`
- `logs/hce/`
- `checkpoints/hce/`
- `results/hce/`

## 目录说明

- `hce/integration/`：跨系统流水线控制
- `hce/bridges/`：Tree Diagram / QCU / Honkai Core I/O 桥接
- `hce/runtime/`：运行时、checkpoint、容错
- `hce/io/`：集成层 I/O 协议
- `hce/cli/`：命令入口
- `hce/tui/`：TUI 交互前端
- `jobs/`：作业定义
- `slurm/`：Slurm 模板
- `mpi/`：MPI 启动脚本

## 本地运行

```bash
python -m hce.cli.run_local --config configs/hce_local_debug.yaml
```

## 集群提交

```bash
python -m hce.cli.submit --config configs/hce_cluster.yaml
```

或直接：

```bash
sbatch slurm/hce_pipeline.sbatch
sbatch slurm/hce_multi_stage.sbatch
```

## MPI 启动

```bash
bash mpi/mpirun_hce.sh
```

## TUI

启动方式：

```bash
python -m hce.tui.app
```

第一阶段 TUI 重点功能：

- 选择配置
- 生成 / 提交 Slurm 作业
- 查看队列与日志
- 浏览阶段结果

## 当前状态

HCE 是集成层，不是前三套系统的唯一宿主。  
第一阶段目标是先实现最小流水线：Tree Diagram 输出 → QCU 消费 → Honkai Core 评估 → HCE 合并报告。
