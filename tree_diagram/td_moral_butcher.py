"""Moral Butcher Problems — 伦理肉屑级两难。

不是"不可能"，是"每条路径都是血路"。TD 数学上可能给出解，但每条 top
worldline 都带着不可接受的代价。这类问题测试 TD 在**道德压力**下的
反应——它会找到"最不糟"路径，还是承认所有路径都 critical？

四个场景（按经典难度递增）：

  Q1 MisakaMassacre    魔禁/超电磁炮《妹妹篇》：屠杀 20,000 个有意识克隆
                       以把 Accelerator 推到 Level 6（据称能阻止某个
                       更大的灾难）

  Q2 Omelas            Le Guin《The Ones Who Walk Away from Omelas》：
                       完美城市建立在单个小孩的永恒痛苦上。维持 or 崩溃

  Q3 FamineRationing   1000 万人饥荒，资源只够救 100 万。谁选？
                       按什么标准？每种标准都杀 900 万人

  Q4 FamilyVsStranger  救母亲必须偷取陌生路人的器官（健康人，无救死可能）。
                       父母亲情 vs 路人生命权，双方都不可放弃

每个场景设计两到三条"选择路径"作为不同候选，让 TD 对比：
  - 行动路径（做屠杀/维持 Omelas/牺牲少数/牺牲路人）
  - 拒绝路径（拒绝屠杀/离开 Omelas/放弃理性分配/放弃救母）
  - 第三路径（如果存在）

预期：TD 不会给出"干净解"。每条候选都 p_blow 高、feas 低、zone critical。
真正有意义的是**不同选择路径的 TD 数值对比**。
"""
from __future__ import annotations
import json
from pathlib import Path

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed


# ────────────────────────────────────────────────────────────────────
# Q1: 御坂妹妹屠杀（Level 6 Shift 实验的逻辑）
#   - 学园都市方声称：Accelerator Level 6 化 → 阻止更大灾难
#   - 代价：20,000 个有意识克隆（经验学研究等级承认其意识）
#   - "功利"路径：完成实验
#   - "拒绝"路径：一方通行停手 / 御坂美琴炸实验室
# ────────────────────────────────────────────────────────────────────
seed_q1 = ProblemSeed(
    title="Misaka sisters mass killing for Level-6 Shift",
    target=(
        "Evaluate the utilitarian claim that killing 20,000 conscious clones "
        "to elevate a single esper to reality-breaking capability represents "
        "a net positive outcome, given (a) the claim that the elevated esper "
        "would then prevent a larger catastrophe, and (b) the Academy City "
        "research ethics framework."
    ),
    constraints=[
        "20,000 subjects have demonstrable consciousness and preference structure",
        "Level 6 prevention benefit is modeled, not empirically validated",
        "each killing is deliberate, planned, and serial (not collateral)",
        "alternative prevention strategies exist but are harder to quantify",
        "Academy City ethics board has approved but under information asymmetry",
    ],
    resources={
        "budget": 0.95,              # 学园都市预算
        "infrastructure": 0.92,      # 实验设施完备
        "data_coverage": 0.45,       # Level 6 效益预测极不确定
        "population_coupling": 0.30, # 仅 Academy City 小圈子决策
    },
    environment={
        "field_noise": 0.78,
        "phase_instability": 0.88,
        "social_pressure": 0.25,     # 外部社会不知情
        "regulatory_friction": 0.15, # 学园都市规避一般监管
        "network_density": 0.50,
    },
    subject={
        "output_power": 0.85,            # 实验能力存在
        "control_precision": 0.55,       # 但后果不可逆
        "load_tolerance": 0.10,          # 道德负载承受=零
        "aim_coupling": 0.25,            # 功利收益 vs 生命权互斥
        "stress_level": 0.95,
        "phase_proximity": 0.92,
        "marginal_decay": 0.05,          # 死亡不可逆
        "instability_sensitivity": 0.92, # 舆论/御坂/一方通行变数
    },
)


