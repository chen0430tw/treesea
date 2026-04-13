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
