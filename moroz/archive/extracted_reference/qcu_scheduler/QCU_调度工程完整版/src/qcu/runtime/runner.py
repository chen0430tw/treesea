from __future__ import annotations

from qcu.scheduler.request_ingress import RequestIngress
from qcu.scheduler.cluster_scheduler import ClusterScheduler
from qcu.scheduler.collapse_scheduler import CollapseScheduler
from qcu.scheduler.termination_policy import TerminationPolicy
from qcu.governance.opu_bridge import OPUBridge, StepStats

class QCURunner:
    def __init__(self, qcu_core, opu_core=None):
        self.ingress = RequestIngress()
        self.cluster_scheduler = ClusterScheduler()
        self.collapse_scheduler = CollapseScheduler()
        self.termination = TerminationPolicy()
        self.qcu_core = qcu_core
        self.opu_bridge = OPUBridge(opu_core) if opu_core is not None else None

    def run(self, request):
        request = self.ingress.normalize(request)
        plan = self.cluster_scheduler.build_plan(request)

        results = []
        governance_trace = []

        for cluster_plan in plan.cluster_plans:
            if self.opu_bridge is not None:
                fake_stats = StepStats(
                    hot_pressure=0.2,
                    faults=0,
                    wait_time_s=0.0,
                    rebuild_cost_s=0.0,
                    quality_score=0.95,
                )
                cluster_plan, feedback = self.opu_bridge.observe_and_adjust(cluster_plan, fake_stats)
                governance_trace.append({"cluster_id": cluster_plan.cluster_id, "feedback": feedback.trace})

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

            results.append(
                {
                    "cluster_id": cluster_plan.cluster_id,
                    "collapse_score": collapse_score,
                    "stability": stability,
                    "final_step": current_step,
                }
            )

        return {
            "request_id": request.request_id,
            "qcu_session_id": request.qcu_session_id,
            "collapse_results": results,
            "governance_trace": governance_trace,
        }
