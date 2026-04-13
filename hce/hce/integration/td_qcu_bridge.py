# td_qcu_bridge.py
"""
Tree Diagram → QCU 流水线桥接。

负责将 Tree Diagram 的输出接到 QCU 的输入，
形成 tree_then_sea 的前半段。
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..bridges.td_io_bridge import TreeDiagramIOBridge, TreeCandidateView
from ..bridges.qcu_io_bridge import QCUIOBridge, SeaCandidateView


class TDQCUBridge:
    """Tree Diagram → QCU 阶段桥接器。

    负责：
    1. 从 TreeOutputBundle 提取候选
    2. 转换为 CollapseRequest
    3. （外部调用 QCU）
    4. 从 SeaOutputBundle 提取结果
    """

    def __init__(self) -> None:
        self.td_bridge = TreeDiagramIOBridge()
        self.qcu_bridge = QCUIOBridge()

    def tree_to_sea_input(
        self,
        request_id: str,
        tree_output: dict,
    ) -> dict:
        """将 TreeOutputBundle 转换为 QCU CollapseRequest。

        Parameters
        ----------
        request_id : str
        tree_output : dict

        Returns
        -------
        dict
            CollapseRequest 格式
        """
        candidates = self.td_bridge.extract_candidates(tree_output)
        return self.qcu_bridge.build_collapse_request(request_id, candidates)

    def extract_both(
        self,
        tree_output: dict,
        sea_output: dict,
    ) -> Dict[str, Any]:
        """同时提取树海双方结果，形成统一视图。

        Returns
        -------
        dict
            {
                "tree_candidates": [...],
                "sea_results": [...],
                "merged": [...],
            }
        """
        tree_candidates = self.td_bridge.extract_candidates(tree_output)
        sea_results = self.qcu_bridge.extract_results(sea_output)

        # 按 candidate_id 合并
        sea_map = {sr.candidate_id: sr for sr in sea_results}
        merged = []
        for tc in tree_candidates:
            sr = sea_map.get(tc.candidate_id)
            merged.append({
                "candidate_id": tc.candidate_id,
                "tree_score": tc.tree_score,
                "branch_state": tc.branch_state,
                "collapse_score": sr.collapse_score if sr else None,
                "stability": sr.stability if sr else None,
                "has_sea_result": sr is not None,
            })

        return {
            "tree_candidates": [tc.to_dict() for tc in tree_candidates],
            "sea_results": [sr.to_dict() for sr in sea_results],
            "merged": merged,
        }
