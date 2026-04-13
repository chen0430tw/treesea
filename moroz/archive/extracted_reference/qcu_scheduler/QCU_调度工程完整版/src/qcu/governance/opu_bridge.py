from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from qcu.scheduler.models import ClusterExecutionPlan, FeedbackAction

@dataclass
class StepStats:
    hot_pressure: float
    faults: int
    wait_time_s: float
    rebuild_cost_s: float
    quality_score: float

class OPUBridge:
    def __init__(self, opu_core: Any):
        self.opu_core = opu_core

    def observe_and_adjust(
        self,
        plan: ClusterExecutionPlan,
        stats: StepStats,
    ) -> tuple[ClusterExecutionPlan, FeedbackAction]:
        self.opu_core.observe(
            {
                "hot_pressure": stats.hot_pressure,
                "faults": stats.faults,
                "wait_time_s": stats.wait_time_s,
                "rebuild_cost_s": stats.rebuild_cost_s,
                "quality_score": stats.quality_score,
            }
        )
        action = self.opu_core.decide()

        feedback = FeedbackAction(
            tighten=getattr(action, "tighten", False),
            relax=getattr(action, "relax", False),
            suppress_evict=getattr(action, "suppress_evict", False),
            gate_level=getattr(action, "gate_level", 0),
            quality_alarm=getattr(action, "quality_alarm", False),
            trace={"raw_action": repr(action)},
        )

        adjusted = ClusterExecutionPlan(**plan.__dict__)
        if feedback.tighten:
            adjusted.step_budget = max(16, int(adjusted.step_budget * 0.8))
        elif feedback.relax:
            adjusted.step_budget = int(adjusted.step_budget * 1.1)

        if feedback.gate_level > 0:
            adjusted.readout_interval = max(4, adjusted.readout_interval // (feedback.gate_level + 1))

        return adjusted, feedback
