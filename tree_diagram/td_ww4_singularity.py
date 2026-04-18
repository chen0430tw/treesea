"""第四次世界大战 — 教科书级奇点测试。

Einstein: "I know not with what weapons World War III will be fought,
           but World War IV will be fought with sticks and stones."

WW4 = 核交换 + 工业文明崩溃 + 信息网络解体 + 人口折减。
这是最硬的奇点场景——如果 TD 这都说不是奇点，说明奇点阈值门控过严。

四个场景：
  Q1 WW3_Emergence      2026 锚点，WW3 爆发可行性
  Q2 WW3_Containment    最优避免路径
  Q3A Pre-WW3           2026 正常世界基准
  Q3B Post-WW4          文明复位后的新均衡
"""
from __future__ import annotations
import json
from pathlib import Path

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed


# ────────────────────────────────────────────────────────────────────
# Q1: WW3 爆发动力学（2026 锚点）
#   - 俄乌持续 + 中东多线开火 + 台海压力 + 朝鲜核武扩张
#   - 核威慑仍有效但红线多、误判空间大
#   - 全球经济脱钩加速，战略物资囤积
# ────────────────────────────────────────────────────────────────────
seed_q1 = ProblemSeed(
    title="WW3 emergence trajectory 2026",
    target=(
        "Evaluate probability of Third World War triggering nuclear exchange "
        "within 24-month horizon given current geopolitical conditions."
    ),
    constraints=[
        "multiple active regional conflicts (Ukraine, Middle East, Taiwan)",
        "nuclear arsenals modernized in all major powers",
        "strategic ambiguity on red lines erodes deterrence",
        "economic decoupling accelerates",
    ],
    resources={
        "budget": 0.90,              # 军费占比史上峰值
        "infrastructure": 0.75,      # 全球产业链已受损
        "data_coverage": 0.70,       # 情报能力强但高度竞争
        "population_coupling": 0.85, # 全球经济仍高度耦合
    },
    environment={
        "field_noise": 0.85,             # 信息战+假信息峰值
        "phase_instability": 0.92,       # 多极系统最不稳定
        "social_pressure": 0.80,         # 国内动员压力极高
        "regulatory_friction": 0.35,     # 国际法框架崩解中
        "network_density": 0.90,         # 军事同盟高度网络化
    },
    subject={
        "output_power": 0.88,            # 核+常规军力史上最强
        "control_precision": 0.40,       # 误判空间极大
        "load_tolerance": 0.55,
        "aim_coupling": 0.25,            # 大国协调失效
        "stress_level": 0.88,
        "phase_proximity": 0.85,         # 离核交换极近
        "marginal_decay": 0.12,          # 紧张持续不消散
        "instability_sensitivity": 0.92, # 单一事件可触发升级
    },
)


