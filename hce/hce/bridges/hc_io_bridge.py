# hc_io_bridge.py
"""
Honkai Core I/O 桥接。

负责将 Tree + QCU 的中间结果转换为 Honkai Core 可接受的输入，
以及将 HCReportBundle 结果转换为 HCE 可消费的格式。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .td_io_bridge import TreeCandidateView
from .qcu_io_bridge import SeaCandidateView


class HonkaiCoreIOBridge:
    """Honkai Core ↔ HCE I/O 桥接器。"""

    def build_scenario(
        self,
        request_id: str,
        tree_candidates: List[TreeCandidateView],
        sea_results: List[SeaCandidateView],
        energy_params: Optional[Dict[str, float]] = None,
        threshold_params: Optional[Dict[str, float]] = None,
    ) -> dict:
        """将 Tree + QCU 结果转换为 ScenarioConfig 格式。

        Parameters
        ----------
        request_id : str
        tree_candidates : list of TreeCandidateView
        sea_results : list of SeaCandidateView
        energy_params, threshold_params : dict, optional

        Returns
        -------
        dict
            ScenarioConfig.from_dict() 可接受的格式
        """
        # 建立 candidate_id → sea_result 映射
        sea_map: Dict[str, SeaCandidateView] = {}
        for sr in sea_results:
            sea_map[sr.candidate_id] = sr

        candidates = []
        for tc in tree_candidates:
            sr = sea_map.get(tc.candidate_id)
            payload = {
                "tree_score": tc.tree_score,
                "collapse_score": sr.collapse_score if sr else 0.5,
                "stability": sr.stability if sr else 0.5,
                "branch_state": tc.branch_state,
                "resource_weight": tc.resource_weight,
            }
            candidates.append({
                "candidate_id": tc.candidate_id,
                "payload": payload,
            })

        scenario = {
            "scenario_id": f"hce_scenario_{request_id}",
            "request_id": request_id,
            "candidates": candidates,
        }

        if energy_params:
            scenario["energy_params"] = energy_params
        if threshold_params:
            scenario["threshold_params"] = threshold_params

        return scenario

    def build_scenario_auto(
        self,
        request_id: str,
        tree_output: dict,
        sea_output: dict,
        energy_params: Optional[Dict[str, float]] = None,
        threshold_params: Optional[Dict[str, float]] = None,
        seed_environment: Optional[Dict[str, float]] = None,
        seed_subject: Optional[Dict[str, float]] = None,
    ) -> dict:
        """全自动构建 HC 场景：从 TD+QCU 原始输出自动提取所有分数。

        不需要手动赋值 tree_score 和 herrscher_risk。

        自动提取逻辑：
        - tree_score: 从 TD oracle 的 top_families/vein_backbone 取 balanced_score/feasibility
        - collapse_score: 从 QCU entries 取 C_end
        - stability: 从 TD vein_backbone 取 stability，或 1-C_end
        - herrscher_risk: 从 TD vein_backbone 取 risk，或从候选的极端程度推算
        - noise: 从 QCU entries 取 dtheta_end
        """
        oracle = tree_output.get("oracle_details", {})
        hydro = tree_output.get("hydro_control", {})

        # === 从 TD 提取分数 ===
        # 来源 1: top_families (有 final_balanced_score, balanced_score)
        top_families = oracle.get("top_families", [])
        # 来源 2: vein_backbone (有 feasibility, stability, risk)
        vein = hydro.get("vein_backbone", {})
        vein_nodes = vein.get("nodes", [])
        # 来源 3: vein_stats (全局统计)
        vein_stats = hydro.get("vein_stats", {})
        # 来源 4: best_worldline
        best_wl = tree_output.get("best_worldline", oracle.get("best_worldline", {}))

        # 全局基线值（用于归一化和 fallback）
        mean_risk = hydro.get("mean_risk", 0.3)
        mean_score = hydro.get("mean_balanced_score", 0.5)
        mean_stability = vein.get("mean_stability", 0.6)

        # === 从 QCU 提取 ===
        entries = sea_output.get("entries", [])
        collapse_results = sea_output.get("collapse_results", [])
        sea_items = collapse_results or entries

        # C_end 统计（用于归一化 herrscher_risk）
        c_ends = [e.get("C_end", e.get("collapse_score", 0.5)) for e in sea_items]
        c_mean = sum(c_ends) / len(c_ends) if c_ends else 0.5
        c_std = (sum((c - c_mean) ** 2 for c in c_ends) / max(len(c_ends), 1)) ** 0.5

        # === 注意力评分：每个候选获得差异化的 tree_score ===
        from ..integration.candidate_attention import (
            extract_td_features,
            compute_attention_scores,
            compute_auto_herrscher_risk,
        )

        td_features = extract_td_features(tree_output)

        # 注入 seed 的原始环境/主体参数，确保不同问题有不同的注意力分布
        if seed_environment:
            for k, v in seed_environment.items():
                td_features[f"seed_{k}"] = float(v)
        if seed_subject:
            for k, v in seed_subject.items():
                td_features[f"seed_{k}"] = float(v)

        # 提取候选参数用于注意力计算
        cand_payloads = []
        for sea_entry in sea_items:
            # QCU entry 的 metadata 里可能有原始参数
            payload = sea_entry.get("metadata", {})
            # 或者从 label 解析不了，直接用 QCU 运行参数
            # 这些参数在 CollapseRequest 里传入，QCU entry 不一定保留
            # fallback: 从 entry 的数值特征反推策略特性
            if not any(k in payload for k in ("gamma_pcm", "gamma_boost")):
                # 用 C_end 和 dtheta_end 反推策略特性
                c_end = sea_entry.get("C_end", sea_entry.get("collapse_score", 0.5))
                dtheta = abs(sea_entry.get("dtheta_end", 0.1))
                elapsed = sea_entry.get("elapsed_sec", 1.0)
                payload = {
                    "gamma_pcm": min(0.3, c_end * 10),      # C_end 高 → 高同步耗散
                    "gamma_boost": min(1.0, 1.0 - c_end),   # C_end 低 → 高增强
                    "boost_duration": max(1.0, elapsed / 5), # 耗时长 → 长 duration
                    "gamma_phi0": min(0.5, dtheta),          # dtheta 大 → 高相位噪声
                }
            cand_payloads.append(payload)

        # 计算注意力分数 → tree_score
        attention_scores = compute_attention_scores(
            td_features, cand_payloads, temperature=0.5
        )

        # === 构建候选 ===
        candidates = []
        for i, sea_entry in enumerate(sea_items):
            cid = sea_entry.get("run_id", sea_entry.get("candidate_id", f"cand_{i}"))
            short_cid = cid.split("/")[-1] if "/" in cid else cid
            c_end = sea_entry.get("C_end", sea_entry.get("collapse_score", 0.5))

            tree_score = attention_scores[i] if i < len(attention_scores) else 0.5
            stability = 1.0 - c_end
            noise = abs(sea_entry.get("dtheta_end", 0.1))

            herrscher_risk = compute_auto_herrscher_risk(
                td_features, cand_payloads[i], c_end, c_mean, c_std
            )

            candidates.append({
                "candidate_id": short_cid,
                "payload": {
                    "tree_score": tree_score,
                    "collapse_score": c_end,
                    "stability": stability,
                    "noise": noise,
                    "herrscherization_risk": herrscher_risk,
                },
            })

        scenario = {
            "scenario_id": f"hce_auto_{request_id}",
            "request_id": request_id,
            "candidates": candidates,
        }

        if energy_params:
            scenario["energy_params"] = energy_params
        if threshold_params:
            scenario["threshold_params"] = threshold_params

        return scenario

    def extract_recommendation(self, hc_report: dict) -> dict:
        """从 HCReportBundle dict 提取建议摘要。

        Returns
        -------
        dict
            包含 action, writeback_allowed, energy_summary, risk_summary
        """
        rec = hc_report.get("recommendation", {})
        energy = hc_report.get("energy_estimate", {})
        risk_entries = hc_report.get("risk_entries", [])

        # 汇总风险
        risk_levels = [r.get("risk_level", "safe") for r in risk_entries]
        worst_risk = "safe"
        for level in ["terminal", "critical", "warning", "safe"]:
            if level in risk_levels:
                worst_risk = level
                break

        return {
            "action": rec.get("action", "proceed"),
            "confidence": rec.get("confidence", 0.0),
            "writeback_allowed": rec.get("writeback_allowed", True),
            "energy_summary": {
                "total_energy": energy.get("total_energy", 0.0),
                "state": energy.get("state", "unknown"),
                "gain_factor": energy.get("gain_factor", 0.0),
            },
            "risk_summary": {
                "worst_risk": worst_risk,
                "n_entries": len(risk_entries),
                "n_critical": sum(1 for r in risk_entries if r.get("risk_level") in ("critical", "terminal")),
            },
        }
