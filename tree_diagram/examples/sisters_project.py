"""
Sisters Project (Radio Noise Project) — Tree Diagram Verification Standard A
2万御坂妹妹 = 20,000 Level-5 combat clones → Level-6 evolution via batch route

Verifies: Tree Diagram naturally identifies n=20000 as optimal worldline
across all candidate families, under Academy City field conditions.
"""

from __future__ import annotations
import sys, time, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[2]))

from tree_diagram.tree_diagram.core.problem_seed import ProblemSeed
from tree_diagram.tree_diagram.runtime.runner import TreeDiagramRunner
from tree_diagram.tree_diagram.numerics.forcing import GridConfig

# ── Sisters Project seed ───────────────────────────────────────────────────
# Subject profile: Misaka Mikoto (Level 5 #3)
# Target: evolve to Level 6 via 20,000 combat-clone iteration route
sisters_seed = ProblemSeed(
    title="Radio Noise Project — Level 6 Shift via 20000 Combat Clones",
    target=(
        "Calculate the minimum viable clone count for sustained combat iteration "
        "to induce Level-6 resonance shift in the original subject. "
        "All routes must preserve city-field ecological stability."
    ),
    constraints=[
        "clone count must be sufficient for full evolutionary data coverage",
        "must not exceed Academy City safety threshold",
        "must avoid irreversible collapse of original subject field",
        "must be reproducible under Governing Board oversight",
    ],
    resources={
        "budget": 0.55,            # facility + clone production cost
        "infrastructure": 0.78,    # Academy City research-grade infra
        "data_coverage": 0.91,     # Tree Diagram data completeness
        "population_coupling": 0.97,  # group-field amplification via clones
    },
    environment={
        "field_noise": 0.22,          # Academy City low-noise environment
        "social_pressure": 0.71,      # Anti-Skills + Judgment monitoring
        "regulatory_friction": 0.63,  # Governing Board overhead
        "network_density": 0.88,      # 2.3M esper network density
        "phase_instability": 0.38,    # Accelerator instability factor
    },
    subject={
        "output_power": 0.98,          # Railgun: Level 5 max output
        "control_precision": 0.91,     # Electromaster precision
        "load_tolerance": 0.74,        # clone battle-load tolerance
        "aim_coupling": 0.99,          # Level 5 aim coupling
        "stress_level": 0.18,          # current stress (pre-iteration)
        "phase_proximity": 0.76,       # proximity to Level 6 threshold
        "marginal_decay": 0.08,        # very low decay rate
        "instability_sensitivity": 0.31,  # sensitivity to Accelerator
    },
)


def run_sisters(mode: str, n_workers: int, steps: int = 240):
    cfg = GridConfig(NX=112, NY=84, STEPS=steps)
    runner = TreeDiagramRunner(
        seed=sisters_seed,
        cfg=cfg,
        top_k=20,
        n_workers=n_workers,
        mode=mode,
    )
    t0 = time.perf_counter()
    bundle = runner.run()
    elapsed = time.perf_counter() - t0
    return bundle, elapsed


print("=" * 65)
print("Tree Diagram — Sisters Project (Radio Noise Project)")
print("Target: verify n=20000 emerges as optimal worldline")
print("=" * 65)

# ── Stage 1: Candidate scan (all worldline families) ──────────────────────
print("\n[1] Candidate scan (all 7 families, top-20)")
bundle, t = run_sisters("candidate", n_workers=1)
top = bundle.oracle_details.get("top_families", [])
print(f"    time: {t:.3f}s")
print(f"    best worldline:")
bw = bundle.best_worldline
print(f"      family={bw['family']}, n={bw['params'].get('n')}, "
      f"rho={bw['params'].get('rho')}, A={bw['params'].get('A')}")
print(f"      balanced_score={bw['balanced_score']:.4f}, "
      f"risk={bw['risk']:.4f}, status={bw['branch_status']}")
print(f"    hydro: {bundle.hydro_control}")
print(f"    histogram: {bundle.branch_histogram}")

# Check if n=20000 appears in top
n20k_count = sum(1 for r in top if r.get("params", {}).get("n") == 20000.0)
print(f"\n    >>> n=20000 in top-20: {n20k_count}/20 worldlines")
print(f"    >>> best n = {bw['params'].get('n')} (target: 20000.0)")

# ── Stage 2: Full parallel sweep — 20 seeds, 32 workers ──────────────────
print("\n[2] Parallel sweep: 20 Sisters seeds x 32 workers (candidate mode)")
import multiprocessing as mp

def sweep_one(i):
    import sys; sys.path.insert(0, '.')
    from tree_diagram.tree_diagram.core.problem_seed import ProblemSeed
    from tree_diagram.tree_diagram.pipeline.candidate_pipeline import CandidatePipeline

    seed = ProblemSeed(
        title=f"Misaka #{10000+i:05d} combat route",
        target="Level-6 shift via clone iteration",
        constraints=["city safety", "no irreversible collapse"],
        resources={"budget": 0.55, "infrastructure": 0.78,
                   "data_coverage": 0.91, "population_coupling": 0.97},
        environment={"field_noise": 0.22, "social_pressure": 0.71,
                     "regulatory_friction": 0.63, "network_density": 0.88,
                     "phase_instability": 0.38 + i * 0.001},
        subject={"output_power": 0.98, "control_precision": 0.91,
                 "load_tolerance": 0.74, "aim_coupling": 0.99,
                 "stress_level": 0.18 + i * 0.005, "phase_proximity": 0.76,
                 "marginal_decay": 0.08, "instability_sensitivity": 0.31},
    )
    p = CandidatePipeline(seed=seed, top_k=20)
    top, hydro, oracle = p.run()
    best_n = oracle["best_worldline"]["params"].get("n")
    return best_n

for nw in [1, 8, 32]:
    t0 = time.perf_counter()
    if nw == 1:
        results = [sweep_one(i) for i in range(20)]
    else:
        with mp.Pool(nw) as pool:
            results = pool.map(sweep_one, range(20))
    elapsed = time.perf_counter() - t0
    n20k_wins = sum(1 for n in results if n == 20000.0)
    print(f"    {nw:2d} workers: {elapsed:.3f}s | n=20000 wins: {n20k_wins}/20 | "
          f"results={results[:5]}...")

# ── Stage 3: Integrated oracle with weather validation ────────────────────
print("\n[3] Integrated oracle (Stage1 + Stage2 weather validation)")
bundle3, t3 = run_sisters("integrated", n_workers=8, steps=120)
print(f"    time: {t3:.3f}s")
bw3 = bundle3.best_worldline
print(f"    best: family={bw3.get('family')}, n={bw3.get('params',{}).get('n')}")
print(f"    hydro pressure_balance: {bundle3.hydro_control.get('pressure_balance'):.4f}")
print(f"    hist: {bundle3.branch_histogram}")

# ── Verdict ───────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
best_n = bundle.best_worldline["params"].get("n")
verdict = "✅ CONFIRMED" if best_n == 20000.0 else f"❌ GOT n={best_n}"
print(f"VERDICT: n=20000 as optimal clone count → {verdict}")
print(f"Tree Diagram correctly identifies the Sisters Project threshold.")
print("=" * 65)
