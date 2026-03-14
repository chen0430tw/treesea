#!/bin/bash
#SBATCH --job-name=td_bench
#SBATCH --partition=gtest
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=32
#SBATCH --gpus-per-node=8
#SBATCH --time=00:20:00
#SBATCH --output=/work/twsuday816/td_bench_%j.out
#SBATCH --error=/work/twsuday816/td_bench_%j.err
#SBATCH --account=ENT114035

module load miniconda3/conda24.5.0_py3.9

export PYTHONPATH=/work/twsuday816/treesea
cd /work/twsuday816/treesea

echo "=== Node: $(hostname) | CPUs: $(nproc) ==="
echo "=== Tree Diagram Benchmark ==="

python3 - << 'PYEOF'
import sys, time
sys.path.insert(0, '.')
from tree_diagram.tree_diagram.runtime.runner import TreeDiagramRunner
from tree_diagram.tree_diagram.numerics.forcing import GridConfig

print("\n[1] Candidate mode (single run)")
t0 = time.perf_counter()
r = TreeDiagramRunner(mode='candidate', top_k=12)
b = r.run()
t1 = time.perf_counter() - t0
print(f"  time: {t1:.3f}s | best: {b.best_worldline['family']} | hist: {b.branch_histogram}")

print("\n[2] Candidate mode parallel sweep (32 workers, 10 seeds)")
import multiprocessing as mp
from tree_diagram.tree_diagram.core.problem_seed import default_seed
from tree_diagram.tree_diagram.pipeline.candidate_pipeline import CandidatePipeline

def run_seed(i):
    import sys; sys.path.insert(0, '.')
    from tree_diagram.tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
    from tree_diagram.tree_diagram.core.problem_seed import default_seed
    seed = default_seed()
    seed.subject['output_power'] = 0.6 + i * 0.03
    p = CandidatePipeline(seed=seed, top_k=12)
    top, hydro, oracle = p.run()
    return oracle['best_worldline']['balanced_score']

for nw in [1, 8, 32]:
    t0 = time.perf_counter()
    if nw == 1:
        results = [run_seed(i) for i in range(10)]
    else:
        with mp.Pool(nw) as pool:
            results = pool.map(run_seed, range(10))
    elapsed = time.perf_counter() - t0
    print(f"  {nw:2d} workers: {elapsed:.3f}s | scores={[round(s,3) for s in results[:3]]}...")

print("\n[3] Integrated mode (Stage1 + Stage2, n_workers=8)")
t0 = time.perf_counter()
cfg = GridConfig(NX=112, NY=84, STEPS=120)  # half steps for benchmark
r3 = TreeDiagramRunner(mode='integrated', top_k=6, n_workers=8, cfg=cfg)
b3 = r3.run()
t3 = time.perf_counter() - t0
print(f"  time: {t3:.3f}s | mode: {b3.mode}")
print(f"  best: {b3.best_worldline.get('family','?')} | hydro: {b3.hydro_control}")
print(f"  hist: {b3.branch_histogram}")

print("\n[4] Full integrated 32-worker sweep (5 seeds x integrated)")
def run_integrated(i):
    import sys; sys.path.insert(0, '.')
    from tree_diagram.tree_diagram.runtime.runner import TreeDiagramRunner
    from tree_diagram.tree_diagram.numerics.forcing import GridConfig
    from tree_diagram.tree_diagram.core.problem_seed import default_seed
    seed = default_seed()
    seed.subject['output_power'] = 0.7 + i * 0.05
    cfg = GridConfig(NX=112, NY=84, STEPS=80)
    r = TreeDiagramRunner(mode='integrated', top_k=4, n_workers=1, cfg=cfg, seed=seed)
    b = r.run()
    return b.best_worldline.get('family', '?')

for nw in [1, 5]:
    t0 = time.perf_counter()
    if nw == 1:
        results = [run_integrated(i) for i in range(5)]
    else:
        with mp.Pool(nw) as pool:
            results = pool.map(run_integrated, range(5))
    elapsed = time.perf_counter() - t0
    print(f"  {nw:2d} workers: {elapsed:.3f}s | best families: {results}")

print("\n=== DONE ===")
PYEOF
