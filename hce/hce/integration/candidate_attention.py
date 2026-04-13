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

    # 从 Tree 语义摘要中恢复环境阻力
    contradiction = oracle.get("core_contradiction", "")
    resistance = 0.0
    for word in ("resist", "drag", "noise", "fail", "crisis", "pressure", "conflict"):
        if word in contradiction.lower():
            resistance += 0.15
    features["env_resistance"] = min(resistance, 1.0)

    return features


def extract_candidate_features(candidate_params: dict) -> Dict[str, float]:
    """从 QCU 候选参数提取特征向量。"""
    raw = _extract_candidate_raw_features(candidate_params)
    semantic = _extract_candidate_identity_features(candidate_params)
    return _collapse_candidate_semantics(raw, semantic)


def _extract_candidate_raw_features(candidate_params: dict) -> Dict[str, float]:
    """提取候选的原始物理/数值特征。"""
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
        "balance": 1.0 - abs(conservatism - aggressiveness),
        "recklessness": aggressiveness * (1.0 - 0.5 * conservatism - 0.3 * patience),
    }


def _extract_candidate_identity_features(candidate_params: dict) -> Dict[str, float]:
    """从 label/candidate_id 提取候选身份语义。"""
    label = str(candidate_params.get("label", "")).lower()
    candidate_id = str(candidate_params.get("candidate_id", "")).lower()
    text = f"{label} {candidate_id}"

    token_map = _build_candidate_token_map(text)
    institutional_support = _compute_institutional_support(token_map)

    return {
        "alliance_synergy": float(token_map["joint"]),
        "institutional_support": institutional_support,
        "commercial_drive": float(token_map["spacex"]),
        "state_drive": float(token_map["china"]),
        "schedule_inertia": float(token_map["slip"]),
    }


def _match_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _build_candidate_token_map(text: str) -> Dict[str, bool]:
    token_specs = {
        "spacex": ("spacex",),
        "nasa": ("nasa", "artemis"),
        "china": ("china", "tianwen"),
        "slip": ("slip", "delay", "2045"),
    }
    token_map = {name: _match_any(text, tokens) for name, tokens in token_specs.items()}
    token_map["joint"] = _has_joint_marker(text)
    token_map["joint"] = token_map["joint"] or (token_map["spacex"] and token_map["nasa"])
    return token_map


def _compute_institutional_support(token_map: Dict[str, bool]) -> float:
    return min(
        1.0,
        0.7 * float(token_map["nasa"])
        + 0.6 * float(token_map["china"])
        + 0.2 * float(token_map["spacex"]),
    )


def _has_joint_marker(text: str) -> bool:
    return ("+" in text) or ("joint" in text)


def _collapse_candidate_semantics(
    raw_features: Dict[str, float],
    semantic_features: Dict[str, float],
) -> Dict[str, float]:
    """将候选原始特征和身份语义坍缩为少量候选潜变量。"""
    conservatism = raw_features["conservatism"]
    patience = raw_features["patience"]
    risk_appetite = raw_features["risk_appetite"]
    aggressiveness = raw_features["aggressiveness"]

    alliance_synergy = semantic_features["alliance_synergy"]
    institutional_support = semantic_features["institutional_support"]
    commercial_drive = semantic_features["commercial_drive"]
    state_drive = semantic_features["state_drive"]
    schedule_inertia = semantic_features["schedule_inertia"]

    survivability = min(1.0, 0.55 * conservatism + 0.25 * patience + 0.20 * (1.0 - risk_appetite))
    execution_speed = min(1.0, 0.65 * aggressiveness + 0.20 * commercial_drive + 0.15 * (1.0 - schedule_inertia))
    coordination = min(1.0, 0.70 * alliance_synergy + 0.30 * institutional_support)
    institutional_capacity = institutional_support

    return {
        **raw_features,
        **semantic_features,
        "survivability": survivability,
        "execution_speed": execution_speed,
        "coordination": coordination,
        "institutional_capacity": institutional_capacity,
    }


# ================================================================
# Stage 1: AFFINITY — 线性注意力
# ================================================================

