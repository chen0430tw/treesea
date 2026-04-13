from __future__ import annotations

from .models import CollapseRequest, CollapsePlan, ClusterExecutionPlan

class ClusterScheduler:
    def build_plan(self, request: CollapseRequest) -> CollapsePlan:
        default_step_budget = int(request.budget["default_step_budget"])
        default_readout_interval = int(request.budget["default_readout_interval"])
        default_checkpoint_interval = int(request.budget["default_checkpoint_interval"])

        ranked_clusters = sorted(
            request.clusters, key=lambda c: c.cluster_priority, reverse=True
        )

        cluster_plans: list[ClusterExecutionPlan] = []
        for cluster in ranked_clusters:
            candidate_ids = [c.candidate_id for c in cluster.candidates]
            step_budget = max(32, int(default_step_budget * max(1.0, cluster.cluster_priority)))
            step_budget = min(step_budget, int(request.termination_policy["max_steps"]))

            cluster_plans.append(
                ClusterExecutionPlan(
                    cluster_id=cluster.cluster_id,
                    candidate_ids=candidate_ids,
                    step_budget=step_budget,
                    readout_interval=default_readout_interval,
                    checkpoint_interval=default_checkpoint_interval,
                    backend=request.backend,
                    priority=cluster.cluster_priority,
                    metadata={"qcu_profile": request.qcu_profile, "budget_hint": cluster.budget_hint},
                )
            )

        return CollapsePlan(
            request_id=request.request_id,
            qcu_session_id=request.qcu_session_id,
            cluster_plans=cluster_plans,
            metadata={"source": "cluster_scheduler"},
        )
