"""
QCU CPU Parallel Benchmark
Tests multi-core scaling via Python multiprocessing (embarrassingly parallel sweep).
Also tests NumPy BLAS thread scaling via OMP_NUM_THREADS.
"""

import os
import time
import sys
import multiprocessing as mp

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[2]))

from qcu.qcu.core.state_repr import IQPUConfig
from qcu.qcu.core.iqpu_runtime import IQPU


def run_one(args):
    d, steps, idx = args
    cfg = IQPUConfig(Nq=1, Nm=2, d=d, dt=0.05, t_max=steps * 0.05,
                     device="cpu", track_entanglement=False, obs_every=steps)
    iqpu = IQPU(cfg)
    result = iqpu.run_qcl_v6(
        label=f"sweep_{idx}",
        t1=2.0 + idx * 0.1, t2=5.0,
        omega_x=1.0,
        gamma_pcm=0.2, gamma_qim=0.03,
        gamma_boost=0.9, boost_duration=3.0,
        gamma_reset=0.25, gamma_phi0=0.6,
        eps_boost=4.0, boost_phase_trim=0.012,
    )
    return result.elapsed_sec


def bench_parallel(d: int, n_tasks: int, n_workers: int, steps: int = 100) -> float:
    args = [(d, steps, i) for i in range(n_tasks)]
    t0 = time.perf_counter()
    if n_workers == 1:
        for a in args:
            run_one(a)
    else:
        with mp.Pool(n_workers) as pool:
            pool.map(run_one, args)
    return time.perf_counter() - t0


print("=" * 60)
print("QCU CPU Parallel Benchmark")
print(f"CPUs available : {mp.cpu_count()}")
print(f"OMP_NUM_THREADS: {os.environ.get('OMP_NUM_THREADS', 'default')}")
print("=" * 60)

# --- Part 1: BLAS thread scaling (single task, vary OMP via env hint) ---
print("\n[1] Single-task timing across d (serial baseline)")
print(f"{'d':>4}  {'DIM':>5}  {'time(s)':>9}")
print("-" * 30)
for d in [4, 6, 8, 10, 12]:
    DIM = 4 * (d ** 2)
    t = run_one((d, 200, 0))
    print(f"{d:>4}  {DIM:>5}  {t:>9.3f}")

# --- Part 2: Multi-process sweep scaling ---
d_test = 10
n_tasks = 32
print(f"\n[2] Parallel sweep scaling (d={d_test}, {n_tasks} tasks)")
print(f"{'Workers':>8}  {'Wall(s)':>8}  {'Speedup':>8}  {'Efficiency':>10}")
print("-" * 45)

t_serial = bench_parallel(d_test, n_tasks, n_workers=1, steps=80)
print(f"{'1':>8}  {t_serial:>8.2f}  {'1.00x':>8}  {'100%':>10}")

for nw in [2, 4, 8, 16, 32]:
    if nw > mp.cpu_count():
        break
    t = bench_parallel(d_test, n_tasks, n_workers=nw, steps=80)
    speedup = t_serial / t
    eff = speedup / nw * 100
    print(f"{nw:>8}  {t:>8.2f}  {speedup:>7.2f}x  {eff:>9.1f}%")

print("=" * 60)
