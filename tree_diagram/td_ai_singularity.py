"""2026 年 4 月锚点：TD 分析 AI 将给世界带来什么变化。

四个场景：
  Q1 Emergence        2026 年底 - 2027 年，Transformative AI 涌现路径
  Q2 Alignment        最优对齐/遏制策略的可行性
  Q3A Pre-AI          AI 大规模部署前的均衡（2020 年基准）
  Q3B Post-AI         AGI 广泛部署后的新均衡（假设 2030 年）

奇点判定和 COVID 那次一样：
  - zone 相同 + |Δscore| < 0.10 → 扰动，不是奇点
  - zone 跳跃或 |Δscore| > 0.10 → 真奇点
"""
from __future__ import annotations
import json
from pathlib import Path

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed


# ────────────────────────────────────────────────────────────────────
# Q1: Transformative AI 涌现条件（2026-2027 窗口）
#
# 背景：
#  - Frontier models: Claude Opus 4.7, GPT-5, Gemini 2.5 等已进入 agentic 阶段
#  - Agentic workflow 已经大规模商用（Claude Code、Cursor、Devin）
#  - 算力投入历史最高（单模型训练 >1e26 FLOPs）
#  - 对齐研究仍远落后于 capability 研究
#  - 全球监管框架刚起步（EU AI Act、US EO 14110、中国规定）
# ────────────────────────────────────────────────────────────────────
seed_q1 = ProblemSeed(
    title="Transformative AI emergence trajectory 2026-2027",
    target=(
        "Evaluate the probability and pathway by which agentic AI systems "
        "reach transformative capability level within the next 18-24 months, "
        "given current compute scaling, model architectures, and alignment status."
    ),
    constraints=[
        "compute continues exponential growth (>4x year over year)",
        "alignment research lags capability by ~2 years",
        "regulatory framework exists but enforcement inconsistent globally",
        "no major compute-limiting export controls during window",
    ],
    resources={
        "budget": 0.94,              # 前沿训练预算史上最高
        "infrastructure": 0.88,      # GPU/TPU/Trainium 规模空前
        "data_coverage": 0.82,       # 公开数据+合成数据大幅扩展
        "population_coupling": 0.86, # 用户采用率极高（ChatGPT 几亿活跃）
    },
    environment={
        "field_noise": 0.72,             # AI 能力/风险叙事混乱
        "phase_instability": 0.90,       # 能力提升速度极快（月级跃升）
        "social_pressure": 0.55,         # 公众警觉中等
        "regulatory_friction": 0.38,     # 全球监管碎片化、弱约束
        "network_density": 0.88,         # AI 服务 API 密集部署
    },
    subject={
        "output_power": 0.88,            # frontier 能力已达研究生级
        "control_precision": 0.45,       # 对齐/可解释性弱
        "load_tolerance": 0.60,
        "aim_coupling": 0.58,            # RLHF/Constitutional AI 部分奏效
        "stress_level": 0.72,
        "phase_proximity": 0.82,         # 离 AGI 临界点近
        "marginal_decay": 0.10,          # 能力持续指数增长
        "instability_sensitivity": 0.85, # 小的架构改动可能巨大跃迁
    },
)


