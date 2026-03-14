# HCE 技术栈选型文档

## 1. 选型结论

HCE 当前阶段的主开发语言应统一为：

**Python 为主，C++ / CUDA 为性能热点扩展。**

不建议在现阶段把主线改成：

- Rust
- Go
- 全仓库 C++

原因很明确：  
HCE 现在仍处于**原型迁移 + 仓库重构 + HPC 运行骨架建立**阶段，首要目标不是极限性能，而是：

- 让四系统真正独立运行
- 建立统一 I/O
- 跑通 Slurm / MPI / TUI
- 保持 legacy 原型可迁移
- 让 Claude / 人工都能快速协作

在这个阶段，Python 的综合收益最高。

---

## 2. 当前项目特征

HCE 不是普通单机脚本仓库，而是一个面向超算 / 训练集群的四系统工程：

- Tree Diagram
- QCU
- Honkai Core
- HCE

并且具备以下现实约束：

- 已有原型源码主要为 Python
- 需要传统 Slurm 提交模式
- 需要 MPI / 多节点并行
- 需要 TUI 作为集群前端
- 需要快速重构与渐进迁移
- 需要大量文档、配置、日志、结果归档
- 需要后续再决定哪些核心值得下沉优化

因此语言选型必须优先服务于：

**迁移效率、工程一致性、集群可用性、可维护性。**

---

## 3. 为什么主语言选 Python

## 3.1 与现有原型直接同构

当前已经存在的主要原型脚本就是 Python：

- `tree_diagram_complete_mini_colab_v3_active.py`
- `tree_diagram_weather_oracle_v5_tuned.py`
- `qcu_reconstructed.py`
- `qcu_full_reconstructed.py`

这意味着如果继续用 Python：

- 原型可直接迁移
- 无需跨语言重写
- 可直接对照 legacy 拆模块
- 重构成本最低

如果改用 Rust / Go / C++，则首先会发生的不是“系统更强”，而是：

- 原型迁移速度大幅下降
- 模块重构与语言迁移耦合在一起
- 仓库骨架刚建立就要面对重写成本

这不划算。

---

## 3.2 适合做系统层与调度层

HCE 当前最重要的并不是“一个超快 kernel”，而是完整系统层：

- CLI
- TUI
- 配置加载
- Slurm 提交
- 日志读取
- 结果归档
- manifest 管理
- checkpoint 路径管理
- 跨模块桥接
- 实验扫描

这些工作，Python 非常适合。

也就是说，HCE 当前真正的主战场是：

> **工程编排层，而不是纯数值核层。**

Python 在这部分的开发效率远高于大多数替代方案。

---

## 3.3 适合 HPC 原型期

很多人会直觉认为“超算项目就应该主语言 C++/Fortran”。  
但 HCE 当前并不是成熟数值程序的最终生产态，而是：

- 研究型工程
- 原型重构期
- 架构定型期
- 多系统边界建立期

在这个阶段，Python 最有优势的地方不是“绝对性能”，而是：

- 试错快
- 重构快
- 文档同步快
- 与 YAML / JSON / shell / sbatch 配合顺手
- 易于让 Claude 或人工协作

所以对 HCE 来说，Python 不是妥协，而是**阶段最优解**。

---

## 4. 四系统分别适合什么语言策略

## 4.1 Tree Diagram

建议：**Python 主实现**

原因：

- 当前两个原型本来就是 Python
- Tree Diagram 包含大量非纯数值层逻辑：
  - seed
  - background inference
  - group field
  - worldline generation
  - branch ecology
  - ranking / oracle
- 即使有数值部分，也不代表整系统该换语言

结论：

> Tree Diagram 先完整 Python 化，后续若某些 worldline 批量评估确实成为瓶颈，再局部下沉。

---

## 4.2 QCU

建议：**Python 主实现，热点预留 C++ / CUDA 下沉口**

QCU 是四系统里最可能出现性能热点的部分。  
因为它可能包含：

- 矩阵/张量推进
- 大量状态更新
- 重复数值迭代
- collapse / readout 前后的高密度计算

因此它的最优策略不是“现在就全改 C++”，而是：

1. 先用 Python 把结构和接口跑通
2. 找出热点
3. 再把热点下沉为：
   - C++
   - CUDA
   - 或其它高性能扩展

结论：

> QCU 是最适合后期混合语言优化的系统，但不是现在就该整体重写的系统。

---

## 4.3 Honkai Core

建议：**纯 Python**

Honkai Core 主要承担：

- 能量模型
- 阈值模型
- 风险分析
- 判据计算
- 理论报告生成

这部分的瓶颈通常不在语言本身，而在：

- 模型是否定义清楚
- 输入输出是否统一
- 判据是否能复用
- 报告是否能和 HCE 桥接

