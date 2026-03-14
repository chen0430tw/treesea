"""
QCU GPU Benchmark
CPU vs GPU (CuPy) speedup across different Hilbert space dimensions.
"""

import time
import numpy as np

try:
    import cupy as cp
    HAS_CUPY = True
except ImportError:
    HAS_CUPY = False

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[2]))

from qcu.qcu.core.state_repr import IQPUConfig
from qcu.qcu.core.iqpu_runtime import IQPU


def bench_one(d: int, device: str, steps: int = 200) -> float:
    cfg = IQPUConfig(Nq=1, Nm=2, d=d, dt=0.05, t_max=steps * 0.05, device=device,
                     track_entanglement=False, obs_every=50)
    iqpu = IQPU(cfg)
    result = iqpu.run_qcl_v6(
        label="bench",
        t1=2.0, t2=5.0,
        omega_x=1.0,
        gamma_pcm=0.2, gamma_qim=0.03,
        gamma_boost=0.9, boost_duration=3.0,
        gamma_reset=0.25, gamma_phi0=0.6,
        eps_boost=4.0, boost_phase_trim=0.012,
    )
    return result.elapsed_sec


print("=" * 55)
print("QCU GPU Benchmark")
if HAS_CUPY:
    print(f"CuPy version : {cp.__version__}")
    try:
        print(f"GPU          : {cp.cuda.runtime.getDeviceProperties(0)['name'].decode()}")
    except Exception:
        import subprocess
        r = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                           capture_output=True, text=True)
        print(f"GPU          : {r.stdout.strip()}")
else:
    print("CuPy not available — CPU only")
print("=" * 55)
print(f"{'d':>4}  {'DIM':>5}  {'CPU(s)':>8}  {'GPU(s)':>8}  {'Speedup':>8}")
print("-" * 55)

for d in [4, 6, 8, 10, 12]:
    Nq, Nm = 1, 2
    DIM = (2 ** Nq) * (d ** Nm)

    # warmup
    bench_one(d, "cpu", steps=20)
    t_cpu = bench_one(d, "cpu", steps=300)

    if HAS_CUPY:
        bench_one(d, "cuda", steps=20)
        t_gpu = bench_one(d, "cuda", steps=300)
        speedup = t_cpu / t_gpu
        print(f"{d:>4}  {DIM:>5}  {t_cpu:>8.3f}  {t_gpu:>8.3f}  {speedup:>7.2f}x")
    else:
        print(f"{d:>4}  {DIM:>5}  {t_cpu:>8.3f}  {'N/A':>8}  {'N/A':>8}")

print("=" * 55)
