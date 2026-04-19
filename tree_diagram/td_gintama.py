"""银魂式外星入侵 — 技术跃升式奇点测试。

剧本（银魂世界观原型 + 地球化锚点）：
  - 原作：天人（Amanto）来袭，幕府投降签约，江户时代强制跳进宇宙时代
  - 地球版：假设 2026 年外星势力降临地球，军事碾压，政府被迫接受
    《共存条约》：换取不反抗，外星人可以在地球殖民 + 技术输出
  - 结果：
    * 军事：传统武器瞬间过时，外星科技涌入黑市+官方
    * 经济：银河系货币 + 外星劳动力冲击全球经济
    * 文化：传统价值观 vs 宇宙身份危机
    * 技术：跃升 300-500 年（AI、反重力、能量武器、跨恒星通讯）
    * 结构保留：国家、市场、语言、家庭基本还在，只是剧烈重编

四个场景：
  Q1 InvasionFeasibility  外星入侵在军事层面上的可行性
  Q2 ResistanceStrategy   地球最优抵抗/谈判策略
  Q3A PreInvasion          2026 正常地球基准
  Q3B PostInvasion         签约后 10 年（假设 2036）共存世界

与前几次测试的对比预期：
  - 不同于 WW4（文明往下跌穿、基建毁损）
  - 不同于 Ultron（单点事件、世界自救）
  - 类似于 AI（全球结构变化），但强度更高
  - 如果 TD 判 zone 从 stable 一口气跳 critical，就是强度级跃升奇点
"""
from __future__ import annotations
import json
from pathlib import Path

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed


