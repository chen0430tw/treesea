# Tree Diagram

Tree Diagram 是一个**单一系统**，其当前参考源码基线由两个原型脚本共同组成：

- `legacy/imported_single_file_prototypes/tree_diagram_complete_mini_colab_v3_active.py`
- `legacy/imported_single_file_prototypes/tree_diagram_weather_oracle_v5_tuned.py`

这两个文件不是两个并列模式，也不是“主体 + 附属壳层”的关系。  
它们共同构成当前 Tree Diagram 原型集合。

## 一句话定义

Tree Diagram 是树端裁决、世界线生成、分支生态、数值演算与 Oracle 排名合一的独立运行系统。

## 当前结构原则

正式重构阶段，Tree Diagram 目录应按以下语义组织：

- `source_basis/`：明确两个原型文件共同作为迁移基线
- `abstracts/`：抽象层，放 seed / background / group field / worldline / ecology 等
- `numerics/`：数值层，放 weather state / dynamics / forcing / ensemble / ranking 等
- `pipeline/`：把抽象层与数值层接成完整 Tree Diagram 流程
- `io/`：输入输出协议
- `runtime/`：运行时
- `cli/`：本地运行、集群提交、结果查看
- `distributed/`：MPI / 分片执行支持

## 禁止误解

不要把 `tree_diagram_weather_oracle_v5_tuned.py` 视为：
- 独立系统
- 第二模式
- 外部壳层项目

它属于 Tree Diagram 同一原型集合的一部分。

## 本地运行

```bash
python -m tree_diagram.cli.run_local --config configs/td_local_debug.yaml
```

## 集群提交

```bash
python -m tree_diagram.cli.submit --config configs/td_cluster.yaml
```

## MPI 启动

```bash
bash mpi/mpirun_td.sh
```
