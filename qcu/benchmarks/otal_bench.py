# benchmarks/otal_bench.py
"""
OTAL 三组 benchmark（Section 12）

12.1  RK4-only  vs  OTAL + RK4
12.2  OTAL-only 快搜效果
12.3  稀疏图 vs 稠密图

用法：
    cd D:/treesea/qcu
    py -3.13 benchmarks/otal_bench.py
"""

from __future__ import annotations

import sys
import time
import random
import string
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from qcu.core.state_repr import IQPUConfig
from qcu.core.iqpu_runtime import IQPU
from qcu.otal.runner import OTALRunner, OTALConfig


# ── 公共参数 ──────────────────────────────────────────────────────────

RK4_PARAMS = dict(
    t1=3.0, t2=5.0, omega_x=1.0,
    gamma_pcm=0.2, gamma_qim=0.03,
    gamma_boost=0.9, boost_duration=3.0,
    gamma_reset=0.25, gamma_phi0=0.6,
    eps_boost=4.0, boost_phase_trim=0.012,
)

def make_cfg(profile="fast_search"):
    cfg = IQPUConfig(Nq=2, Nm=2, d=6)
    cfg.profile = profile
    return cfg.finalize()

def make_candidates(n: int) -> list:
    rng = random.Random(42)
    return [
        "".join(rng.choices(string.ascii_lowercase + string.digits, k=6))
        for _ in range(n)
    ]

def run_iqpu_batch(labels: list, profile="fast_search") -> float:
    """对所有候选跑一遍 IQPU，返回总耗时（秒）。"""
    cfg  = make_cfg(profile)
    iqpu = IQPU(cfg)
    t0   = time.perf_counter()
    for label in labels:
        iqpu.run_qcl_v6(label=label, **RK4_PARAMS)
    return time.perf_counter() - t0


# ── 12.1  RK4-only vs OTAL + RK4 ─────────────────────────────────────

def bench_12_1(n_candidates: int = 20):
    print(f"\n{'='*60}")
    print(f"12.1  RK4-only vs OTAL + RK4   (N={n_candidates})")
    print("="*60)

    labels = make_candidates(n_candidates)

    # ── RK4-only ──
    t_rk4 = run_iqpu_batch(labels, profile="fast_search")
    print(f"  RK4-only 全量          : {t_rk4:.3f} s  ({n_candidates} 候选)")

    # ── OTAL 预筛 ──
    runner = OTALRunner(n_steps=20, theta_c=1.2, top_k=5, full_physics_ratio=0.2, seed=0)
    run    = runner.prefilter(labels)

    fp_labels = [c["candidate_id"] for c in run.otal_result.full_physics_queue]
    n_fp      = len(fp_labels)

    t_fp = run_iqpu_batch(fp_labels, profile="fast_search") if fp_labels else 0.0
    t_total = run.prefilter_time_s + t_fp

    print(f"  OTAL 预筛              : {run.prefilter_time_s*1000:.1f} ms")
    print(f"  full_physics 候选数    : {n_fp}")
    print(f"  IQPU (full_physics)   : {t_fp:.3f} s")
    print(f"  OTAL + RK4 合计        : {t_total:.3f} s")
    print(f"  加速比                 : {t_rk4/t_total:.1f}×")
    print(f"  筛除率                 : {(1 - n_fp/n_candidates)*100:.0f}%")


# ── 12.2  OTAL-only 快搜效果 ──────────────────────────────────────────

def bench_12_2(n_candidates: int = 50):
    print(f"\n{'='*60}")
    print(f"12.2  OTAL-only 快搜效果   (N={n_candidates})")
    print("="*60)

    labels = make_candidates(n_candidates)
    runner = OTALRunner(n_steps=30, theta_c=1.0, top_k=5, full_physics_ratio=0.1, seed=1)
    run    = runner.prefilter(labels)

    state = run.state

    # 相位集中度（全图 Kuramoto 序参量）
    from qcu.otal.oscillatory_direction import local_phase_concentration
    all_dirs  = [n.direction for n in state.nodes]
    R_global  = local_phase_concentration(all_dirs)

    # collapse 热点
    collapse  = run.otal_result.collapse_queue
    fp        = run.otal_result.full_physics_queue

    top_scores = sorted([n.local_score for n in state.nodes], reverse=True)[:5]

    print(f"  OTAL 耗时              : {run.prefilter_time_s*1000:.1f} ms")
    print(f"  全局相位集中度 (R)     : {R_global:.4f}  (1=完全同相, 0=均匀)")
    print(f"  坍缩候选数 (θ≥Θ_c)    : {len(collapse)}")
    print(f"  full_physics 候选数    : {len(fp)}")
    print(f"  Top-5 成熟度分         : {[f'{s:.3f}' for s in top_scores]}")

    if collapse:
        print(f"  最高坍缩候选:")
        for c in collapse[:3]:
            print(f"    [{c['candidate_id']}] score={c['local_score']:.3f} "
                  f"phase={c['phase']:.3f}rad")


# ── 12.3  稀疏图 vs 稠密图 ───────────────────────────────────────────

def bench_12_3(n_candidates: int = 30):
    print(f"\n{'='*60}")
    print(f"12.3  稀疏图 vs 稠密图   (N={n_candidates})")
    print("="*60)

    labels = make_candidates(n_candidates)

    configs = [
        ("稀疏 (edges=2)",  OTALConfig(n_steps=20, n_edges=2,  theta_c=1.2, seed=2)),
        ("中等 (edges=5)",  OTALConfig(n_steps=20, n_edges=5,  theta_c=1.2, seed=2)),
        ("稠密 (edges=12)", OTALConfig(n_steps=20, n_edges=12, theta_c=1.2, seed=2)),
    ]

    for label, cfg in configs:
        runner = OTALRunner(cfg=cfg)
        run    = runner.prefilter(labels)

        from qcu.otal.oscillatory_direction import local_phase_concentration
        all_dirs = [n.direction for n in run.state.nodes]
        R        = local_phase_concentration(all_dirs)

        top3 = sorted([n.local_score for n in run.state.nodes], reverse=True)[:3]

        print(f"  [{label}]")
        print(f"    OTAL 耗时      : {run.prefilter_time_s*1000:.1f} ms")
        print(f"    全局 R         : {R:.4f}")
        print(f"    坍缩候选数     : {run.n_collapse}")
        print(f"    Top-3 成熟度   : {[f'{s:.3f}' for s in top3]}")


# ── 主函数 ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("OTAL Benchmark Suite")
    print(f"运行环境：Python {sys.version.split()[0]}")

    bench_12_1(n_candidates=20)
    bench_12_2(n_candidates=50)
    bench_12_3(n_candidates=30)

    print(f"\n{'='*60}")
    print("全部 benchmark 完成")
    print("="*60)
