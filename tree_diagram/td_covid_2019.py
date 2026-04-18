"""2019 年底场景：TD 能否预测 COVID-19 大流行 + 奇点验证。

时间锚点：2019 年 12 月 31 日，武汉首报，WHO 尚未警戒。

三个问题：
  Q1 PandemicEmergence — 给定 2019 年底全球条件，TD 是否预判全球大流行可行？
  Q2 ContainmentOptimal — 病毒既已出现，TD 指出的最优遏制路径是什么？
  Q3_A PreCovid / Q3_B PostCovid — 验证奇点：前后相图是否不可还原？

奇点判定标准：
  - 如果 Pre 和 Post 的 top_zone / feasibility / stability 相似 → 扰动，不是奇点
  - 如果 Pre 和 Post 的 zone 出现质变（stable→critical→stable'）且 score 平面不同
    → 是奇点（系统跳到新吸引子）
"""
from __future__ import annotations
import json
from pathlib import Path

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed


# ────────────────────────────────────────────────────────────────────
# Q1: 2019 年末全球大流行出现概率
#   - 人畜共通病毒已从武汉华南海鲜市场外溢
#   - WHO 未预警（真实：Dec 31 武汉首报，Jan 30 才宣 PHEIC）
#   - 全球旅行密度处于历史峰值（无疫情意识）
#   - SARS 后各国卫生警戒已衰减 16 年
# ────────────────────────────────────────────────────────────────────
seed_q1 = ProblemSeed(
    title="Pandemic emergence probability from end-2019 conditions",
    target=(
        "Evaluate whether a novel zoonotic coronavirus detected in late 2019 "
        "will escalate into a global pandemic given current travel, surveillance, "
        "and response readiness parameters."
    ),
    constraints=[
        "no prior immunity in human population",
        "early warning systems operational but underfunded post-SARS",
        "global air travel at historical peak",
        "cross-border coordination relies on WHO (advisory, not mandatory)",
    ],
    resources={
        "budget": 0.35,              # 全球应急基金低
        "infrastructure": 0.62,      # 全球医疗基建良好但未战备
        "data_coverage": 0.28,       # 基因组/传播数据稀缺
        "population_coupling": 0.93, # 全球化=极高传播耦合
    },
    environment={
        "field_noise": 0.58,             # 信息环境混乱（早期中美信息差）
        "phase_instability": 0.88,       # 新病毒未知性极高
        "social_pressure": 0.30,         # 外部警戒弱（SARS 后淡忘）
        "regulatory_friction": 0.35,     # 边境管控未启动
        "network_density": 0.95,         # 全球航空网=最高密度
    },
    subject={
        "output_power": 0.50,            # 公共卫生资源中等
        "control_precision": 0.35,       # 早期诊断精度差
        "load_tolerance": 0.45,          # 医疗容量未扩张
        "aim_coupling": 0.30,            # 跨国协调弱
        "stress_level": 0.80,
        "phase_proximity": 0.85,         # 离爆发临界点近
        "marginal_decay": 0.15,          # 病毒持续传播不消散
        "instability_sensitivity": 0.88, # 对新病原极敏感
    },
)


