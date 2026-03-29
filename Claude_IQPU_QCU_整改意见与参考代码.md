# Claude 整改意见与参考代码
## IQPU / QCU Runtime、Lindblad Solver、Readout 性能整改说明

**版本**：v1.0  
**作者**：430  
**对象**：Claude / 协作代码代理  
**用途**：指导对当前 `iqpu_runtime.py`、`lindblad_solver.py`、`readout.py` 的性能整改，目标是解决 **IQPU 的 Lindblad RK4 GPU 路径 25 秒过慢** 的问题。  
**重点**：这是对**现有核心算法实现**的定向整改说明，不是理论重写。

---

# 0. 问题背景

当前现象是：

- IQPU / QCU 的 **Lindblad + RK4 演化** 在 GPU 上跑一轮约 **25 秒**
- 而传统直接验证 `abc123` 这类目标只需约 **6 秒**

这不意味着 QCU 理论无效，而意味着：

> **当前实现仍然是“高保真开放量子动力学模拟优先”，没有切出真正的“快搜模式”。**

此外，当前代码同时存在：

- solver 热路径有多余 Python 开销
- readout 高频同步 GPU → CPU
- 默认观测过密
- 纠缠观测过重
- dtype 配置不够激进
- runtime / solver / readout 之间没有明确的轻重模式分离

---

# 1. 结论总览

当前瓶颈不在单一点，而在三层叠加：

## 1.1 Solver 层：算得重
`lindblad_solver.py` 当前做的是：

- 密度矩阵
- Lindblad 开放系统
- RK4 四次 RHS
- 反复矩阵乘法
- 归一化与厄米修正

这本来就远重于“直接验证一个候选字符串”。

## 1.2 Readout 层：同步重
`readout.py` 当前做的是：

- 高频 `expect(...)`
- 动态 backend 判断
- 大量 `float(...) / np.real(...) / np.angle(...)`
- 可选 negativity 计算

这会频繁打断 GPU 流水，造成 device-host 同步热点。

## 1.3 Runtime 层：调度过密
`iqpu_runtime.py` 当前在：

- 观测频率
- 快照逻辑
- 纠缠监控
- 日志收集

上偏向“高保真实验模式”，而不是“快搜任务模式”。

---

# 2. Claude 的整改目标

Claude 需要做的不是“随便加速一下”，而是把整个执行链正式拆成两种 profile：

## A. Full Physics Mode（高保真模式）
用于：
- 论文图
- 物理解释
- 完整 Lindblad 验证
- gate window / negativity / 全日志监控

### 特征
- `complex128`
- `track_entanglement=True`
- `obs_every` 较密
- 保留完整 readout
- 完整状态验收

## B. Fast Search Mode（快搜模式）
用于：
- 候选结构搜索
- abc123 类任务
- Hash / prefix-zero / reverse search 预筛
- 局部峰值显形

### 特征
- `complex64`
- `track_entanglement=False`
- `negativity_every=0`
- `obs_every` 稀疏
- 只保留最小必要观测量
- 减少 GPU → CPU 同步

> **整改完成标准不是“代码更优雅”，而是“快搜模式明显比原版快，且不破坏高保真模式”。**

---

# 3. 针对 `lindblad_solver.py` 的整改意见

---

## 3.1 把 backend 判定外提

### 当前问题
`lindblad_rhs()` 内部做 backend 识别，例如：

```python
try:
    import cupy
    xp = cupy.get_array_module(rho)
except ImportError:
    xp = np
```

这会在热路径中反复执行。

### 整改要求
- 不允许在 `lindblad_rhs()` 内部做 backend 动态判断
- `xp` 必须在 solver 初始化时确定
- `lindblad_rhs(xp, rho, H, ...)` 显式传入 backend

### 参考代码

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

## 3.2 把 dtype 做成配置项

### 当前问题
`alloc_rk4_buffers()` 固定 `complex128`，GPU 上代价太高。

### 整改要求
- 增加 `dtype` 参数
- `fast_search` 默认允许 `complex64`
- `full_physics` 保留 `complex128`

### 参考代码

```python
def alloc_rk4_buffers(DIM, xp, dtype):
    z = lambda: xp.zeros((DIM, DIM), dtype=dtype)
    return z(), z(), z(), z(), z(), z(), z(), z()
```

---

## 3.3 函数内 import 必须移到模块级

### 当前问题
`rk4_step()` 内部 import `enforce_density_matrix`

### 整改要求
- 所有热路径函数不得在函数体内 import
- 模块顶层统一 import / 绑定

---

## 3.4 初态构建支持 backend 原生创建

### 当前问题
当前路径类似：

```python
rho = xp.asarray(build_initial_state(...))
```

这意味着先 CPU 构建，再搬到 GPU。

### 整改要求
- `build_initial_state()` 支持传入 `xp`
- 初态直接在目标 backend 上构建

---

# 4. 针对 `readout.py` 的整改意见

---

## 4.1 `expect()` 不能动态判断 backend

### 当前问题
每个 `expect()` 都做 backend 判定，且在高频观测里会被反复调用。

### 整改要求
- `expect(xp, rho, op)` 显式接收 backend
- 不允许在 `expect()` 内部 import cupy / get_array_module

