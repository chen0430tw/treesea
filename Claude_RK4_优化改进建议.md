# Claude 改进建议：RK4 / Lindblad / Runtime / Readout 优化说明
## IQPU / QCU 核心算法性能整改建议

**版本**：v1.0  
**作者**：430  
**对象**：Claude / 协作代码代理  
**用途**：针对当前 IQPU / QCU 的 RK4 + Lindblad 演化路径过慢问题，给出结构化整改建议。  
**适用文件**：
- `iqpu_runtime.py`
- `lindblad_solver.py`
- `readout.py`

---

# 0. 问题概述

当前现象：

- IQPU / QCU 的 **Lindblad + RK4** GPU 路径约需 **25 秒**
- 传统直接验证某候选（例如 `abc123`）只需约 **6 秒**

这不意味着 QCU 理论失效，而意味着当前实现仍然把：

- **高保真物理演化**
- **任务级快搜**
- **高频观测 / 纠缠监测**
- **GPU 与 Python 间同步**

全部绑在同一条执行链里。

因此，整改目标不是“随便调快一点”，而是把系统正式拆成：

1. **Full Physics Mode（高保真模式）**
2. **Fast Search Mode（快搜模式）**

---

# 1. 结论摘要

当前性能瓶颈来自三层叠加：

## 1.1 Solver 层太重
`lindblad_solver.py` 当前走的是：

- 密度矩阵
- Lindblad 开放系统
- RK4 四次 RHS
- 多个 collapse channels
- 归一化与厄米修正

这本身就比“直接 hash 比较”重很多。

## 1.2 Readout 层同步过密
`readout.py` 当前存在：

- 高频 `expect(...)`
- 动态 backend 判断
- 大量 `float / np.real / np.angle`
- 可选 negativity 计算

这会频繁触发 GPU -> CPU 同步。

## 1.3 Runtime 层调度过密
`iqpu_runtime.py` 当前更像：

- 高保真实验执行器
- 论文图数据采集器

而不是：

- 候选快搜执行器

---

# 2. 关键判断

必须明确：

> **当前慢，不是因为 QCU 理论没用，而是因为“高保真物理模拟路径”和“快搜任务路径”没有正式拆开。**

所以整改方向不是推翻 Lindblad 或 RK4，而是：

- 清理 solver 热路径
- 降低 readout 同步频率
- 将 runtime 做成双 profile
- 把高保真模式和快搜模式分层

---

# 3. 对 `lindblad_solver.py` 的整改建议

---

## 3.1 backend 判定必须外提

### 当前问题
若在 `lindblad_rhs()` 内部执行类似：

```python
try:
    import cupy
    xp = cupy.get_array_module(rho)
except ImportError:
    xp = np
```

则该逻辑会在 RK4 热路径里被重复执行。

### 改进原则
- backend 不允许在 RHS 内部动态判断
- `xp` 必须在 solver 初始化时确定
- RHS 只接收已经固定的 `xp`

### 参考写法

```python
def lindblad_rhs(xp, rho, H, c_cache, tmp1, tmp2, out):
    xp.matmul(H, rho, out=tmp1)
    xp.matmul(rho, H, out=tmp2)
    out[:] = -1j * (tmp1 - tmp2)

    for c, cd, cd_c in c_cache:
        xp.matmul(c, rho, out=tmp1)
        xp.matmul(tmp1, cd, out=tmp2)
        out[:] += tmp2

        xp.matmul(cd_c, rho, out=tmp1)
        out[:] += -0.5 * tmp1

        xp.matmul(rho, cd_c, out=tmp1)
        out[:] += -0.5 * tmp1

    return out
```

---

## 3.2 dtype 必须参数化

### 当前问题
若缓冲区固定 `complex128`，GPU 开销会明显变大。

### 改进原则
- solver 必须允许配置 `complex64 / complex128`
- `fast_search` 默认应优先尝试 `complex64`
- `full_physics` 保留 `complex128`

### 参考写法

```python
def alloc_rk4_buffers(DIM, xp, dtype):
    z = lambda: xp.zeros((DIM, DIM), dtype=dtype)
    return z(), z(), z(), z(), z(), z(), z(), z()
```

---

## 3.3 热路径内禁止函数级 import

### 当前问题
如果 `rk4_step()` 或 `lindblad_rhs()` 内部再 import 其他函数，会污染热路径。

### 改进原则
- 所有 import 放到模块顶层
- 若需要加速，可提前绑定本地引用

---

## 3.4 初态构建应支持 backend 原生创建

### 当前问题
如果先在 CPU 上构建初态，再 `xp.asarray(...)` 搬到 GPU，会产生额外成本。

### 改进原则
- `build_initial_state()` 支持传入 `xp`
- 初态直接在目标 backend 上构建

---

# 4. 对 `readout.py` 的整改建议

---

## 4.1 `expect()` 不允许动态判断 backend

### 当前问题
如果 `expect()` 内部动态判断 `cupy.get_array_module(...)`，则高频观测时成本很高。

### 改进原则
- 改成 `expect(xp, rho, op)`
- backend 由 runtime / solver 外部确定

### 参考写法

```python
def expect(xp, rho, op):
    return xp.trace(rho @ op)
```

---

## 4.2 快照函数必须拆成 fast / full 两版

### 当前问题
目前 `compute_step_snapshot(...)` 往往把：

- `a_vals`
- `C`
- `rel_phase`
- negativity
- `n_vals`
- `sz_vals`
- 各种 Python 标量化

揉在一起。

### 改进原则
必须拆成：

#### `compute_step_snapshot_fast(...)`
只做：
- `a_vals`
- `C`
- `rel_phase`

#### `compute_step_snapshot_full(...)`
才做：
- negativity
- `n_vals`
- `sz_vals`
- 全量 dataclass 封装

