"""QCURunner — 完整调度运行器。对位迁移自 archive QCU_调度工程完整版。

两个入口：
1. run_qcu() — 旧版：直接接 MOROZ adapters/backends（保持向后兼容）
2. QCURunner.run() — 新版：走 scheduler 完整链路

qcu_core（新版）需满足 duck-typing:
    .run_window(cluster_id, candidate_ids, start_step, end_step, do_readout)
    -> dict with "collapse_score", "stability"
"""
from __future__ import annotations

import time
from typing import Any, Optional

from qcu.runtime.state import RuntimeState
from qcu.opu.core import OPU
from qcu.opu.config import OPUConfig
from qcu.opu.stats import StepStats as OPUStepStats
from qcu.scheduler.request_ingress import RequestIngress
from qcu.scheduler.cluster_scheduler import ClusterScheduler
from qcu.scheduler.collapse_scheduler import CollapseScheduler
from qcu.scheduler.termination_policy import TerminationPolicy
from qcu.governance.opu_bridge import OPUBridge, StepStats


# ═══════════════════════════════════════════════════════════════════════════════
# 旧版入口（保持向后兼容，MOROZ backends 调用此函数）
# ═══════════════════════════════════════════════════════════════════════════════

def run_qcu(runtime_cfg) -> dict:
    """旧版 QCU runner，被 moroz/backends/qcu_backend.py 调用。"""
    opu = OPU(OPUConfig(enabled=True, high_water=0.85, low_water=0.6))
    candidates = list(runtime_cfg.mapped_candidates)
    started = time.perf_counter()
    ranked = []
    should_stop = False

    steps = 3 if runtime_cfg.profile == "toy" else 5 if runtime_cfg.profile == "benchmark" else 7

    for step in range(1, 1 + steps):
        scored = []
        for item in candidates:
            mapped = item["mapped"]
            collapse_score = (
                1.0 * float(item["base_score"])
                + 0.5 * mapped["domain_hint"]
                + 0.7 * mapped["personal_hint"]
                + 0.8 * mapped["context_hint"]
                + 0.6 * mapped["syntax_hint"]
            )
            scored.append((collapse_score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score = scored[0][0] if scored else 0.0

        # 翻译 RuntimeState → OPU StepStats
        opu_stats = OPUStepStats(
            step=step,
            step_time_s=time.perf_counter() - started,
            hot_pressure=min(1.0, len(scored) / 100.0),
            faults=0,
            wait_time_s=0.0,
            rebuild_cost_s=0.0,
            quality_score=min(1.0, 0.5 + best_score / 10.0),
        )
        actions = opu.tick(opu_stats)

        # 检查 OPU 是否发出质量警报或 tighten → 视为 early_stop 信号
        if opu.quality_alarm or any(a.type == 'tighten' for a in actions):
            should_stop = True
            candidates = [item for _, item in scored[:min(10, len(scored))]]
            break

        candidates = [item for _, item in scored[:max(3, len(scored) // 2)]]

    for it in candidates:
        mapped = it["mapped"]
        final_score = (
            1.0 * float(it["base_score"])
            + 0.5 * mapped["domain_hint"]
            + 0.7 * mapped["personal_hint"]
            + 0.8 * mapped["context_hint"]
            + 0.6 * mapped["syntax_hint"]
        )
        ranked.append({
            "text": it["text"],
            "base_score": it["base_score"],
            "collapse_score": final_score,
            "final_score": final_score,
            "trace_summary": {"profile": runtime_cfg.profile},
            "source_layers": it["source_layers"],
            "meta": it["meta"],
        })

    ranked.sort(key=lambda x: x["final_score"], reverse=True)
    elapsed = time.perf_counter() - started

    return {
        "status": "completed",
        "ranked": ranked,
        "elapsed_sec": elapsed,
        "steps": step,
        "effective_candidates": len(candidates),
        "converged": True,
        "stop_reason": "early_stop" if should_stop else "converged",
        "diagnostics": {"profile": runtime_cfg.profile},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 新版入口（走完整 scheduler 链路）
# ═══════════════════════════════════════════════════════════════════════════════

class QCURunner:
    """完整调度运行器：Ingress → ClusterScheduler → CollapseScheduler → Termination。"""

    def __init__(self, qcu_core: Any, opu_core: Optional[Any] = None):
        self.ingress = RequestIngress()
        self.cluster_scheduler = ClusterScheduler()
        self.collapse_scheduler = CollapseScheduler()
        self.termination = TerminationPolicy()
        self.qcu_core = qcu_core
        self.opu_bridge = OPUBridge(opu_core) if opu_core is not None else None

    def run(self, request) -> dict:
        request = self.ingress.normalize(request)
        plan = self.cluster_scheduler.build_plan(request)

        results = []
        governance_trace = []

        for cluster_plan in plan.cluster_plans:
            if self.opu_bridge is not None:
                fake_stats = StepStats(
                    hot_pressure=0.2, faults=0, wait_time_s=0.0,
                    rebuild_cost_s=0.0, quality_score=0.95,
                )
                cluster_plan, feedback = self.opu_bridge.observe_and_adjust(
                    cluster_plan, fake_stats
                )
                governance_trace.append({
                    "cluster_id": cluster_plan.cluster_id,
                    "feedback": feedback.trace,
                })

            windows = self.collapse_scheduler.split_windows(cluster_plan)
            collapse_score = 0.0
            stability = 0.0
            current_step = 0

            for window in windows:
                partial = self.qcu_core.run_window(
                    cluster_id=cluster_plan.cluster_id,
                    candidate_ids=cluster_plan.candidate_ids,
                    start_step=window.start_step,
                    end_step=window.end_step,
                    do_readout=window.do_readout,
                )
                collapse_score = partial["collapse_score"]
                stability = partial["stability"]
                current_step = window.end_step

                if self.termination.should_stop(
                    collapse_score=collapse_score,
                    stability=stability,
                    current_step=current_step,
                    target_collapse_score=request.termination_policy["target_collapse_score"],
                    target_stability=request.termination_policy["target_stability"],
                    max_steps=request.termination_policy["max_steps"],
                ):
                    break

            results.append({
                "cluster_id": cluster_plan.cluster_id,
                "collapse_score": collapse_score,
                "stability": stability,
                "final_step": current_step,
            })

        return {
            "request_id": request.request_id,
            "qcu_session_id": request.qcu_session_id,
            "collapse_results": results,
            "governance_trace": governance_trace,
        }
