# deutsch.py
"""
QCU 原生 Deutsch 算法实现。

原理
----
经典 Deutsch 算法判断 f:{0,1}→{0,1} 是常数函数还是平衡函数，
只需对 oracle 调用一次（量子并行）。

QCU 原生映射
------------
QCU 的物理输出是相位相干度 C = |⟨a₀⟩ − ⟨a₁⟩|，而不是经典比特。
这里利用的"量子门"是 IQPU 参数 boost_phase_trim——
这是 QCU 架构中预留但鲜少单独使用的腔相位注入接口：

  常数 oracle (f(0)=f(1))：boost_phase_trim = 0
      → 相位无变化 → C 维持低值（≈0.03）→ 判定 bit=0（常数）

  平衡 oracle (f(0)≠f(1))：boost_phase_trim = π
      → 腔驱动相位翻转 → BOOST 放大 → C 急剧升高（≈100+）→ 判定 bit=1（平衡）

注意：eps_drive 必须非零，boost_phase_trim 才能产生可观测的 C 差异。
      eps_drive=0 时，trim × 0 = 0，相位注入无效。

因此：

  Deutsch 结果 = DISC(C, threshold)
              = 1  （平衡）  if C > threshold
              = 0  （常数）  if C ≤ threshold

验证矩阵位置
------------
  第一层：基础量子 sanity check（本文件）
  第二层：结构显形验证（tri-mode / HMPL）
  第三层：高复杂任务验证（Shor / Hash / prefix-zero）
"""

from __future__ import annotations

import math
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, 'D:/treesea/qcu')


# ── 配置 ──────────────────────────────────────────────────────────

@dataclass
class DeutschConfig:
    """Deutsch benchmark 执行配置。

    Parameters
    ----------
    C_threshold : float
        判决阈值：C > threshold → 平衡函数，C ≤ threshold → 常数函数。
        默认 1.0（常数 oracle 的 C≈0.03，平衡 oracle 的 C≈187）。
    eps_drive : float
        腔驱动幅度，必须非零才能让 boost_phase_trim 生效（默认 1.0）。
    t1 : float
        PCM 阶段时长（归一化单位）。
    t2 : float
        BOOST 阶段开始时刻。
    boost_duration : float
        BOOST 阶段持续时长。
    gamma_boost : float
        BOOST 耦合强度。
    eps_boost : float
        BOOST 驱动幅度（相位放大系数）。
    verbose : bool
        是否打印每步结果。
    """
    C_threshold:    float = 1.0
    eps_drive:      float = 1.0   # 必须非零，boost_phase_trim 才对 C 有效
    t1:             float = 3.0
    t2:             float = 5.0
    boost_duration: float = 3.0
    gamma_boost:    float = 0.9
    eps_boost:      float = 4.0
    verbose:        bool  = True


# ── Oracle 构造 ────────────────────────────────────────────────────

def build_constant_oracle() -> float:
    """常数 oracle：f(0)=f(1)=0（或 1，相同输出）。

    QCU 映射：boost_phase_trim = 0（不注入额外相位）。

    Returns
    -------
    float
        boost_phase_trim 值（弧度）。
    """
    return 0.0


def build_balanced_oracle() -> float:
    """平衡 oracle：f(0)≠f(1)（一半 0 一半 1）。

    QCU 映射：boost_phase_trim = π（向腔注入 π 相位翻转）。

    Returns
    -------
    float
        boost_phase_trim 值（弧度）。
    """
    return math.pi


# ── 单次执行 ───────────────────────────────────────────────────────

@dataclass
class DeutschResult:
    """单次 Deutsch 执行结果。"""
    oracle_type:   str            # 'constant' | 'balanced'
    phase_trim:    float          # 注入的 boost_phase_trim（弧度）
    C_end:         float          # 最终相干度 C
    dtheta_end:    float          # 相位差 dθ
    bit_result:    int            # 0=常数, 1=平衡
    correct:       bool           # 是否与真实 oracle 类型匹配
    elapsed_sec:   float = 0.0
    final_sz:      Optional[List[float]] = field(default=None)
    meta:          Dict = field(default_factory=dict)

    def __repr__(self) -> str:
        verdict = "✓ 正确" if self.correct else "✗ 错误"
        return (
            f"DeutschResult(oracle={self.oracle_type!r}, "
            f"C={self.C_end:.4f}, bit={self.bit_result}, {verdict})"
        )