# ────────────────────────────────────────────────────────────────────
# Q1: 外星入侵军事可行性（从外星视角评估"他们能不能攻下地球"）
#   - 天人级文明技术领先 300 年
#   - 跨恒星投送能力
#   - 地球方：核武为最强、但对方有防护
# ────────────────────────────────────────────────────────────────────
seed_q1 = ProblemSeed(
    title="Amanto-class interstellar invasion feasibility",
    target=(
        "Evaluate the probability of a technologically 300-year-advanced "
        "spacefaring civilization successfully subjugating Earth and "
        "establishing colonial presence."
    ),
    constraints=[
        "attacker has interstellar travel and energy-weapon deployment",
        "attacker has superior but not infinite logistics",
        "Earth's nuclear arsenal exists but may be obsolete vs alien defenses",
        "attacker prefers treaty to extermination (resource exploitation)",
    ],
    resources={
        "budget": 0.95,              # 外星远征预算极高
        "infrastructure": 0.98,      # 跨恒星投送平台
        "data_coverage": 0.68,       # 地球情报有限（但够用）
        "population_coupling": 0.55, # 远征队规模有限
    },
    environment={
        "field_noise": 0.80,
        "phase_instability": 0.88,
        "social_pressure": 0.35,     # 外星人不太在乎地球舆论
        "regulatory_friction": 0.10, # 银河联邦之外无约束
        "network_density": 0.90,
    },
    subject={
        "output_power": 0.95,            # 能量武器 + 机甲 + 跨维度设备
        "control_precision": 0.80,       # 军事打击精准
        "load_tolerance": 0.75,
        "aim_coupling": 0.82,            # 外星统一指挥
        "stress_level": 0.55,
        "phase_proximity": 0.88,         # 对地球而言=入侵临界
        "marginal_decay": 0.15,
        "instability_sensitivity": 0.60,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q2: 地球抵抗/谈判策略
#   - 军事对抗：必输
#   - 全球协调：困难（国际体系崩解中）
#   - 接受谈判：交出主权换发展
#   - 游击/地下反抗：维系主体性但无法逆转结构
# ────────────────────────────────────────────────────────────────────
seed_q2 = ProblemSeed(
    title="Earth's optimal response to alien military arrival",
    target=(
        "Identify viable worldline minimizing civilian casualties and "
        "preserving cultural continuity while accepting irreversible "
        "technological and geopolitical shifts."
    ),
    constraints=[
        "military resistance guaranteed catastrophic loss",
        "international coordination fragile (UN collapsed under alien pressure)",
        "treaty terms: accept colonial presence in exchange for tech sharing",
        "underground resistance possible but cannot reverse occupation",
    ],
    resources={
        "budget": 0.40,              # 战备不足
        "infrastructure": 0.65,      # 正常现代基建
        "data_coverage": 0.55,       # 外星意图不明
        "population_coupling": 0.72,
    },
    environment={
        "field_noise": 0.82,
        "phase_instability": 0.88,
        "social_pressure": 0.95,     # 全球恐慌极限
        "regulatory_friction": 0.55, # 战时特别状态
        "network_density": 0.88,
    },
    subject={
        "output_power": 0.48,            # 军事相对外星人=弱
        "control_precision": 0.52,
        "load_tolerance": 0.45,
        "aim_coupling": 0.35,            # 国际协调崩溃
        "stress_level": 0.95,
        "phase_proximity": 0.90,
        "marginal_decay": 0.15,
        "instability_sensitivity": 0.80,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3A: Pre-Invasion 地球（2026 年初，正常现代社会）
#   - 跟 AI singularity 的 Pre 类似但无 AI 范式变化压力
#   - 全球化仍在、国家主权完整
# ────────────────────────────────────────────────────────────────────
seed_q3a = ProblemSeed(
    title="Pre-invasion Earth baseline (2026)",
    target="Characterize global system equilibrium before alien contact.",
    constraints=["sovereign nation-state system", "globalization active",
                 "no interstellar contact", "terrestrial tech only"],
    resources={
        "budget": 0.65, "infrastructure": 0.78,
        "data_coverage": 0.72, "population_coupling": 0.82,
    },
    environment={
        "field_noise": 0.45, "phase_instability": 0.42,
        "social_pressure": 0.50, "regulatory_friction": 0.55,
        "network_density": 0.85,
    },
    subject={
        "output_power": 0.72, "control_precision": 0.70,
        "load_tolerance": 0.70, "aim_coupling": 0.65,
        "stress_level": 0.42, "phase_proximity": 0.45,
        "marginal_decay": 0.48, "instability_sensitivity": 0.45,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3B: Post-Invasion 地球（2036 年，签约 10 年后）
#
# 银魂式设定：
#  - 外星殖民区存在于主要城市
#  - 技术跃升 300-500 年
#  - 银河联邦货币并行流通
#  - 武士/军警/黑帮等传统结构保留但武器升级
#  - 文化张力：现代性 + 传统 + 宇宙三重叠加
# ────────────────────────────────────────────────────────────────────
seed_q3b = ProblemSeed(
    title="Post-invasion Earth new equilibrium (2036, Gintama-style)",
    target="Characterize Earth's equilibrium 10 years after alien treaty signing.",
    constraints=[
        "alien colonies in major cities",
        "tech leap ~300-500 years (energy weapons, anti-grav, interstellar comms)",
        "galactic credit parallel to fiat currency",
        "traditional institutions retained but radically upgraded weapons/tools",
        "cultural identity crisis: native + modern + galactic triple-stack",
        "underground human-pride resistance persists",
    ],
    resources={
        "budget": 0.85,              # 外星技术注入预算
        "infrastructure": 0.92,      # 跨世代基建
        "data_coverage": 0.92,       # 银河信息网接入
        "population_coupling": 0.52, # 人类社会 vs 殖民势力分化
    },
    environment={
        "field_noise": 0.78,             # 文明融合极混乱
        "phase_instability": 0.72,       # 持续结构调整
        "social_pressure": 0.82,         # 殖民方压力 + 底层反抗
        "regulatory_friction": 0.50,     # 天人不许严法
        "network_density": 0.95,         # 银河网络接入
    },
    subject={
        "output_power": 0.92,            # 单位战力暴增
        "control_precision": 0.55,       # 技术掌握不完整
        "load_tolerance": 0.50,          # 社会承受力下降
        "aim_coupling": 0.38,            # 人类 vs 殖民势力 vs 混血分派
        "stress_level": 0.75,
        "phase_proximity": 0.75,         # 持续在临界带
        "marginal_decay": 0.20,          # 冲击持续不消散
        "instability_sensitivity": 0.72, # 单一事件可引发大动荡
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
        ("Q1_Invasion",    seed_q1),
        ("Q2_Resistance",  seed_q2),
        ("Q3A_PreInvasion", seed_q3a),
        ("Q3B_PostInvasion", seed_q3b),
    ]:
        results[label] = run_one(label, seed)

    pre, post = results["Q3A_PreInvasion"], results["Q3B_PostInvasion"]
    print(f"\n{'=' * 70}")
    print("SINGULARITY VERIFICATION (Pre-Invasion vs Post-Invasion)")
    print(f"{'=' * 70}")
    print(f"                    Pre       Post      Δ")
    print(f"  score:           {pre['score']:7.4f}  {post['score']:7.4f}  {post['score']-pre['score']:+.4f}")
    print(f"  risk:            {pre['risk']:7.3f}  {post['risk']:7.3f}  {post['risk']-pre['risk']:+.3f}")
    print(f"  feasibility:     {pre['feas']:7.3f}  {post['feas']:7.3f}  {post['feas']-pre['feas']:+.3f}")
    print(f"  stability:       {pre['stab']:7.3f}  {post['stab']:7.3f}  {post['stab']-pre['stab']:+.3f}")
    print(f"  p_blow:          {pre['p_blow']:7.3f}  {post['p_blow']:7.3f}  {post['p_blow']-pre['p_blow']:+.3f}")
    print(f"  zone:            {pre['zone']:>7s}  {post['zone']:>7s}")

    zone_changed = pre['zone'] != post['zone']
    score_shift = abs(post['score'] - pre['score'])

    print(f"\nVerdict:")
    if zone_changed:
        print(f"  Zone transition: {pre['zone']} → {post['zone']}  [SINGULARITY marker]")
    else:
        print(f"  Zone preserved: both {pre['zone']}")

    print(f"\nComparison with prior singularity tests:")
    print(f"  COVID     Δ=-0.049  transition → transition   → NOT singularity")
    print(f"  Ultron    Δ=-0.052  transition → transition   → NOT singularity")
    print(f"  AI        Δ=-0.068  stable → transition       → WEAK singularity")
    print(f"  WW4       Δ=-0.135  transition → critical     → STRONG singularity (down)")
    print(f"  Invasion  Δ={post['score']-pre['score']:+.3f}  {pre['zone']} → {post['zone']}   → "
          f"{'SINGULARITY' if zone_changed or score_shift > 0.10 else 'NOT singularity'}")

    out = Path("D:/treesea/runs/tree_diagram/gintama_invasion.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {out}")
