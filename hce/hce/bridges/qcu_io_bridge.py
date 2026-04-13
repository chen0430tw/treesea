# qcu_io_bridge.py
"""
QCU I/O 桥接。

负责将 QCU 的输出 (SeaOutputBundle) 转换为 HCE 内部可消费的格式，
以及将 HCE 候选列表转换为 QCU 可接受的输入。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .td_io_bridge import TreeCandidateView


@dataclass
class SeaCandidateView:
    """HCE 内部对 QCU 坍缩结果的统一视图。"""
    candidate_id: str
    collapse_score: float
    readout: Dict[str, Any]
    phase_signature: Dict[str, Any]
    stability: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "collapse_score": self.collapse_score,
            "readout": self.readout,
            "phase_signature": self.phase_signature,
            "stability": self.stability,
            "metadata": self.metadata,
        }


class QCUIOBridge:
    """QCU ↔ HCE I/O 桥接器。"""

    def extract_results(self, sea_output: dict) -> List[SeaCandidateView]:
        """从 SeaOutputBundle dict 提取坍缩结果。

        Parameters
        ----------
        sea_output : dict
            SeaOutputBundle.to_dict() 的结果

        Returns
        -------
        list of SeaCandidateView
        """
        results = []

        # 从 collapse_results 提取
        collapse_results = sea_output.get("collapse_results", [])
        if collapse_results:
            for cr in collapse_results:
                results.append(SeaCandidateView(
                    candidate_id=cr.get("candidate_id", f"qcu_{len(results)}"),
                    collapse_score=cr.get("collapse_score", 0.0),
                    readout=cr.get("readout", {}),
                    phase_signature=cr.get("phase_signature", {}),
                    stability=cr.get("stability", 0.5),
                ))
        else:
            # 从 entries 提取 (QCU readout_schema 格式)
            entries = sea_output.get("entries", [])
            for entry in entries:
                results.append(SeaCandidateView(
                    candidate_id=entry.get("run_id", f"qcu_{len(results)}"),
                    collapse_score=entry.get("C_end", 0.0),
                    readout={
                        "final_sz": entry.get("final_sz", []),
                        "final_n": entry.get("final_n", []),
                    },
                    phase_signature={
                        "final_rel_phase": entry.get("final_rel_phase", []),
                        "dtheta_end": entry.get("dtheta_end", 0.0),
                    },
                    stability=1.0 - abs(entry.get("C_end", 0.5)),
                ))

        return results

    def build_collapse_request(
        self,
        request_id: str,
        candidates: List[TreeCandidateView],
    ) -> dict:
        """将 Tree Diagram 候选转换为 QCU CollapseRequest 格式。

        Parameters
        ----------
        request_id : str
        candidates : list of TreeCandidateView

        Returns
        -------
        dict
            CollapseRequest 格式
        """
        clusters = []
        for cand in candidates:
            clusters.append({
                "cluster_id": cand.candidate_id,
                "candidates": [{
                    "candidate_id": cand.candidate_id,
                    "payload": {
                        "label": cand.candidate_id,
                        "tree_score": cand.tree_score,
                        **cand.worldline,
                    },
                }],
            })

        return {
            "request_id": request_id,
            "qcu_session_id": f"qcu_sess_{request_id}",
            "clusters": clusters,
        }
