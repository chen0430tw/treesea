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