### 参考代码

```python
def expect(xp, rho, op):
    return xp.trace(rho @ op)
```

---

## 4.2 快照函数必须拆成轻重两版

### 整改要求
新增两个函数：

- `compute_step_snapshot_fast(...)`
- `compute_step_snapshot_full(...)`

### fast 版只做
- `a_vals`
- `C`
- `rel_phase`

### full 版才做
- negativity
- 全部 `n_vals`
- 全部 `sz_vals`
- 完整 dataclass 封装

### 参考代码

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
`track_entanglement=True` 时，negativity 很可能每个观测点都算一次。

### 整改要求
- 增加 `negativity_every`
- 快搜模式默认 `0`
- 高保真模式默认 `>= 8` 或更稀疏

### 参考代码

```python
if cfg.track_entanglement and cfg.negativity_every > 0 and (i % cfg.negativity_every) == 0:
    neg = negativity_qubit0_vs_rest(xp, rho)
else:
    neg = None
```

---

## 4.4 延迟标量化

### 当前问题
当前 `float(...)`、`np.real(...)`、`np.angle(...)` 太早发生，会触发同步。

### 整改要求
- 在 GPU 上尽量保持张量态
- 只在必要时转 host
- 允许批量回传再统一整理

---

# 5. 针对 `iqpu_runtime.py` 的整改意见

---

## 5.1 引入 profile 概念

### 整改要求
至少支持：

- `mode="full_physics"`
- `mode="fast_search"`

### 参考代码

```python
@dataclass
class IQPUFastProfile:
    obs_every: int = 8
    negativity_every: int = 0
    track_entanglement: bool = False
    dtype: str = "complex64"
    backend: str = "cupy"
```

并允许：

```python
cfg = apply_fast_profile(cfg)
```

---

## 5.2 观测频率必须降下来

### 当前问题
`obs_every=1` 时，每步都 snapshot，会严重打断 GPU。

### 整改要求
- `fast_search` 默认 `obs_every >= 8`
- 对 Hash / abc123 类任务，可进一步放宽到 `16` 或 `32`

---

## 5.3 Runtime 必须控制 readout 路径

### 整改要求
在主循环里，根据 mode 选择：

- `compute_step_snapshot_fast`
- `compute_step_snapshot_full`

### 参考代码

```python
if mode == "fast_search":
    snap = compute_step_snapshot_fast(...)
else:
    snap = compute_step_snapshot_full(...)
```

---

## 5.4 最终观测和过程观测分离

### 当前问题
过程里已经在不断做读出，末态又会重复算一次完整 observables。

### 整改要求
- 过程观测：最小必要集
- 最终观测：完整集
- 不要在每个 step 同时做两套

---

# 6. 建议新增的文件结构

```text
qcu/
├─ core/
│  ├─ iqpu_runtime.py
│  ├─ lindblad_solver.py
│  └─ profiles.py
├─ readout/
│  ├─ readout_fast.py
│  ├─ readout_full.py
│  └─ metrics.py
├─ benchmarks/
│  ├─ perf_compare.py
│  └─ deutsch_benchmark.py
└─ labs/
```

---

# 7. 建议新增的 benchmark

Claude 重构完成后，必须补至少这四类对照：

## 7.1 原版 vs 优化版
- 原版 runtime + solver
- 优化版 runtime + solver

## 7.2 NumPy vs CuPy
- numpy / complex128
- cupy / complex128
- cupy / complex64

## 7.3 full_physics vs fast_search
- 同一任务，比较总时长、末态误差、结构显影差异

## 7.4 高频观测 vs 稀疏观测
- `obs_every=1`
- `obs_every=8`
- `obs_every=16`

---

# 8. Claude 输出结果时必须包含

每次整改后，输出必须带上：

1. **改了哪些热路径**
2. **哪些 backend 判定被外提**
3. **dtype 是否已参数化**
4. **fast/full 两种 mode 是否已分离**
5. **readout 是否已拆成轻重两版**
6. **benchmark 结果**
7. **是否保持与原理论语义一致**

推荐模板：

```text
本次整改完成：
- lindblad_rhs 改为显式传入 xp
- alloc_rk4_buffers 支持 complex64/complex128
- readout 拆为 fast/full 两版
- runtime 新增 fast_search profile
- negativity 改为稀疏采样

benchmark：
- 原版 cupy: 25.1s
- 优化 full_physics: 18.4s
- 优化 fast_search: 7.2s

说明：
- 理论语义未改，仍为 Lindblad + RK4 主干
- 仅将观测/同步/数据类型策略做 profile 化
```

---

# 9. 最短总结

Claude 在整改这套 IQPU / QCU 核心算法时，必须记住：

> **当前问题不是“QCU 理论没用”，而是“高保真物理模拟路径和任务快搜路径没有分开”。**

所以整改的正确方向不是推翻现有 solver，而是：

- 清理热路径
- 减少同步
- 参数化 dtype
- 把 readout 轻重分离
- 把 runtime 做成 full / fast 双 profile

如果把整件事压成一句最核心的话：

> **先把 GPU 从“不断被读出来的人类观察对象”变回“连续推进的数值引擎”。**
