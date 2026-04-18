"""Run CandidatePipeline on three NaN-propagation (zombie) questions.

映射：丧尸语义 → Tree Diagram 内核认识的气象场字段
- subject.aim_coupling           ↔ 训练收敛指向性（高=健康）
- subject.control_precision      ↔ 数值检查严格度（高=防丧尸）
- subject.phase_proximity        ↔ 离相变/发散的距离
- subject.marginal_decay         ↔ 边际衰减（高=信号消散快）
- subject.load_tolerance         ↔ 负载容忍度
- subject.instability_sensitivity ↔ 对不稳定的敏感度（高=易被感染）
- subject.stress_level           ↔ 应力水平
- environment.field_noise        ↔ 数值噪声（高=NaN 温床）
- environment.phase_instability  ↔ 相位不稳（高=易爆炸）
- environment.social_pressure    ↔ 外部监控压力
- environment.regulatory_friction ↔ 防护约束强度
- environment.network_density    ↔ 传播网络密度
- resources.population_coupling  ↔ 传播耦合（高=感染快）
- resources.data_coverage        ↔ 观测覆盖
- resources.budget               ↔ 检测预算
- resources.infrastructure       ↔ 基础设施稳定性
"""
from __future__ import annotations
import json
from pathlib import Path

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed


# ────────────────────────────────────────────────────────────────────
# Q1: NaN/Inf 怎么感染 ——「温床 + 弱检查 + 高传播耦合」
# ────────────────────────────────────────────────────────────────────
seed_q1 = ProblemSeed(
    title="NaN/Inf propagation pathway analysis",
    target="Identify infection pathway by which numeric instability bypasses clamps and spreads to downstream signals.",
    constraints=["propagation bypasses clamps", "infected outputs look plausible"],
    resources={
        "budget": 0.30,               # 检测预算低
        "infrastructure": 0.40,       # 基础设施弱
        "data_coverage": 0.45,        # 观测不全
        "population_coupling": 0.90,  # 传播耦合极高
    },
    environment={
        "field_noise": 0.85,             # 数值噪声极高（NaN 温床）
        "phase_instability": 0.82,       # 相位不稳（易爆炸）
        "social_pressure": 0.20,         # 外部监控弱
        "regulatory_friction": 0.15,     # 防护约束极弱
        "network_density": 0.88,         # 传播网络密集
    },
    subject={
        "output_power": 0.70,
        "control_precision": 0.18,          # 数值检查极弱（关键：丧尸入口）
        "load_tolerance": 0.35,
        "aim_coupling": 0.30,               # 收敛指向性差
        "stress_level": 0.80,               # 高应力
        "phase_proximity": 0.88,            # 极接近发散
        "marginal_decay": 0.10,             # 信号不消散（污染会持续传）
        "instability_sensitivity": 0.90,    # 对不稳定极敏感
    },
)


