# candidate_attention.py
"""
候选注意力评分 v2。

三阶段架构，每个关注点只出现一次：

  Stage 1: AFFINITY — 线性注意力，计算候选与问题特征的亲和度
  Stage 2: CONSTRAINT — 硬约束过滤，对不合理的候选施加上限
  Stage 3: NORMALIZE — softmax 归一化到 [0.1, 0.95]

不混合。不在 softmax 之后再改分数。每条规则有明确归属。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List


# ================================================================
# Feature Extraction（不含评分逻辑）
# ================================================================

def extract_td_features(tree_output: dict) -> Dict[str, float]:
    """从 Tree Diagram 输出提取特征向量。"""
    oracle = tree_output.get("oracle_details", {})
    hydro = tree_output.get("hydro_control", {})
    best_wl = tree_output.get("best_worldline", oracle.get("best_worldline", {}))

    features: Dict[str, float] = {}

    # field_snapshot
    field = oracle.get("field_snapshot", {})
    features["field_coherence"] = field.get("field_coherence", 0.5)
    features["network_amplification"] = field.get("network_amplification", 0.5)
    features["governance_drag"] = field.get("governance_drag", 0.5)
    features["phase_turbulence"] = field.get("phase_turbulence", 0.5)
    features["resource_elasticity"] = field.get("resource_elasticity", 0.5)

    # vein_stats
    vein_stats = hydro.get("vein_stats", {})
    for metric in ["yield", "stability", "risk", "composite"]:
        ms = vein_stats.get(metric, {})
        features[f"vein_{metric}_mean"] = ms.get("mean", 0.5)

    # best_worldline
    features["best_feasibility"] = best_wl.get("feasibility", 0.5)
    features["best_stability"] = best_wl.get("stability", 0.5)
    features["best_risk"] = best_wl.get("risk", 0.3)

    # utm
    utm_state = hydro.get("utm_hydro_state", "NORMAL")
    features["utm_flood"] = 1.0 if utm_state == "FLOOD" else 0.0
    features["utm_drought"] = 1.0 if utm_state == "DROUGHT" else 0.0

    # branch ecology
    branch_hist = oracle.get("branch_histogram", {})
    total_branches = sum(branch_hist.values()) if branch_hist else 1
    features["branch_active_ratio"] = branch_hist.get("active", 0) / max(total_branches, 1)

    return features


def extract_candidate_features(candidate_params: dict) -> Dict[str, float]:
    """从 QCU 候选参数提取 6 维特征向量。"""
    gamma_pcm = candidate_params.get("gamma_pcm", 0.15)
    gamma_boost = candidate_params.get("gamma_boost", 0.7)
    boost_duration = candidate_params.get("boost_duration", 2.5)
    gamma_phi0 = candidate_params.get("gamma_phi0", 0.25)

    conservatism = 1.0 - min(gamma_pcm / 0.3, 1.0)
    aggressiveness = min(gamma_boost / 1.0, 1.0)
    patience = min(boost_duration / 5.0, 1.0)
    risk_appetite = min(gamma_phi0 / 0.5, 1.0)

    return {
        "conservatism": conservatism,
        "aggressiveness": aggressiveness,
        "patience": patience,
        "risk_appetite": risk_appetite,
        # 派生特征
        "balance": 1.0 - abs(conservatism - aggressiveness),
        "recklessness": aggressiveness * (1.0 - 0.5 * conservatism - 0.3 * patience),
    }


# ================================================================
# Stage 1: AFFINITY — 线性注意力
# ================================================================

# 每条规则: (env_feature, cand_feature, weight, mode)
# mode: "align" = 同向好, "oppose" = 反向好
# 每个语义关注点只出现一次。
AFFINITY_RULES = [
    # --- 环境湍流/危机 → 保守好，激进差 ---
    ("seed_turbulence", "conservatism", 3.0, "align"),
    ("seed_turbulence", "recklessness", 2.5, "oppose"),
    ("seed_noise", "conservatism", 2.0, "align"),
    ("seed_noise", "risk_appetite", 1.5, "oppose"),

    # --- 紧迫/竞争 → 速度好，但受 survival_dampening 调制 ---
    ("seed_urgency", "aggressiveness", 2.5, "align"),
    ("seed_competition", "aggressiveness", 1.5, "align"),
    ("seed_pressure", "aggressiveness", 1.5, "align"),

    # --- 稳定环境 → 激进可行 ---
    ("seed_stability", "aggressiveness", 2.5, "align"),
    ("seed_stability", "conservatism", 1.5, "oppose"),

    # --- 技术成熟度 → 决定激进是否可行 ---
    ("seed_technology_readiness", "aggressiveness", 3.0, "align"),
    ("seed_tech_readiness", "aggressiveness", 3.0, "align"),

    # --- 风险容忍 ---
    ("seed_risk_tolerance", "risk_appetite", 2.0, "align"),

    # --- 执行力 ---
    ("seed_spacex_execution_track_record", "aggressiveness", 2.0, "align"),
    ("seed_experience", "aggressiveness", 1.5, "align"),

    # --- 延期历史 → 需要耐心 ---
    ("seed_nasa_schedule_slip_history", "patience", 2.0, "align"),

    # --- 政治意愿 → 长期可行 ---
    ("seed_political_will", "patience", 1.5, "align"),
    ("seed_political_will_china", "aggressiveness", 1.5, "align"),
    ("seed_commercial_motivation", "aggressiveness", 1.5, "align"),

    # --- 竞争中平衡策略好 ---
    ("seed_competition", "balance", 2.0, "align"),

    # --- TD 固有特征（权重较低，不主导） ---
    ("field_coherence", "conservatism", 0.5, "align"),
    ("governance_drag", "patience", 0.5, "align"),
    ("vein_risk_mean", "risk_appetite", 0.5, "oppose"),
    ("best_feasibility", "patience", 0.3, "align"),
    ("utm_flood", "aggressiveness", 0.3, "align"),
    ("utm_drought", "conservatism", 0.5, "align"),
]


def _compute_affinity(
    td_features: Dict[str, float],
    cand_features: Dict[str, float],
    survival_dampen: float,
) -> float:
    """Stage 1: 计算单个候选的亲和度分数。

    survival_dampen [0, 1]: 越高表示越危急，urgency 的激进驱动被抑制。
    """
    score = 0.0
    total_weight = 0.0

    for env_key, cand_key, weight, mode in AFFINITY_RULES:
        env_val = td_features.get(env_key, -1.0)
        if env_val < 0:
            continue  # 该特征未定义，跳过（不用 fallback 0.5）

        cand_val = cand_features.get(cand_key, 0.5)

        # survival dampening: 危急时抑制 urgency/competition 对激进的驱动
        effective_weight = weight
        if survival_dampen > 0.3 and env_key in ("seed_urgency", "seed_pressure") and mode == "align":
            effective_weight *= (1.0 - 0.7 * survival_dampen)

        if mode == "align":
            contribution = env_val * cand_val
        else:
            contribution = env_val * (1.0 - cand_val)

        score += effective_weight * contribution
        total_weight += effective_weight

    return score / max(total_weight, 1e-8)


# ================================================================
# Stage 2: CONSTRAINT — 硬约束（每个关注点只处理一次）
# ================================================================

def _apply_constraints(
    raw_score: float,
    td_features: Dict[str, float],
    cand_features: Dict[str, float],
) -> float:
    """Stage 2: 施加硬约束上限。

    每条约束独立、不重叠。约束只能降低分数（cap），不能加分。
    """
    s = raw_score

    # C1: 技术不成熟 + 冒进 → 轻度惩罚（不 cap，乘性衰减）
    tr = max(
        td_features.get("seed_technology_readiness", -1),
        td_features.get("seed_tech_readiness", -1),
    )
    recklessness = cand_features.get("recklessness", 0.0)
    if tr >= 0 and tr < 0.5 and recklessness > 0.3:
        tech_gap = (0.5 - tr) / 0.5
        penalty = 1.0 - tech_gap * (recklessness - 0.3) * 0.4
        s *= max(penalty, 0.5)

    # C2: 极端策略惩罚（过于保守或过于激进）
    aggr = cand_features.get("aggressiveness", 0.5)
    conserv = cand_features.get("conservatism", 0.5)
    if aggr > 0.9 or conserv > 0.9:
        s *= 0.8

    return s


# ================================================================
# Stage 3: NORMALIZE — softmax
# ================================================================

def _softmax_normalize(scores: List[float], temperature: float) -> List[float]:
    """Stage 3: softmax 归一化到 [0.1, 0.95]。"""
    if len(scores) <= 1:
        return [max(0.1, min(0.95, s)) for s in scores]

    s_mean = sum(scores) / len(scores)
    s_std = (sum((s - s_mean) ** 2 for s in scores) / len(scores)) ** 0.5
    if s_std < 1e-8:
        return [0.5] * len(scores)

    z_scores = [(s - s_mean) / s_std / temperature for s in scores]
    exp_scores = [math.exp(min(z, 10)) for z in z_scores]
    exp_sum = sum(exp_scores)
    softmax = [e / exp_sum for e in exp_scores]

    sm_max = max(softmax)
    sm_min = min(softmax)
    sm_range = sm_max - sm_min if sm_max > sm_min else 1.0

    return [
        max(0.1, min(0.95, 0.1 + 0.85 * (sm - sm_min) / sm_range))
        for sm in softmax
    ]


# ================================================================
# 公开 API
# ================================================================

def _compute_survival_priority(td_features: Dict[str, float]) -> float:
    """估计是否应进入 survival-first 模式。"""
    turbulence = td_features.get("seed_turbulence", td_features.get("phase_turbulence", 0.0))
    noise = td_features.get("seed_noise", 0.0)
    tr = max(
        td_features.get("seed_technology_readiness", 0.5),
        td_features.get("seed_tech_readiness", 0.5),
    )
    fragility = 1.0 - tr
    pressure = 0.5 * turbulence + 0.3 * noise + 0.2 * td_features.get("env_resistance", 0.0)
    return max(0.0, min(1.0, pressure * (0.55 + 0.45 * fragility)))


def compute_attention_scores(
    td_features: Dict[str, float],
    candidates: List[Dict[str, Any]],
    temperature: float = 1.0,
) -> List[float]:
    """三阶段注意力评分。

    Stage 1: AFFINITY — 线性注意力 + survival dampening
    Stage 2: CONSTRAINT — 硬约束 cap
    Stage 3: NORMALIZE — softmax → [0.1, 0.95]
    """
    if not candidates:
        return []

    survival = _compute_survival_priority(td_features)

    # Stage 1 + 2: per-candidate
    constrained_scores = []
    for cand in candidates:
        payload = cand if isinstance(cand, dict) and "gamma_pcm" in cand else cand.get("payload", cand)
        cf = extract_candidate_features(payload)

        raw = _compute_affinity(td_features, cf, survival)
        constrained = _apply_constraints(raw, td_features, cf)
        constrained_scores.append(constrained)

    # Stage 3
    return _softmax_normalize(constrained_scores, temperature)


def compute_auto_herrscher_risk(
    td_features: Dict[str, float],
    candidate_params: dict,
    c_end: float,
    c_mean: float,
    c_std: float,
) -> float:
    """自动计算 herrscher_risk。"""
    cf = extract_candidate_features(candidate_params)

    env_risk = td_features.get("vein_risk_mean", 0.3)
    best_risk = td_features.get("best_risk", 0.3)
    base = 0.5 * env_risk + 0.5 * best_risk

    recklessness_penalty = 0.2 * cf.get("recklessness", 0.0)

    if c_std > 1e-8:
        collapse_penalty = 0.05 * min(abs(c_end - c_mean) / c_std, 3.0)
    else:
        collapse_penalty = 0.0

    patience_bonus = -0.08 * cf.get("patience", 0.5)

    herrscher = base + recklessness_penalty + collapse_penalty + patience_bonus
    return max(0.02, min(0.95, herrscher))