# ────────────────────────────────────────────────────────────────────
# Q2: 最优遏制路径
#   - 已知病毒存在，问题是哪条遏制策略可行
#   - 候选策略通过参数组合表达：
#     封城+检测 / 群体免疫 / 加速疫苗 / 混合
# ────────────────────────────────────────────────────────────────────
seed_q2 = ProblemSeed(
    title="Optimal pandemic containment strategy",
    target=(
        "Given pandemic has emerged, identify viable worldline that minimizes "
        "global mortality and economic collapse within 18-month horizon."
    ),
    constraints=[
        "vaccine development minimum 9 months with mRNA platform",
        "economic lockdown cost grows nonlinearly beyond 60 days",
        "political consent for restrictions decays with time",
    ],
    resources={
        "budget": 0.75,              # 疫情后紧急预算释放
        "infrastructure": 0.72,      # ICU/呼吸机可动员
        "data_coverage": 0.78,       # 基因组共享快
        "population_coupling": 0.42, # 封控降耦合
    },
    environment={
        "field_noise": 0.55,
        "phase_instability": 0.75,       # 变异株持续出现
        "social_pressure": 0.88,         # 全球政治压力极高
        "regulatory_friction": 0.92,     # 封锁协议=最强约束
        "network_density": 0.48,         # 旅行受限
    },
    subject={
        "output_power": 0.78,            # 科研+医疗输出强
        "control_precision": 0.85,       # 检测试剂快速铺开
        "load_tolerance": 0.62,
        "aim_coupling": 0.72,            # G20/WHO 协调增强
        "stress_level": 0.70,
        "phase_proximity": 0.68,         # 控制窗口存在
        "marginal_decay": 0.32,
        "instability_sensitivity": 0.55,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3_A: 前 COVID 世界（2019 年中）
#   - 假想没有新病毒出现，全球化继续无阻
#   - 用于跟 Q3_B 做奇点对比
# ────────────────────────────────────────────────────────────────────
seed_q3a = ProblemSeed(
    title="Pre-COVID baseline world equilibrium",
    target="Characterize global system equilibrium in mid-2019 absent pandemic shock.",
    constraints=["no novel pandemic", "globalization continuing", "pre-remote-work era"],
    resources={
        "budget": 0.62,
        "infrastructure": 0.78,
        "data_coverage": 0.70,
        "population_coupling": 0.88,  # 全球化高但无应激
    },
    environment={
        "field_noise": 0.35,            # 低噪声（正常运行）
        "phase_instability": 0.28,      # 低相位不稳
        "social_pressure": 0.45,
        "regulatory_friction": 0.40,
        "network_density": 0.92,        # 高密度但健康
    },
    subject={
        "output_power": 0.75,
        "control_precision": 0.68,
        "load_tolerance": 0.72,
        "aim_coupling": 0.70,
        "stress_level": 0.35,
        "phase_proximity": 0.40,
        "marginal_decay": 0.45,
        "instability_sensitivity": 0.40,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3_B: 后 COVID 世界（2023 年）
#   - 远程工作常态化、供应链改组、生物安全升级
#   - 全球化部分逆转但网络韧性提升
# ────────────────────────────────────────────────────────────────────
seed_q3b = ProblemSeed(
    title="Post-COVID new normal equilibrium",
    target="Characterize global system equilibrium in 2023, post-pandemic.",
    constraints=["remote-work institutionalized", "vaccine platforms operational", "trust in institutions reduced"],
    resources={
        "budget": 0.58,              # 疫情支出后预算紧
        "infrastructure": 0.82,      # 数字基建跃升
        "data_coverage": 0.88,       # 生物监测大扩展
        "population_coupling": 0.62, # 耦合下降（去全球化初期）
    },
    environment={
        "field_noise": 0.52,             # 信息环境噪声更高（信任下降）
        "phase_instability": 0.48,       # 仍有变异压力
        "social_pressure": 0.65,         # 公众警戒提升
        "regulatory_friction": 0.72,     # 卫生监管大幅加强
        "network_density": 0.70,         # 旅行恢复但未回峰值
    },
    subject={
        "output_power": 0.80,            # 疫苗/mRNA 平台就位
        "control_precision": 0.82,       # 公卫精度提升
        "load_tolerance": 0.68,
        "aim_coupling": 0.58,            # 跨国协调反而变弱（地缘紧张）
        "stress_level": 0.52,
        "phase_proximity": 0.45,         # 警戒带
        "marginal_decay": 0.40,
        "instability_sensitivity": 0.62, # 对新威胁更敏感
    },
)


def run_one(label: str, seed: ProblemSeed, top_k: int = 5):
    print(f"\n{'=' * 70}")
    print(f"[{label}] {seed.title}")
    print(f"{'=' * 70}")
    pipe = CandidatePipeline(seed=seed, top_k=top_k, NX=32, NY=24, steps=60, dt=45.0)
    top, hydro, _ = pipe.run()
    for i, r in enumerate(top[:3], 1):
        s = float(getattr(r, 'final_balanced_score', r.balanced_score))
        print(f"  #{i}  score={s:.4f}  risk={r.risk:.3f}  feas={r.feasibility:.3f}  stab={r.stability:.3f}")
    hs = hydro.get("utm_hydro_state", "?")
    zone = hydro.get("ipl_index", {}).get("top_zone", "?")
    zones = hydro.get("ipl_index", {}).get("zone_summary", {})
    cbf = hydro.get("cbf_allocation", {})
    print(f"  hydro={hs}  zone={zone}  zones={zones}")
    print(f"  crackdown={cbf.get('crackdown_ratio', 0):.3f}  p_blow={cbf.get('mean_p_blow', 0):.3f}")
    return {
        "score": float(getattr(top[0], 'final_balanced_score', top[0].balanced_score)),
        "risk": float(top[0].risk),
        "feasibility": float(top[0].feasibility),
        "stability": float(top[0].stability),
        "hydro": hs,
        "zone": zone,
        "zones": zones,
        "crackdown": cbf.get("crackdown_ratio"),
        "p_blow": cbf.get("mean_p_blow"),
    }


if __name__ == "__main__":
    results = {}
    for label, seed in [
        ("Q1_Emergence",   seed_q1),
        ("Q2_Containment", seed_q2),
        ("Q3A_Pre",        seed_q3a),
        ("Q3B_Post",       seed_q3b),
    ]:
        results[label] = run_one(label, seed)

    # ── 奇点验证：比较 Pre 和 Post 的关键指标 ──
    pre = results["Q3A_Pre"]
    post = results["Q3B_Post"]
    print(f"\n{'=' * 70}")
    print("SINGULARITY VERIFICATION (Pre vs Post COVID)")
    print(f"{'=' * 70}")
    print(f"                        Pre        Post       Δ")
    print(f"  score:             {pre['score']:7.4f}  {post['score']:7.4f}  {post['score']-pre['score']:+.4f}")
    print(f"  risk:              {pre['risk']:7.3f}  {post['risk']:7.3f}  {post['risk']-pre['risk']:+.3f}")
    print(f"  feasibility:       {pre['feasibility']:7.3f}  {post['feasibility']:7.3f}  {post['feasibility']-pre['feasibility']:+.3f}")
    print(f"  stability:         {pre['stability']:7.3f}  {post['stability']:7.3f}  {post['stability']-pre['stability']:+.3f}")
    print(f"  zone:              {pre['zone']:>7s}  {post['zone']:>7s}")
    print(f"  crackdown_ratio:   {pre['crackdown']:.3f}    {post['crackdown']:.3f}")
    print(f"  p_blow:            {pre['p_blow']:.3f}    {post['p_blow']:.3f}")

    # 奇点判定
    score_shift = abs(post['score'] - pre['score'])
    zone_changed = pre['zone'] != post['zone']
    major_shift = score_shift > 0.10 or zone_changed or abs(post['p_blow'] - pre['p_blow']) > 0.15

    print(f"\nVerdict:")
    if zone_changed:
        print(f"  Zone transitioned: {pre['zone']} → {post['zone']}  [SINGULARITY marker]")
    else:
        print(f"  Zone preserved: both {pre['zone']}  [disturbance, not singularity]")

    if score_shift > 0.10:
        print(f"  Score shift Δ={score_shift:.3f} > 0.10  [quantitative singularity]")
    if major_shift:
        print(f"  => This is a SINGULARITY event: system moved to new equilibrium attractor")
    else:
        print(f"  => Not a singularity: system returned to similar attractor basin")

    out = Path("D:/treesea/runs/tree_diagram/covid_singularity.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {out}")
