# OTAL — 振荡拓扑近似层

**Oscillatory Topology Approximation Layer**

## 定位

OTAL 是 QCU 的快搜代理层，位于候选态池与高保真 Lindblad/RK4 验证层之间。

```
候选态池 → OTAL → collapse_queue / full_physics_queue → Lindblad/RK4
```

它不是 RK4 的等价替换，而是：
- 前置近似层
- 候选成熟度预筛
- 方向判断层

## 核心公式

**更新规则**：
```
D_i(t+Δt) = (1-λ)·D_i(t) + λ·Σ_{j∈N(i)} w̃_ij·D_j(t) + η_i(t)
```

**成熟度**：
```
M(U,t) = α1·A(U,t) + α2·P(U,t) + α3·S(U,t) - α4·R(U,t)
```

## 模块

| 文件 | 职责 |
|------|------|
| `graph_state.py` | OTALNode / OTALEdge / OTALState 数据结构 |
| `oscillatory_direction.py` | 振荡指向数、相位差、Kuramoto 序参量 |
| `topology_update.py` | 邻域传播更新（一步推进） |
| `maturity_score.py` | 一致性/相位集中度/邻域支持/发散度 → M(U,t) |
| `candidate_filter.py` | 坍缩候选筛选，推入 collapse/full_physics 队列 |
| `runner.py` | OTALRunner 控制器（接入 IQPU 的标准入口） |

## 快速使用

```python
from qcu.otal.runner import OTALRunner

runner = OTALRunner(n_steps=20, theta_c=1.2, top_k=5)
result = runner.prefilter(candidate_labels)

# 只对 full_physics 候选跑 IQPU
for cand in result.otal_result.full_physics_queue:
    iqpu_result = iqpu.run_qcl_v6(label=cand["candidate_id"], ...)
```

## Benchmark（N=20 候选）

| 模式 | 耗时 | 加速比 |
|------|------|--------|
| RK4-only 全量 | 30.8 s | 1× |
| OTAL 预筛 | 343 ms | — |
| OTAL + RK4（筛后） | 0.34 s | **89.8×** |

OTAL-only 快搜：N=50 候选，耗时 15.6 ms，全局相位集中度 R=0.993