# 每条规则: (env_feature, cand_feature, weight, mode)
# mode: "align" = 同向好, "oppose" = 反向好
# 按高频主轴分组，避免重复出现的语义散落成平铺长表。
# Trained weights (nano5, 200 iter, 30 pop, 28 samples)
# Baseline: 76.8% pairwise, 32.1% top-1
# Trained:  85.1% pairwise, 57.1% top-1
AFFINITY_GROUPS = {
    "survival_axis": [
        ("seed_survival_need", "survivability", 0.0889, "align"),
        ("seed_survival_need", "recklessness", 0.7832, "oppose"),
        ("field_coherence", "survivability", 0.6094, "align"),
        ("utm_drought", "survivability", 0.1144, "align"),
    ],
    "execution_axis": [
        ("seed_race_need", "execution_speed", 0.8741, "align"),
        ("seed_urgency", "schedule_inertia", 2.1799, "oppose"),
        ("seed_competition", "schedule_inertia", 1.7316, "oppose"),
        ("seed_commercial_motivation", "commercial_drive", 0.3805, "align"),
        ("seed_international_competition", "state_drive", 0.3154, "align"),
        ("seed_readiness_gap", "state_drive", 0.9636, "oppose"),
    ],
    "coordination_axis": [
        ("seed_coordination_need", "coordination", 0.8757, "align"),
    ],
    "institution_axis": [
        ("seed_institution_need", "institutional_capacity", 0.4373, "align"),
        ("best_feasibility", "institutional_capacity", 0.1034, "align"),
    ],
    "risk_axis": [
        ("seed_risk_tolerance", "risk_appetite", 0.0488, "align"),
        ("vein_risk_mean", "risk_appetite", 0.1332, "oppose"),
    ],
}


def _collapse_td_semantics(td_features: Dict[str, float]) -> Dict[str, float]:
    """将离散 seed 特征坍缩为少量可解释的环境主轴。"""
    collapsed = dict(td_features)

    turbulence = td_features.get("seed_turbulence", td_features.get("phase_turbulence", 0.0))
    noise = td_features.get("seed_noise", 0.0)
    resistance = td_features.get("env_resistance", 0.0)
    urgency = td_features.get("seed_urgency", td_features.get("goal_speed", 0.0))
    pressure = td_features.get("seed_pressure", 0.0)
    competition = max(
        td_features.get("seed_competition", 0.0),
        td_features.get("seed_international_competition", 0.0),
    )
    readiness_gap = td_features.get("seed_readiness_gap", 0.0)
    political_will = td_features.get("seed_political_will", 0.0)
    public_interest = td_features.get("seed_public_interest", 0.0)
    nasa_slip = td_features.get("seed_nasa_schedule_slip_history", 0.0)

    survival_need = min(1.0, 0.35 * turbulence + 0.20 * noise + 0.20 * resistance + 0.25 * readiness_gap)
    race_dampen = 1.0 - 0.55 * survival_need
    race_need = min(1.0, (0.45 * urgency + 0.30 * competition + 0.25 * pressure) * race_dampen)
    coordination_need = min(1.0, 0.65 * readiness_gap + 0.20 * competition + 0.15 * political_will)
    institution_need = min(1.0, 0.45 * political_will + 0.25 * public_interest + 0.30 * nasa_slip)

    collapsed["seed_survival_need"] = survival_need
    collapsed["seed_race_need"] = race_need
    collapsed["seed_coordination_need"] = coordination_need
    collapsed["seed_institution_need"] = institution_need
    return collapsed


def _score_affinity_group(
    td_features: Dict[str, float],
    cand_features: Dict[str, float],
    rules: List[tuple[str, str, float, str]],
) -> tuple[float, float]:
    """计算单个语义主轴的加权得分。"""
    score = 0.0
    total_weight = 0.0

    for env_key, cand_key, weight, mode in rules:
        env_val = td_features.get(env_key, -1.0)
        if env_val < 0:
            continue

        cand_val = cand_features.get(cand_key, 0.5)
        contribution = env_val * cand_val if mode == "align" else env_val * (1.0 - cand_val)
        score += weight * contribution
        total_weight += weight

    return score, total_weight


def _score_survival_axis(td_features: Dict[str, float], cand_features: Dict[str, float]) -> tuple[float, float]:
    return _score_affinity_group(td_features, cand_features, AFFINITY_GROUPS["survival_axis"])


def _score_execution_axis(td_features: Dict[str, float], cand_features: Dict[str, float]) -> tuple[float, float]:
    return _score_affinity_group(td_features, cand_features, AFFINITY_GROUPS["execution_axis"])


def _score_coordination_axis(td_features: Dict[str, float], cand_features: Dict[str, float]) -> tuple[float, float]:
    return _score_affinity_group(td_features, cand_features, AFFINITY_GROUPS["coordination_axis"])


