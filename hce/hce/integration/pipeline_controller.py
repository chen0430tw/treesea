# pipeline_controller.py
"""
多阶段流水线控制器。

根据 PipelineConfig.mode 编排 Tree Diagram → QCU → Honkai Core 的执行顺序，
管理中间产物传递和阶段间检查点。
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from ..io.pipeline_schema import FinalReportBundle, PipelineConfig, RequestBundle
from .td_qcu_bridge import TDQCUBridge
from .hc_bridge import HCBridge
from .result_merge import ResultMerger


class StageResult:
    """单个阶段的执行结果。"""

    def __init__(self, stage_name: str, output: dict, elapsed_sec: float) -> None:
        self.stage_name = stage_name
        self.output = output
        self.elapsed_sec = elapsed_sec

    def to_dict(self) -> dict:
        return {
            "stage_name": self.stage_name,
            "elapsed_sec": self.elapsed_sec,
            "output": self.output,
        }


class PipelineController:
    """多阶段流水线控制器。

    当前阶段只实现模拟执行（不真正调用三个子系统的 Runner），
    而是接受预先计算好的各阶段输出 dict。

    实际集群部署时，PipelineController 会通过 subprocess / sbatch
    调用各子系统的 CLI 入口并收集输出。

    Parameters
    ----------
    config : PipelineConfig
    """

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.td_qcu_bridge = TDQCUBridge()
        self.hc_bridge = HCBridge()
        self.merger = ResultMerger()
        self.stage_results: List[StageResult] = []

    def run_pipeline(
        self,
        request: RequestBundle,
        tree_output: Optional[dict] = None,
        sea_output: Optional[dict] = None,
        hc_output: Optional[dict] = None,
    ) -> FinalReportBundle:
        """执行流水线。

        根据 mode 决定执行哪些阶段。已有的阶段输出直接使用，
        缺失的阶段标记为跳过。

        Parameters
        ----------
        request : RequestBundle
        tree_output : dict, optional
            TreeOutputBundle.to_dict()
        sea_output : dict, optional
            SeaOutputBundle.to_dict()
        hc_output : dict, optional
            HCReportBundle.to_dict()

        Returns
        -------
        FinalReportBundle
        """
        t0 = time.time()
        mode = self.config.mode
        self.stage_results = []

        tree_ref = None
        sea_ref = None
        hc_ref = None

        # Stage 1: Tree Diagram
        if "tree" in mode and tree_output is not None:
            self._record_stage("tree_diagram", tree_output)
            tree_ref = tree_output.get("tree_run_id", "td_provided")

        # Stage 2: QCU
        if "sea" in mode and sea_output is not None:
            self._record_stage("qcu", sea_output)
            sea_ref = sea_output.get("qcu_session_id", sea_output.get("sea_run_id", "qcu_provided"))

        # Stage 3: Honkai Core
        if "hc" in mode:
            if hc_output is not None:
                self._record_stage("honkai_core", hc_output)
                hc_ref = hc_output.get("hc_run_id", "hc_provided")
            elif tree_output and sea_output:
                # 自动构建 HC 场景并运行
                scenario = self.hc_bridge.build_hc_scenario(
                    request_id=request.request_id,
                    tree_output=tree_output,
                    sea_output=sea_output,
                )
                self._record_stage("honkai_core_scenario_built", scenario)

        # Merge
        merged = self.merger.merge(
            request_id=request.request_id,
            tree_output=tree_output,
            sea_output=sea_output,
            hc_output=hc_output,
        )

        return FinalReportBundle(
            request_id=request.request_id,
            tree_ref=tree_ref,
            sea_ref=sea_ref,
            hc_ref=hc_ref,
            final_selection=merged.get("final_selection", {}),
            final_ranking=merged.get("final_ranking", []),
            energy_summary=merged.get("energy_summary", {}),
            risk_summary=merged.get("risk_summary", {}),
            artifacts={
                "stages": [s.to_dict() for s in self.stage_results],
                "mode": mode,
            },
            elapsed_sec=time.time() - t0,
        )

    def _record_stage(self, name: str, output: dict) -> None:
        self.stage_results.append(StageResult(
            stage_name=name,
            output=output,
            elapsed_sec=0.0,
        ))
