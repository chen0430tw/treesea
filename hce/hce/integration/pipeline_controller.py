# pipeline_controller.py
"""
树形调度控制器。

参考 URP 的 IRGraph 调度思路，用树结构替代线性流水线：
  - HCE（根节点）持有全局上下文（seed, request）
  - TD / QCU / HC 是子节点，各自是黑盒计算单元
  - 父节点等子节点返回结果再合并
  - 不需要拓扑排序，天然递归

树结构：
                    HCE (root)
                   /    |     \\
                 TD    QCU     HC
                      (依赖TD) (依赖TD+QCU)

mode 控制哪些子树被激活。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..io.pipeline_schema import FinalReportBundle, PipelineConfig, RequestBundle
from .result_merge import ResultMerger


@dataclass
class ComputeNode:
    """树形调度中的计算节点。

    每个节点是一个黑盒：接收输入 dict，输出结果 dict。
    HCE 不关心节点内部怎么算，只看地址（name）和输出格式。
    """
    name: str
    result: Optional[dict] = None
    elapsed_sec: float = 0.0
    children: List["ComputeNode"] = field(default_factory=list)

    def is_ready(self) -> bool:
        return self.result is not None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "elapsed_sec": self.elapsed_sec,
            "has_result": self.result is not None,
            "children": [c.to_dict() for c in self.children],
        }


class PipelineController:
    """树形调度控制器。

    构建计算树，递归执行，合并结果。

    Parameters
    ----------
    config : PipelineConfig
    """

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.merger = ResultMerger()

    def run_pipeline(
        self,
        request: RequestBundle,
        tree_output: Optional[dict] = None,
        sea_output: Optional[dict] = None,
        hc_output: Optional[dict] = None,
    ) -> FinalReportBundle:
        """构建计算树并递归执行。"""
        t0 = time.time()
        mode = self.config.mode

        # 构建计算树
        root = self._build_tree(mode, tree_output, sea_output, hc_output, request)

        # 递归执行（叶节点先算，结果向上传递）
        self._execute(root, request)

        # 从树中提取各节点结果
        results = self._collect_results(root)
        td_out = results.get("tree_diagram")
        qcu_out = results.get("qcu")
        hc_out = results.get("honkai_core")

        # 合并
        merged = self.merger.merge(
            request_id=request.request_id,
            tree_output=td_out,
            sea_output=qcu_out,
            hc_output=hc_out,
        )

        return FinalReportBundle(
            request_id=request.request_id,
            tree_ref=self._extract_ref(td_out, "tree_run_id", "td"),
            sea_ref=self._extract_ref(qcu_out, "qcu_session_id", "qcu"),
            hc_ref=self._extract_ref(hc_out, "hc_run_id", "hc"),
            final_selection=merged.get("final_selection", {}),
            final_ranking=merged.get("final_ranking", []),
            energy_summary=merged.get("energy_summary", {}),
            risk_summary=merged.get("risk_summary", {}),
            artifacts={
                "tree_structure": root.to_dict(),
                "mode": mode,
            },
            elapsed_sec=time.time() - t0,
        )

    def _build_tree(
        self,
        mode: str,
        tree_output: Optional[dict],
        sea_output: Optional[dict],
        hc_output: Optional[dict],
        request: RequestBundle,
    ) -> ComputeNode:
        """根据 mode 构建计算树。

        树结构由 mode 决定：
          tree_only        → root─TD
          sea_only          → root─QCU
          hc_only           → root─HC
          tree_then_sea     → root─TD─QCU
          tree_then_sea_then_hc → root─TD─QCU─HC（HC 依赖 TD+QCU）
        """
        root = ComputeNode(name="hce_root")

        if "tree" in mode:
            td_node = ComputeNode(name="tree_diagram", result=tree_output)
            root.children.append(td_node)

            if "sea" in mode:
                qcu_node = ComputeNode(name="qcu", result=sea_output)
                td_node.children.append(qcu_node)

                if "hc" in mode:
                    hc_node = ComputeNode(name="honkai_core", result=hc_output)
                    qcu_node.children.append(hc_node)

        elif "sea" in mode:
            qcu_node = ComputeNode(name="qcu", result=sea_output)
            root.children.append(qcu_node)

        elif "hc" in mode:
            hc_node = ComputeNode(name="honkai_core", result=hc_output)
            root.children.append(hc_node)

        return root

    def _execute(self, node: ComputeNode, request: RequestBundle, root: Optional[ComputeNode] = None) -> None:
        """递归执行计算树。叶节点先算，结果向上回传。"""
        if root is None:
            root = node

        # 先递归执行所有子节点
        for child in node.children:
            self._execute(child, request, root)

        # 当前节点：如果没有预设结果，尝试自动计算
        if not node.is_ready() and node.name == "honkai_core":
            # HC 需要 TD + QCU 的结果，从整棵树搜索
            td_result = self._search_tree(root, "tree_diagram")
            qcu_result = self._search_tree(root, "qcu")
            if td_result and qcu_result:
                t0 = time.time()
                node.result = self._auto_run_hc(request, td_result, qcu_result)
                node.elapsed_sec = time.time() - t0

    def _auto_run_hc(self, request: RequestBundle, td_output: dict, qcu_output: dict) -> dict:
        """自动运行 Honkai Core（从 TD+QCU 输出构建场景）。"""
        from ..bridges.hc_io_bridge import HonkaiCoreIOBridge
        from honkai_core.io.scenario_loader import ScenarioConfig
        from honkai_core.runtime.runner import HonkaiCoreRunner

        auto_bridge = HonkaiCoreIOBridge()
        scenario = auto_bridge.build_scenario_auto(
            request_id=request.request_id,
            tree_output=td_output,
            sea_output=qcu_output,
        )
        hc_config = ScenarioConfig.from_dict(scenario)
        return HonkaiCoreRunner(hc_config).run().to_dict()

    def _search_tree(self, node: ComputeNode, target_name: str) -> Optional[dict]:
        """在树中搜索指定名称节点的结果。"""
        if node.name == target_name and node.is_ready():
            return node.result
        for child in node.children:
            result = self._search_tree(child, target_name)
            if result is not None:
                return result
        return None

    def _collect_results(self, root: ComputeNode) -> Dict[str, Optional[dict]]:
        """从树中收集所有节点的结果。"""
        results: Dict[str, Optional[dict]] = {}
        self._walk_collect(root, results)
        return results

    def _walk_collect(self, node: ComputeNode, results: Dict[str, Optional[dict]]) -> None:
        if node.name != "hce_root":
            results[node.name] = node.result
        for child in node.children:
            self._walk_collect(child, results)

    @staticmethod
    def _extract_ref(output: Optional[dict], key: str, prefix: str) -> Optional[str]:
        if output is None:
            return None
        return output.get(key, f"{prefix}_provided")