def _score_institution_axis(td_features: Dict[str, float], cand_features: Dict[str, float]) -> tuple[float, float]:
    return _score_affinity_group(td_features, cand_features, AFFINITY_GROUPS["institution_axis"])


def _score_risk_axis(td_features: Dict[str, float], cand_features: Dict[str, float]) -> tuple[float, float]:
    return _score_affinity_group(td_features, cand_features, AFFINITY_GROUPS["risk_axis"])


def _score_affinity_breakdown(
    td_features: Dict[str, float],
    cand_features: Dict[str, float],
) -> Dict[str, float]:
    """按语义主轴返回归一化后的 affinity breakdown。"""
    group_scores = {
        "survival_axis": _score_survival_axis(td_features, cand_features),
        "execution_axis": _score_execution_axis(td_features, cand_features),
        "coordination_axis": _score_coordination_axis(td_features, cand_features),
        "institution_axis": _score_institution_axis(td_features, cand_features),
        "risk_axis": _score_risk_axis(td_features, cand_features),
    }

    weighted_sum = 0.0
    total_weight = 0.0
    breakdown: Dict[str, float] = {}
    for axis_name, (axis_score, axis_weight) in group_scores.items():
        breakdown[axis_name] = axis_score / max(axis_weight, 1e-8) if axis_weight > 0 else 0.0
        weighted_sum += axis_score
        total_weight += axis_weight

    breakdown["total"] = weighted_sum / max(total_weight, 1e-8)
    return breakdown


def _compute_affinity(
    td_features: Dict[str, float],
    cand_features: Dict[str, float],
) -> float:
    """Stage 1: 计算单个候选的亲和度分数。"""
    return _score_affinity_breakdown(td_features, cand_features)["total"]


# ================================================================
# Stage 2: CONSTRAINT — 硬约束（每个关注点只处理一次）
# ================================================================


def _get_td_readiness(td_features: Dict[str, float], default: float = -1.0) -> float:
    """统一读取技术成熟度 seed。"""
    return max(
        td_features.get("seed_technology_readiness", default),
        td_features.get("seed_tech_readiness", default),
    )


def _apply_readiness_penalty(
    score: float,
    td_features: Dict[str, float],
    cand_features: Dict[str, float],
) -> float:
    """低成熟度下抑制冒进候选。"""
    tr = _get_td_readiness(td_features)
    recklessness = cand_features.get("recklessness", 0.0)
    if not _needs_readiness_penalty(tr, recklessness):
        return score

    penalty = _compute_readiness_penalty(tr, recklessness)
    return score * max(penalty, 0.5)


def _apply_extremeness_penalty(score: float, cand_features: Dict[str, float]) -> float:
    """惩罚过于保守或过于激进的极端方案。"""
    if _is_extreme_candidate(cand_features):
        return score * 0.8
    return score


def _needs_readiness_penalty(tr: float, recklessness: float) -> bool:
    return tr >= 0 and tr < 0.5 and recklessness > 0.3


def _compute_readiness_penalty(tr: float, recklessness: float) -> float:
    tech_gap = (0.5 - tr) / 0.5
    return 1.0 - tech_gap * (recklessness - 0.3) * 0.4


def _is_extreme_candidate(cand_features: Dict[str, float]) -> bool:
    aggr = cand_features.get("aggressiveness", 0.5)
    conserv = cand_features.get("conservatism", 0.5)
    return aggr > 0.9 or conserv > 0.9

def _apply_constraints(
    raw_score: float,
    td_features: Dict[str, float],
    cand_features: Dict[str, float],
) -> float:
    """Stage 2: 施加硬约束上限。

    每条约束独立、不重叠。约束只能降低分数（cap），不能加分。
    """
    score = _apply_readiness_penalty(raw_score, td_features, cand_features)
    return _apply_extremeness_penalty(score, cand_features)


# ================================================================
# Stage 3: NORMALIZE — softmax
# ================================================================

def _softmax_normalize(scores: List[float], temperature: float) -> List[float]:
    """Stage 3: softmax 归一化到 [0.1, 0.95]。"""
    if len(scores) <= 1:
        return [_clamp_score(s) for s in scores]

    s_mean = sum(scores) / len(scores)
    s_std = (sum((s - s_mean) ** 2 for s in scores) / len(scores)) ** 0.5
    if s_std < 1e-8:
        return [0.5] * len(scores)

    z_scores = _compute_z_scores(scores, s_mean, s_std, temperature)
    exp_scores = [math.exp(min(z, 10)) for z in z_scores]
    exp_sum = sum(exp_scores)
    softmax = [e / exp_sum for e in exp_scores]
    return _stretch_softmax_scores(softmax)


