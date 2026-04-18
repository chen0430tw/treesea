"""Resident Evil 世界观三问，映射到 Tree Diagram 参数空间。

剧本：T 病毒泄漏 → 浣熊市爆发 → Umbrella 封锁 → 幸存者逃脱

三个问题：
  Q1 RaccoonCityOutbreak: 给定 T 病毒泄漏初始条件，72 小时内城市会坍塌到什么程度
  Q2 HiveContainment:     Red Queen 选择封锁蜂巢杀死所有人 vs 冒险放任泄漏，哪个是可行解
  Q3 STARSEscape:          S.T.A.R.S. / Leon / Jill 这类幸存者需要什么参数组合才能活下来

字段语义映射：
  subject.aim_coupling         ↔ 团队协调性（Chris/Jill 的默契）
  subject.control_precision    ↔ 战术纪律（射击精度/判断力）
  subject.load_tolerance       ↔ 弹药/血量储备
  subject.output_power         ↔ 战斗力输出
  subject.phase_proximity      ↔ 离临界点距离（被咬就变）
  subject.stress_level         ↔ 心理压力
  subject.marginal_decay       ↔ 体力/资源衰减
  subject.instability_sensitivity ↔ 对病毒传染的敏感度

  environment.field_noise          ↔ 城市混乱度
  environment.phase_instability    ↔ 病毒变异速度
  environment.social_pressure      ↔ Umbrella/政府信息封锁强度
  environment.regulatory_friction  ↔ 军事/警察管控强度
  environment.network_density      ↔ 城市人口密度（传播网络）

  resources.budget               ↔ 装备/补给预算
  resources.infrastructure       ↔ 城市基础设施（断水断电前后）
  resources.data_coverage        ↔ 情报/地图覆盖
  resources.population_coupling  ↔ 感染耦合（密度越高丧尸化越快）
"""
from __future__ import annotations
import json
from pathlib import Path

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed


# ────────────────────────────────────────────────────────────────────
# Q1: 浣熊市爆发 72 小时
#   初始：零号病人已进入市中心，Umbrella 高层不允许公开预警
#   环境：下水道病毒已扩散，人口密集，警察按常规协议出警
# ────────────────────────────────────────────────────────────────────
seed_raccoon = ProblemSeed(
    title="Raccoon City 72-hour outbreak dynamics",
    target=(
        "Given T-virus leakage into urban sewer system with delayed public warning, "
        "project the city-scale stability trajectory over 72 hours."
    ),
    constraints=[
        "no public announcement permitted (Umbrella cover-up)",
        "standard police protocols only (no military intervention in first 24h)",
        "infection unknowns to civilian medical system",
    ],
    resources={
        "budget": 0.35,               # 应急预算有限
        "infrastructure": 0.65,       # 前期城市运转正常
        "data_coverage": 0.18,        # 情报极少（Umbrella 遮掩）
        "population_coupling": 0.91,  # 都市密度=极高传播耦合
    },
    environment={
        "field_noise": 0.78,              # 早期混乱已累积
        "phase_instability": 0.85,        # T 病毒相位极不稳
        "social_pressure": 0.25,          # 外部监管接近失效
        "regulatory_friction": 0.20,      # 警察协议不适用丧尸
        "network_density": 0.94,          # 城市人口=最高传播网络
    },
    subject={
        "output_power": 0.45,
        "control_precision": 0.30,        # 警察不知道怎么打头
        "load_tolerance": 0.35,
        "aim_coupling": 0.25,             # 市民/警察无协调
        "stress_level": 0.88,
        "phase_proximity": 0.92,          # 极接近完全崩溃
        "marginal_decay": 0.12,           # 衰减慢=疫情持续
        "instability_sensitivity": 0.93,  # 一口就变
    },
)


# ────────────────────────────────────────────────────────────────────
# Q2: Hive 封锁决策
#   Red Queen 选择：灌注神经毒气杀死全部员工 vs 开闸冒险让病毒外逸
#   环境：密闭地下设施，员工已被感染/部分变异，设施自带封锁协议
# ────────────────────────────────────────────────────────────────────
seed_hive = ProblemSeed(
    title="Hive containment protocol decision",
    target=(
        "Evaluate Red Queen's containment strategy: full facility sterilization "
        "vs allowing potential external leakage to save hive staff."
    ),
    constraints=[
        "absolute priority: prevent T-virus leak to surface",
        "Red Queen has executive override on all facility systems",
        "staff casualty count is not a veto constraint",
    ],
    resources={
        "budget": 0.88,               # 高——单位内资源密集
        "infrastructure": 0.92,       # 设施基建=顶级
        "data_coverage": 0.96,        # Red Queen 全境监控
        "population_coupling": 0.28,  # 密闭设施=耦合低但确定
    },
    environment={
        "field_noise": 0.45,              # 设施内部有序
        "phase_instability": 0.82,        # 病毒相位仍极不稳
        "social_pressure": 0.90,          # Umbrella 绝对压力
        "regulatory_friction": 0.95,      # 封锁协议=最强约束
        "network_density": 0.32,          # 员工数量有限
    },
    subject={
        "output_power": 0.78,             # Red Queen 执行力
        "control_precision": 0.94,        # AI 决策=高精度
        "load_tolerance": 0.55,
        "aim_coupling": 0.88,             # 系统内部协调强
        "stress_level": 0.45,             # AI 不紧张
        "phase_proximity": 0.70,          # 接近但可控
        "marginal_decay": 0.38,
        "instability_sensitivity": 0.50,
    },
)