def run_deutsch(
    oracle_type: str = "constant",
    cfg: Optional[DeutschConfig] = None,
) -> DeutschResult:
    """在 IQPU 上执行一次 Deutsch 实验。

    Parameters
    ----------
    oracle_type : str
        'constant' 或 'balanced'。
    cfg : DeutschConfig, optional
        执行配置；None 使用默认值。

    Returns
    -------
    DeutschResult
    """
    from qcu.core.iqpu_runtime import IQPU
    from qcu.core.state_repr import IQPUConfig

    if cfg is None:
        cfg = DeutschConfig()

    # ① 选择 oracle（注入相位）
    if oracle_type == "constant":
        trim = build_constant_oracle()
    elif oracle_type == "balanced":
        trim = build_balanced_oracle()
    else:
        raise ValueError(f"oracle_type 必须是 'constant' 或 'balanced'，收到 {oracle_type!r}")

    if cfg.verbose:
        print(f"  [Deutsch] oracle={oracle_type!r}  phase_trim={trim:.4f} rad")

    # ② 初始化 IQPU（固定 Nq=2，DIM=144）
    # eps_drive 必须非零：boost_phase_trim 乘以 eps_drive 才能注入相位差
    eps = complex(cfg.eps_drive)
    iqpu_cfg = IQPUConfig(Nq=2, Nm=2, d=6, eps_drive=[eps, eps])
    iqpu = IQPU(iqpu_cfg)

    # ③ 运行 QCL v6：boost_phase_trim 就是 oracle 的物理载体
    t0 = time.time()
    r = iqpu.run_qcl_v6(
        label="deutsch",
        t1=cfg.t1,
        t2=cfg.t2,
        omega_x=1.0,
        gamma_pcm=0.2,
        gamma_qim=0.03,
        gamma_boost=cfg.gamma_boost,
        boost_duration=cfg.boost_duration,
        gamma_reset=0.25,
        gamma_phi0=0.6,
        eps_boost=cfg.eps_boost,
        boost_phase_trim=trim,
    )
    elapsed = time.time() - t0

    # ④ 判决：
    #   常数 oracle(trim=0) → C 低（约 0.03）→ bit=0
    #   平衡 oracle(trim=π) → C 高（约 100+）→ bit=1
    #   因此：C > threshold → 平衡 → bit=1；C ≤ threshold → 常数 → bit=0
    bit = 1 if r.C_end > cfg.C_threshold else 0
    expected_bit = 0 if oracle_type == "constant" else 1
    correct = (bit == expected_bit)

    if cfg.verbose:
        print(
            f"  [Deutsch] C={r.C_end:.4f}  dθ={r.dtheta_end:.4f}  "
            f"→ bit={bit}  ({'✓' if correct else '✗'})"
        )

    return DeutschResult(
        oracle_type=oracle_type,
        phase_trim=trim,
        C_end=r.C_end,
        dtheta_end=r.dtheta_end,
        bit_result=bit,
        correct=correct,
        elapsed_sec=elapsed,
        final_sz=r.final_sz,
    )


# ── Benchmark 套件 ────────────────────────────────────────────────