def _compute_z_scores(scores: List[float], mean: float, std: float, temperature: float) -> List[float]:
    return [(score - mean) / std / temperature for score in scores]


def _stretch_softmax_scores(softmax_scores: List[float]) -> List[float]:
    sm_max = max(softmax_scores)
    sm_min = min(softmax_scores)
    sm_range = sm_max - sm_min if sm_max > sm_min else 1.0
    return [_clamp_score(0.1 + 0.85 * (sm - sm_min) / sm_range) for sm in softmax_scores]


def _clamp_score(score: float) -> float:
    return max(0.1, min(0.95, score))


# ================================================================
# 公开 API
# ================================================================


def _get_candidate_payload(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """兼容直接 payload 和包装后的候选对象。"""
    if _is_payload_dict(candidate):
        return candidate
    return _unwrap_candidate_payload(candidate)


def _is_payload_dict(candidate: Dict[str, Any]) -> bool:
    return isinstance(candidate, dict) and "gamma_pcm" in candidate


def _unwrap_candidate_payload(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return candidate.get("payload", candidate)


def _score_candidate(td_features: Dict[str, float], candidate: Dict[str, Any]) -> float:
    """执行单个候选的 affinity + constraints。"""
    return _score_candidate_details(td_features, candidate)["constrained_score"]


def _score_candidate_details(
    td_features: Dict[str, float],
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    """执行单个候选评分，并返回各主轴 breakdown。"""
    payload = _get_candidate_payload(candidate)
    cand_features = extract_candidate_features(payload)
    affinity_breakdown = _score_affinity_breakdown(td_features, cand_features)
    raw_score = affinity_breakdown["total"]
    constrained_score = _apply_constraints(raw_score, td_features, cand_features)
    return {
        "candidate_features": cand_features,
        "affinity_breakdown": affinity_breakdown,
        "raw_score": raw_score,
        "constrained_score": constrained_score,
    }


def _prepare_td_features(td_features: Dict[str, float]) -> Dict[str, float]:
    """统一准备用于候选评分的 TD 特征。"""
    prepared = _collapse_td_semantics(td_features)
    return _inject_readiness_gap(prepared)


def _inject_readiness_gap(td_features: Dict[str, float]) -> Dict[str, float]:
    tr = _get_td_readiness(td_features)
    return td_features if tr < 0 else _with_readiness_gap(td_features, tr)


def _with_readiness_gap(td_features: Dict[str, float], readiness: float) -> Dict[str, float]:
    prepared = dict(td_features)
    prepared["seed_readiness_gap"] = max(0.0, 1.0 - readiness)
    return prepared


def _normalize_candidate_scores(
    td_features: Dict[str, float],
    candidates: List[Dict[str, Any]],
    temperature: float,
) -> List[float]:
    constrained_scores = [_score_candidate(td_features, cand) for cand in candidates]
    return _softmax_normalize(constrained_scores, temperature)


def _build_attention_details(
    td_features: Dict[str, float],
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [_score_candidate_details(td_features, cand) for cand in candidates]


def _empty_attention_result() -> Dict[str, Any]:
    return {"scores": [], "details": []}


def _compute_attention_result(
    td_features: Dict[str, float],
    candidates: List[Dict[str, Any]],
    temperature: float,
) -> Dict[str, Any]:
    if not candidates:
        return _empty_attention_result()

    prepared_td = _prepare_td_features(td_features)
    details = _build_attention_details(prepared_td, candidates)
    constrained_scores = [detail["constrained_score"] for detail in details]
    scores = _softmax_normalize(constrained_scores, temperature)
    return {
        "scores": scores,
        "details": details,
    }


def compute_attention_scores(
    td_features: Dict[str, float],
    candidates: List[Dict[str, Any]],
    temperature: float = 1.0,
) -> List[float]:
    """三阶段注意力评分。

    Stage 1: AFFINITY — 线性注意力
    Stage 2: CONSTRAINT — 硬约束 cap
    Stage 3: NORMALIZE — softmax → [0.1, 0.95]
    """
    return _compute_attention_result(td_features, candidates, temperature)["scores"]


def compute_attention_details(
    td_features: Dict[str, float],
    candidates: List[Dict[str, Any]],
    temperature: float = 1.0,
) -> Dict[str, Any]:
    """返回注意力分数和每个候选的主轴贡献 breakdown。"""
    return _compute_attention_result(td_features, candidates, temperature)


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
