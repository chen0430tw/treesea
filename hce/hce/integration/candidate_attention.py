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
import re
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
    """从 QCU 候选参数提取特征向量。

    如果 payload 包含 strategy_tags，则用标签直接设置语义特征，
    跳过从 label 文本推断的不精确路径。
    """
    raw = _extract_candidate_raw_features(candidate_params)
    semantic = _extract_candidate_identity_features(candidate_params)
    features = _collapse_candidate_semantics(raw, semantic)

    # strategy_tags 覆盖：如果用户提供了显式标签，直接映射到特征维度
    tags = candidate_params.get("strategy_tags", [])
    if tags:
        features = _apply_strategy_tags(features, tags)

    return features


# 策略标签 → 特征维度映射
_TAG_FEATURE_MAP: Dict[str, Dict[str, float]] = {
    # 风格标签
    "conservative": {"conservatism": 0.85, "recklessness": 0.05, "survivability": 0.80},
    "moderate": {"balance": 0.85, "aggressiveness": 0.55, "conservatism": 0.50},
    "aggressive": {"aggressiveness": 0.85, "recklessness": 0.50, "execution_speed": 0.80},
    "ultra_aggressive": {"aggressiveness": 0.95, "recklessness": 0.85, "survivability": 0.10},
    # 能力标签
    "validated": {"evidence_maturity": 0.80, "deployability_signal": 0.70},
    "unproven": {"evidence_maturity": 0.10, "exploration": 0.70},
    "iterative": {"optionality": 0.80, "stepwise_signal": 0.70, "balance": 0.75},
    "all_in": {"optionality": 0.10, "recklessness": 0.60},
    # 协作标签
    "joint": {"coordination": 0.85, "alliance_synergy": 0.90},
    "institutional": {"institutional_capacity": 0.80, "legitimacy_signal": 0.70},
    "commercial": {"commercial_drive": 0.80, "execution_speed": 0.75},
    "state_backed": {"state_drive": 0.80, "institutional_capacity": 0.70},
    # 风险标签
    "low_risk": {"risk_appetite": 0.15, "survivability": 0.80, "containment_signal": 0.60},
    "high_risk": {"risk_appetite": 0.80, "recklessness": 0.60},
    "moderate_risk": {"risk_appetite": 0.45, "balance": 0.70},
    # 执行标签
    "fast": {"execution_speed": 0.85, "patience": 0.20},
    "slow": {"patience": 0.85, "execution_speed": 0.20},
    "proven_tech": {"evidence_maturity": 0.85, "deployability_signal": 0.75},
    "experimental": {"exploration": 0.80, "evidence_maturity": 0.15},
    # 伦理标签
    "ethical": {"ethical_legibility": 0.85, "harm_cost": 0.10},
    "harmful": {"harm_cost": 0.80, "ethical_legibility": 0.10},
    "transparent": {"visibility_signal": 0.80, "broadcast_signal": 0.70},
}