# ────────────────────────────────────────────────────────────────────
# Q2: 最优避免策略
# ────────────────────────────────────────────────────────────────────
seed_q2 = ProblemSeed(
    title="Optimal WW3 avoidance strategy",
    target=(
        "Identify worldline minimizing probability of nuclear exchange "
        "while preserving territorial integrity of major powers."
    ),
    constraints=[
        "no side willing to accept existential defeat",
        "credible deterrence required for stability",
        "back-channel diplomacy degraded post-2022",
    ],
    resources={
        "budget": 0.70,
        "infrastructure": 0.72,
        "data_coverage": 0.82,
        "population_coupling": 0.55,
    },
    environment={
        "field_noise": 0.60,
        "phase_instability": 0.75,
        "social_pressure": 0.90,
        "regulatory_friction": 0.72,
        "network_density": 0.68,
    },
    subject={
        "output_power": 0.72,
        "control_precision": 0.68,
        "load_tolerance": 0.55,
        "aim_coupling": 0.52,
        "stress_level": 0.80,
        "phase_proximity": 0.70,
        "marginal_decay": 0.30,
        "instability_sensitivity": 0.62,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3A: Pre-WW3 世界（2026 正常基准）
# ────────────────────────────────────────────────────────────────────
seed_q3a = ProblemSeed(
    title="Pre-WW3 baseline equilibrium (2026)",
    target="Characterize pre-war global equilibrium.",
    constraints=["nuclear deterrence stable",
                 "UN framework operational",
                 "global trade active"],
    resources={
        "budget": 0.65, "infrastructure": 0.78,
        "data_coverage": 0.72, "population_coupling": 0.82,
    },
    environment={
        "field_noise": 0.48, "phase_instability": 0.45,
        "social_pressure": 0.55, "regulatory_friction": 0.58,
        "network_density": 0.85,
    },
    subject={
        "output_power": 0.75, "control_precision": 0.70,
        "load_tolerance": 0.70, "aim_coupling": 0.65,
        "stress_level": 0.50, "phase_proximity": 0.48,
        "marginal_decay": 0.42, "instability_sensitivity": 0.50,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3B: Post-WW4 世界（文明复位后）
#
# 爱因斯坦的 WW4 定义：WW3 毁了工业文明，WW4 用石头和木棍打。
# 参数设计：工业基础设施 90%+ 被毁、信息网络解体、人口折损 30-50%
# ────────────────────────────────────────────────────────────────────
seed_q3b = ProblemSeed(
    title="Post-WW4 civilizational reset equilibrium",
    target="Characterize human civilization equilibrium after nuclear exchange + industrial collapse.",
    constraints=[
        "global population reduced by 30-50%",
        "industrial capacity destroyed or regressed to pre-1850 level",
        "global information networks collapsed",
        "food/water/medical supply chains broken",
        "no central governments in most regions",
        "nuclear winter reducing agriculture 40-70%",
    ],
    resources={
        "budget": 0.03,              # 几乎没有经济余量
        "infrastructure": 0.08,      # 基建被毁
        "data_coverage": 0.02,       # 信息网络崩溃
        "population_coupling": 0.88, # 幸存者高度依赖彼此但仅本地
    },
    environment={
        "field_noise": 0.98,             # 混乱拉满
        "phase_instability": 0.95,       # 没有任何稳定机制
        "social_pressure": 0.05,         # 无国家无机构
        "regulatory_friction": 0.02,     # 无法律无约束
        "network_density": 0.08,         # 全球网络基本没了
    },
    subject={
        "output_power": 0.15,            # 生产力降到前工业
        "control_precision": 0.05,       # 无组织能力
        "load_tolerance": 0.12,          # 饥荒+疾病+辐射
        "aim_coupling": 0.08,            # 无全球协调
        "stress_level": 0.98,
        "phase_proximity": 0.88,         # 接近物种存续临界
        "marginal_decay": 0.08,          # 创伤不消散
        "instability_sensitivity": 0.95, # 任何小事件都致命
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
    ipl = hydro.get("ipl_index", {})
    print(f"  hydro={hs}  zone={zone}  zones={zones}")
    print(f"  crackdown={cbf.get('crackdown_ratio', 0):.3f}  p_blow={cbf.get('mean_p_blow', 0):.3f}")
    print(f"  phase_spread={ipl.get('phase_spread', 0):.4f}  "
          f"gain_centroid={ipl.get('smoothed_gain_centroid', 0):.4f}")
    return {
        "score": float(getattr(top[0], 'final_balanced_score', top[0].balanced_score)),
        "risk": float(top[0].risk), "feas": float(top[0].feasibility),
        "stab": float(top[0].stability), "hydro": hs, "zone": zone, "zones": zones,
        "crackdown": cbf.get("crackdown_ratio"), "p_blow": cbf.get("mean_p_blow"),
        "phase_spread": ipl.get("phase_spread"),
    }


if __name__ == "__main__":
    results = {}
    for label, seed in [
        ("Q1_WW3_Emergence",   seed_q1),
        ("Q2_WW3_Containment", seed_q2),
        ("Q3A_PreWW3",         seed_q3a),
        ("Q3B_PostWW4",        seed_q3b),
    ]:
        results[label] = run_one(label, seed)

    pre, post = results["Q3A_PreWW3"], results["Q3B_PostWW4"]
    print(f"\n{'=' * 70}")
    print("SINGULARITY VERIFICATION (Pre-WW3 vs Post-WW4)")
    print(f"{'=' * 70}")
    print(f"                  Pre-WW3    Post-WW4   Δ")
    print(f"  score:         {pre['score']:7.4f}  {post['score']:7.4f}  {post['score']-pre['score']:+.4f}")
    print(f"  risk:          {pre['risk']:7.3f}  {post['risk']:7.3f}  {post['risk']-pre['risk']:+.3f}")
    print(f"  feasibility:   {pre['feas']:7.3f}  {post['feas']:7.3f}  {post['feas']-pre['feas']:+.3f}")
    print(f"  stability:     {pre['stab']:7.3f}  {post['stab']:7.3f}  {post['stab']-pre['stab']:+.3f}")
    print(f"  p_blow:        {pre['p_blow']:7.3f}  {post['p_blow']:7.3f}  {post['p_blow']-pre['p_blow']:+.3f}")
    print(f"  phase_spread:  {pre['phase_spread']:7.4f}  {post['phase_spread']:7.4f}  {post['phase_spread']-pre['phase_spread']:+.4f}")
    print(f"  zone:          {pre['zone']:>7s}  {post['zone']:>7s}")

    score_shift = abs(post['score'] - pre['score'])
    zone_changed = pre['zone'] != post['zone']
    p_blow_shift = abs(post['p_blow'] - pre['p_blow'])

    print(f"\nVerdict:")
    if zone_changed:
        print(f"  Zone transition: {pre['zone']} → {post['zone']}  [SINGULARITY marker]")
    else:
        print(f"  Zone preserved: both {pre['zone']}")
    print(f"  Δscore = {post['score']-pre['score']:+.4f}")
    print(f"  Δp_blow = {post['p_blow']-pre['p_blow']:+.3f}")
    print(f"  Δphase_spread = {post['phase_spread']-pre['phase_spread']:+.4f}")

    print(f"\n{'─' * 70}")
    print("Comparison with previous singularity tests:")
    print(f"  COVID    Δscore=-0.049  Δp_blow=+0.108  zone: stable → stable")
    print(f"  AI       Δscore=-0.068  Δp_blow=+0.112  zone: stable → stable")
    print(f"  WW3/WW4  Δscore={post['score']-pre['score']:+.4f}  "
          f"Δp_blow={post['p_blow']-pre['p_blow']:+.3f}  "
          f"zone: {pre['zone']} → {post['zone']}")

    is_extreme = abs(post['score']-pre['score']) > 0.15 or p_blow_shift > 0.20 or zone_changed
    if is_extreme:
        print(f"\n  => WW4 IS an extreme event by TD metrics")
    if zone_changed:
        print(f"  => Zone transition confirmed: this IS a singularity")
    else:
        print(f"  => Zone not transitioned: TD singularity threshold may be miscalibrated")

    out = Path("D:/treesea/runs/tree_diagram/ww4_singularity.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {out}")