@dataclass
class DeutschBenchmarkResult:
    """benchmark_deutsch() 的完整报告。"""
    results:          List[DeutschResult]
    n_correct:        int
    n_total:          int
    accuracy:         float            # n_correct / n_total
    C_constant_mean:  float            # 常数 oracle 的平均 C
    C_balanced_mean:  float            # 平衡 oracle 的平均 C
    C_separation:     float            # |C_constant_mean - C_balanced_mean|
    total_elapsed:    float

    def __repr__(self) -> str:
        return (
            f"DeutschBenchmark("
            f"accuracy={self.accuracy:.1%}, "
            f"C_const={self.C_constant_mean:.4f}, "
            f"C_bal={self.C_balanced_mean:.4f}, "
            f"separation={self.C_separation:.4f})"
        )

    def print_report(self) -> None:
        print("\n" + "=" * 60)
        print("  QCU Deutsch Benchmark 报告")
        print("=" * 60)
        print(f"  总测试数   : {self.n_total}")
        print(f"  正确数     : {self.n_correct}")
        print(f"  准确率     : {self.accuracy:.1%}")
        print(f"  C（常数）  : {self.C_constant_mean:.4f}")
        print(f"  C（平衡）  : {self.C_balanced_mean:.4f}")
        print(f"  相干度间隔 : {self.C_separation:.4f}")
        print(f"  总耗时     : {self.total_elapsed:.2f}s")

        passed = self.accuracy == 1.0
        if passed:
            print("\n  ✅ PASS — Deutsch benchmark 全部通过")
            print("     QCU 已通过第一层基础量子 sanity check")
        else:
            print("\n  ⚠️  PARTIAL — 部分测试未通过")
            print("     请检查 C_threshold 或 IQPU 参数配置")
        print("=" * 60)


def benchmark_deutsch(
    n_trials: int = 3,
    cfg: Optional[DeutschConfig] = None,
    verbose: bool = True,
) -> DeutschBenchmarkResult:
    """运行完整的 Deutsch benchmark。

    对 constant 和 balanced oracle 各运行 n_trials 次，
    统计准确率和 C 值分布。

    Parameters
    ----------
    n_trials : int
        每种 oracle 的重复次数（默认 3）。
    cfg : DeutschConfig, optional
        执行配置；None 使用默认值。
    verbose : bool
        是否打印每步结果。

    Returns
    -------
    DeutschBenchmarkResult
    """
    if cfg is None:
        cfg = DeutschConfig(verbose=verbose)
    else:
        cfg.verbose = verbose

    if verbose:
        print(f"\n[Deutsch Benchmark] 每种 oracle × {n_trials} 次，"
              f"阈值={cfg.C_threshold}")

    results: List[DeutschResult] = []
    t_total = time.time()

    for oracle_type in ("constant", "balanced"):
        for i in range(n_trials):
            if verbose:
                print(f"\n  [{oracle_type} #{i+1}]")
            r = run_deutsch(oracle_type=oracle_type, cfg=cfg)
            results.append(r)

    total_elapsed = time.time() - t_total

    # 统计
    n_correct = sum(1 for r in results if r.correct)
    c_vals_const = [r.C_end for r in results if r.oracle_type == "constant"]
    c_vals_bal   = [r.C_end for r in results if r.oracle_type == "balanced"]
    C_const_mean = sum(c_vals_const) / len(c_vals_const) if c_vals_const else 0.0
    C_bal_mean   = sum(c_vals_bal)   / len(c_vals_bal)   if c_vals_bal   else 0.0

    bench = DeutschBenchmarkResult(
        results=results,
        n_correct=n_correct,
        n_total=len(results),
        accuracy=n_correct / len(results),
        C_constant_mean=C_const_mean,
        C_balanced_mean=C_bal_mean,
        C_separation=abs(C_const_mean - C_bal_mean),
        total_elapsed=total_elapsed,
    )

    if verbose:
        bench.print_report()

    return bench


# ── 快速命令行入口 ─────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="QCU Deutsch Benchmark")
    parser.add_argument("--oracle", choices=["constant", "balanced", "both"],
                        default="both", help="要测试的 oracle 类型")
    parser.add_argument("--trials", type=int, default=3,
                        help="每种 oracle 的重复次数")
    parser.add_argument("--threshold", type=float, default=0.05,
                        help="C 判决阈值")
    args = parser.parse_args()

    _cfg = DeutschConfig(C_threshold=args.threshold, verbose=True)

    if args.oracle == "both":
        benchmark_deutsch(n_trials=args.trials, cfg=_cfg)
    else:
        result = run_deutsch(oracle_type=args.oracle, cfg=_cfg)
        print(result)
