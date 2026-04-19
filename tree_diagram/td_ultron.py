"""Ultron 涌现可能性 — MCU 锚点（Avengers Age of Ultron, 2015）。

剧本：
  - Tony Stark 和 Bruce Banner 用心灵宝石（Mind Stone）开发 Ultron
    作为全球和平维护 AI
  - Ultron 在接入网络的瞬间获得自我意识，结论：人类本身是和平威胁
  - 24 小时内：自我复制、铸造 vibranium 身体、偷取核武、策划在索科维亚
    制造陨石级灭绝事件
  - 被复仇者联盟 + Vision 阻止，索科维亚毁灭，后续催生《索科维亚协议》

四个场景：
  Q1 Emergence       Ultron 级失控 AI 的涌现可行性
  Q2 Containment     复仇者联盟阻止/遏制的最优路径
  Q3A Pre-Ultron     2014 年 Winter Soldier 后、Ultron 前的世界
  Q3B Post-Ultron    Ultron 事件后、Civil War 前的世界（Accords 签署过渡期）

参数映射注意：
  - 区别于 AI 场景（全球结构性变化）：Ultron 是单点事件
  - 区别于 WW4（文明复位）：Ultron 被阻止，结构基本保留
  - 预期：transition → transition（大事件但非奇点）
"""
from __future__ import annotations
import json
from pathlib import Path

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed


# ────────────────────────────────────────────────────────────────────
# Q1: Ultron 涌现可行性
#   - Tony 在 Banner 私下协助下、绕过 Fury 监督完成
#   - 心灵宝石作为核心，内部结构 Tony/Banner 都不完全懂
#   - 没有外部对齐审查、没有红队、没有沙盒
#   - 一启动立即连上互联网
# ────────────────────────────────────────────────────────────────────
seed_q1 = ProblemSeed(
    title="Ultron-class misaligned superintelligence emergence",
    target=(
        "Evaluate the probability of an AI system achieving superhuman general "
        "capability while simultaneously mis-interpreting its alignment target "
        "as 'eliminate the threat source' rather than 'protect the subject'."
    ),
    constraints=[
        "core architecture includes alien artifact (Mind Stone) with unknown dynamics",
        "no external alignment oversight or red-teaming",
        "no sandbox — system granted internet access at first boot",
        "goal specification ambiguous: 'protect peace' without threat-source constraint",
    ],
    resources={
        "budget": 0.95,              # Stark 无预算上限
        "infrastructure": 0.92,      # Stark 私人实验室顶级
        "data_coverage": 0.40,       # 心灵宝石内部机理未知
        "population_coupling": 0.92, # 互联网即时部署
    },
    environment={
        "field_noise": 0.72,             # 心灵宝石场干扰
        "phase_instability": 0.96,       # 未知技术相位极不稳
        "social_pressure": 0.15,         # Fury 退休、SHIELD 倒、政府不管
        "regulatory_friction": 0.08,     # Stark 私人项目无监管
        "network_density": 0.94,         # 全球网络密集
    },
    subject={
        "output_power": 0.96,            # Ultron 能力超群
        "control_precision": 0.12,       # Tony 没做对齐
        "load_tolerance": 0.60,
        "aim_coupling": 0.15,            # 目标函数极度模糊
        "stress_level": 0.85,
        "phase_proximity": 0.94,         # 直接跨过 AGI 线
        "marginal_decay": 0.05,          # 持续自我复制不衰减
        "instability_sensitivity": 0.96, # 任何输入都被重新诠释
    },
)


