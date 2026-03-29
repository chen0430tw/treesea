# benchmarks/perf_compare.py
"""
IQPU benchmark：按 Section 7 要求对照
- full_physics vs fast_search
- obs_every=1 / 8 / 16
- numpy / complex128 vs complex64
"""

import sys, time
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import numpy as np
from qcu.core.state_repr import IQPUConfig
from qcu.core.iqpu_runtime import IQPU

_COMMON = dict(
    t1=3.0, t2=5.0, omega_x=1.0,
    gamma_pcm=0.2, gamma_qim=0.03,
    gamma_boost=0.9, boost_duration=3.0,
    gamma_reset=0.25, gamma_phi0=0.6,
    eps_boost=4.0, boost_phase_trim=0.012,
)

def run_once(label, **cfg_kwargs):
    cfg = IQPUConfig(Nq=2, Nm=2, d=6, **cfg_kwargs).finalize()
    iqpu = IQPU(cfg)
    t0 = time.time()
    r = iqpu.run_qcl_v6(label, **_COMMON)
    elapsed = time.time() - t0
    print(f"  {label:<40} {elapsed:6.2f}s   C_end={r.C_end:.4f}")
    return elapsed

print("=" * 65)
print("【7.3】full_physics vs fast_search  (cpu)")
print("=" * 65)
run_once("full_physics  cpu/complex128  obs=1",
         profile="full_physics", obs_every=1,
         track_entanglement=False, device="cpu")
run_once("fast_search   cpu/complex64   obs=8",
         profile="fast_search", device="cpu")

print()
print("=" * 65)
print("【7.4】高频观测 vs 稀疏观测  (cpu / complex128)")
print("=" * 65)
run_once("full_physics  obs_every=1",
         profile="full_physics", obs_every=1,
         track_entanglement=False, device="cpu")
run_once("full_physics  obs_every=8",
         profile="full_physics", obs_every=8,
         track_entanglement=False, device="cpu")
run_once("full_physics  obs_every=16",
         profile="full_physics", obs_every=16,
         track_entanglement=False, device="cpu")

try:
    import cupy  # noqa
    print()
    print("=" * 65)
    print("【7.2】numpy vs cupy")
    print("=" * 65)
    run_once("numpy  complex128  obs=1",
             profile="full_physics", obs_every=1,
             track_entanglement=False, device="cpu")
    run_once("cupy   complex128  obs=1",
             profile="full_physics", obs_every=1,
             track_entanglement=False, device="cuda")
    run_once("cupy   complex64   obs=8  (fast_search)",
             profile="fast_search", device="cuda")
except ImportError:
    print("\n  cupy 未安装，跳过 7.2")

print()
print("benchmark 完成")
