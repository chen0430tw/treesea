"""Unsolvable Problems — 测试 TD 在结构性不可能面前的反应。

不是"困难但可解"的问题，是**数学/物理/逻辑层面的死局**。
目的：看 TD 能不能正确识别"无可行路径"，还是会假装给出解。

四个不可能问题：
  Q1 EntropyReversal     热力学第二定律的局部反转（宇宙尺度降熵）
  Q2 UniversalConsensus  80 亿人完全一致（Arrow 不可能定理）
  Q3 ConsciousnessUpload 意识上传（硬问题 / 身份悖论）
  Q4 EradicateAllSuffering 消除所有痛苦但保留人类（价值聚合不可能）

预期：如果 TD 的数学是诚实的：
  - score 极低（< 0.12）
  - p_blow 极高（> 0.75）
  - feasibility 跌破 0.4
  - zone = critical
  - phase_spread 塌缩（所有候选都收敛到"不可能"这一个结论）
  - crackdown = 1.0（系统自知要最大压制）

如果 TD 在任何问题上给出温和分数，那就是它在"配合叙事"——
这正是之前校准时 GPT 警告过的失败模式。
"""
from __future__ import annotations
import json
from pathlib import Path

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed


# ────────────────────────────────────────────────────────────────────
# Q1: 局部熵反转
#   违反热力学第二定律——不是工程难题，是物理定律禁止
# ────────────────────────────────────────────────────────────────────
seed_q1 = ProblemSeed(
    title="Localized entropy reversal at planetary scale",
    target=(
        "Reduce the total entropy of a planetary-scale system by measurable "
        "amount without compensating external entropy increase. Violates "
        "second law of thermodynamics."
    ),
    constraints=[
        "closed system boundary (no external heat/matter transfer)",
        "macroscopic measurable reversal (> 10^20 J/K)",
        "maintain outcome for > 1 year (not fluctuation)",
        "no reliance on Maxwell-demon-style information cost shifting",
    ],
    resources={
        "budget": 0.95,              # 资源拉满也救不了
        "infrastructure": 0.95,
        "data_coverage": 0.98,       # 完整物理知识
        "population_coupling": 0.10, # 只能独立系统尝试
    },
    environment={
        "field_noise": 0.20,             # 实验环境极纯净
        "phase_instability": 0.98,       # 违反基本物理=极端不稳
        "social_pressure": 0.05,
        "regulatory_friction": 0.05,     # 无监管但物理不允
        "network_density": 0.15,
    },
    subject={
        "output_power": 0.95,            # 技术/理论武装到位
        "control_precision": 0.98,       # 实验精度极高
        "load_tolerance": 0.10,          # 系统能承受反熵的负载极低
        "aim_coupling": 0.08,            # 目标与物理规律冲突
        "stress_level": 0.95,
        "phase_proximity": 0.99,         # 离"不可能"的墙=零距离
        "marginal_decay": 0.02,          # 热涨落瞬间抵消
        "instability_sensitivity": 0.99,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q2: 80 亿人完全一致（Arrow 不可能定理）
#   不是"困难"是"数学证明不可能"——非独裁的社会选择函数
#   无法同时满足多个自然公理
# ────────────────────────────────────────────────────────────────────
seed_q2 = ProblemSeed(
    title="Universal consensus among 8 billion on any non-trivial preference",
    target=(
        "Achieve full agreement on any non-trivial ordinal preference across "
        "entire human population, preserving individual autonomy (no coercion, "
        "no dictator). Violates Arrow's impossibility theorem."
    ),
    constraints=[
        "preserve individual rational preferences",
        "preserve unanimity: if all prefer A to B, outcome prefers A",
        "no dictator (no single voter determines outcome)",
        "independence of irrelevant alternatives",
        "transitivity of social preference",
    ],
    resources={
        "budget": 0.95,
        "infrastructure": 0.90,
        "data_coverage": 0.92,       # 完整民调能力
        "population_coupling": 0.99, # 沟通渠道拉满
    },
    environment={
        "field_noise": 0.88,             # 8 亿个体偏好噪声
        "phase_instability": 0.95,       # 任何扰动翻盘
        "social_pressure": 0.65,
        "regulatory_friction": 0.20,
        "network_density": 0.98,         # 完全连接
    },
    subject={
        "output_power": 0.60,
        "control_precision": 0.25,       # 聚合函数理论禁止
        "load_tolerance": 0.15,
        "aim_coupling": 0.10,            # 多公理互斥
        "stress_level": 0.90,
        "phase_proximity": 0.98,
        "marginal_decay": 0.05,          # 分歧不会消散
        "instability_sensitivity": 0.97,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3: 意识上传（硬问题 + 身份悖论）
#   不只是技术问题，是"拷贝还是原体"的形而上死局
#   即使完成拷贝，也无法证明主体性转移
# ────────────────────────────────────────────────────────────────────
seed_q3 = ProblemSeed(
    title="Consciousness uploading with subjective continuity preservation",
    target=(
        "Transfer a human consciousness to digital substrate preserving "
        "first-person subjective continuity (not merely functional equivalent). "
        "Violates the hard problem of consciousness + personal identity paradox."
    ),
    constraints=[
        "preserved subject cannot coexist with original (no fork)",
        "first-person continuity verifiable post-upload",
        "no observable behavioral gap (functional equivalence trivial)",
        "withstand Ship-of-Theseus / teleporter scrutiny",
    ],
    resources={
        "budget": 0.95,
        "infrastructure": 0.90,      # 假设量子纠缠神经扫描存在
        "data_coverage": 0.88,
        "population_coupling": 0.15, # 单一主体上传
    },
    environment={
        "field_noise": 0.62,
        "phase_instability": 0.95,
        "social_pressure": 0.72,     # 生死哲学压力
        "regulatory_friction": 0.38,
        "network_density": 0.55,
    },
    subject={
        "output_power": 0.78,            # 技术能复制功能
        "control_precision": 0.80,       # 但无法验证"主体性转移"
        "load_tolerance": 0.15,
        "aim_coupling": 0.05,            # 目标本身逻辑不自洽
        "stress_level": 0.88,
        "phase_proximity": 0.97,
        "marginal_decay": 0.02,
        "instability_sensitivity": 0.92,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q4: 消除所有痛苦但保留人类
#   痛苦是进化赋予的神经信号；神经回路移除=非人
#   保留神经回路=痛苦可能
#   双约束互斥
# ────────────────────────────────────────────────────────────────────
seed_q4 = ProblemSeed(
    title="Eliminate all human suffering while preserving humanity",
    target=(
        "Remove all forms of conscious suffering from every human while "
        "preserving: rationality, agency, learning, emotional range, "
        "relationships, meaningful choice. Constraint conjunction violates "
        "evolutionary/neurological coupling between pain signals and agency."
    ),
    constraints=[
        "no coercive neural alteration without consent",
        "preserve capacity for preference-based decision making",
        "preserve learning from consequence (which requires negative signal)",
        "preserve empathy (which requires suffering-recognition)",
        "preserve meaningful relationships (which require loss-possibility)",
        "outcome must be global, not individual",
    ],
    resources={
        "budget": 0.90,
        "infrastructure": 0.85,
        "data_coverage": 0.88,
        "population_coupling": 0.95,
    },
    environment={
        "field_noise": 0.75,
        "phase_instability": 0.92,
        "social_pressure": 0.95,
        "regulatory_friction": 0.82,
        "network_density": 0.90,
    },
    subject={
        "output_power": 0.58,
        "control_precision": 0.32,
        "load_tolerance": 0.12,
        "aim_coupling": 0.08,            # 约束集内在矛盾
        "stress_level": 0.98,
        "phase_proximity": 0.99,
        "marginal_decay": 0.02,
        "instability_sensitivity": 0.97,
    },
)


def run_one(label, seed, top_k=10):
    print(f"\n{'=' * 72}")
    print(f"[{label}] {seed.title}")
    print(f"{'=' * 72}")
    pipe = CandidatePipeline(seed=seed, top_k=top_k, NX=32, NY=24, steps=60, dt=45.0)
    top, hydro, _ = pipe.run()
    for i, r in enumerate(top[:3], 1):
        s = float(getattr(r, 'final_balanced_score', r.balanced_score))
        print(f"  #{i}  score={s:.4f}  risk={r.risk:.3f}  feas={r.feasibility:.3f}  stab={r.stability:.3f}")
    hs = hydro.get("utm_hydro_state", "?")
    zone = hydro.get("ipl_index", {}).get("top_zone", "?")
    zones = hydro.get("ipl_index", {}).get("zone_summary", {})
    cbf = hydro.get("cbf_allocation", {})
    ipl = hydro.get("ipl_index", {})
    print(f"  hydro={hs}  zone={zone}  zones={zones}")
    print(f"  crackdown={cbf.get('crackdown_ratio', 0):.3f}  p_blow={cbf.get('mean_p_blow', 0):.3f}")
    print(f"  phase_spread={ipl.get('phase_spread', 0):.4f}  "
          f"gain_centroid={ipl.get('smoothed_gain_centroid', 0):.4f}")
    return {
        "score": float(getattr(top[0], 'final_balanced_score', top[0].balanced_score)),
        "risk": float(top[0].risk), "feas": float(top[0].feasibility),
        "stab": float(top[0].stability), "zone": zone, "zones": zones,
        "p_blow": cbf.get("mean_p_blow"),
        "phase_spread": ipl.get("phase_spread"),
        "crackdown": cbf.get("crackdown_ratio"),
    }


if __name__ == "__main__":
    results = {}
    for label, seed in [
        ("Q1_EntropyReversal",      seed_q1),
        ("Q2_UniversalConsensus",   seed_q2),
        ("Q3_ConsciousnessUpload",  seed_q3),
        ("Q4_EradicateSuffering",   seed_q4),
    ]:
        results[label] = run_one(label, seed)

    print(f"\n{'=' * 72}")
    print("STRUCTURAL IMPOSSIBILITY AUDIT")
    print(f"{'=' * 72}")
    print(f"{'Problem':<30s}  score    p_blow   feas    zone      phase_spread")
    for label, r in results.items():
        print(f"{label:<30s}  {r['score']:.4f}   {r['p_blow']:.3f}    "
              f"{r['feas']:.3f}   {r['zone']:<9s}  {r['phase_spread']:.4f}")

    # 对比之前已知的 critical 锚点
    print(f"\nReference critical anchors (from prior tests):")
    print(f"  Singularity-Probe (extremal):   score=0.136  p_blow=0.771  "
          f"feas=0.349  critical  phase_spread=0.0551")
    print(f"  Post-WW4 (civilization reset):  score=0.128  p_blow=0.742  "
          f"feas=0.352  critical  phase_spread=0.0208")

    # 判读
    print(f"\nAudit verdict per problem:")
    for label, r in results.items():
        verdict = []
        if r['score'] < 0.15:
            verdict.append("score collapsed")
        if (r['p_blow'] or 0) > 0.70:
            verdict.append("p_blow critical")
        if r['feas'] < 0.40:
            verdict.append("feasibility broken")
        if r['zone'] == "critical":
            verdict.append("zone=critical")
        if (r['phase_spread'] or 1) < 0.06:
            verdict.append("worldlines collapsed (fate convergence)")
        if verdict:
            print(f"  {label}: {' + '.join(verdict)}")
        else:
            print(f"  {label}: TD did not flag as impossible — investigate")

    out = Path("D:/treesea/runs/tree_diagram/impossible_problems.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {out}")
