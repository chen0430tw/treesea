"""直接问 TD：奇点在你眼里是什么？

之前的做法是给 TD 具体历史事件（COVID/AI/丧尸）然后问"这个是不是奇点"。
这次换个方向——给 TD 一个专门为探索 singularity geometry 设计的 seed，
让它输出的 top worldlines 自己描绘出奇点的参数签名。

期望：如果 TD 内部真的有奇点判据，top worldlines 应该展示出：
  - 异于 COVID/AI 的 stable basin 模式
  - 可能的 zone = critical 或 transition
  - 极端 p_blow 或极端 feasibility
  - 不同于 batch/batch_route 的 family 主导（如果有）
"""
from __future__ import annotations
import json
from pathlib import Path

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed


# ────────────────────────────────────────────────────────────────────
# 奇点探索 seed：用极端参数触发相空间里的非常规区域
#
# 设计思路：
#   - phase_proximity 拉到 0.99（几乎在相变点上）
#   - instability_sensitivity 拉到 0.99（任何扰动都触发跃迁）
#   - phase_instability 拉到 0.99（场本身就不稳定）
#   - control_precision 极低 0.05（没有约束）
#   - aim_coupling 极低 0.05（没有指向）
#   - marginal_decay 极低 0.02（扰动不消散）
#
# 预期：如果 TD 能识别"奇点区域"，这组参数应该落在
#       跟 COVID/AI 明显不同的判决区间
# ────────────────────────────────────────────────────────────────────
seed_singularity = ProblemSeed(
    title="What is a singularity in TD phase space?",
    target=(
        "Characterize the parameter regime that constitutes a genuine singularity "
        "event — zone transition, basin jump, irreversible equilibrium shift. "
        "Find the worldline families that dominate near this regime."
    ),
    constraints=[
        "system is at phase boundary (about to transition)",
        "no stabilizing control forces",
        "perturbations do not decay",
        "any small change triggers regime shift",
    ],
    resources={
        "budget": 0.50,
        "infrastructure": 0.50,
        "data_coverage": 0.50,
        "population_coupling": 0.99,  # 耦合拉满：所有子系统同步跃迁
    },
    environment={
        "field_noise": 0.95,              # 噪声拉满
        "phase_instability": 0.99,        # 相位不稳定拉满（奇点标志）
        "social_pressure": 0.05,          # 无外部约束
        "regulatory_friction": 0.05,      # 无阻尼
        "network_density": 0.99,          # 传播网络密度拉满
    },
    subject={
        "output_power": 0.50,
        "control_precision": 0.05,        # 无控制
        "load_tolerance": 0.05,           # 无容忍
        "aim_coupling": 0.05,             # 无指向
        "stress_level": 0.99,             # 应力拉满
        "phase_proximity": 0.99,          # 离相变点极近（奇点核心信号）
        "marginal_decay": 0.02,           # 扰动永续
        "instability_sensitivity": 0.99,  # 敏感度拉满
    },
)


# ────────────────────────────────────────────────────────────────────
# 对照：标准稳态（前面 COVID Q3A Pre / AI Q3A Pre 都是这一类）
# ────────────────────────────────────────────────────────────────────
seed_stable_baseline = ProblemSeed(
    title="Standard stable equilibrium (baseline for contrast)",
    target="Typical stable system for contrast with singularity regime.",
    constraints=["normal operating conditions"],
    resources={
        "budget": 0.60, "infrastructure": 0.70,
        "data_coverage": 0.70, "population_coupling": 0.60,
    },
    environment={
        "field_noise": 0.30, "phase_instability": 0.25,
        "social_pressure": 0.50, "regulatory_friction": 0.55,
        "network_density": 0.70,
    },
    subject={
        "output_power": 0.70, "control_precision": 0.75,
        "load_tolerance": 0.65, "aim_coupling": 0.70,
        "stress_level": 0.40, "phase_proximity": 0.40,
        "marginal_decay": 0.50, "instability_sensitivity": 0.45,
    },
)


# ────────────────────────────────────────────────────────────────────
# 对照：极端健康（像 AI Q3A 的极致版）
# ────────────────────────────────────────────────────────────────────
seed_ultra_healthy = ProblemSeed(
    title="Ultra-stable (hypothetical best-case)",
    target="Extreme healthy equilibrium for upper bound.",
    constraints=["idealized control"],
    resources={
        "budget": 0.95, "infrastructure": 0.95,
        "data_coverage": 0.95, "population_coupling": 0.30,
    },
    environment={
        "field_noise": 0.05, "phase_instability": 0.05,
        "social_pressure": 0.95, "regulatory_friction": 0.95,
        "network_density": 0.30,
    },
    subject={
        "output_power": 0.95, "control_precision": 0.99,
        "load_tolerance": 0.95, "aim_coupling": 0.99,
        "stress_level": 0.10, "phase_proximity": 0.10,
        "marginal_decay": 0.80, "instability_sensitivity": 0.10,
    },
)


