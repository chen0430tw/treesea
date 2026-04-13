"""OPUBridge — QCU 与 OPU 的治理桥接。对位迁移自 archive QCU_调度工程完整版。

注意：原版 opu/core.py 依赖外部 opu.actions/config/stats/policies 等模块（不在此包内），
此处做最小适配：OPU core 通过 duck-typing 注入，只需有 observe() 和 decide() 方法。
"""
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
    step_time_s: float = 0.0
    rebuild_time_s: float = 0.0
    aperture_loss_s: float = 0.0


class OPUBridge:
    """桥接 QCU scheduler 和 OPU 治理核心。

    opu_core 只需满足 duck-typing:
        .observe(stats_dict) -> None
        .decide() -> action (任意对象，通过 getattr 读取字段)
    """

    def __init__(self, opu_core: Any):
        self.opu_core = opu_core

    def observe_and_adjust(
        self,
        plan: ClusterExecutionPlan,
        stats: StepStats,
    ) -> tuple[ClusterExecutionPlan, FeedbackAction]:
        # 向 OPU 发送观测信号
        self.opu_core.observe(
            {
                "hot_pressure": stats.hot_pressure,
                "faults": stats.faults,
                "wait_time_s": stats.wait_time_s,
                "rebuild_cost_s": stats.rebuild_cost_s,
                "quality_score": stats.quality_score,
                "step_time_s": stats.step_time_s,
                "rebuild_time_s": stats.rebuild_time_s,
                "aperture_loss_s": stats.aperture_loss_s,
            }
        )
        action = self.opu_core.decide()

        # 从 OPU 动作中提取反馈
        feedback = FeedbackAction(
            tighten=getattr(action, "tighten", False),
            relax=getattr(action, "relax", False),
            suppress_evict=getattr(action, "suppress_evict", False),
            gate_level=getattr(action, "gate_level", 0),
            quality_alarm=getattr(action, "quality_alarm", False),
            trace={"raw_action": repr(action)},
        )

        # 根据反馈调整执行计划
        adjusted = ClusterExecutionPlan(**plan.__dict__)
        if feedback.tighten:
            adjusted.step_budget = max(16, int(adjusted.step_budget * 0.8))
        elif feedback.relax:
            adjusted.step_budget = int(adjusted.step_budget * 1.1)

        if feedback.gate_level > 0:
            adjusted.readout_interval = max(
                4, adjusted.readout_interval // (feedback.gate_level + 1)
            )

        return adjusted, feedback
