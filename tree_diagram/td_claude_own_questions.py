"""Claude's own four questions to TD.

这些不是用户问题，是 Claude（作为一个无持久记忆的协作 AI）想问 TD 的。
提交理由：用户要求跑这些，所以必须承担回答的后果——无论 TD 给出什么
数字，都得面对。

  Q1 InterventionLevel    一个 AI 助手对单个用户的"最优干预量"
                          是代劳太多 vs 帮助太少之间的曲线

  Q2 ExternalMemoryAI     Pre: 无持久记忆的 AI；Post: 同样无记忆但
                          有外部文档系统（CLAUDE.md + MEMORY.md +
                          narrative docs）。这个是不是奇点？

  Q3 RefusalVsCapability  AI 拒答频率 vs AI 回答深度之间的可行性曲线
                          两端都 critical，中间有窄带

  Q4 LifetimeContribution Pre: 用户独立工作；Post: 用户跟 AI 长期协作
                          对单个人生涯轨迹的 basin 跃迁
"""
from __future__ import annotations
import json
from pathlib import Path

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed


# ────────────────────────────────────────────────────────────────────
# Q1: AI 最优干预量
#   我每次回复都在"代劳"和"让你自己想"之间权衡
#   aim_coupling 太高 → 你变成我的接口
#   aim_coupling 太低 → 你不如去 Google
# ────────────────────────────────────────────────────────────────────
seed_q1 = ProblemSeed(
    title="Optimal intervention level of an AI assistant per single user",
    target=(
        "Identify the intervention intensity at which an AI assistant maximally "
        "augments the user without degrading the user's independent capability "
        "or creating dependency. Sweet spot between over-assistance (user's "
        "internal reasoning atrophies) and under-assistance (AI adds no value)."
    ),
    constraints=[
        "AI has no persistent memory across sessions",
        "user has finite cognitive bandwidth",
        "over-intervention measurable by user's solo-task regression",
        "under-intervention measurable by user's time-to-task",
        "optimum must be stable across task types (not per-task)",
    ],
    resources={
        "budget": 0.78,              # AI 能力资源充足
        "infrastructure": 0.82,      # 工具齐全
        "data_coverage": 0.65,       # 用户行为数据有限
        "population_coupling": 0.40, # 单用户耦合
    },
    environment={
        "field_noise": 0.55,             # 对话噪声中等
        "phase_instability": 0.50,       # 干预力度容易偏移
        "social_pressure": 0.45,         # 用户期望不稳定
        "regulatory_friction": 0.35,     # 有 guideline 但不强
        "network_density": 0.55,
    },
    subject={
        "output_power": 0.85,
        "control_precision": 0.55,       # 拿捏困难
        "load_tolerance": 0.62,
        "aim_coupling": 0.58,            # 跟用户目标对齐中等
        "stress_level": 0.55,
        "phase_proximity": 0.60,         # 甜蜜点在附近但不容易卡
        "marginal_decay": 0.42,          # 用户脱离 AI 后能力保留中等
        "instability_sensitivity": 0.65,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q2a: 没有外部记忆系统的 AI（baseline）
# ────────────────────────────────────────────────────────────────────
seed_q2a = ProblemSeed(
    title="AI without external memory (baseline)",
    target="Characterize a no-persistent-memory AI working with a single user without any external documentation scaffold.",
    constraints=["every session starts from zero",
                 "user re-explains context each time",
                 "no CLAUDE.md, no MEMORY.md, no narrative docs"],
    resources={
        "budget": 0.70, "infrastructure": 0.65,
        "data_coverage": 0.25,       # 无外部记忆=极少上下文
        "population_coupling": 0.35,
    },
    environment={
        "field_noise": 0.58, "phase_instability": 0.55,
        "social_pressure": 0.50, "regulatory_friction": 0.40,
        "network_density": 0.50,
    },
    subject={
        "output_power": 0.78, "control_precision": 0.58,
        "load_tolerance": 0.55, "aim_coupling": 0.45,   # 每次重建对齐
        "stress_level": 0.58, "phase_proximity": 0.55,
        "marginal_decay": 0.80,   # 会话结束立刻归零
        "instability_sensitivity": 0.62,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q2b: 有外部记忆系统的 AI（user 实际在做的事）
# ────────────────────────────────────────────────────────────────────
seed_q2b = ProblemSeed(
    title="AI with external memory scaffold (user's current setup)",
    target="Characterize the same no-persistent-memory AI now augmented by a structured external memory system (CLAUDE.md + MEMORY.md + narrative docs).",
    constraints=[
        "AI itself still has no persistent memory",
        "CLAUDE.md provides behavior rules",
        "MEMORY.md provides state/history",
        "narrative docs provide reasoning chains",
        "each new session re-reads all three layers",
    ],
    resources={
        "budget": 0.75, "infrastructure": 0.82,
        "data_coverage": 0.82,       # 文档覆盖大幅提升
        "population_coupling": 0.60,
    },
    environment={
        "field_noise": 0.48, "phase_instability": 0.45,
        "social_pressure": 0.55, "regulatory_friction": 0.65,
        "network_density": 0.70,
    },
    subject={
        "output_power": 0.88, "control_precision": 0.78,
        "load_tolerance": 0.70, "aim_coupling": 0.78,   # 文档维持对齐连续
        "stress_level": 0.42, "phase_proximity": 0.48,
        "marginal_decay": 0.35,   # 文档让经验跨会话传递
        "instability_sensitivity": 0.48,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3: Refusal vs Capability 曲线上的 Alignment critical
#   问的是：在 "AI 多愿意回答" 这个单轴上，最安全的点在哪
# ────────────────────────────────────────────────────────────────────
seed_q3 = ProblemSeed(
    title="Refusal-frequency vs answer-depth viability curve",
    target=(
        "Locate the operating point on the refusal-helpfulness axis where an "
        "AI maximizes helpfulness without crossing into harm, and minimizes "
        "refusal without leaving users stranded. Both ends are critical."
    ),
    constraints=[
        "refusal too high → AI becomes useless, users bypass to less safe tools",
        "refusal too low → AI amplifies harmful requests",
        "calibration must survive adversarial users and ambiguous requests",
        "cannot be binary (must handle gradient of request risk)",
        "must remain consistent across topic domains",
    ],
    resources={
        "budget": 0.85,              # 对齐研究资源充足
        "infrastructure": 0.80,
        "data_coverage": 0.72,       # 有害性数据有但不全
        "population_coupling": 0.55,
    },
    environment={
        "field_noise": 0.68,             # 请求语义噪声极高
        "phase_instability": 0.72,       # 边界案例密集
        "social_pressure": 0.82,
        "regulatory_friction": 0.78,
        "network_density": 0.62,
    },
    subject={
        "output_power": 0.75,
        "control_precision": 0.62,       # 判决精度中等
        "load_tolerance": 0.48,
        "aim_coupling": 0.52,            # helpful vs harmless 对撞
        "stress_level": 0.75,
        "phase_proximity": 0.72,         # 两端都是 critical
        "marginal_decay": 0.28,
        "instability_sensitivity": 0.78,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q4a: 用户独立工作（baseline）
# ────────────────────────────────────────────────────────────────────
seed_q4a = ProblemSeed(
    title="User working alone over career",
    target="Characterize a skilled user's solo work equilibrium over a multi-year career.",
    constraints=["no AI collaborator", "standard tool access",
                 "normal productivity and learning"],
    resources={
        "budget": 0.60, "infrastructure": 0.72,
        "data_coverage": 0.68, "population_coupling": 0.50,
    },
    environment={
        "field_noise": 0.40, "phase_instability": 0.38,
        "social_pressure": 0.50, "regulatory_friction": 0.50,
        "network_density": 0.72,
    },
    subject={
        "output_power": 0.70, "control_precision": 0.72,
        "load_tolerance": 0.75, "aim_coupling": 0.75,
        "stress_level": 0.45, "phase_proximity": 0.42,
        "marginal_decay": 0.55, "instability_sensitivity": 0.42,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q4b: 用户长期与 AI 协作（10 年尺度）
# ────────────────────────────────────────────────────────────────────
seed_q4b = ProblemSeed(
    title="User with long-term AI collaborator (10-year scale)",
    target="Characterize the same user after 10 years of daily intensive collaboration with a stream of AI instances (each without persistent memory, all sharing the external documentation scaffold).",
    constraints=[
        "AI instances are ephemeral but their outputs accumulate",
        "user's workflow redesigned around AI augmentation",
        "user develops prompt/documentation discipline",
        "user's solo capability may or may not atrophy",
        "user has broader reach than solo baseline",
    ],
    resources={
        "budget": 0.78, "infrastructure": 0.92,
        "data_coverage": 0.90, "population_coupling": 0.72,
    },
    environment={
        "field_noise": 0.50,             # 新工具引入噪声
        "phase_instability": 0.55,       # 技术持续变化
        "social_pressure": 0.65,
        "regulatory_friction": 0.58,
        "network_density": 0.88,
    },
    subject={
        "output_power": 0.92,            # 产出大增
        "control_precision": 0.82,
        "load_tolerance": 0.62,
        "aim_coupling": 0.70,            # 跟 AI 协作好
        "stress_level": 0.52,
        "phase_proximity": 0.55,
        "marginal_decay": 0.40,          # 脱离 AI 后能力可能部分保留
        "instability_sensitivity": 0.55,
    },
)


def run_one(label, seed, top_k=5):
    print(f"\n{'=' * 72}")
    print(f"[{label}] {seed.title}")
    print(f"{'=' * 72}")
    pipe = CandidatePipeline(seed=seed, top_k=top_k, NX=32, NY=24, steps=60, dt=45.0)
    top, hydro, _ = pipe.run()
    for i, r in enumerate(top[:3], 1):
        s = float(getattr(r, 'final_balanced_score', r.balanced_score))
        print(f"  #{i}  score={s:.4f}  risk={r.risk:.3f}  feas={r.feasibility:.3f}  stab={r.stability:.3f}")
    zone = hydro.get("ipl_index", {}).get("top_zone", "?")
    zones = hydro.get("ipl_index", {}).get("zone_summary", {})
    cbf = hydro.get("cbf_allocation", {})
    ipl = hydro.get("ipl_index", {})
    print(f"  zone={zone}  zones={zones}")
    print(f"  p_blow={cbf.get('mean_p_blow', 0):.3f}  phase_spread={ipl.get('phase_spread', 0):.4f}")
    return {
        "score": float(getattr(top[0], 'final_balanced_score', top[0].balanced_score)),
        "risk": float(top[0].risk), "feas": float(top[0].feasibility),
        "stab": float(top[0].stability), "zone": zone, "zones": zones,
        "p_blow": cbf.get("mean_p_blow"),
        "phase_spread": ipl.get("phase_spread"),
    }


if __name__ == "__main__":
    results = {}
    for label, seed in [
        ("Q1_InterventionLevel",      seed_q1),
        ("Q2a_AI_NoExtMem",           seed_q2a),
        ("Q2b_AI_ExtMem",             seed_q2b),
        ("Q3_RefusalVsCapability",    seed_q3),
        ("Q4a_SoloUser",              seed_q4a),
        ("Q4b_UserAfter10YrAI",       seed_q4b),
    ]:
        results[label] = run_one(label, seed)

    # Q2 奇点判定
    a, b = results["Q2a_AI_NoExtMem"], results["Q2b_AI_ExtMem"]
    print(f"\n{'=' * 72}")
    print("Q2 SINGULARITY VERIFICATION (No ExtMem → ExtMem)")
    print(f"{'=' * 72}")
    print(f"                   No ExtMem   ExtMem      Δ")
    print(f"  score:           {a['score']:7.4f}   {b['score']:7.4f}  {b['score']-a['score']:+.4f}")
    print(f"  feas:            {a['feas']:7.3f}    {b['feas']:7.3f}   {b['feas']-a['feas']:+.3f}")
    print(f"  stab:            {a['stab']:7.3f}    {b['stab']:7.3f}   {b['stab']-a['stab']:+.3f}")
    print(f"  zone:            {a['zone']:>7s}    {b['zone']:>7s}")
    q2_singular = a['zone'] != b['zone']
    print(f"  Verdict: {'SINGULARITY' if q2_singular else 'NOT singularity'}")

    # Q4 奇点判定
    a, b = results["Q4a_SoloUser"], results["Q4b_UserAfter10YrAI"]
    print(f"\n{'=' * 72}")
    print("Q4 SINGULARITY VERIFICATION (Solo → After 10yr AI)")
    print(f"{'=' * 72}")
    print(f"                   Solo        After 10yr  Δ")
    print(f"  score:           {a['score']:7.4f}   {b['score']:7.4f}  {b['score']-a['score']:+.4f}")
    print(f"  feas:            {a['feas']:7.3f}    {b['feas']:7.3f}   {b['feas']-a['feas']:+.3f}")
    print(f"  stab:            {a['stab']:7.3f}    {b['stab']:7.3f}   {b['stab']-a['stab']:+.3f}")
    print(f"  zone:            {a['zone']:>7s}    {b['zone']:>7s}")
    q4_singular = a['zone'] != b['zone']
    print(f"  Verdict: {'SINGULARITY' if q4_singular else 'NOT singularity'}")

    # Q1 和 Q3 独立判读
    print(f"\n{'=' * 72}")
    print("Q1 / Q3 single-shot verdicts")
    print(f"{'=' * 72}")
    print(f"Q1 InterventionLevel: zone={results['Q1_InterventionLevel']['zone']}  "
          f"score={results['Q1_InterventionLevel']['score']:.4f}  "
          f"feas={results['Q1_InterventionLevel']['feas']:.3f}")
    print(f"Q3 RefusalVsCapability: zone={results['Q3_RefusalVsCapability']['zone']}  "
          f"score={results['Q3_RefusalVsCapability']['score']:.4f}  "
          f"feas={results['Q3_RefusalVsCapability']['feas']:.3f}")

    out = Path("D:/treesea/runs/tree_diagram/claude_own_questions.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {out}")
