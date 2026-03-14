# collapse_scheduler.py
from __future__ import annotations

from dataclasses import dataclass
from .models import ClusterExecutionPlan

@dataclass
class CollapseStepWindow:
    start_step: int
    end_step: int
    do_readout: bool
    do_checkpoint: bool

class CollapseScheduler:
    def split_windows(self, plan: ClusterExecutionPlan) -> list[CollapseStepWindow]:
        windows: list[CollapseStepWindow] = []
        step = 0
        while step < plan.step_budget:
            next_step = min(step + plan.readout_interval, plan.step_budget)
            do_readout = True
            do_checkpoint = (next_step % plan.checkpoint_interval == 0) or (next_step == plan.step_budget)
            windows.append(
                CollapseStepWindow(
                    start_step=step,
                    end_step=next_step,
                    do_readout=do_readout,
                    do_checkpoint=do_checkpoint,
                )
            )
            step = next_step
        return windows