# ────────────────────────────────────────────────────────────────────
# Q2: AI 对齐/遏制的最优策略
#
# 问：给定 Q1 的涌现前提，什么策略组合可以遏制坏后果？
#  - 可调节参数：对齐研究投入、算力访问限制、监管、透明度、评估基础设施
# ────────────────────────────────────────────────────────────────────
seed_q2 = ProblemSeed(
    title="Optimal AI alignment and containment strategy",
    target=(
        "Given transformative AI is emerging, identify worldline that minimizes "
        "catastrophic misalignment risk while preserving scientific and economic "
        "benefit within 36-month horizon."
    ),
    constraints=[
        "alignment tax (capability-safety tradeoff) is real and nonzero",
        "international coordination difficult due to strategic competition",
        "open weights proliferation cannot be fully reversed",
        "interpretability research 3-5 years behind capability",
    ],
    resources={
        "budget": 0.70,              # 安全投入大幅增加但仍远少于能力
        "infrastructure": 0.75,      # 评估基础设施逐步建立
        "data_coverage": 0.65,       # 红队/对齐数据集扩展
        "population_coupling": 0.50, # 对齐社区耦合加强但规模小
    },
    environment={
        "field_noise": 0.60,
        "phase_instability": 0.78,       # 能力仍快速变化
        "social_pressure": 0.82,         # AI Safety 警觉峰值
        "regulatory_friction": 0.72,     # 监管加强（EU/US/中国协同不完整）
        "network_density": 0.55,         # 前沿实验室协同加强
    },
    subject={
        "output_power": 0.68,            # 对齐技术输出中等
        "control_precision": 0.78,       # 评估+红队+mechanistic interp 成熟
        "load_tolerance": 0.55,
        "aim_coupling": 0.72,            # Constitutional AI/RLHF++ 有效
        "stress_level": 0.80,
        "phase_proximity": 0.65,         # 仍在风险窗口但可控
        "marginal_decay": 0.28,
        "instability_sensitivity": 0.60,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3A: 前 AI 大规模部署世界（2020 年基准）
#
# 锚点：GPT-3 发布前，AI 仍是专业工具而非通用 Agent
# 经济结构：传统知识工作占 GDP 主体，AI 仅在窄领域替代
# 信息环境：搜索引擎驱动，AI 生成内容不显著
# ────────────────────────────────────────────────────────────────────
seed_q3a = ProblemSeed(
    title="Pre-AI-deployment baseline equilibrium (2020)",
    target="Characterize global system equilibrium before transformative AI deployment.",
    constraints=["AI as narrow tools only", "human-written content dominant",
                 "knowledge work not yet automated", "software still manually written"],
    resources={
        "budget": 0.65,
        "infrastructure": 0.75,
        "data_coverage": 0.72,
        "population_coupling": 0.70,
    },
    environment={
        "field_noise": 0.38,             # 信息环境相对稳定
        "phase_instability": 0.32,       # 技术变化线性
        "social_pressure": 0.48,
        "regulatory_friction": 0.45,
        "network_density": 0.85,         # 互联网高密度但未被 AI 重塑
    },
    subject={
        "output_power": 0.72,
        "control_precision": 0.70,
        "load_tolerance": 0.70,
        "aim_coupling": 0.68,
        "stress_level": 0.40,
        "phase_proximity": 0.38,         # 远离 AI 临界
        "marginal_decay": 0.50,
        "instability_sensitivity": 0.40,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3B: 后 AGI 部署世界（2030 年假设）
#
# 锚点：AGI 级 Agent 已大规模部署
# 经济结构：70%+ 知识工作由 AI 执行，人类进入人机协作
# 信息环境：AI 生成内容占主体，人类内容需标签认证
# 认知生态：教育/研究/创作范式根本重构
# ────────────────────────────────────────────────────────────────────
seed_q3b = ProblemSeed(
    title="Post-AGI deployment new equilibrium (2030)",
    target="Characterize global system equilibrium after widespread AGI deployment.",
    constraints=[
        "AGI-level agents widely deployed across knowledge work",
        "labor market restructured (some jobs gone, new coordination roles)",
        "information ecosystem requires provenance tracking",
        "educational institutions redesigned for human-AI collaboration",
        "autonomous decision systems in critical infrastructure",
    ],
    resources={
        "budget": 0.48,              # 资源分配重构，部分人类资源流向 AI 维护
        "infrastructure": 0.95,      # 基建跃升（AI 数据中心、能源网重构）
        "data_coverage": 0.96,       # 全域感知（AI 生成+AI 消费）
        "population_coupling": 0.42, # 人-AI 耦合增强，人-人耦合下降
    },
    environment={
        "field_noise": 0.68,             # 信息环境噪声极高（真假难辨）
        "phase_instability": 0.55,       # 技术仍快速迭代
        "social_pressure": 0.75,         # 监管/认证压力峰值
        "regulatory_friction": 0.82,     # AI 监管框架完备但仍落后
        "network_density": 0.95,         # AI Agent 网络密度爆炸
    },
    subject={
        "output_power": 0.92,            # AI + 人类协作产出巨大
        "control_precision": 0.70,       # 对齐部分解决，仍有边界情况
        "load_tolerance": 0.58,          # 认知负载重构
        "aim_coupling": 0.55,            # 全局目标一致性下降（多 AI 系统）
        "stress_level": 0.65,
        "phase_proximity": 0.72,         # 仍在 ASI 逼近窗口
        "marginal_decay": 0.25,          # 能力仍在增长
        "instability_sensitivity": 0.70,
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
        ("Q2_Alignment",   seed_q2),
        ("Q3A_PreAI",      seed_q3a),
        ("Q3B_PostAI",     seed_q3b),
    ]:
        results[label] = run_one(label, seed)

    pre, post = results["Q3A_PreAI"], results["Q3B_PostAI"]
    print(f"\n{'=' * 70}")
    print("SINGULARITY VERIFICATION (Pre-AI vs Post-AI)")
    print(f"{'=' * 70}")
    print(f"                        Pre-AI     Post-AI    Δ")
    print(f"  score:             {pre['score']:7.4f}  {post['score']:7.4f}  {post['score']-pre['score']:+.4f}")
    print(f"  risk:              {pre['risk']:7.3f}  {post['risk']:7.3f}  {post['risk']-pre['risk']:+.3f}")
    print(f"  feasibility:       {pre['feasibility']:7.3f}  {post['feasibility']:7.3f}  {post['feasibility']-pre['feasibility']:+.3f}")
    print(f"  stability:         {pre['stability']:7.3f}  {post['stability']:7.3f}  {post['stability']-pre['stability']:+.3f}")
    print(f"  zone:              {pre['zone']:>7s}  {post['zone']:>7s}")
    print(f"  p_blow:            {pre['p_blow']:.3f}    {post['p_blow']:.3f}")

    score_shift = abs(post['score'] - pre['score'])
    zone_changed = pre['zone'] != post['zone']
    p_blow_shift = abs(post['p_blow'] - pre['p_blow'])
    major_shift = score_shift > 0.10 or zone_changed or p_blow_shift > 0.15

    print(f"\nVerdict:")
    if zone_changed:
        print(f"  Zone transition: {pre['zone']} → {post['zone']}  [SINGULARITY marker]")
    else:
        print(f"  Zone preserved: both {pre['zone']}  [no zone-level singularity]")
    if score_shift > 0.10:
        print(f"  Score shift Δ={score_shift:.3f} > 0.10  [quantitative singularity]")
    if p_blow_shift > 0.15:
        print(f"  p_blow shift Δ={p_blow_shift:.3f} > 0.15  [stability regime change]")

    print()
    if major_shift:
        print(f"  => This IS a SINGULARITY event: new equilibrium attractor")
    else:
        print(f"  => This is NOT a singularity: same basin, different coordinates")

    # 对比 COVID
    print(f"\n{'─' * 70}")
    print("Comparison with COVID singularity test:")
    print(f"  COVID  Δscore = -0.049  zone: stable → stable   → NOT singularity")
    print(f"  AI     Δscore = {post['score']-pre['score']:+.3f}  "
          f"zone: {pre['zone']} → {post['zone']}  → "
          f"{'SINGULARITY' if major_shift else 'NOT singularity'}")

    out = Path("D:/treesea/runs/tree_diagram/ai_singularity.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved → {out}")
