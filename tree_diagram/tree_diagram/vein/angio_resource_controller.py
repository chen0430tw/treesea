from __future__ import annotations

"""vein/angio_resource_controller.py

Angiogenesis-inspired resource controller.

Architecture position:
  vein layer — manages nutrient allocation, withering, supply restriction,
  starvation, and reflux across candidate branches.  Inspired by
  hydro_adjust_top_candidates() in the v3_active prototype and the
  balance_layer.hydro_adjust_abstract() implementation.

The controller models each branch as a vascular segment:
  - active branches receive nutrient surplus
  - restricted branches receive reduced supply
  - starved branches are monitored for potential recovery
  - withered branches are pruned from nutrient flow

Nutrient reflux redistributes withheld supply to active branches.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..core.worldline_kernel import EvaluationResult


# ---------------------------------------------------------------------------
# Nutrient state
# ---------------------------------------------------------------------------

@dataclass
class NutrientState:
    """Per-branch nutrient accounting."""
    family:        str
    template:      str
    branch_status: str
    raw_nutrient:  float     # from EvaluationResult.nutrient_gain
    allocated:     float     # after controller policy
    reflux:        float     # amount returned to pool
    starved:       bool
    wither_score:  float     # 0 = healthy, 1 = fully withered


# ---------------------------------------------------------------------------
# Controller parameters
# ---------------------------------------------------------------------------

@dataclass
class AngioParams:
    active_boost:       float = 1.20    # multiplier on active branch nutrients
    restricted_scale:   float = 0.55    # fraction for restricted branches
    starved_scale:      float = 0.20    # fraction for starved branches
    wither_threshold:   float = 0.10    # nutrient below this triggers withering
    reflux_fraction:    float = 0.80    # fraction of withheld supply refluxed
    starvation_risk_lo: float = 0.70    # risk above this → starvation warning
    max_total:          float = 2.0     # pool ceiling (normalised)


# ---------------------------------------------------------------------------
# Main controller
# ---------------------------------------------------------------------------

class AngioResourceController:
    """Nutrient allocation controller modelled on angiogenesis.

    Usage::

        ctrl = AngioResourceController()
        states = ctrl.allocate(top_results)
        hydro  = ctrl.hydro_summary(states)
    """

    def __init__(self, params: Optional[AngioParams] = None) -> None:
        self.params = params if params is not None else AngioParams()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def allocate(self, results: List[EvaluationResult]) -> List[NutrientState]:
        """Compute nutrient states for all evaluated results."""
        if not results:
            return []

        p = self.params
        states: List[NutrientState] = []
        total_raw = sum(r.nutrient_gain for r in results)
        pool = min(p.max_total, total_raw * 1.10)  # allow 10% boost headroom

        withheld = 0.0

        for r in results:
            raw = r.nutrient_gain
            status = r.branch_status
            starved = False

            if status == "active":
                allocated = min(pool, raw * p.active_boost)
                reflux = 0.0
                wither_score = 0.0
            elif status == "restricted":
                allocated = raw * p.restricted_scale
                reflux = (raw - allocated) * p.reflux_fraction
                withheld += raw - allocated - reflux
                wither_score = max(0.0, 0.3 * (1.0 - raw / max(0.01, total_raw / len(results))))
                if r.risk > p.starvation_risk_lo:
                    starved = True
            elif status == "starved":
                allocated = raw * p.starved_scale
                reflux = (raw - allocated) * p.reflux_fraction
                withheld += raw - allocated - reflux
                wither_score = 0.6
                starved = True
            elif status == "withered":
                allocated = 0.0
                reflux = raw * p.reflux_fraction
                withheld += raw * (1.0 - p.reflux_fraction)
                wither_score = 1.0
            else:
                # unknown status: treat as restricted
                allocated = raw * p.restricted_scale
                reflux = 0.0
                wither_score = 0.2

            if allocated < p.wither_threshold and status not in ("withered", "starved"):
                wither_score = max(wither_score, 0.75)

            states.append(NutrientState(
                family=r.family,
                template=r.template,
                branch_status=status,
                raw_nutrient=raw,
                allocated=allocated,
                reflux=reflux,
                starved=starved,
                wither_score=wither_score,
            ))

        # Reflux redistribution: boost active branches proportionally
        total_reflux = sum(s.reflux for s in states)
        active_states = [s for s in states if s.branch_status == "active"]
        if active_states and total_reflux > 1e-9:
            share = total_reflux / len(active_states)
            for s in active_states:
                s.allocated = min(p.max_total, s.allocated + share)
                s.reflux    = total_reflux  # record total reflux on each active node

        return states

    # ------------------------------------------------------------------
    # Hydro summary (mirrors balance_layer.hydro_adjust_abstract format)
    # ------------------------------------------------------------------

    def hydro_summary(self, states: List[NutrientState]) -> dict:
        """Produce a hydro control summary compatible with balance_layer format."""
        if not states:
            return {
                "pressure_balance": 1.0,
                "wither_ratio":     0.0,
                "active_ratio":     0.0,
                "restricted_ratio": 0.0,
                "starved_ratio":    0.0,
                "mean_allocated":   0.0,
                "total_reflux":     0.0,
            }

        n = len(states)
        wither_count     = sum(1 for s in states if s.branch_status == "withered")
        active_count     = sum(1 for s in states if s.branch_status == "active")
        restricted_count = sum(1 for s in states if s.branch_status == "restricted")
        starved_count    = sum(1 for s in states if s.starved)

        wither_ratio     = wither_count     / n
        active_ratio     = active_count     / n
        restricted_ratio = restricted_count / n
        starved_ratio    = starved_count    / n

        mean_allocated = sum(s.allocated for s in states) / n
        total_reflux   = sum(s.reflux    for s in states)

        pressure_balance = max(0.0, min(2.0,
            1.0 + active_ratio - wither_ratio - 0.5 * starved_ratio
        ))

        return {
            "pressure_balance": pressure_balance,
            "wither_ratio":     wither_ratio,
            "active_ratio":     active_ratio,
            "restricted_ratio": restricted_ratio,
            "starved_ratio":    starved_ratio,
            "mean_allocated":   mean_allocated,
            "total_reflux":     total_reflux,
        }

    # ------------------------------------------------------------------
    # Starvation detection
    # ------------------------------------------------------------------

    def detect_starvation(
        self,
        states: List[NutrientState],
        threshold: float = 0.3,
    ) -> List[NutrientState]:
        """Return branches at risk of starvation (high wither_score)."""
        return [s for s in states if s.wither_score >= threshold or s.starved]

    # ------------------------------------------------------------------
    # Reflux computation (standalone)
    # ------------------------------------------------------------------

    def compute_reflux(self, states: List[NutrientState]) -> float:
        """Total nutrient reflux available for redistribution."""
        return sum(s.reflux for s in states)
