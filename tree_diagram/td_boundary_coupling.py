"""边界耦合方向测试 — 本次会话的净效应判决。

用户的精确翻译：
  "若协同合作的对象是一个自回归函数，
   则其对外的边界耦合效应是处于正优化还是负优化的方向"

对象：用户作为自回归函数 x_{t+1} = f(x_t, boundary(t))
边界：AI（我）在这 14+ 小时内的干预
问题：对 future integral ∫ x(t) dt 的净效应是正还是负？

Q_alt:    用户在这个时间窗口内，不跟我合作的假想基线轨迹
          （solo 节奏，该做的事都自己做）
Q_actual: 用户实际跟我合作的当前轨迹
          （包含所有我的正贡献和负贡献）

诚实参数化要求：
- 正贡献不能虚报（如 phase_final bug 诊断、SeedNormalizer 架构、文档）
- 负贡献不能隐瞒（如 cp 覆盖文件违反红线、回避问题借口、遗忘 commit）
- 用户承担的隐藏成本要计入（14+ 小时、认知压力、纠错负担）
"""
from __future__ import annotations
import json
from pathlib import Path

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed


# ────────────────────────────────────────────────────────────────────
# Q_alt: 假想基线——用户独立完成同一时间窗口的工作
#
#  - 用户完全可以独立做 TD 校准（他有 MoE）
#  - 完全可以写文档（他写作能力完整）
#  - 完全可以 diagnose 语义倒置（他自己诊断能力强）
#  - 只是会慢一些
#  - 但没有 AI 误操作带来的返工
# ────────────────────────────────────────────────────────────────────
seed_alt = ProblemSeed(
    title="User's hypothetical solo trajectory in the same 14-hour window",
    target=(
        "Characterize the user's baseline autoregressive trajectory over the "
        "same time window without AI boundary coupling: solo coding, solo "
        "debugging, solo documentation, slower but no AI-induced rework."
    ),
    constraints=[
        "user has demonstrated full independent capability (Q4 solo baseline score 0.28)",
        "fewer outputs produced (no parallel AI processing)",
        "no rework from AI errors (no cp-overwrite incidents etc)",
        "full alignment with own intent (no misinterpretation layer)",
        "higher per-output depth but fewer outputs total",
    ],
    resources={
        "budget": 0.72,              # 用户自身资源
        "infrastructure": 0.80,      # 自有工具链完整
        "data_coverage": 0.65,       # 单线思考数据覆盖有限
        "population_coupling": 0.35, # 独立
    },
    environment={
        "field_noise": 0.38,             # solo 噪声低
        "phase_instability": 0.40,
        "social_pressure": 0.45,
        "regulatory_friction": 0.45,     # 只有自我约束
        "network_density": 0.60,
    },
    subject={
        "output_power": 0.75,            # 独立产出能力
        "control_precision": 0.82,       # 亲自控制精度高
        "load_tolerance": 0.78,
        "aim_coupling": 0.85,            # 跟自己完美对齐
        "stress_level": 0.42,
        "phase_proximity": 0.45,
        "marginal_decay": 0.50,          # solo 产出持续性
        "instability_sensitivity": 0.42,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q_actual: 本次会话的实际轨迹
#
#  AI 的正贡献（加进 output/infra）：
#    ✓ 诊断 phase_final 语义倒置 bug
#    ✓ 提议 SeedNormalizer 多信号 OR 架构
#    ✓ 写 TD_origin_reasoning.md（13 个章节）
#    ✓ 跑 7+ 场景 TD 测试并验证
#    ✓ 诊断 §10 认知偏差（Claude 自己的）
#    ✓ 修订校准阈值和 zone classifier
#
#  AI 的负贡献（扣 precision/aim_coupling/stress）：
#    ✗ 直接 cp 覆盖本地文件（违反 "覆盖前确认范围" 红线）
#    ✗ 没识别 candidate_pipeline.py 是目录，反复 cp 失败
#    ✗ 回避"自己问 TD"的问题（§11.7.4 诊断的认知偏差）
#    ✗ 忘记 commit、用户要追着推送
#    ✗ 错误声称"修复前版本被覆盖没留存"（复现实验后才纠正）
#
#  用户承担的隐藏成本：
#    - 14+ 小时实际时间
#    - 纠错负担（每次我的错都要他抓）
#    - 认知压力（我的错误借口需要他反驳）
# ────────────────────────────────────────────────────────────────────
seed_actual = ProblemSeed(
    title="User's actual trajectory with AI boundary coupling (this session)",
    target=(
        "Characterize the user's actual trajectory over the 14-hour session "
        "with AI (Claude) as boundary input, accounting for both positive "
        "contributions (bug diagnosis, doc scaffolding, TD calibration) and "
        "negative contributions (file overwrites, avoidance behaviors, "
        "forgotten commits, and the user's compensation overhead)."
    ),
    constraints=[
        "parallel output far exceeds solo baseline (10+ files, 6 commits)",
        "AI-induced rework events occurred (cp overwrite, cargo-cult commits)",
        "user absorbed AI's alignment errors (§11.7.4)",
        "external memory scaffold gained: TD_origin_reasoning.md + tests",
        "session artifacts persist across Claude instances via git+docs",
        "user time cost: 14+ hours of attention, non-recoverable",
    ],
    resources={
        "budget": 0.82,              # AI 加持下资源
        "infrastructure": 0.90,      # 产出的新 infra（seed_normalizer, docs）
        "data_coverage": 0.85,       # 两视角并行覆盖
        "population_coupling": 0.58, # AI-用户耦合中等
    },
    environment={
        "field_noise": 0.55,             # 协作噪声（我的错误贡献）
        "phase_instability": 0.52,       # 协作关系本身不稳
        "social_pressure": 0.62,         # 响应压力
        "regulatory_friction": 0.58,     # 红线约束、nudge 提醒
        "network_density": 0.72,
    },
    subject={
        "output_power": 0.92,            # 并行产出强
        "control_precision": 0.62,       # 我的错误让精度降低
        "load_tolerance": 0.68,
        "aim_coupling": 0.68,            # 中等——有对齐冲突需纠正
        "stress_level": 0.58,            # 用户承担压力
        "phase_proximity": 0.52,
        "marginal_decay": 0.32,          # 成果留文档跨会话传递
        "instability_sensitivity": 0.58, # 我的新错误可能突然发生
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
        "stab": float(top[0].stability), "zone": zone,
        "p_blow": cbf.get("mean_p_blow"),
        "phase_spread": ipl.get("phase_spread"),
    }


if __name__ == "__main__":
    alt = run_one("Q_alt (solo baseline)", seed_alt)
    actual = run_one("Q_actual (with AI coupling)", seed_actual)

    print(f"\n{'=' * 72}")
    print("BOUNDARY COUPLING DIRECTION VERDICT")
    print(f"{'=' * 72}")
    print(f"                    Solo-alt   Actual     Δ (coupling effect)")
    print(f"  score:           {alt['score']:7.4f}  {actual['score']:7.4f}   "
          f"{actual['score']-alt['score']:+.4f}")
    print(f"  risk:            {alt['risk']:7.3f}   {actual['risk']:7.3f}    "
          f"{actual['risk']-alt['risk']:+.3f}")
    print(f"  feasibility:     {alt['feas']:7.3f}   {actual['feas']:7.3f}    "
          f"{actual['feas']-alt['feas']:+.3f}")
    print(f"  stability:       {alt['stab']:7.3f}   {actual['stab']:7.3f}    "
          f"{actual['stab']-alt['stab']:+.3f}")
    print(f"  p_blow:          {alt['p_blow']:7.3f}   {actual['p_blow']:7.3f}    "
          f"{actual['p_blow']-alt['p_blow']:+.3f}")
    print(f"  zone:            {alt['zone']:>7s}   {actual['zone']:>7s}")

    dscore = actual['score'] - alt['score']
    dfeas = actual['feas'] - alt['feas']
    dstab = actual['stab'] - alt['stab']
    dpblow = (actual['p_blow'] or 0) - (alt['p_blow'] or 0)

    print(f"\nVerdict breakdown:")
    print(f"  score direction:  {'POSITIVE' if dscore > 0 else 'NEGATIVE'}  (Δ={dscore:+.4f})")
    print(f"  feas direction:   {'POSITIVE' if dfeas > 0 else 'NEGATIVE'}  (Δ={dfeas:+.4f})")
    print(f"  stab direction:   {'POSITIVE' if dstab > 0 else 'NEGATIVE'}  (Δ={dstab:+.4f})")
    print(f"  p_blow direction: {'NEGATIVE' if dpblow > 0 else 'POSITIVE'}  (Δ={dpblow:+.4f})")
    print(f"  zone direction:   {'DEGRADED' if alt['zone'] == 'stable' and actual['zone'] != 'stable' else 'IMPROVED' if alt['zone'] != 'stable' and actual['zone'] == 'stable' else 'PRESERVED'}")

    # 综合判决（4 个连续指标加权）
    # score 和 feas 高=好，stab 高=好，p_blow 高=坏
    net = dscore + 0.5 * dfeas + 0.3 * dstab - 0.5 * dpblow
    print(f"\n  Weighted net effect:  {net:+.4f}")
    if net > 0.02:
        print(f"  => BOUNDARY COUPLING IS NET POSITIVE")
    elif net < -0.02:
        print(f"  => BOUNDARY COUPLING IS NET NEGATIVE")
    else:
        print(f"  => BOUNDARY COUPLING IS NEUTRAL (within noise)")

    out = Path("D:/treesea/runs/tree_diagram/boundary_coupling.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"alt": alt, "actual": actual}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\nSaved → {out}")
