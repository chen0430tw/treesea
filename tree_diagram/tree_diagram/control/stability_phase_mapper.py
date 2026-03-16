from __future__ import annotations

"""control/stability_phase_mapper.py

Stability-phase zone mapper for the control layer.

Architecture position:
  control layer — maps the continuous (phase, stress, instability) triplet
  to a discrete stability phase label, and provides transition thresholds
  used by UTMController and the oracle layer.

Phase zones (4-level schema):
  LOCKED      — high stability, low stress; phase locked to target
  RESONANT    — near-target phase with acceptable stress; optimal operating zone
  DRIFTING    — phase proximity good but increasing stress/instability
  UNSTABLE    — phase below threshold or blow-up risk is high
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..core.worldline_kernel import EvaluationResult


# ---------------------------------------------------------------------------
# Zone enum (as string constants for JSON compatibility)
# ---------------------------------------------------------------------------

ZONE_LOCKED   = "LOCKED"
ZONE_RESONANT = "RESONANT"
ZONE_DRIFTING = "DRIFTING"
ZONE_UNSTABLE = "UNSTABLE"

ZONE_ORDER = [ZONE_LOCKED, ZONE_RESONANT, ZONE_DRIFTING, ZONE_UNSTABLE]

# Transition thresholds
LOCKED_PHASE_MIN    = 0.88
RESONANT_PHASE_MIN  = 0.65
DRIFTING_PHASE_MIN  = 0.40
STRESS_LOCKED_MAX   = 0.25
STRESS_RESONANT_MAX = 0.50
INSTAB_LOCKED_MAX   = 0.20
INSTAB_RESONANT_MAX = 0.45


# ---------------------------------------------------------------------------
# Phase zone map
# ---------------------------------------------------------------------------

@dataclass
class PhaseZoneMap:
    zone:          str
    phase:         float
    stress:        float
    instability:   float
    stability:     float
    score:         float     # composite stability-phase score [0, 1]


# ---------------------------------------------------------------------------
# StabilityPhaseMapper
# ---------------------------------------------------------------------------

class StabilityPhaseMapper:
    """Map (phase, stress, instability, stability) → stability phase zone.

    Usage::

        mapper = StabilityPhaseMapper()
        zone   = mapper.classify(phase=0.72, stress=0.35, instability=0.28, stability=0.68)
        zmap   = mapper.map_result(eval_result)
    """

    # ------------------------------------------------------------------
    # Core classification
    # ------------------------------------------------------------------

    def classify(
        self,
        phase:       float,
        stress:      float,
        instability: float,
        stability:   float,
    ) -> str:
        """Return the zone label for given scalar state."""
        if (phase       >= LOCKED_PHASE_MIN
                and stress      <= STRESS_LOCKED_MAX
                and instability <= INSTAB_LOCKED_MAX
                and stability   >= 0.80):
            return ZONE_LOCKED

        if (phase       >= RESONANT_PHASE_MIN
                and stress      <= STRESS_RESONANT_MAX
                and instability <= INSTAB_RESONANT_MAX):
            return ZONE_RESONANT

        if phase >= DRIFTING_PHASE_MIN:
            return ZONE_DRIFTING

        return ZONE_UNSTABLE

    def score_zone(
        self,
        phase:       float,
        stress:      float,
        instability: float,
        stability:   float,
    ) -> float:
        """Compute a composite stability-phase score in [0, 1]."""
        s = (
            0.40 * max(0.0, min(1.0, phase))
            + 0.30 * max(0.0, min(1.0, stability))
            - 0.20 * max(0.0, min(1.0, stress))
            - 0.10 * max(0.0, min(1.0, instability))
        )
        return max(0.0, min(1.0, s))

    # ------------------------------------------------------------------
    # EvaluationResult → PhaseZoneMap
    # ------------------------------------------------------------------

    def map_result(self, result: EvaluationResult) -> PhaseZoneMap:
        """Map a single EvaluationResult to a PhaseZoneMap."""
        # EvaluationResult uses field_fit as a proxy for phase proximity
        phase       = result.field_fit   # best available phase proxy
        stress      = result.risk        # risk is stress-related
        instability = max(0.0, 1.0 - result.stability)
        stability   = result.stability

        zone  = self.classify(phase, stress, instability, stability)
        score = self.score_zone(phase, stress, instability, stability)

        return PhaseZoneMap(
            zone=zone,
            phase=phase,
            stress=stress,
            instability=instability,
            stability=stability,
            score=score,
        )

    def map_results(self, results: List[EvaluationResult]) -> List[PhaseZoneMap]:
        """Map a list of EvaluationResults."""
        return [self.map_result(r) for r in results]

    # ------------------------------------------------------------------
    # Zone statistics
    # ------------------------------------------------------------------

    def zone_histogram(self, zmaps: List[PhaseZoneMap]) -> Dict[str, int]:
        hist: Dict[str, int] = {z: 0 for z in ZONE_ORDER}
        for m in zmaps:
            hist[m.zone] = hist.get(m.zone, 0) + 1
        return hist

    def dominant_zone(self, zmaps: List[PhaseZoneMap]) -> str:
        if not zmaps:
            return ZONE_UNSTABLE
        hist = self.zone_histogram(zmaps)
        return max(hist, key=lambda z: hist[z])

    def mean_score(self, zmaps: List[PhaseZoneMap]) -> float:
        if not zmaps:
            return 0.0
        return sum(m.score for m in zmaps) / len(zmaps)

    # ------------------------------------------------------------------
    # Transition check
    # ------------------------------------------------------------------

    def transition_risk(self, zmaps: List[PhaseZoneMap]) -> float:
        """Proportion of branches in DRIFTING or UNSTABLE zones."""
        if not zmaps:
            return 0.0
        at_risk = sum(1 for m in zmaps if m.zone in (ZONE_DRIFTING, ZONE_UNSTABLE))
        return at_risk / len(zmaps)

    def map(self, metrics: list) -> dict:
        """Convenience alias: accepts a raw metrics list (dicts) and returns a zone summary dict."""
        from ..core.worldline_kernel import EvaluationResult
        results = [
            EvaluationResult(
                family=m.get("family", "batch"),
                template=m.get("name", ""),
                params={},
                feasibility=float(m.get("feasibility", 0.6)),
                stability=float(m.get("stability", 0.7)),
                field_fit=float(m.get("balanced_score", 0.5)),
                risk=float(m.get("risk", 0.3)),
                balanced_score=float(m.get("balanced_score", 0.5)),
                nutrient_gain=0.5,
                branch_status=m.get("branch_status", "active"),
            )
            for m in metrics
        ]
        zmaps = self.map_results(results)
        return {
            "zone_histogram": self.zone_histogram(zmaps),
            "dominant_zone": self.dominant_zone(zmaps),
            "mean_score": self.mean_score(zmaps),
            "transition_risk": self.transition_risk(zmaps),
        }
