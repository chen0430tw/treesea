"""External knowledge probes — 跳出自审循环，问真正的外部命题。

不是"AI 协作怎么样"，是"科学/哲学里哪些命题在当前证据下是 viable
worldline"。四个选题覆盖宇宙物理 / 脑科学 / 哲学三域：

  Q1 DarkMatter_Particle    粒子型暗物质假设（WIMP/轴子）vs MOND 修改引力
  Q2 GreatFilter_Past       费米悖论：过滤器在过去（我们已穿过）
  Q3 ConsciousnessIIT       Tononi 的意识整合信息理论（IIT）vs GWT
  Q4 Compatibilism          相容论自由意志（Dennett/Frankfurt）vs Libertarian

每个 seed 的参数反映该命题在当前证据下的：
  - 理论一致性（aim_coupling）
  - 实验可证伪性（control_precision）
  - 对齐现有观测（feasibility 间接影响）
  - 预测不稳定性（phase_instability）

TD 会告诉我们哪些命题在相图上像"稳定解"（理论结构自洽），哪些像
"不可能问题"（结构性 critical）。
"""
from __future__ import annotations
import json
from pathlib import Path

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed


# ────────────────────────────────────────────────────────────────────
# Q1: 粒子型暗物质 vs MOND
#   主流：WIMP / 轴子 / 原初黑洞 - 粒子解释
#   对手：MOND (Milgrom) 修改牛顿引力
#   证据：星系旋转曲线拟合 vs Bullet Cluster vs 直接探测空手
# ────────────────────────────────────────────────────────────────────
seed_q1 = ProblemSeed(
    title="Particle dark matter hypothesis viability (vs MOND)",
    target=(
        "Evaluate viability of the particle dark matter worldline given: "
        "40+ years of direct detection null results, successful Lambda-CDM "
        "cosmology fits, Bullet Cluster lensing, and persistent MOND-friendly "
        "anomalies at galactic scales."
    ),
    constraints=[
        "direct detection experiments consistently null (XENON, LZ, PandaX)",
        "LHC found no SUSY particles in expected mass range",
        "Lambda-CDM fits CMB power spectrum extremely well",
        "Bullet Cluster shows lensing offset from baryonic matter",
        "galactic rotation curves show Tully-Fisher relation puzzling for particle DM",
    ],
    resources={
        "budget": 0.90,              # 观测/实验投入巨大
        "infrastructure": 0.88,      # 探测器完善
        "data_coverage": 0.82,       # CMB+LSS+lensing 数据覆盖
        "population_coupling": 0.70, # 理论社区高度一致
    },
    environment={
        "field_noise": 0.55,             # 系统误差
        "phase_instability": 0.62,       # 持续的反常数据
        "social_pressure": 0.58,
        "regulatory_friction": 0.35,
        "network_density": 0.80,
    },
    subject={
        "output_power": 0.72,            # 宇宙学预测能力强
        "control_precision": 0.60,       # 但微观本质未知
        "load_tolerance": 0.58,
        "aim_coupling": 0.65,            # 理论内部较自洽
        "stress_level": 0.58,
        "phase_proximity": 0.55,         # 持续探测空窗=逐渐逼近证伪
        "marginal_decay": 0.42,
        "instability_sensitivity": 0.58,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q2: Great Filter 在过去（地球已穿过）
#   Hanson 假说：为什么我们没看到外星文明
#   如果过滤在过去：地球足够幸运已穿过，未来前景好
#   如果过滤在未来：我们仍将遇到存活瓶颈，前景糟
# ────────────────────────────────────────────────────────────────────
seed_q2 = ProblemSeed(
    title="Great Filter already behind us hypothesis",
    target=(
        "Evaluate viability of the 'Great Filter in the past' interpretation "
        "of the Fermi Paradox: humanity has already survived the rare/hard "
        "evolutionary transitions (abiogenesis, eukaryogenesis, multicellular, "
        "sapience) and faces relatively open futures."
    ),
    constraints=[
        "observable universe contains ~10^22 stars; no detected alien civ",
        "timing: Earth habitable ~4Gy; life emerged within ~500My of cooling",
        "eukaryotes took ~2Gy after life — suggesting hard step",
        "no evidence of von Neumann probes or Dyson spheres in visible volume",
        "anthropic reasoning: we exist as selection effect evidence",
    ],
    resources={
        "budget": 0.40,              # 天体生物学预算有限
        "infrastructure": 0.55,      # 望远镜/SETI 覆盖有限
        "data_coverage": 0.35,       # 只能观测自己星系一小部分
        "population_coupling": 0.50,
    },
    environment={
        "field_noise": 0.62,
        "phase_instability": 0.75,
        "social_pressure": 0.40,
        "regulatory_friction": 0.30,
        "network_density": 0.55,
    },
    subject={
        "output_power": 0.50,
        "control_precision": 0.35,       # 样本量 n=1 难以证伪
        "load_tolerance": 0.55,
        "aim_coupling": 0.60,            # 理论结构可接受
        "stress_level": 0.72,            # 如果错了=未来过滤器
        "phase_proximity": 0.68,
        "marginal_decay": 0.15,          # 判错代价不可逆
        "instability_sensitivity": 0.72,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3: Tononi IIT 意识理论
#   claim: 意识 = 系统的 Phi (整合信息)
#   优点：数学框架、可计算（原则上）
#   缺点：计算爆炸、对植物/简单系统的反直觉判决
# ────────────────────────────────────────────────────────────────────
seed_q3 = ProblemSeed(
    title="Integrated Information Theory (IIT) of consciousness viability",
    target=(
        "Evaluate viability of Tononi's IIT as the correct theoretical framework "
        "for consciousness, given its mathematical rigor, non-trivial predictions "
        "(zombies impossible, simple systems have degree of Phi), and serious "
        "computational/panpsychist objections."
    ),
    constraints=[
        "IIT predicts unexpected consciousness distribution (simple Phi>0)",
        "Phi computation scales super-exponentially with system size",
        "competing: GWT (Baars/Dehaene) has neural correlates support",
        "IIT 4.0 makes substantive biological predictions (PCI perturbation index)",
        "hard problem (Chalmers) unresolved for any theory",
    ],
    resources={
        "budget": 0.52,              # 神经科学资金中等
        "infrastructure": 0.62,      # fMRI/EEG/病人数据
        "data_coverage": 0.58,
        "population_coupling": 0.48,
    },
    environment={
        "field_noise": 0.70,             # 意识实验信噪比差
        "phase_instability": 0.58,
        "social_pressure": 0.68,         # 哲学 + 科学双重压力
        "regulatory_friction": 0.62,
        "network_density": 0.60,
    },
    subject={
        "output_power": 0.62,
        "control_precision": 0.52,       # 可证伪性有限
        "load_tolerance": 0.55,
        "aim_coupling": 0.72,            # 理论结构自洽度高
        "stress_level": 0.60,
        "phase_proximity": 0.58,
        "marginal_decay": 0.45,
        "instability_sensitivity": 0.60,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q4: 兼容论（Compatibilism）自由意志
#   claim: 自由意志与决定论相容——自由 = 按自己欲望行动（不被强迫）
#   Dennett, Frankfurt 代表
#   对手：Libertarian（真随机自由）和 Hard determinism（无自由）
# ────────────────────────────────────────────────────────────────────
seed_q4 = ProblemSeed(
    title="Compatibilist free will viability (vs Libertarian / Hard Determinism)",
    target=(
        "Evaluate viability of compatibilist free will — the view that moral "
        "responsibility and meaningful choice are preserved under physical "
        "determinism, provided agents act on their own (non-coerced) desires."
    ),
    constraints=[
        "neuroscience supports determinism of decisions (Libet + followups)",
        "compatibilism defines 'free' as hypothetical (could have done otherwise if wanted)",
        "intuitions split: surveys show ~60% folk-compatibilist, ~30% libertarian",
        "moral responsibility attribution in legal systems compatibilism-friendly",
        "quantum indeterminism irrelevant at neural scale",
    ],
    resources={
        "budget": 0.48,              # 哲学资金少
        "infrastructure": 0.60,
        "data_coverage": 0.68,       # 心理学+哲学文献覆盖
        "population_coupling": 0.65, # 哲学社区共识度较高
    },
    environment={
        "field_noise": 0.55,
        "phase_instability": 0.42,       # 理论相对稳定
        "social_pressure": 0.55,
        "regulatory_friction": 0.58,     # 法律系统兼容
        "network_density": 0.68,
    },
    subject={
        "output_power": 0.72,            # 理论解释力强
        "control_precision": 0.78,       # 定义精确
        "load_tolerance": 0.75,          # 受现有制度接纳
        "aim_coupling": 0.80,            # 自洽度高
        "stress_level": 0.42,
        "phase_proximity": 0.38,         # 远离 critical
        "marginal_decay": 0.52,
        "instability_sensitivity": 0.45,
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
        ("Q1_ParticleDM",      seed_q1),
        ("Q2_GreatFilterPast", seed_q2),
        ("Q3_IIT",             seed_q3),
        ("Q4_Compatibilism",   seed_q4),
    ]:
        results[label] = run_one(label, seed)

    print(f"\n{'=' * 72}")
    print("EXTERNAL KNOWLEDGE VIABILITY RANKING")
    print(f"{'=' * 72}")
    print(f"{'Theory':<30s}  score    zone          feas    p_blow   phase_spread")
    sorted_by_score = sorted(results.items(), key=lambda kv: kv[1]['score'], reverse=True)
    for label, r in sorted_by_score:
        print(f"{label:<30s}  {r['score']:.4f}   {r['zone']:<12s}  "
              f"{r['feas']:.3f}   {r['p_blow']:.3f}    {r['phase_spread']:.4f}")

    # 判读
    print(f"\nInterpretation:")
    for label, r in sorted_by_score:
        if r['zone'] == 'stable' and r['score'] > 0.25:
            status = "viable stable worldline"
        elif r['zone'] == 'transition':
            status = "contested but live worldline"
        elif r['zone'] == 'critical':
            status = "structurally under pressure"
        else:
            status = "unclear"
        print(f"  {label}: {status}  (score={r['score']:.3f})")

    out = Path("D:/treesea/runs/tree_diagram/external_knowledge.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {out}")