# ────────────────────────────────────────────────────────────────────
# Q2: 污染 run 能存活多久 ——「症状不明显 + 检测滞后 + 中等衰减」
# ────────────────────────────────────────────────────────────────────
seed_q2 = ProblemSeed(
    title="Infected run persistence duration before detection",
    target="Model time-to-detection for a corrupted training run under realistic monitoring latency.",
    constraints=["bounded lifespan", "detector has observation window"],
    resources={
        "budget": 0.50,               # 中等检测预算
        "infrastructure": 0.60,
        "data_coverage": 0.55,
        "population_coupling": 0.60,  # 中等传播
    },
    environment={
        "field_noise": 0.50,
        "phase_instability": 0.55,
        "social_pressure": 0.40,         # 监控压力中等（有延迟）
        "regulatory_friction": 0.45,     # 约束中等
        "network_density": 0.62,
    },
    subject={
        "output_power": 0.60,
        "control_precision": 0.42,          # 检查一般（症状被掩盖）
        "load_tolerance": 0.55,
        "aim_coupling": 0.50,
        "stress_level": 0.55,
        "phase_proximity": 0.62,            # 接近但未跨越相变
        "marginal_decay": 0.35,             # 衰减中等（存活时间有限）
        "instability_sensitivity": 0.60,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3: 未污染 run 如何保持健康 ——「低噪声 + 强检查 + 高指向性」
# ────────────────────────────────────────────────────────────────────
seed_q3 = ProblemSeed(
    title="Conditions for uninfected runs to remain healthy",
    target="Identify input/config regime where training run remains in HEALTHY state across all zombie classes.",
    constraints=["avoid all 5 zombie classes", "tolerate realistic noise"],
    resources={
        "budget": 0.75,               # 检测预算充足
        "infrastructure": 0.85,       # 基础设施稳
        "data_coverage": 0.82,        # 观测覆盖好
        "population_coupling": 0.30,  # 传播耦合低（隔离好）
    },
    environment={
        "field_noise": 0.20,             # 数值噪声低
        "phase_instability": 0.18,       # 相位稳
        "social_pressure": 0.75,         # 监控强
        "regulatory_friction": 0.80,     # 防护约束强
        "network_density": 0.35,         # 传播网络稀
    },
    subject={
        "output_power": 0.85,
        "control_precision": 0.92,          # 数值检查严格
        "load_tolerance": 0.80,
        "aim_coupling": 0.95,               # 收敛指向性极强
        "stress_level": 0.22,               # 低应力
        "phase_proximity": 0.35,            # 远离发散
        "marginal_decay": 0.18,             # 低衰减（健康信号持久）
        "instability_sensitivity": 0.25,    # 对不稳定不敏感
    },
)


def run_one(label: str, seed: ProblemSeed, top_k: int = 5, steps: int = 60):
    print(f"\n{'=' * 70}")
    print(f"[{label}] {seed.title}")
    print(f"{'=' * 70}")
    pipe = CandidatePipeline(
        seed=seed, top_k=top_k, NX=32, NY=24, steps=steps, dt=45.0, n_workers=1,
    )
    top, hydro, oracle = pipe.run()

    print(f"Top {len(top)} worldlines:")
    for i, r in enumerate(top, 1):
        score = getattr(r, 'final_balanced_score', getattr(r, 'balanced_score', 0.0))
        print(f"  #{i}  score={score:.4f}  risk={r.risk:.3f}  feas={r.feasibility:.3f}  "
              f"stab={r.stability:.3f}  {r.family}/{r.template}")

    hs = hydro.get("utm_hydro_state", "?")
    zone = hydro.get("ipl_index", {}).get("top_zone", "?")
    zones = hydro.get("ipl_index", {}).get("zone_summary", {})
    print(f"\nhydro={hs}  top_zone={zone}  zones={zones}")

    exp = oracle.get("llm_explanation", {})
    summary = exp.get("summary") or exp.get("text", "")
    if summary:
        print(f"Oracle: {summary[:350]}")

    return {"top": top, "hydro": hydro, "oracle": oracle}


if __name__ == "__main__":
    results = {}
    for label, seed in [("Q1", seed_q1), ("Q2", seed_q2), ("Q3", seed_q3)]:
        results[label] = run_one(label, seed)

    out = Path("D:/treesea/runs/tree_diagram/zombie_inquiry.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = {}
    for label, r in results.items():
        summary[label] = {
            "top_families": [x.family for x in r["top"]],
            "top_scores": [float(getattr(x, 'final_balanced_score', x.balanced_score)) for x in r["top"]],
            "risks": [float(x.risk) for x in r["top"]],
            "feasibilities": [float(x.feasibility) for x in r["top"]],
            "stabilities": [float(x.stability) for x in r["top"]],
            "hydro_state": r["hydro"].get("utm_hydro_state"),
            "top_zone": r["hydro"].get("ipl_index", {}).get("top_zone"),
            "zone_summary": r["hydro"].get("ipl_index", {}).get("zone_summary", {}),
        }
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {out}")