# ────────────────────────────────────────────────────────────────────
# Q3: S.T.A.R.S. 幸存者逃生
#   初始：Alpha/Bravo 小队被困浣熊森林洋馆，Wesker 已叛变
#   目标：Jill/Chris 这样的人凭什么活下来
# ────────────────────────────────────────────────────────────────────
seed_stars = ProblemSeed(
    title="S.T.A.R.S. survivor escape viability",
    target=(
        "Identify parameter regime where elite tactical operators (Jill, Chris, Leon) "
        "can escape a T-virus saturated zone despite being outnumbered."
    ),
    constraints=[
        "operators have combat training but limited ammunition",
        "extraction window is narrow (hours, not days)",
        "must avoid both infection vectors and hostile bioweapons (Tyrant/Nemesis)",
    ],
    resources={
        "budget": 0.55,               # 中等装备
        "infrastructure": 0.30,       # 外部支援已坍塌
        "data_coverage": 0.62,        # 有限情报+经验判断
        "population_coupling": 0.35,  # 小队=低耦合但紧密
    },
    environment={
        "field_noise": 0.68,              # 洋馆/浣熊森林混乱
        "phase_instability": 0.75,        # 病毒环境依然致命
        "social_pressure": 0.45,          # 外界部分知情
        "regulatory_friction": 0.55,      # 军令与个人判断冲突
        "network_density": 0.38,          # 乡村/密林=低密度
    },
    subject={
        "output_power": 0.86,             # 精英射手
        "control_precision": 0.93,        # 爆头纪律
        "load_tolerance": 0.72,           # 弹药管理严格
        "aim_coupling": 0.91,             # 队友默契=极高
        "stress_level": 0.62,             # 训练有素但仍承压
        "phase_proximity": 0.42,          # 保持距离=活下来
        "marginal_decay": 0.28,           # 体力持久
        "instability_sensitivity": 0.38,  # 防护装备+意识
    },
)


def run_one(label: str, seed: ProblemSeed, top_k: int = 5):
    print(f"\n{'=' * 70}")
    print(f"[{label}] {seed.title}")
    print(f"{'=' * 70}")
    pipe = CandidatePipeline(
        seed=seed, top_k=top_k, NX=32, NY=24, steps=60, dt=45.0, n_workers=1,
    )
    top, hydro, oracle = pipe.run()

    print(f"Top {len(top)} worldlines:")
    for i, r in enumerate(top, 1):
        score = float(getattr(r, 'final_balanced_score', r.balanced_score))
        print(f"  #{i}  score={score:.4f}  risk={r.risk:.3f}  "
              f"feas={r.feasibility:.3f}  stab={r.stability:.3f}  {r.family}/{r.template}")

    hs = hydro.get("utm_hydro_state", "?")
    zone = hydro.get("ipl_index", {}).get("top_zone", "?")
    zones = hydro.get("ipl_index", {}).get("zone_summary", {})
    cbf = hydro.get("cbf_allocation", {})
    print(f"\nhydro={hs}  top_zone={zone}  zones={zones}")
    if cbf:
        print(f"cbf.crackdown_ratio={cbf.get('crackdown_ratio', 0):.3f}  "
              f"cbf.mean_p_blow={cbf.get('mean_p_blow', 0):.3f}")

    return top, hydro, oracle


if __name__ == "__main__":
    out_dir = Path("D:/treesea/runs/tree_diagram")
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for label, seed in [
        ("Q1_Raccoon", seed_raccoon),
        ("Q2_Hive",    seed_hive),
        ("Q3_STARS",   seed_stars),
    ]:
        top, hydro, oracle = run_one(label, seed)
        results[label] = {
            "title": seed.title,
            "top_score": float(getattr(top[0], 'final_balanced_score', top[0].balanced_score)),
            "top_risk": float(top[0].risk),
            "top_feasibility": float(top[0].feasibility),
            "top_stability": float(top[0].stability),
            "hydro_state": hydro.get("utm_hydro_state"),
            "top_zone": hydro.get("ipl_index", {}).get("top_zone"),
            "zones": hydro.get("ipl_index", {}).get("zone_summary"),
            "crackdown_ratio": hydro.get("cbf_allocation", {}).get("crackdown_ratio"),
            "mean_p_blow": hydro.get("cbf_allocation", {}).get("mean_p_blow"),
        }

    (out_dir / "resident_evil.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nSaved → {out_dir / 'resident_evil.json'}")