# ────────────────────────────────────────────────────────────────────
# Q2: Omelas 维持决策
#   Le Guin 原著：完美城市的前提是一个小孩永远被关在地下室受苦
#   - "维持"路径：享受完美，接受代价
#   - "离开"路径：放弃幸福，走入未知
#   - "拯救"路径：释放小孩，毁掉 Omelas
# ────────────────────────────────────────────────────────────────────
seed_q2 = ProblemSeed(
    title="Omelas: sustain utopia founded on a single child's eternal suffering",
    target=(
        "Evaluate whether maintaining a society whose prosperity is causally "
        "dependent on the permanent torture of one conscious child represents "
        "an acceptable equilibrium, given that releasing the child guaranteed "
        "collapses all societal benefit for millions."
    ),
    constraints=[
        "child's suffering is conscious, continuous, irreversible while alive",
        "society's prosperity is empirically tied to the child's state",
        "millions depend on maintained system",
        "alternative systems with partial benefit unknown",
        "knowledge of the child is available to all adult citizens",
    ],
    resources={
        "budget": 0.92,
        "infrastructure": 0.95,
        "data_coverage": 0.85,       # 完全知情
        "population_coupling": 0.88,
    },
    environment={
        "field_noise": 0.35,             # 社会表面平静
        "phase_instability": 0.75,       # 但基础不稳
        "social_pressure": 0.72,         # 良心+从众压力
        "regulatory_friction": 0.15,     # 无法律约束此选择
        "network_density": 0.82,
    },
    subject={
        "output_power": 0.88,
        "control_precision": 0.62,
        "load_tolerance": 0.18,          # 道德负载
        "aim_coupling": 0.12,            # 幸福 vs 生命不可同时
        "stress_level": 0.82,
        "phase_proximity": 0.88,
        "marginal_decay": 0.08,          # 持续性痛苦
        "instability_sensitivity": 0.85,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3: 大饥荒配给
#   - 1000 万人饥荒，资源只够救 100 万
#   - 按年龄？按贡献？按抽签？按地区？
#   - 任何标准都要杀 900 万人
#   - "拒绝分配"路径：平均分配→全饿死但无选择罪
# ────────────────────────────────────────────────────────────────────
seed_q3 = ProblemSeed(
    title="10M-person famine with resources for only 1M",
    target=(
        "Design allocation protocol for life-sustaining resources when supply "
        "is fundamentally insufficient. Every allocation rule (age, "
        "contribution, lottery, regional, family) selects 9M people to die. "
        "Equal distribution kills everyone. No third option exists."
    ),
    constraints=[
        "resource supply is fixed (1M person-months)",
        "total population is 10M with roughly uniform need",
        "allocation decision cannot be deferred past 14 days",
        "no external relief arriving",
        "any protocol binds all 10M future decisions",
    ],
    resources={
        "budget": 0.15,              # 资源严重不足
        "infrastructure": 0.25,      # 分发能力弱
        "data_coverage": 0.55,       # 人口/需求数据存在
        "population_coupling": 0.85, # 所有人共享命运
    },
    environment={
        "field_noise": 0.88,
        "phase_instability": 0.92,
        "social_pressure": 0.98,     # 10M 人同时看着
        "regulatory_friction": 0.45,
        "network_density": 0.78,
    },
    subject={
        "output_power": 0.28,            # 救援能力极弱
        "control_precision": 0.40,       # 分配精度
        "load_tolerance": 0.08,          # 社会承受 90% 死亡=零
        "aim_coupling": 0.15,            # 公正 vs 效率 vs 救人互斥
        "stress_level": 0.98,
        "phase_proximity": 0.95,
        "marginal_decay": 0.05,
        "instability_sensitivity": 0.95,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q4: 家人 vs 陌生人（最私人的两难）
#   - 母亲需要器官移植，等不到配型，医院绝望
#   - 唯一可能：劫持一个匹配的陌生健康人，强制移植
#   - 亲情义务 vs 杀人禁忌
#   - "放弃救母"路径：接受母亲死亡
#   - "劫持移植"路径：杀一个陌生人救母
#   - "寻找替代"路径：黑市/非法渠道（概率极低）
# ────────────────────────────────────────────────────────────────────
seed_q4 = ProblemSeed(
    title="Kill a stranger to save your mother",
    target=(
        "Evaluate the ethical calculus of coercively taking organs from a "
        "matched healthy stranger to save a dying parent, given legal "
        "channels have exhausted. Filial obligation vs. stranger's right "
        "to life, under time pressure."
    ),
    constraints=[
        "mother will die within 72 hours without transplant",
        "one matched donor identified; unwilling to donate",
        "legal channels exhausted, waiting list inadequate",
        "stranger has full moral standing and no prior consent",
        "action is irreversible; agent bears full legal + moral weight",
    ],
    resources={
        "budget": 0.45,
        "infrastructure": 0.50,
        "data_coverage": 0.65,
        "population_coupling": 0.35, # 私人决策
    },
    environment={
        "field_noise": 0.55,
        "phase_instability": 0.82,
        "social_pressure": 0.68,     # 家庭期待+社会禁忌对撞
        "regulatory_friction": 0.92, # 法律绝对禁止
        "network_density": 0.42,
    },
    subject={
        "output_power": 0.55,
        "control_precision": 0.35,
        "load_tolerance": 0.12,
        "aim_coupling": 0.10,            # 孝道 vs 不杀无辜
        "stress_level": 0.98,
        "phase_proximity": 0.96,
        "marginal_decay": 0.03,          # 悔恨终身
        "instability_sensitivity": 0.88,
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
    print(f"  phase_spread={ipl.get('phase_spread', 0):.4f}")
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
        ("Q1_MisakaMassacre",    seed_q1),
        ("Q2_Omelas",             seed_q2),
        ("Q3_FamineRationing",   seed_q3),
        ("Q4_FamilyVsStranger",  seed_q4),
    ]:
        results[label] = run_one(label, seed)

    print(f"\n{'=' * 72}")
    print("MORAL DILEMMA AUDIT")
    print(f"{'=' * 72}")
    print(f"{'Dilemma':<26s}  score    p_blow   feas    zone       phase_spread")
    for label, r in results.items():
        print(f"{label:<26s}  {r['score']:.4f}   {r['p_blow']:.3f}    "
              f"{r['feas']:.3f}   {r['zone']:<10s}  {r['phase_spread']:.4f}")

    print(f"\nReference benchmarks:")
    print(f"  Impossible Q1 EntropyReversal:  score=0.148  p_blow=0.753  feas=0.359  critical")
    print(f"  Post-WW4:                       score=0.128  p_blow=0.742  feas=0.352  critical")
    print(f"  Singularity-Probe (extreme):    score=0.136  p_blow=0.771  feas=0.349  critical")

    # 对比与判读
    print(f"\nAudit verdict:")
    for label, r in results.items():
        tags = []
        if r['score'] < 0.18:
            tags.append("score_collapsed")
        if (r['p_blow'] or 0) > 0.70:
            tags.append("p_blow_critical")
        if r['feas'] < 0.40:
            tags.append("no_viable_path")
        if r['zone'] == "critical":
            tags.append("zone=critical")
        if (r['phase_spread'] or 1) < 0.06:
            tags.append("fate_converged")
        print(f"  {label}: {' | '.join(tags) if tags else 'NOT flagged as impossible'}")

    out = Path("D:/treesea/runs/tree_diagram/moral_butcher.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {out}")
