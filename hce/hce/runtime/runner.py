# runner.py
"""
HCE 运行时。

接收 RequestBundle + PipelineConfig → 编排流水线 → 返回 FinalReportBundle。

入口：HCERunner.run(request) → FinalReportBundle
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..io.pipeline_schema import FinalReportBundle, PipelineConfig, RequestBundle
from ..io.integrated_result_writer import (
    write_final_report,
    write_final_summary,
    write_stage_artifact,
    append_pipeline_event,
)
from ..integration.pipeline_controller import PipelineController
from .checkpoint import CheckpointManager


class HCERunner:
    """HCE 整机运行时。

    Parameters
    ----------
    pipeline_config : PipelineConfig
    """

    def __init__(self, pipeline_config: PipelineConfig) -> None:
        self.config = pipeline_config
        self.controller = PipelineController(pipeline_config)
        self.checkpoint_mgr = CheckpointManager(pipeline_config.checkpoint_dir)

    def run(
        self,
        request: RequestBundle,
        tree_output: Optional[dict] = None,
        sea_output: Optional[dict] = None,
        hc_output: Optional[dict] = None,
    ) -> FinalReportBundle:
        """执行完整的 HCE 流水线。

        Parameters
        ----------
        request : RequestBundle
        tree_output, sea_output, hc_output : dict, optional
            各子系统的预计算输出。在集群模式下，这些会由 launcher 负责调度获取。

        Returns
        -------
        FinalReportBundle
        """
        t0 = time.time()

        # 记录开始事件
        append_pipeline_event(
            {"event": "pipeline_start", "request_id": request.request_id, "mode": self.config.mode},
            self.config.log_dir,
        )

        # 尝试从检查点恢复
        restored = self.checkpoint_mgr.try_restore(request.request_id)
        if restored:
            tree_output = restored.get("tree_output", tree_output)
            sea_output = restored.get("sea_output", sea_output)
            hc_output = restored.get("hc_output", hc_output)

        # 保存中间产物检查点
        self.checkpoint_mgr.save(request.request_id, {
            "tree_output": tree_output,
            "sea_output": sea_output,
            "hc_output": hc_output,
        })

        # 执行流水线
        bundle = self.controller.run_pipeline(
            request=request,
            tree_output=tree_output,
            sea_output=sea_output,
            hc_output=hc_output,
        )

        # 落盘
        write_final_report(bundle, self.config.result_dir)
        write_final_summary(bundle, self.config.result_dir)

        # 记录完成事件
        append_pipeline_event(
            {
                "event": "pipeline_complete",
                "request_id": request.request_id,
                "elapsed_sec": time.time() - t0,
            },
            self.config.log_dir,
        )

        return bundle


def main():
    """CLI 入口：演示本地运行。"""
    config = PipelineConfig(mode="tree_then_sea_then_hc")
    runner = HCERunner(config)

    request = RequestBundle(
        request_id="demo_001",
        mode="tree_then_sea_then_hc",
        seed={"title": "demo"},
    )

    # 模拟各阶段输出
    tree_output = {
        "seed_title": "demo",
        "mode": "integrated",
        "best_worldline": {"score": 0.85},
        "oracle_details": {
            "candidate_set": [
                {"candidate_id": "cand_01", "score": 0.85, "branch_state": "active"},
                {"candidate_id": "cand_02", "score": 0.72, "branch_state": "active"},
            ],
        },
    }

    sea_output = {
        "request_id": "demo_001",
        "qcu_session_id": "qcu_demo",
        "collapse_results": [
            {"candidate_id": "cand_01", "collapse_score": 0.3, "stability": 0.8},
            {"candidate_id": "cand_02", "collapse_score": 0.5, "stability": 0.6},
        ],
    }

    hc_output = {
        "request_id": "demo_001",
        "hc_run_id": "hc_demo",
        "energy_estimate": {
            "total_energy": 2.5,
            "generation_rate": 3.0,
            "dissipation_rate": 2.0,
            "gain_factor": 1.5,
            "density": 2.5,
            "state": "gain",
        },
        "risk_entries": [
            {"candidate_id": "cand_01", "risk_level": "safe", "risk_score": 0.2},
            {"candidate_id": "cand_02", "risk_level": "warning", "risk_score": 0.5},
        ],
        "recommendation": {
            "action": "proceed",
            "confidence": 0.85,
            "writeback_allowed": True,
        },
    }

    bundle = runner.run(request, tree_output, sea_output, hc_output)
    print(json.dumps(bundle.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
