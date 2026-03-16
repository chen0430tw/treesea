from __future__ import annotations

"""control/utm_controller.py

UTM (Unified Traffic Management) state machine controller.

Architecture position:
  control layer — implements the three-state governance machine that
  drives higher-level decisions about candidate routing and resource
  commitment.  Mirrors the UMDST GovernanceState model (NORMAL /
  NEGOTIATE / CRACKDOWN) but adds transition hysteresis and event
  history for audit.

States:
  NORMAL     — system within safe operating band; proceed normally
  NEGOTIATE  — yellow zone; reduce throughput, increase scrutiny
  CRACKDOWN  — red zone; halt risky candidates, enforce hard limits
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# State enum
# ---------------------------------------------------------------------------

class UTMState(str, Enum):
    NORMAL     = "NORMAL"
    NEGOTIATE  = "NEGOTIATE"
    CRACKDOWN  = "CRACKDOWN"


# ---------------------------------------------------------------------------
# Transition event
# ---------------------------------------------------------------------------

@dataclass
class UTMEvent:
    from_state:  str
    to_state:    str
    trigger:     str
    p_blow:      float
    step:        int


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class UTMController:
    """Three-state UTM state machine with hysteresis and event log.

    Hysteresis prevents rapid oscillation between states:
      - Transition UP   (toward CRACKDOWN) requires 1 consecutive trigger
      - Transition DOWN (toward NORMAL)    requires ``cool_down`` steps

    Usage::

        ctrl = UTMController(p0=0.60, p1=0.85)
        new_state = ctrl.update(p_blow=0.72, step=1)
    """

    def __init__(
        self,
        p0:        float = 0.60,
        p1:        float = 0.85,
        cool_down: int   = 3,
    ) -> None:
        self.p0        = p0
        self.p1        = p1
        self.cool_down = cool_down

        self._state:         UTMState      = UTMState.NORMAL
        self._steps_in_band: int           = 0   # steps spent below p0
        self._events:        List[UTMEvent] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> UTMState:
        return self._state

    @property
    def events(self) -> List[UTMEvent]:
        return list(self._events)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, p_blow: float, step: int = 0, reason: str = "") -> UTMState:
        """Advance state machine given current p_blow signal."""
        prev = self._state

        if p_blow >= self.p1:
            new_state = UTMState.CRACKDOWN
            self._steps_in_band = 0
        elif p_blow >= self.p0:
            new_state = UTMState.NEGOTIATE
            self._steps_in_band = 0
        else:
            # Below p0 — count toward cool-down
            self._steps_in_band += 1
            if self._state == UTMState.NORMAL or self._steps_in_band >= self.cool_down:
                new_state = UTMState.NORMAL
            else:
                new_state = self._state   # hold until cooled

        if new_state != prev:
            trigger = reason or f"p_blow={p_blow:.4f}"
            self._events.append(UTMEvent(
                from_state=prev.value,
                to_state=new_state.value,
                trigger=trigger,
                p_blow=p_blow,
                step=step,
            ))
            self._state = new_state

        return self._state

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def reset(self) -> None:
        self._state = UTMState.NORMAL
        self._steps_in_band = 0
        self._events.clear()

    def is_safe(self) -> bool:
        return self._state == UTMState.NORMAL

    def handshake_allowed(self) -> bool:
        return self._state in (UTMState.NORMAL, UTMState.NEGOTIATE)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state":          self._state.value,
            "p0":             self.p0,
            "p1":             self.p1,
            "cool_down":      self.cool_down,
            "steps_in_band":  self._steps_in_band,
            "n_events":       len(self._events),
            "last_event":     {
                "from":    self._events[-1].from_state,
                "to":      self._events[-1].to_state,
                "trigger": self._events[-1].trigger,
                "p_blow":  self._events[-1].p_blow,
            } if self._events else None,
        }
