# td_io_bridge.py
"""
Tree Diagram I/O 桥接。

负责将 Tree Diagram 的输出 (TreeOutputBundle) 转换为 HCE 内部可消费的格式，
以及将 HCE 的反馈转换为 Tree Diagram 可接受的回写格式。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TreeCandidateView:
    """HCE 内部对 Tree Diagram 候选的统一视图。"""
    candidate_id: str
    worldline: Dict[str, Any]
    tree_score: float
    branch_state: str      # "active" | "restricted" | "starved" | "withered"
    resource_weight: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "worldline": self.worldline,
            "tree_score": self.tree_score,
            "branch_state": self.branch_state,
            "resource_weight": self.resource_weight,
            "metadata": self.metadata,
        }


class TreeDiagramIOBridge:
    """Tree Diagram ↔ HCE I/O 桥接器。"""

    def extract_candidates(self, tree_output: dict) -> List[TreeCandidateView]:
        """从 TreeOutputBundle dict 提取候选列表。

        Parameters
        ----------
        tree_output : dict
            TreeOutputBundle.to_dict() 的结果

        Returns
        -------
        list of TreeCandidateView
        """
        candidates = []

        # 从 oracle_details 中提取候选集
        oracle = tree_output.get("oracle_details", {})
        candidate_set = oracle.get("candidate_set", [])

        if candidate_set:
            for cs in candidate_set:
                candidates.append(TreeCandidateView(
                    candidate_id=cs.get("candidate_id", f"td_{len(candidates)}"),
                    worldline=cs.get("worldline", {}),
                    tree_score=cs.get("score", 0.0),
                    branch_state=cs.get("branch_state", "active"),
                    resource_weight=cs.get("resource_weight", 1.0),
                ))
        else:
            # 从 best_worldline 构建单候选
            best = tree_output.get("best_worldline", {})
            if best:
                candidates.append(TreeCandidateView(
                    candidate_id="td_best",
                    worldline=best,
                    tree_score=best.get("score", 0.0),
                    branch_state="active",
                    resource_weight=1.0,
                ))

        return candidates

    def build_feedback(
        self,
        candidate_id: str,
        confidence_boost: float = 0.0,
        stability_penalty: float = 0.0,
        phase_hint: str = "",
        recommend_branch_state: str = "active",
    ) -> dict:
        """构建弱回写反馈对象。

        Returns
        -------
        dict
            符合 HCE 整合版总规范 §8.1 的 feedback 格式
        """
        return {
            "candidate_id": candidate_id,
            "feedback": {
                "confidence_boost": confidence_boost,
                "stability_penalty": stability_penalty,
                "phase_hint": phase_hint,
                "recommend_branch_state": recommend_branch_state,
            },
        }