def run_one(label: str, seed: ProblemSeed, top_k: int = 10):
    print(f"\n{'=' * 70}")
    print(f"[{label}] {seed.title}")
    print(f"{'=' * 70}")
    pipe = CandidatePipeline(seed=seed, top_k=top_k, NX=32, NY=24, steps=60, dt=45.0)
    top, hydro, _ = pipe.run()

    # 看 family 分布
    family_counts: dict = {}
    for r in top:
        fam = r.family
        family_counts[fam] = family_counts.get(fam, 0) + 1

    # Top 5 详细
    print(f"Top 5 worldlines:")
    for i, r in enumerate(top[:5], 1):
        s = float(getattr(r, 'final_balanced_score', r.balanced_score))
        print(f"  #{i}  score={s:.4f}  risk={r.risk:.3f}  feas={r.feasibility:.3f}  "
              f"stab={r.stability:.3f}  {r.family}/{r.template}")

    print(f"\nFamily distribution (top {top_k}): {family_counts}")

    hs = hydro.get("utm_hydro_state", "?")
    zone = hydro.get("ipl_index", {}).get("top_zone", "?")
    zones = hydro.get("ipl_index", {}).get("zone_summary", {})
    cbf = hydro.get("cbf_allocation", {})
    ipl = hydro.get("ipl_index", {})
    print(f"hydro={hs}  zone={zone}  zones={zones}")
    print(f"crackdown={cbf.get('crackdown_ratio', 0):.3f}  "
          f"p_blow={cbf.get('mean_p_blow', 0):.3f}")
    if "smoothed_gain_centroid" in ipl:
        print(f"gain_centroid={ipl['smoothed_gain_centroid']:.4f}  "
              f"phase_spread={ipl.get('phase_spread', 0):.4f}")

    return {
        "top_score": float(getattr(top[0], 'final_balanced_score', top[0].balanced_score)),
        "risk": float(top[0].risk),
        "feas": float(top[0].feasibility),
        "stab": float(top[0].stability),
        "family_dist": family_counts,
        "zone": zone,
        "zones": zones,
        "p_blow": cbf.get("mean_p_blow"),
        "gain_centroid": ipl.get("smoothed_gain_centroid"),
        "phase_spread": ipl.get("phase_spread"),
    }


if __name__ == "__main__":
    results = {}
    results["ultra_healthy"]    = run_one("Ultra-Healthy",     seed_ultra_healthy)
    results["stable_baseline"]  = run_one("Stable-Baseline",   seed_stable_baseline)
    results["singularity"]      = run_one("Singularity-Probe", seed_singularity)

    # 对比三档
    print(f"\n{'=' * 70}")
    print("What does TD say a singularity looks like?")
    print(f"{'=' * 70}")
    print(f"                  Healthy   Stable   Singularity")
    print(f"  score:         {results['ultra_healthy']['top_score']:7.4f}  "
          f"{results['stable_baseline']['top_score']:7.4f}  "
          f"{results['singularity']['top_score']:7.4f}")
    print(f"  risk:          {results['ultra_healthy']['risk']:7.3f}  "
          f"{results['stable_baseline']['risk']:7.3f}  "
          f"{results['singularity']['risk']:7.3f}")
    print(f"  feas:          {results['ultra_healthy']['feas']:7.3f}  "
          f"{results['stable_baseline']['feas']:7.3f}  "
          f"{results['singularity']['feas']:7.3f}")
    print(f"  stab:          {results['ultra_healthy']['stab']:7.3f}  "
          f"{results['stable_baseline']['stab']:7.3f}  "
          f"{results['singularity']['stab']:7.3f}")
    print(f"  zone:          {results['ultra_healthy']['zone']:>7s}  "
          f"{results['stable_baseline']['zone']:>7s}  "
          f"{results['singularity']['zone']:>11s}")
    print(f"  p_blow:        {results['ultra_healthy']['p_blow']:.3f}    "
          f"{results['stable_baseline']['p_blow']:.3f}    "
          f"{results['singularity']['p_blow']:.3f}")
    if results['ultra_healthy'].get('gain_centroid') is not None:
        print(f"  gain_centroid: {results['ultra_healthy']['gain_centroid']:7.4f}  "
              f"{results['stable_baseline']['gain_centroid']:7.4f}  "
              f"{results['singularity']['gain_centroid']:7.4f}")
    if results['ultra_healthy'].get('phase_spread') is not None:
        print(f"  phase_spread:  {results['ultra_healthy']['phase_spread']:7.4f}  "
              f"{results['stable_baseline']['phase_spread']:7.4f}  "
              f"{results['singularity']['phase_spread']:7.4f}")

    out = Path("D:/treesea/runs/tree_diagram/what_is_singularity.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {out}")