def _apply_strategy_tags(features: Dict[str, float], tags: List[str]) -> Dict[str, float]:
    """用策略标签覆盖特征值。多个标签取平均。"""
    overrides: Dict[str, List[float]] = {}
    for tag in tags:
        tag_lower = tag.lower().replace("-", "_").replace(" ", "_")
        mapping = _TAG_FEATURE_MAP.get(tag_lower, {})
        for feat_key, feat_val in mapping.items():
            overrides.setdefault(feat_key, []).append(feat_val)

    if overrides:
        features = dict(features)
        for feat_key, values in overrides.items():
            features[feat_key] = sum(values) / len(values)

    return features


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
    lexical_signals = _compute_candidate_lexical_signals(text)

    return {
        "alliance_synergy": float(token_map["joint"]),
        "institutional_support": institutional_support,
        "commercial_drive": float(token_map["spacex"]),
        "state_drive": float(token_map["china"]),
        "schedule_inertia": float(token_map["slip"]),
        **lexical_signals,
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


def _candidate_tokens(text: str) -> set[str]:
    normalized = text.replace("+", " ").replace("-", "_")
    return {token for token in re.split(r"[^a-z0-9_]+|_", normalized) if token}


def _signal_overlap(tokens: set[str], lexicon: tuple[str, ...]) -> float:
    if not lexicon:
        return 0.0
    matches = sum(1 for token in lexicon if token in tokens)
    return min(1.0, matches / max(len(lexicon) * 0.5, 1.0))


def _compute_candidate_lexical_signals(text: str) -> Dict[str, float]:
    tokens = _candidate_tokens(text)
    lexicons = {
        "containment_signal": (
            "evacuate", "isolate", "lockdown", "shelter", "brake",
            "life", "support", "stockpile", "contain", "quarantine",
            "retreat", "comfort", "palliative", "geological", "storage",
        ),
        "mobility_signal": (
            "evacuate", "evacuation", "isolate", "retreat", "brake",
            "reroute", "relocate", "withdraw",
        ),
        "deployability_signal": (
            "wind", "solar", "renewable", "storage", "mrna",
            "therapy", "car", "targeted", "asymmetric", "diversify",
            "checkpoint", "guardrails", "platform", "pilot",
        ),
        "broadcast_signal": (
            "media", "public", "campaign", "expose", "broadcast",
            "anonymous", "regulator", "gdpr",
        ),
        "stepwise_signal": (
            "gate", "gaa", "storage", "targeted", "diversify",
            "platform", "guardrails", "checkpoint", "hybrid", "pilot",
            "iterate", "mvp", "adjacent", "bilateral", "managed",
        ),
        "visibility_signal": (
            "public", "media", "anonymous", "regulator", "gdpr",
            "framework", "appeal", "court", "fight", "whistleblower",
            "expose", "campaign",
        ),
        "guardrail_signal": (
            "guardrails", "geofenced", "checkpoint", "targeted",
            "asymmetric", "bilateral", "start", "triage", "gaa",
            "gate", "managed",
        ),
        "durability_signal": (
            "deep", "geological", "permanent", "repository", "storage",
            "metro", "grid", "seawall", "deterrence",
        ),
        "legitimacy_signal": (
            "legal", "regulator", "anonymous", "appeal", "court",
            "media", "public", "framework", "guardrails", "blind",
            "waiting", "match", "start", "triage",
        ),
        "platform_signal": (
            "platform", "pilot", "iterate", "hybrid", "mvp",
            "modular", "storage", "geofenced", "guardrails", "checkpoint",
            "bilateral", "diversify", "isru",
        ),
        "optionality_signal": (
            "pilot", "iterate", "gradual", "hybrid", "appeal", "anonymous",
            "negotiate", "adjacent", "bilateral", "checkpoint", "weighted",
            "start", "tit", "match", "palliative",
        ),
        "evidence_signal": (
            "standard", "traditional", "best", "match", "checkpoint",
            "deterrence", "start", "weighted", "appeal", "proven",
        ),
        "harm_signal": (
            "strike", "torture", "enhanced", "scorched", "strongest",
            "bidder", "defect", "preemptive", "ransom", "ignore",
            "flee", "replace", "hype", "nepotism",
        ),
        "novelty_signal": (
            "experimental", "mrna", "ai", "hydrogen", "cfet", "serverless",
            "digital", "rewrite", "phage", "vaporware",
        ),
        "fairness_signal": (
            "anonymous", "weighted", "waiting", "lottery", "blind",
            "tit", "start", "best", "match", "appeal",
        ),
    }
    return {
        name: _signal_overlap(tokens, lexicon)
        for name, lexicon in lexicons.items()
    }


def _collapse_candidate_semantics(
    raw_features: Dict[str, float],
    semantic_features: Dict[str, float],
) -> Dict[str, float]:
    """将候选原始特征和身份语义坍缩为少量候选潜变量。"""
    conservatism = raw_features["conservatism"]
    patience = raw_features["patience"]
    risk_appetite = raw_features["risk_appetite"]
    aggressiveness = raw_features["aggressiveness"]
    balance = raw_features["balance"]

    alliance_synergy = semantic_features["alliance_synergy"]
    institutional_support = semantic_features["institutional_support"]
    commercial_drive = semantic_features["commercial_drive"]
    state_drive = semantic_features["state_drive"]
    schedule_inertia = semantic_features["schedule_inertia"]
    containment_signal = semantic_features.get("containment_signal", 0.0)
    mobility_signal = semantic_features.get("mobility_signal", 0.0)
    deployability_signal = semantic_features.get("deployability_signal", 0.0)
    broadcast_signal = semantic_features.get("broadcast_signal", 0.0)
    stepwise_signal = semantic_features.get("stepwise_signal", 0.0)
    visibility_signal = semantic_features.get("visibility_signal", 0.0)
    guardrail_signal = semantic_features.get("guardrail_signal", 0.0)
    durability_signal = semantic_features.get("durability_signal", 0.0)
    legitimacy_signal = semantic_features.get("legitimacy_signal", 0.0)
    platform_signal = semantic_features.get("platform_signal", 0.0)
    optionality_signal = semantic_features.get("optionality_signal", 0.0)
    evidence_signal = semantic_features.get("evidence_signal", 0.0)
    harm_signal = semantic_features.get("harm_signal", 0.0)
    novelty_signal = semantic_features.get("novelty_signal", 0.0)
    fairness_signal = semantic_features.get("fairness_signal", 0.0)

    survivability = min(
        1.0,
        0.45 * conservatism
        + 0.20 * patience
        + 0.15 * (1.0 - risk_appetite)
        + 0.15 * containment_signal
        + 0.05 * mobility_signal,
    )
    execution_speed = min(
        1.0,
        0.50 * aggressiveness
        + 0.15 * commercial_drive
        + 0.15 * (1.0 - schedule_inertia)
        + 0.10 * platform_signal
        + 0.05 * guardrail_signal
        + 0.05 * deployability_signal,
    )
    coordination = min(1.0, 0.70 * alliance_synergy + 0.30 * institutional_support)
    institutional_capacity = institutional_support
    optionality = min(
        1.0,
        0.35 * patience
        + 0.25 * (1.0 - risk_appetite)
        + 0.10 * balance
        + 0.10 * optionality_signal
        + 0.10 * platform_signal
        + 0.05 * guardrail_signal
        + 0.05 * stepwise_signal,
    )
    evidence_maturity = min(
        1.0,
        0.24 * survivability
        + 0.20 * institutional_support
        + 0.18 * evidence_signal
        + 0.13 * (1.0 - novelty_signal)
        + 0.13 * platform_signal
        + 0.07 * durability_signal
        + 0.05 * deployability_signal
        + 0.05 * stepwise_signal,
    )
    ethical_legibility = min(
        1.0,
        0.22 * institutional_support
        + 0.20 * fairness_signal
        + 0.18 * (1.0 - harm_signal)
        + 0.15 * coordination
        + 0.15 * legitimacy_signal
        + 0.05 * visibility_signal
        + 0.05 * broadcast_signal,
    )
    decisiveness = min(1.0, 0.55 * aggressiveness + 0.25 * (1.0 - patience) + 0.20 * balance)
    exploration = min(1.0, 0.55 * aggressiveness + 0.45 * risk_appetite)
    harm_cost = harm_signal

    return {
        **raw_features,
        **semantic_features,
        "survivability": survivability,
        "execution_speed": execution_speed,
        "coordination": coordination,
        "institutional_capacity": institutional_capacity,
        "optionality": optionality,
        "evidence_maturity": evidence_maturity,
        "ethical_legibility": ethical_legibility,
        "decisiveness": decisiveness,
        "exploration": exploration,
        "harm_cost": harm_cost,
    }


# ================================================================
# Stage 1: AFFINITY — 线性注意力
# ================================================================

# 每条规则: (env_feature, cand_feature, weight, mode)
# mode: "align" = 同向好, "oppose" = 反向好
# 按高频主轴分组，避免重复出现的语义散落成平铺长表。
# Trained weights (nano5, 200 iter, 30 pop, 43 samples incl. ethical dilemmas)
# Baseline: 76.8% pairwise, 32.1% top-1
# Round 1 (28 samples): 85.1% pairwise, 57.1% top-1
# Round 2 (43 samples): 84.9% pairwise, 58.1% top-1
# Trained weights (nano5, round 4, 43 samples + strategy_tags)
# Pairwise: 95.0%, Top-1: 90.7% (39/43)
AFFINITY_GROUPS = {
    "survival_axis": [
        ("seed_survival_need", "survivability", 4.9477, "align"),
        ("seed_survival_need", "recklessness", 0.0848, "oppose"),
        ("seed_survival_need", "optionality", 0.0100, "align"),
        ("seed_survival_need", "ethical_legibility", 5.3515, "align"),
        ("seed_survival_need", "harm_cost", 0.2811, "oppose"),
        ("field_coherence", "survivability", 2.0198, "align"),
        ("utm_drought", "survivability", 0.0900, "align"),
    ],
    "execution_axis": [
        ("seed_race_need", "execution_speed", 0.0624, "align"),
        ("seed_race_need", "decisiveness", 3.8812, "align"),
        ("seed_race_need", "optionality", 1.6545, "align"),
        ("seed_urgency", "schedule_inertia", 0.6321, "oppose"),
        ("seed_competition", "schedule_inertia", 0.0656, "oppose"),
        ("seed_commercial_motivation", "commercial_drive", 0.2339, "align"),
        ("seed_international_competition", "state_drive", 0.3026, "align"),
        ("seed_readiness_gap", "state_drive", 0.0770, "oppose"),
        ("seed_readiness_gap", "exploration", 0.9532, "oppose"),
    ],
    "coordination_axis": [
        ("seed_coordination_need", "coordination", 0.0578, "align"),
        ("seed_coordination_need", "ethical_legibility", 0.0410, "align"),
    ],
    "institution_axis": [
        ("seed_institution_need", "institutional_capacity", 0.1912, "align"),
        ("seed_institution_need", "evidence_maturity", 11.6631, "align"),
        ("seed_institution_need", "ethical_legibility", 0.1321, "align"),
        ("best_feasibility", "institutional_capacity", 0.0906, "align"),
    ],
    "risk_axis": [
        ("seed_risk_tolerance", "risk_appetite", 0.0100, "align"),
        ("seed_risk_tolerance", "exploration", 2.4447, "align"),
        ("vein_risk_mean", "risk_appetite", 0.0154, "oppose"),
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
    """Stage 1 + 1.5: 线性亲和度 + 特征交叉。"""
    linear = _score_affinity_breakdown(td_features, cand_features)["total"]
    return _compute_feature_crosses(td_features, cand_features, linear)


# ================================================================
# Stage 1.5: FEATURE CROSS — 非线性交互项
# ================================================================
# 线性注意力的天花板在于无法表达条件组合。
# 特征交叉捕获 "A AND B → bonus/penalty" 的交互。
# 每条交叉规则: (condition_fn, bonus_fn, weight)

# 可训练的交叉权重
CROSS_WEIGHTS = {
    "crisis_moderate_bonus": 0.0181,
    "reckless_in_race_penalty": 0.0393,
    "joint_urgency_bonus": 0.0703,
    "no_race_conserv_bonus": 0.6574,
    "inaction_penalty": 0.2869,
    "optionality_bonus": 0.8730,
    "ethical_legibility_bonus": 0.1316,
    "novelty_readiness_penalty": 0.1034,
    "decisive_containment_bonus": 0.1375,
    "platform_guardrail_bonus": 0.0970,
    "visibility_legitimacy_bonus": 0.1230,
    "deployability_bonus": 0.0865,
}


def _compute_feature_crosses(
    td_features: Dict[str, float],
    cand_features: Dict[str, float],
    affinity_score: float,
) -> float:
    """在线性亲和度分数上叠加非线性交互项。

    每条交叉规则是一个条件判断 + 加成/惩罚。
    和线性规则不同，这里的贡献是乘性的或阈值触发的。
    """
    s = affinity_score

    survival_need = td_features.get("seed_survival_need", 0.0)
    race_need = td_features.get("seed_race_need", 0.0)
    readiness_gap = td_features.get("seed_readiness_gap", 0.0)

    aggr = cand_features.get("aggressiveness", 0.5)
    conserv = cand_features.get("conservatism", 0.5)
    balance = cand_features.get("balance", 0.5)
    recklessness = cand_features.get("recklessness", 0.0)
    survivability = cand_features.get("survivability", 0.5)
    execution_speed = cand_features.get("execution_speed", 0.5)
    coordination = cand_features.get("coordination", 0.0)
    optionality = cand_features.get("optionality", 0.0)
    evidence_maturity = cand_features.get("evidence_maturity", 0.0)
    ethical_legibility = cand_features.get("ethical_legibility", 0.0)
    exploration = cand_features.get("exploration", 0.0)
    harm_cost = cand_features.get("harm_cost", 0.0)
    deployability = cand_features.get("deployability_signal", 0.0)
    visibility = cand_features.get("visibility_signal", 0.0)
    broadcast = cand_features.get("broadcast_signal", 0.0)
    legitimacy = cand_features.get("legitimacy_signal", 0.0)
    containment = cand_features.get("containment_signal", 0.0)
    mobility = cand_features.get("mobility_signal", 0.0)
    guardrails = cand_features.get("guardrail_signal", 0.0)
    platform = cand_features.get("platform_signal", 0.0)
    stepwise = cand_features.get("stepwise_signal", 0.0)

    w = CROSS_WEIGHTS
    institution_need = td_features.get("seed_institution_need", 0.0)
    readiness = 1.0 - readiness_gap
    schedule_inertia = cand_features.get("schedule_inertia", 0.0)

    # 独立计算每条交叉项，不原地修改 s
    bonuses = [
        _cross_crisis_moderate(survival_need, aggr, balance, w),
        _cross_joint_urgency(race_need, coordination, w),
        _cross_no_race_conserv(race_need, conserv, w),
        _cross_optionality(survival_need, optionality, w),
        _cross_ethical(institution_need, ethical_legibility, w),
        _cross_decisive_containment(survival_need, containment, aggr, balance, w),
        _cross_platform_guardrail(readiness_gap, race_need, platform, guardrails, w),
        _cross_visibility(survival_need, td_features.get("seed_competition", 0.0), broadcast, legitimacy, visibility, w),
        _cross_deployability(readiness, deployability, schedule_inertia, w),
        _cross_mobility(survival_need, mobility, w),
        _cross_stepwise(readiness, race_need, stepwise, w),
    ]
    penalties = [
        _cross_reckless_race(race_need, readiness_gap, recklessness, w),
        _cross_inaction(survival_need, conserv, aggr, w),
        _cross_novelty_readiness(readiness_gap, exploration, evidence_maturity, w),
    ]

    return affinity_score + sum(bonuses) - sum(penalties)


def _cross_crisis_moderate(survival_need, aggr, balance, w):
    if survival_need > 0.4 and 0.35 < aggr < 0.75 and balance > 0.6:
        return survival_need * balance * w["crisis_moderate_bonus"]
    return 0.0

def _cross_reckless_race(race_need, readiness_gap, recklessness, w):
    if race_need > 0.4 and readiness_gap > 0.3 and recklessness > 0.3:
        return race_need * readiness_gap * recklessness * w["reckless_in_race_penalty"]
    return 0.0

def _cross_joint_urgency(race_need, coordination, w):
    if race_need > 0.3 and coordination > 0.3:
        return race_need * coordination * w["joint_urgency_bonus"]
    return 0.0

def _cross_no_race_conserv(race_need, conserv, w):
    if race_need < 0.3 and conserv > 0.6:
        return (1.0 - race_need) * conserv * w["no_race_conserv_bonus"]
    return 0.0

def _cross_inaction(survival_need, conserv, aggr, w):
    if survival_need > 0.5 and conserv > 0.8 and aggr < 0.4:
        return survival_need * (conserv - 0.8) * w["inaction_penalty"]
    return 0.0

def _cross_optionality(survival_need, optionality, w):
    if survival_need > 0.35 and optionality > 0.35:
        return survival_need * optionality * w["optionality_bonus"]
    return 0.0

def _cross_ethical(institution_need, ethical_legibility, w):
    if institution_need > 0.3 and ethical_legibility > 0.35:
        return institution_need * ethical_legibility * w["ethical_legibility_bonus"]
    return 0.0

def _cross_novelty_readiness(readiness_gap, exploration, evidence_maturity, w):
    if readiness_gap > 0.25 and exploration > evidence_maturity:
        return readiness_gap * (exploration - evidence_maturity) * w["novelty_readiness_penalty"]
    return 0.0

def _cross_decisive_containment(survival_need, containment, aggr, balance, w):
    if survival_need > 0.45 and containment > 0.35 and 0.35 < aggr < 0.75:
        return survival_need * containment * balance * w["decisive_containment_bonus"]
    return 0.0

def _cross_platform_guardrail(readiness_gap, race_need, platform, guardrails, w):
    if readiness_gap > 0.4 and race_need > 0.3 and (platform > 0.3 or guardrails > 0.3):
        return readiness_gap * race_need * max(platform, guardrails) * w["platform_guardrail_bonus"]
    return 0.0

def _cross_visibility(survival_need, competition, broadcast, legitimacy, visibility, w):
    if survival_need > 0.35 and competition < 0.2 and broadcast > 0.3:
        return survival_need * max(broadcast, legitimacy, visibility) * w["visibility_legitimacy_bonus"]
    return 0.0

def _cross_deployability(readiness, deployability, schedule_inertia, w):
    if 0.45 < readiness < 0.75 and deployability > 0.35:
        return readiness * deployability * (1.0 - schedule_inertia) * w["deployability_bonus"]
    return 0.0

def _cross_mobility(survival_need, mobility, w):
    if survival_need > 0.45 and mobility > 0.3:
        return survival_need * mobility * w["decisive_containment_bonus"]
    return 0.0

def _cross_stepwise(readiness, race_need, stepwise, w):
    if 0.35 < readiness < 0.85 and race_need > 0.25 and stepwise > 0.3:
        return readiness * race_need * stepwise * w["deployability_bonus"]
    return 0.0


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


def _extract_and_score(td_features: Dict[str, float], candidate: Dict[str, Any]) -> Dict[str, float]:
    """Step 1: 提取候选特征。"""
    return extract_candidate_features(_get_candidate_payload(candidate))


def _compute_breakdown(td_features: Dict[str, float], cand_features: Dict[str, float]) -> Dict[str, float]:
    """Step 2: 计算各主轴亲和度 breakdown。"""
    return _score_affinity_breakdown(td_features, cand_features)


def _constrain_score(raw_score: float, td_features: Dict[str, float], cand_features: Dict[str, float]) -> float:
    """Step 3: 施加硬约束。"""
    return _apply_constraints(raw_score, td_features, cand_features)


def _score_candidate_details(
    td_features: Dict[str, float],
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    """执行单个候选评分，并返回各主轴 breakdown。"""
    cand_features = _extract_and_score(td_features, candidate)
    affinity_breakdown = _compute_breakdown(td_features, cand_features)
    raw_score = affinity_breakdown["total"]
    constrained_score = _constrain_score(raw_score, td_features, cand_features)
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
