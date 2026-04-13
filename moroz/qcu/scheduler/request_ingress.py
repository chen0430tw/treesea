"""RequestIngress — 请求规范化。对位迁移自 archive QCU_调度工程完整版。"""
from __future__ import annotations

from .models import CollapseRequest


class RequestIngress:
    def normalize(self, request: CollapseRequest) -> CollapseRequest:
        if not request.request_id:
            raise ValueError("request_id is required")
        if not request.qcu_session_id:
            raise ValueError("qcu_session_id is required")
        if not request.clusters:
            raise ValueError("clusters must not be empty")

        request.budget.setdefault("default_step_budget", 128)
        request.budget.setdefault("default_readout_interval", 16)
        request.budget.setdefault("default_checkpoint_interval", 32)

        request.termination_policy.setdefault("target_collapse_score", 0.90)
        request.termination_policy.setdefault("target_stability", 0.80)
        request.termination_policy.setdefault("max_steps", 512)
        return request