### 参考写法

```python
def compute_step_snapshot_fast(xp, rho, aJ, phi_ref):
    a0 = complex(as_scalar(expect(xp, rho, aJ[0])))
    a1 = complex(as_scalar(expect(xp, rho, aJ[1])))

    C = float(abs(a0 - a1))
    rel_phase = [
        wrap_pi(np.angle(a0) - phi_ref),
        wrap_pi(np.angle(a1) - phi_ref),
    ]
    return C, rel_phase
```

---

## 4.3 negativity 必须稀疏化或关闭

### 当前问题
纠缠监测很可能是 readout 里最重的一项，尤其涉及：

- partial transpose
- eigvalsh

### 改进原则
- 增加 `negativity_every`
- `fast_search` 默认 `0`
- `full_physics` 默认稀疏采样，不要每步都算

### 参考写法

```python
if cfg.track_entanglement and cfg.negativity_every > 0 and (i % cfg.negativity_every) == 0:
    neg = negativity_qubit0_vs_rest(xp, rho)
else:
    neg = None
```

---

## 4.4 延迟标量化

### 当前问题
频繁的：

- `float(...)`
- `np.real(...)`
- `np.angle(...)`

会触发 GPU 同步。

### 改进原则
- 尽量在 GPU 上保留张量态
- 仅在必要时拉回 CPU
- 能批量转换就不要逐项转换

---

# 5. 对 `iqpu_runtime.py` 的整改建议

---

## 5.1 引入 profile 体系

### 改进原则
runtime 至少支持：

- `mode="full_physics"`
- `mode="fast_search"`

### 参考 profile

```python
from dataclasses import dataclass

@dataclass
class IQPUFastProfile:
    name: str = "fast_search"
    obs_every: int = 8
    negativity_every: int = 0
    track_entanglement: bool = False
    dtype: str = "complex64"
    backend: str = "cupy"
```

---

## 5.2 观测频率必须降下来

### 当前问题
`obs_every=1` 会让 readout 高频打断 solver。

### 改进原则
- `fast_search` 默认 `obs_every >= 8`
- 对 hash / abc123 类任务可进一步提高到 `16` 或 `32`

---

## 5.3 runtime 必须选择 readout 路径

### 改进原则
主循环里不能永远走同一个 snapshot 逻辑。

### 参考写法

```python
if mode == "fast_search":
    snap = compute_step_snapshot_fast(...)
else:
    snap = compute_step_snapshot_full(...)
```

---

## 5.4 过程观测与最终观测分离

### 当前问题
过程里频繁观测，末态又重复做完整观测。

### 改进原则
- 过程观测：最小必要集
- 最终观测：完整集
- 不要每步都做最终等级的读出

---

# 6. 推荐的新文件结构

```text
qcu/
├─ core/
│  ├─ iqpu_runtime.py
│  ├─ lindblad_solver.py
│  ├─ profiles.py
│  └─ initial_state.py
├─ readout/
│  ├─ readout_fast.py
│  ├─ readout_full.py
│  ├─ metrics.py
│  └─ entanglement.py
├─ benchmarks/
│  ├─ perf_compare.py
│  └─ runtime_profile_bench.py
└─ labs/
```

---

# 7. benchmark 必须补的对照

Claude 在整改后，必须至少提供以下 benchmark：

## 7.1 原版 vs 优化版
- 原版 runtime + solver
- 优化版 runtime + solver

## 7.2 NumPy vs CuPy
- numpy / complex128
- cupy / complex128
- cupy / complex64

## 7.3 full_physics vs fast_search
- 同一任务比较总时长
- 同时比较主要输出是否仍可用

## 7.4 高频观测 vs 稀疏观测
- `obs_every=1`
- `obs_every=8`
- `obs_every=16`

---

# 8. Claude 必须交付的输出

每次整改后，输出必须包含：

1. 改了哪些热路径
2. 哪些 backend 判定被外提
3. dtype 是否参数化
4. fast/full 两种模式是否已分离
5. readout 是否拆成轻重两版
6. benchmark 数据
7. 是否保持理论语义一致

### 推荐汇报模板

```text
本次整改完成：
- lindblad_rhs 改为显式传入 xp
- alloc_rk4_buffers 支持 complex64 / complex128
- readout 拆为 fast / full 两版
- runtime 新增 fast_search profile
- negativity 改为稀疏采样

benchmark：
- 原版 cupy: 25.1s
- 优化 full_physics: 18.4s
- 优化 fast_search: 7.2s

说明：
- 理论语义未改，仍保留 Lindblad + RK4 主干
- 仅将观测、同步、数据类型策略做 profile 化
```

---

# 9. 最终目标

最终目标不是把 Lindblad / RK4 废掉，而是让系统正式支持：

## Full Physics Mode
- 高保真
- 可解释
- 论文级 / 验证级
- 保留完整物理监测

## Fast Search Mode
- 快速候选筛选
- 减少同步
- 稀疏观测
- 适合 hash / candidate / local collapse 任务

也就是：

> **把“求解器”与“仪器”分开。**

当前代码的问题，是把两者混成了一条链。

---

# 10. 最短总结

Claude 在整改 IQPU / QCU 当前 RK4 路径时，必须记住：

> **当前慢，不是因为 QCU 理论无效，而是因为高保真物理模拟、重读出、频繁同步和快搜任务被绑在了一起。**

所以正确的整改方向是：

- 清理 solver 热路径
- 减少 readout 同步
- 参数化 dtype
- 把 runtime 拆成 full / fast 双 profile
- 让 GPU 尽可能连续推进，而不是每几步就被 Python 拉回来做人类可读观测

如果压成一句最核心的话：

> **先把 GPU 从“不断被观察的实验对象”变回“持续推进的数值引擎”。**
