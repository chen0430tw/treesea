# hc_bridge.py
"""
QCU → Honkai Core 流水线桥接。

负责将 Tree + QCU 的中间结果转换为 Honkai Core 的输入场景。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..bridges.td_io_bridge import TreeDiagramIOBridge, TreeCandidateView
from ..bridges.qcu_io_bridge import QCUIOBridge, SeaCandidateView
from ..bridges.hc_io_bridge import HonkaiCoreIOBridge


class HCBridge:
    """QCU → Honkai Core 阶段桥接器。

    负责：
    1. 从 Tree + QCU 输出构建 ScenarioConfig
    2. （外部调用 Honkai Core）
    3. 从 HCReportBundle 提取建议
    """

    def __init__(self) -> None:
        self.td_bridge = TreeDiagramIOBridge()
        self.qcu_bridge = QCUIOBridge()
        self.hc_bridge = HonkaiCoreIOBridge()

    def build_hc_scenario(
        self,
        request_id: str,
        tree_output: dict,
        sea_output: dict,
        energy_params: Optional[Dict[str, float]] = None,
        threshold_params: Optional[Dict[str, float]] = None,
    ) -> dict:
        """构建 Honkai Core 场景配置。

        Parameters
        ----------
        request_id : str
        tree_output : dict
        sea_output : dict
        energy_params, threshold_params : dict, optional

        Returns
        -------
        dict
            ScenarioConfig 格式
        """
        tree_candidates = self.td_bridge.extract_candidates(tree_output)
        sea_results = self.qcu_bridge.extract_results(sea_output)

        return self.hc_bridge.build_scenario(
            request_id=request_id,
            tree_candidates=tree_candidates,
            sea_results=sea_results,
            energy_params=energy_params,
            threshold_params=threshold_params,
        )

    def extract_hc_recommendation(self, hc_report: dict) -> dict:
        """从 HCReportBundle 提取建议摘要。"""
        return self.hc_bridge.extract_recommendation(hc_report)
