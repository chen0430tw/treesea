# controller.py
from __future__ import annotations
from dataclasses import dataclass, field
from qcu.runtime.state import RuntimeState

@dataclass
class ControlAction:
    tighten: float = 0.0
    relax: float = 0.0
    suppress: list[int] = field(default_factory=list)
    boost: list[int] = field(default_factory=list)
    early_stop: bool = False
    reason: str = ""

class OPUController:
    def tick(self, state: RuntimeState) -> ControlAction:
        if state.quality_signal > 0.92 and state.attractor_density > 0.85:
            return ControlAction(early_stop=True, reason="stable peak reached")
        return ControlAction()