因此 Honkai Core 没必要复杂化。  
Python 足够，而且最合适。

---

## 4.4 HCE

建议：**纯 Python**

HCE 是：

- 集成运行时
- bridge 层
- pipeline 层
- TUI 前端
- Slurm / MPI 外壳

这一层最重要的是：

- 连接
- 调度
- 归档
- 观察
- 恢复

不是极限数值性能。

因此 HCE 用 Python 最合适。

---

## 5. TUI 适合什么语言

建议：**Python + Textual**

原因：

- 与主语言一致
- 与当前项目结构一致
- 适合快速构建 HPC 前端壳
- 便于整合：
  - 作业提交
  - 队列查看
  - 日志 tail
  - 结果浏览

TUI 在 HCE 里应该是：

> **集群操作前端壳**

而不是独立桌面应用。

所以没必要为了 TUI 单独引入别的语言或框架。

---

## 6. Slurm / MPI 适合什么语言

建议：**Python 编排 + shell 启动脚本**

也就是：

- Python：
  - 生成配置
  - 生成/选择 sbatch
  - 调用 `sbatch`
  - 解析 `squeue / sacct / scontrol`
  - 组织日志和结果路径

- shell：
  - `mpirun_*.sh`
  - module load
  - 集群环境初始化

这种组合最稳。

不要把所有集群逻辑都塞进 Python，也不要把所有逻辑都写成 shell。  
最合理的是：

> **Python 做编排，shell 做启动。**

---

## 7. 为什么不建议 Go

Go 的优势主要在：

- CLI
- 服务端工具
- 运维型程序
- 并发网络程序

但 HCE 当前的核心不是这些。  
HCE 的核心是：

- 研究原型迁移
- HPC 作业组织
- 数值代码重构
- 白皮书驱动的系统实现
- 与现有 Python 原型直接对接

Go 在这里最大的问题不是“不能做”，而是：

- 无法直接复用现有 Python 原型
- 数值原型迁移收益不高
- 你会额外承受一层语言迁移成本

所以不建议作为主语言。

---

## 8. 为什么不建议 Rust

Rust 的优势在：

- 内存安全
- 高性能
- 系统级可靠性

但 HCE 当前并不是稳定后的产品工程，而是：

- 架构定型前
- 原型还在迁移
- 文件结构刚建立
- 模块边界还在固定

这个阶段如果主语言换成 Rust，最先发生的问题是：

- 迁移成本激增
- 原型代码几乎都要重写
- 重构节奏变慢
- Claude / 人工协作门槛变高

所以 Rust 不是不能用，而是：

> **现在用它当主语言，时机不对。**

---

## 9. 为什么不建议“全仓库 C++”

C++ 当然适合做高性能核。  
但它不适合作为 HCE 当前阶段的统一主语言。

原因：

- 配置、路径、日志、归档、脚本编排开发效率差
- 对当前 Python 原型复用差
- 对 TUI、Slurm 编排、实验管理不划算
- 仓库结构正在成型时，全仓库 C++ 会拖慢所有事情

更合理的路线是：

> **Python 先把系统架起来，C++ 只处理被证明真的慢的热点。**

---

## 10. 最推荐的最终技术栈

## 10.1 主语言
- Python

## 10.2 集群前端
- Python
- Textual（TUI）

## 10.3 集群编排
- Python
- shell（module / mpirun / environment bootstrap）

## 10.4 并行接口
- MPI（通过 Python 层封装）
- Slurm（通过 sbatch/srun 驱动）

## 10.5 配置格式
- YAML

## 10.6 结果与日志
- JSON / JSONL / Markdown 报告
- 统一落入：
  - `runs/`
  - `checkpoints/`
  - `logs/`
  - `results/`

## 10.7 性能热点扩展
- C++
- CUDA

---

## 11. 实施建议

最合理的实施顺序如下：

### 第一阶段
全仓库统一 Python，先把四系统入口跑通：

- `run_local.py`
- `submit.py`
- `inspect.py`

### 第二阶段
用 Python 完成：

- I/O schema
- runtime
- Slurm 模板组织
- MPI 启动脚本
- TUI 框架

### 第三阶段
定位真正热点：

- Tree Diagram 的批量 worldline 评估
- QCU 的矩阵/张量推进
- 其它高频数值核

### 第四阶段
只对热点做下沉：

- C++ 扩展
- CUDA kernel
- 或其他专用数值实现

---

## 12. 最终建议

一句话结论：

> **HCE 现在最适合用 Python 做统一主语言，把四系统完整跑通；等 QCU 或 Tree Diagram 的某些数值核心被证明是真正瓶颈，再局部下沉到 C++ / CUDA。**

这是当前阶段成本最低、速度最快、最不容易把项目结构搞乱的路线。
