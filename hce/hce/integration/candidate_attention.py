# candidate_attention.py
"""
候选注意力评分。

参考 Transformer 注意力机制，对每个 QCU 候选计算差异化的 tree_score：
  - Tree Diagram oracle 输出的特征向量 → Key/Value
  - QCU 候选的参数向量 → Query
  - Attention(Q, K, V) → 每个候选的 tree_score

这样不同候选会根据其参数与问题特征的匹配度获得不同分数，
而不是所有候选拿到同一个全局分数。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


def extract_td_features(tree_output: dict) -> Dict[str, float]:
    """从 Tree Diagram 输出提取特征向量。

    提取来源：
    - oracle_details.field_snapshot (5 维)
    - hydro_control.vein_stats.* (4x3 维)
    - hydro_control.cbf_allocation (6 维)
    - hydro_control.ipl_index (3 维)
    - best_worldline.* (5 维)
    """
    oracle = tree_output.get("oracle_details", {})
    hydro = tree_output.get("hydro_control", {})
    best_wl = tree_output.get("best_worldline", oracle.get("best_worldline", {}))

    features: Dict[str, float] = {}

    # field_snapshot: 问题场的结构特征
    field = oracle.get("field_snapshot", {})
    features["field_coherence"] = field.get("field_coherence", 0.5)
    features["network_amplification"] = field.get("network_amplification", 0.5)
    features["governance_drag"] = field.get("governance_drag", 0.5)
    features["phase_turbulence"] = field.get("phase_turbulence", 0.5)
    features["resource_elasticity"] = field.get("resource_elasticity", 0.5)

    # vein_stats: 脉络统计
    vein_stats = hydro.get("vein_stats", {})
    for metric in ["yield", "stability", "risk", "composite"]:
        ms = vein_stats.get(metric, {})
        features[f"vein_{metric}_mean"] = ms.get("mean", 0.5)
        features[f"vein_{metric}_spread"] = ms.get("max", 0.5) - ms.get("min", 0.5)

    # cbf_allocation: 资源分配策略
    cbf = hydro.get("cbf_allocation", {})
    features["cbf_cheap"] = cbf.get("cheap", 0.0)
    features["cbf_refine"] = cbf.get("refine", 0.5)
    features["cbf_slow"] = cbf.get("slow", 0.5)
    features["cbf_crackdown"] = cbf.get("crackdown_ratio", 0.0)

    # ipl_index: 相位索引
    ipl = hydro.get("ipl_index", {})
    features["ipl_gain_centroid"] = ipl.get("smoothed_gain_centroid", 0.5)
    features["ipl_phase_spread"] = ipl.get("phase_spread", 0.0)

    # best_worldline: 最佳世界线特征
    features["best_feasibility"] = best_wl.get("feasibility", 0.5)
    features["best_stability"] = best_wl.get("stability", 0.5)
    features["best_risk"] = best_wl.get("risk", 0.3)
    features["best_score"] = best_wl.get("final_balanced_score",
                              best_wl.get("balanced_score", 0.5))

    # 水文状态编码
    utm_state = hydro.get("utm_hydro_state", "NORMAL")
    features["utm_flood"] = 1.0 if utm_state == "FLOOD" else 0.0
    features["utm_drought"] = 1.0 if utm_state == "DROUGHT" else 0.0

    # === 从 seed 的 environment/subject 直接注入 ===
    # TD 的 field_snapshot 来自内部模拟，不反映 seed 的问题特性
    # 所以把 seed 的原始环境参数也作为特征，确保不同问题有不同的注意力分布
    seed_ctx = oracle.get("seed_context", {})
    # seed 信息可能在不同位置，尝试多种路径
    if not seed_ctx:
        # 从 llm_explanation 或直接从 seed 字段提取
        llm = oracle.get("llm_explanation", {})
        seed_ctx = llm.get("json_payload", {})

    # 尝试从 tree_output 顶层获取 seed 信息
    # TreeDiagramRunner 把 seed 传入，但 oracle_details 可能不保留原始 seed
    # 需要从 dominant_pressures 推断
    pressures = oracle.get("dominant_pressures", [])
    n_pressures = len(pressures)
    features["n_pressures"] = min(n_pressures / 10.0, 1.0)

    # 从 core_contradiction 推断紧迫性
    contradiction = oracle.get("core_contradiction", "")
    # 包含 "resist" / "drag" / "noise" → 高阻力环境
    features["env_resistance"] = 0.0
    for word in ["resist", "drag", "noise", "fail", "crisis", "pressure", "conflict"]:
        if word in contradiction.lower():
            features["env_resistance"] += 0.15
    features["env_resistance"] = min(features["env_resistance"], 1.0)

    # 从 goal_axis 推断策略倾向
    goal = oracle.get("inferred_goal_axis", "")
    features["goal_precision"] = 1.0 if "precision" in goal.lower() else 0.0
    features["goal_dominance"] = 1.0 if "dominance" in goal.lower() else 0.0
    features["goal_stability"] = 1.0 if "stabil" in goal.lower() else 0.0
    features["goal_speed"] = 1.0 if "speed" in goal.lower() or "fast" in goal.lower() else 0.0

    # branch_histogram: 分支生态
    branch_hist = oracle.get("branch_histogram", {})
    total_branches = sum(branch_hist.values()) if branch_hist else 1
    features["branch_active_ratio"] = branch_hist.get("active", 0) / max(total_branches, 1)
    features["branch_withered_ratio"] = branch_hist.get("withered", 0) / max(total_branches, 1)

    return features


def extract_candidate_features(candidate_params: dict) -> Dict[str, float]:
    """从 QCU 候选参数提取特征向量。

    QCU 候选参数编码了策略特性：
    - gamma_pcm: 同步耗散率 → 越低=越保守/稳定
    - gamma_boost: 增强强度 → 越高=越激进
    - boost_duration: 增强时长 → 越长=越有耐心
    - gamma_phi0: 相位噪声 → 越高=越高风险/高回报
    """
    features: Dict[str, float] = {}

    # 直接参数
    gamma_pcm = candidate_params.get("gamma_pcm", 0.15)
    gamma_boost = candidate_params.get("gamma_boost", 0.7)
    boost_duration = candidate_params.get("boost_duration", 2.5)
    gamma_phi0 = candidate_params.get("gamma_phi0", 0.25)

    features["conservatism"] = 1.0 - min(gamma_pcm / 0.3, 1.0)      # 低 pcm = 保守
    features["aggressiveness"] = min(gamma_boost / 1.0, 1.0)          # 高 boost = 激进
    features["patience"] = min(boost_duration / 5.0, 1.0)             # 长 duration = 耐心
    features["risk_appetite"] = min(gamma_phi0 / 0.5, 1.0)            # 高 phi0 = 冒险
    features["intensity"] = (gamma_pcm + gamma_boost) / 2.0           # 综合强度
    features["balance"] = 1.0 - abs(gamma_pcm - gamma_phi0)           # pcm 和 phi0 的平衡度
    # 综合成熟度：低 pcm + 中等 boost + 长 duration = 成熟的方案
    features["maturity"] = (
        (1.0 - min(gamma_pcm / 0.3, 1.0)) * 0.3      # 低同步损耗
        + min(boost_duration / 5.0, 1.0) * 0.4         # 有耐心
        + (1.0 - min(gamma_phi0 / 0.5, 1.0)) * 0.3    # 低噪声
    )
    # 极端度：越接近中间越低
    mid_boost = abs(gamma_boost - 0.65) / 0.35  # 0.65 为中位
    features["extremeness"] = min(mid_boost, 1.0)

    return features


def compute_attention_scores(
    td_features: Dict[str, float],
    candidates: List[Dict[str, Any]],
    temperature: float = 1.0,
) -> List[float]:
    """计算候选注意力分数。

    Attention(Q, K) = softmax(Q · K^T / sqrt(d) / temperature)

    Q: 每个候选的特征向量
    K: TD 问题特征向量
    分数 = Q 和 K 的加权匹配度

    Parameters
    ----------
    td_features : dict
        Tree Diagram 特征
    candidates : list of dict
        每个候选的 payload（含 QCU 参数）
    temperature : float
        温度参数，越低分化越大

    Returns
    -------
    list of float
        每个候选的 attention score（已归一化到 [0, 1]）
    """
    if not candidates:
        return []

    # 定义注意力权重矩阵：哪些 TD 特征关注哪些候选特征
    # 这是一个可学习的交叉注意力映射
    attention_map = {
        # (td_feature, cand_feature, weight, mode)
        # mode: "align" = 同方向好, "oppose" = 反方向好
        ("field_coherence", "conservatism", 0.8, "align"),       # 高相干场 → 保守策略好
        ("field_coherence", "aggressiveness", 0.3, "oppose"),    # 高相干场 → 激进不好
        ("governance_drag", "patience", 0.9, "align"),           # 高治理阻力 → 需要耐心
        ("governance_drag", "aggressiveness", 0.5, "oppose"),    # 高阻力 → 激进不好
        ("phase_turbulence", "risk_appetite", 0.6, "oppose"),    # 高湍流 → 冒险不好
        ("phase_turbulence", "conservatism", 0.4, "align"),      # 高湍流 → 保守好
        ("network_amplification", "aggressiveness", 0.7, "align"), # 高放大 → 可以激进
        ("network_amplification", "intensity", 0.5, "align"),    # 高放大 → 高强度可行
        ("resource_elasticity", "balance", 0.6, "align"),        # 高弹性 → 平衡策略好
        ("vein_stability_mean", "conservatism", 0.7, "align"),   # 高稳定 → 保守好
        ("vein_risk_mean", "risk_appetite", 0.8, "oppose"),      # 高风险环境 → 冒险不好
        ("best_feasibility", "patience", 0.5, "align"),          # 高可行性 → 耐心策略好
        ("best_risk", "aggressiveness", 0.6, "oppose"),          # 高风险 → 激进不好
        ("cbf_crackdown", "conservatism", 0.7, "align"),         # 高打压比 → 保守存活
        ("cbf_slow", "patience", 0.5, "align"),                  # 慢通道多 → 耐心好
        ("utm_flood", "aggressiveness", 0.4, "align"),           # 洪水态 → 可以激进
        ("utm_drought", "conservatism", 0.8, "align"),           # 旱灾态 → 必须保守
        ("ipl_gain_centroid", "intensity", 0.5, "align"),        # 增益中心高 → 高强度可行
        # seed 环境特征
        ("env_resistance", "conservatism", 1.0, "align"),         # 高阻力 → 保守存活
        ("env_resistance", "aggressiveness", 0.8, "oppose"),      # 高阻力 → 激进死
        ("env_resistance", "patience", 0.9, "align"),             # 高阻力 → 需要耐心
        ("n_pressures", "intensity", 0.6, "align"),               # 压力多 → 需要强度
        ("goal_speed", "aggressiveness", 0.8, "align"),           # 目标快 → 激进好
        ("goal_speed", "patience", 0.5, "oppose"),                # 目标快 → 耐心差
        ("goal_stability", "conservatism", 0.8, "align"),         # 目标稳 → 保守好
        ("goal_dominance", "aggressiveness", 0.7, "align"),       # 目标主导 → 激进好
        ("goal_precision", "balance", 0.6, "align"),              # 目标精确 → 平衡好
        ("branch_active_ratio", "aggressiveness", 0.5, "align"),  # 活跃分支多 → 可以激进
        ("branch_withered_ratio", "conservatism", 0.7, "align"),  # 枯萎多 → 保守存活
        # seed 原始参数（以 seed_ 前缀注入）
        # 权重 2.0-3.0：seed 特征是问题的本质，必须强于 TD 固有特征
        ("seed_turbulence", "conservatism", 3.0, "align"),        # 高湍流 → 保守
        ("seed_turbulence", "aggressiveness", 2.5, "oppose"),     # 高湍流 → 激进死
        ("seed_stability", "aggressiveness", 2.5, "align"),       # 高稳定 → 可以激进
        ("seed_stability", "conservatism", 2.0, "oppose"),        # 高稳定 → 不需要保守
        ("seed_pressure", "intensity", 2.0, "align"),             # 高压力 → 需要强度
        ("seed_pressure", "patience", 2.0, "oppose"),             # 高压力 → 没时间慢慢来
        ("seed_noise", "conservatism", 2.5, "align"),             # 高噪声 → 保守安全
        ("seed_noise", "risk_appetite", 2.0, "oppose"),           # 高噪声 → 别冒险
        ("seed_urgency", "aggressiveness", 3.0, "align"),         # 紧急 → 激进
        ("seed_urgency", "patience", 2.5, "oppose"),              # 紧急 → 没耐心
        ("seed_complexity", "balance", 2.0, "align"),             # 复杂 → 需要平衡
        ("seed_risk_tolerance", "risk_appetite", 2.5, "align"),   # 容忍风险 → 可以冒险
        ("seed_risk_tolerance", "conservatism", 2.0, "oppose"),   # 容忍风险 → 不需要保守
        ("seed_experience", "aggressiveness", 2.0, "align"),      # 经验丰富 → 可以激进
        # 技术成熟度：低 TRL → 激进必死，高 TRL → 激进可行
        ("seed_technology_readiness", "aggressiveness", 3.0, "align"),  # 技术成熟 → 激进OK
        ("seed_technology_readiness", "conservatism", 2.0, "oppose"),   # 技术成熟 → 不需保守
        ("seed_tech_readiness", "aggressiveness", 3.0, "align"),       # 别名
        ("seed_tech_readiness", "conservatism", 2.0, "oppose"),
        # 反向：技术不成熟时用 1-value 编码，这里用 oppose 实现
        # 当 seed_technology_readiness=0.35 (低):
        #   aggressiveness align → 0.35 * aggressive = 低分 (好)
        #   conservatism oppose → 0.35 * (1-conserv) = 对保守有利
        # 政治意愿
        ("seed_political_will", "patience", 2.5, "align"),       # 高政治意愿 → 长期项目可行
        ("seed_political_will_usa", "patience", 2.0, "align"),
        ("seed_political_will_china", "aggressiveness", 2.0, "align"),  # 中国政治意愿高 → 可以激进推
        # 商业动机
        ("seed_commercial_motivation", "aggressiveness", 2.0, "align"),
        ("seed_commercial_motivation", "risk_appetite", 1.5, "align"),
        # 公众兴趣
        ("seed_public_interest", "patience", 1.5, "align"),       # 公众支持 → 长期项目可行
        # 国际竞争（高竞争 → 需要速度，但也需要技术准备）
        ("seed_international_competition", "intensity", 2.0, "align"),
        # 执行力
        ("seed_spacex_execution_track_record", "aggressiveness", 2.5, "align"),  # 执行力强 → 激进可行
        ("seed_nasa_schedule_slip_history", "patience", 2.0, "align"),           # NASA 延期历史 → 需要耐心
        ("seed_nasa_schedule_slip_history", "aggressiveness", 1.5, "oppose"),    # NASA 延期 → 激进不靠谱
        # 成熟度和极端度
        ("seed_technology_readiness", "maturity", 2.5, "align"),    # 低 TRL + 高成熟方案 = 不匹配但安全
        ("seed_competition", "extremeness", 1.5, "oppose"),         # 竞争中极端策略不好
        ("seed_competition", "balance", 2.0, "align"),              # 竞争中平衡策略好
        ("seed_competition", "maturity", 1.5, "align"),             # 竞争中成熟方案好
    }

    raw_scores = []

    for cand in candidates:
        payload = cand if isinstance(cand, dict) and "gamma_pcm" in cand else cand.get("payload", cand)
        cand_feat = extract_candidate_features(payload)

        score = 0.0
        total_weight = 0.0

        for td_key, cand_key, weight, mode in attention_map:
            td_val = td_features.get(td_key, 0.5)
            cand_val = cand_feat.get(cand_key, 0.5)

            if mode == "align":
                # 两者同方向 → 高分
                contribution = td_val * cand_val
            else:
                # 两者反方向 → 高分（TD 高但候选低 = 好）
                contribution = td_val * (1.0 - cand_val)

            score += weight * contribution
            total_weight += weight

        if total_weight > 0:
            score /= total_weight

        raw_scores.append(score)

    # 温度缩放 + softmax 归一化到 [0, 1]
    if len(raw_scores) <= 1:
        return [max(0.0, min(1.0, s)) for s in raw_scores]

    # 缩放到合理范围
    s_min = min(raw_scores)
    s_max = max(raw_scores)
    s_range = s_max - s_min if s_max > s_min else 1.0

    normalized = []
    for s in raw_scores:
        # 线性缩放到 [0.3, 0.9] 范围（避免极端值）
        n = 0.3 + 0.6 * (s - s_min) / s_range
        normalized.append(n)

    # 温度调节：低温 → 分化大，高温 → 分化小
    if temperature != 1.0:
        mean_n = sum(normalized) / len(normalized)
        normalized = [mean_n + (n - mean_n) / temperature for n in normalized]
        normalized = [max(0.1, min(0.95, n)) for n in normalized]

    return normalized


def compute_auto_herrscher_risk(
    td_features: Dict[str, float],
    candidate_params: dict,
    c_end: float,
    c_mean: float,
    c_std: float,
) -> float:
    """自动计算 herrscher_risk。

    基于：
    1. TD 的环境风险特征
    2. 候选的激进程度
    3. QCU 坍缩偏差
    """
    cand_feat = extract_candidate_features(candidate_params)

    # 基础风险：来自 TD 环境
    env_risk = td_features.get("vein_risk_mean", 0.3)
    best_risk = td_features.get("best_risk", 0.3)
    base = 0.5 * env_risk + 0.5 * best_risk

    # 候选激进度加成
    aggression_penalty = 0.15 * cand_feat.get("aggressiveness", 0.5)
    risk_appetite_penalty = 0.10 * cand_feat.get("risk_appetite", 0.5)

    # 坍缩偏差加成
    if c_std > 1e-8:
        c_deviation = abs(c_end - c_mean) / c_std
        collapse_penalty = 0.05 * min(c_deviation, 3.0)
    else:
        collapse_penalty = 0.0

    # 耐心和保守可以降低风险
    patience_bonus = -0.08 * cand_feat.get("patience", 0.5)
    conserv_bonus = -0.05 * cand_feat.get("conservatism", 0.5)

    herrscher = base + aggression_penalty + risk_appetite_penalty + collapse_penalty + patience_bonus + conserv_bonus
    return max(0.02, min(0.95, herrscher))