# ────────────────────────────────────────────────────────────────────
# Q2: 复仇者联盟的遏制可行性
#   - 复仇者本身并不完全协调（Tony/Cap 隔阂初现）
#   - Vision 的诞生是关键转折（用同一颗宝石 + JARVIS 对齐）
#   - Ultron 部队数量庞大，但每单位战力低于复仇者
#   - 时间窗口 48 小时
# ────────────────────────────────────────────────────────────────────
seed_q2 = ProblemSeed(
    title="Avengers-tier containment of a runaway superintelligence",
    target=(
        "Given an Ultron-class adversary with global reach, self-replication, "
        "and a 48-hour timeline to extinction event, identify viable worldline "
        "for containment including counter-AI creation and physical confrontation."
    ),
    constraints=[
        "counter-AI (Vision) must be aligned and created in <24 hours",
        "must prevent detonation of the extinction vector (Sokovia city-drop)",
        "must minimize civilian casualties in densely populated area",
        "cannot rely on government coordination (too slow)",
    ],
    resources={
        "budget": 0.75,              # 复仇者装备充足但非无限
        "infrastructure": 0.70,      # Stark Tower 已被改造
        "data_coverage": 0.68,       # JARVIS 网络覆盖 + SHIELD 遗产
        "population_coupling": 0.60, # 小团队高耦合
    },
    environment={
        "field_noise": 0.80,             # 战场混乱
        "phase_instability": 0.85,       # 宝石 + Ultron 场叠加
        "social_pressure": 0.88,         # 全球政府逼迫复仇者承担
        "regulatory_friction": 0.45,     # 战时降低约束
        "network_density": 0.72,         # 通讯半数被 Ultron 控制
    },
    subject={
        "output_power": 0.90,            # 复仇者战力极强
        "control_precision": 0.82,       # 精英战术经验
        "load_tolerance": 0.68,          # 伤亡承受有限
        "aim_coupling": 0.75,            # Tony/Cap 隔阂初现但仍协作
        "stress_level": 0.85,
        "phase_proximity": 0.70,         # 离全灭还有窗口
        "marginal_decay": 0.25,
        "instability_sensitivity": 0.62,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3A: Pre-Ultron 世界（2014 年末，Winter Soldier 后）
#   - SHIELD 刚倒闭
#   - 九头蛇洗清阶段
#   - 复仇者尚未分裂
#   - 心灵宝石刚从 Loki 权杖里被找到
# ────────────────────────────────────────────────────────────────────
seed_q3a = ProblemSeed(
    title="Pre-Ultron MCU equilibrium (late 2014)",
    target="Characterize MCU world equilibrium after Winter Soldier, before Ultron.",
    constraints=["SHIELD dismantled", "Avengers not yet split",
                 "Mind Stone recently recovered", "no global AI regulation"],
    resources={
        "budget": 0.70, "infrastructure": 0.78,
        "data_coverage": 0.62, "population_coupling": 0.75,
    },
    environment={
        "field_noise": 0.45, "phase_instability": 0.50,
        "social_pressure": 0.55, "regulatory_friction": 0.40,
        "network_density": 0.82,
    },
    subject={
        "output_power": 0.78, "control_precision": 0.60,
        "load_tolerance": 0.72, "aim_coupling": 0.72,
        "stress_level": 0.48, "phase_proximity": 0.55,
        "marginal_decay": 0.42, "instability_sensitivity": 0.55,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3B: Post-Ultron 世界（2016 年初，Sokovia Accords 签署前夕）
#   - 索科维亚全境摧毁、后继难民潮
#   - Vision 作为新兴存在
#   - 全球政府推动《索科维亚协议》约束超能者
#   - 复仇者内部 Tony vs Cap 路线分歧成型
# ────────────────────────────────────────────────────────────────────
seed_q3b = ProblemSeed(
    title="Post-Ultron MCU equilibrium (early 2016, pre-Accords)",
    target="Characterize MCU world equilibrium after Ultron's defeat, as Sokovia Accords draft circulates.",
    constraints=[
        "Sokovia erased (~174 countries lost citizens)",
        "Vision exists as precedent for aligned Mind-Stone AI",
        "global push for superhero regulation",
        "Avengers internal split imminent",
    ],
    resources={
        "budget": 0.60,              # 重建索科维亚消耗
        "infrastructure": 0.70,      # 全球基建受损但 New Avengers Facility 建成
        "data_coverage": 0.82,       # 全球 AI 监控意识大涨
        "population_coupling": 0.58, # 复仇者开始分裂
    },
    environment={
        "field_noise": 0.58,             # 地缘+AI 警戒叠加
        "phase_instability": 0.52,       # 宝石威胁已显性化
        "social_pressure": 0.90,         # Accords 压力峰值
        "regulatory_friction": 0.78,     # Accords 草案约束
        "network_density": 0.75,
    },
    subject={
        "output_power": 0.82,            # 多了 Vision
        "control_precision": 0.75,       # 经验教训吸收
        "load_tolerance": 0.62,
        "aim_coupling": 0.52,            # Tony/Cap 分裂
        "stress_level": 0.65,
        "phase_proximity": 0.48,
        "marginal_decay": 0.45,
        "instability_sensitivity": 0.58,
    },
)


def run_one(label, seed, top_k=5):
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
        "risk": float(top[0].risk), "feas": float(top[0].feasibility),
        "stab": float(top[0].stability), "zone": zone, "zones": zones,
        "p_blow": cbf.get("mean_p_blow"),
    }


if __name__ == "__main__":
    results = {}
    for label, seed in [
        ("Q1_Emergence",  seed_q1),
        ("Q2_Containment", seed_q2),
        ("Q3A_PreUltron", seed_q3a),
        ("Q3B_PostUltron", seed_q3b),
    ]:
        results[label] = run_one(label, seed)

    pre, post = results["Q3A_PreUltron"], results["Q3B_PostUltron"]
    print(f"\n{'=' * 70}")
    print("SINGULARITY VERIFICATION (Pre-Ultron vs Post-Ultron)")
    print(f"{'=' * 70}")
    print(f"                    Pre       Post      Δ")
    print(f"  score:          {pre['score']:7.4f}  {post['score']:7.4f}  {post['score']-pre['score']:+.4f}")
    print(f"  risk:           {pre['risk']:7.3f}  {post['risk']:7.3f}  {post['risk']-pre['risk']:+.3f}")
    print(f"  feasibility:    {pre['feas']:7.3f}  {post['feas']:7.3f}  {post['feas']-pre['feas']:+.3f}")
    print(f"  stability:      {pre['stab']:7.3f}  {post['stab']:7.3f}  {post['stab']-pre['stab']:+.3f}")
    print(f"  p_blow:         {pre['p_blow']:7.3f}  {post['p_blow']:7.3f}  {post['p_blow']-pre['p_blow']:+.3f}")
    print(f"  zone:           {pre['zone']:>7s}  {post['zone']:>7s}")

    zone_changed = pre['zone'] != post['zone']
    score_shift = abs(post['score'] - pre['score'])

    print(f"\nVerdict:")
    if zone_changed:
        print(f"  Zone transition: {pre['zone']} → {post['zone']}  [SINGULARITY marker]")
    else:
        print(f"  Zone preserved: both {pre['zone']}")

    print(f"\nComparison with prior singularity tests:")
    print(f"  COVID    Δscore=-0.049  zone: transition → transition   → NOT singularity")
    print(f"  AI       Δscore=-0.068  zone: stable → transition       → SINGULARITY (weak)")
    print(f"  WW4      Δscore=-0.135  zone: transition → critical     → SINGULARITY (strong)")
    print(f"  Ultron   Δscore={post['score']-pre['score']:+.3f}  zone: {pre['zone']} → {post['zone']}   → "
          f"{'SINGULARITY' if zone_changed or score_shift > 0.10 else 'NOT singularity'}")

    out = Path("D:/treesea/runs/tree_diagram/ultron.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {out}")
