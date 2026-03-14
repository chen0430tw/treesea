# QCU

QCU 是海端系统，负责高维候选并存、相位调制、局部坍缩、读出与回写，是虚拟量子芯片方向的独立运行系统。

## 一句话定义

QCU 是一个可独立运行的海端求解系统，用于在高维候选空间中执行相位式筛选、局部显形与读出。

## 系统职责

- 状态表示与初始化
- 相位调制
- 候选态重排
- 局部坍缩
- 读出与结果记录
- 参数扫描与批量求解
- solver trace / entanglement metrics 输出

## 输入

典型输入包括：

- state config
- phase / collapse parameters
- workload definition
- scan ranges
- solver setup

配置文件通常位于：

- `configs/qcu_default.yaml`
- `configs/qcu_local_debug.yaml`
- `configs/qcu_cluster.yaml`

## 输出

典型输出包括：

- collapse result
- readout record
- solver trace
- phase scan summary
- entanglement / negativity / runtime metrics

默认输出路径：

- `runs/qcu/`
- `logs/qcu/`
- `checkpoints/qcu/`
- `results/qcu/`

## 目录说明

- `qcu/core/`：核心求解模块
- `qcu/io/`：状态与结果 I/O
- `qcu/runtime/`：运行时
- `qcu/cli/`：命令入口
- `qcu/distributed/`：分布式执行
- `qcu/workloads/`：任务类型，如 factorization / hash_search / collapse_scan
- `jobs/`：作业定义
- `slurm/`：Slurm 模板
- `mpi/`：MPI 启动脚本

## 本地运行

```bash
python -m qcu.cli.run_local --config configs/qcu_local_debug.yaml
```

## 集群提交

```bash
python -m qcu.cli.submit --config configs/qcu_cluster.yaml
```

或直接：

```bash
sbatch slurm/qcu_single.sbatch
sbatch slurm/qcu_multi_node.sbatch
```

## MPI 启动

```bash
bash mpi/mpirun_qcu.sh
```

## 当前迁移状态

当前原型保存在：

- `../legacy/imported_single_file_prototypes/qcu_reconstructed.py`
- `../legacy/imported_single_file_prototypes/qcu_full_reconstructed.py`

后续将逐步拆分到 `core/`、`runtime/`、`io/`。
