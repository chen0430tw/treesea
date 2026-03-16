from __future__ import annotations

"""vein/veinlet_experts.py

Micro-expert ensemble: one specialist expert per candidate family.

Architecture position:
  vein layer — provides family-specific scoring adjustments on top of
  the raw TriVeinScore.  Each VeinletExpert encodes domain knowledge
  about a particular execution family (batch, phase, hybrid, etc.).

Design:
  - VeinletExpert: stateless scorer for one family, returns an adjusted
    composite score and a confidence weight
  - VeinletEnsemble: aggregates all experts, routes each candidate to
    its matching expert, falls back to default for unknown families
"""

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .tri_vein_kernel import TriVeinScore


# ---------------------------------------------------------------------------
# Expert scoring result
# ---------------------------------------------------------------------------

@dataclass
class ExpertScore:
    family:     str
    raw:        float       # composite from TriVeinScore
    adjusted:   float       # after expert policy
    confidence: float       # weight of this expert's opinion [0, 1]
    notes:      str


# ---------------------------------------------------------------------------
# Expert definition
# ---------------------------------------------------------------------------

@dataclass
class VeinletExpert:
    """A micro-expert that specialises in one candidate family.

    Parameters
    ----------
    family_name : str
        Name of the family this expert handles.
    yield_bias : float
        Additive adjustment to yield channel before composite.
    stability_bias : float
        Additive adjustment to stability channel.
    risk_scale : float
        Multiplicative scale on risk channel (>1 = more risk-averse).
    confidence_base : float
        Base confidence for this expert [0, 1].
    """
    family_name:      str
    yield_bias:       float = 0.0
    stability_bias:   float = 0.0
    risk_scale:       float = 1.0
    confidence_base:  float = 0.8

    def score(self, tri: TriVeinScore) -> ExpertScore:
        """Apply expert policy to a TriVeinScore."""
        adj_yield    = max(0.0, min(1.0, tri.yield_    + self.yield_bias))
        adj_stab     = max(0.0, min(1.0, tri.stability + self.stability_bias))
        adj_risk     = max(0.0, min(1.0, tri.risk      * self.risk_scale))

        adjusted = (
            0.45 * adj_yield
            + 0.35 * adj_stab
            - 0.20 * adj_risk
        )

        # Confidence degrades when risk is high
        confidence = self.confidence_base * max(0.2, 1.0 - 0.5 * adj_risk)

        return ExpertScore(
            family=tri.family,
            raw=tri.composite,
            adjusted=adjusted,
            confidence=confidence,
            notes=f"{self.family_name} expert: yield_bias={self.yield_bias:+.3f}, risk_scale={self.risk_scale:.2f}",
        )

    def handles(self, family: str) -> bool:
        return self.family_name == family


# ---------------------------------------------------------------------------
# Built-in expert registry
# ---------------------------------------------------------------------------

def _default_experts() -> Dict[str, VeinletExpert]:
    return {
        "batch":      VeinletExpert("batch",      yield_bias=+0.04, stability_bias=+0.02, risk_scale=0.90, confidence_base=0.88),
        "phase":      VeinletExpert("phase",      yield_bias=+0.02, stability_bias=+0.04, risk_scale=1.00, confidence_base=0.85),
        "hybrid":     VeinletExpert("hybrid",     yield_bias=+0.01, stability_bias=-0.01, risk_scale=1.15, confidence_base=0.78),
        "network":    VeinletExpert("network",    yield_bias=+0.03, stability_bias=+0.01, risk_scale=0.95, confidence_base=0.82),
        "electrical": VeinletExpert("electrical", yield_bias=+0.05, stability_bias=+0.00, risk_scale=1.05, confidence_base=0.80),
        "ascetic":    VeinletExpert("ascetic",    yield_bias=-0.03, stability_bias=+0.06, risk_scale=0.80, confidence_base=0.76),
        "composite":  VeinletExpert("composite",  yield_bias=+0.02, stability_bias=+0.02, risk_scale=0.98, confidence_base=0.83),
        # Weather families
        "weak_mix":     VeinletExpert("weak_mix",     yield_bias=-0.01, stability_bias=+0.03, risk_scale=0.88, confidence_base=0.75),
        "balanced":     VeinletExpert("balanced",     yield_bias=+0.00, stability_bias=+0.02, risk_scale=0.95, confidence_base=0.80),
        "high_mix":     VeinletExpert("high_mix",     yield_bias=+0.04, stability_bias=-0.02, risk_scale=1.10, confidence_base=0.72),
        "humid_bias":   VeinletExpert("humid_bias",   yield_bias=+0.01, stability_bias=+0.01, risk_scale=1.00, confidence_base=0.78),
        "strong_pg":    VeinletExpert("strong_pg",    yield_bias=+0.03, stability_bias=-0.01, risk_scale=1.08, confidence_base=0.74),
        "terrain_lock": VeinletExpert("terrain_lock", yield_bias=-0.02, stability_bias=+0.04, risk_scale=0.92, confidence_base=0.76),
    }


# ---------------------------------------------------------------------------
# VeinletEnsemble
# ---------------------------------------------------------------------------

class VeinletEnsemble:
    """Aggregates all VeinletExperts and routes candidates to their expert.

    Usage::

        ensemble = VeinletEnsemble()
        results  = ensemble.score_all(tri_vein_scores)
    """

    def __init__(
        self,
        experts: Optional[Dict[str, VeinletExpert]] = None,
    ) -> None:
        self._experts = experts if experts is not None else _default_experts()
        self._default = VeinletExpert(
            "default",
            yield_bias=0.0,
            stability_bias=0.0,
            risk_scale=1.0,
            confidence_base=0.65,
        )

    def get_expert(self, family: str) -> VeinletExpert:
        return self._experts.get(family, self._default)

    def score(self, tri: TriVeinScore) -> ExpertScore:
        """Route a TriVeinScore to the matching expert and return ExpertScore."""
        expert = self.get_expert(tri.family)
        return expert.score(tri)

    def score_all(self, tris: List[TriVeinScore]) -> List[ExpertScore]:
        """Score a list of TriVeinScores, one per candidate."""
        return [self.score(t) for t in tris]

    def weighted_aggregate(
        self,
        scores: List[ExpertScore],
    ) -> float:
        """Compute confidence-weighted mean of adjusted scores."""
        if not scores:
            return 0.0
        total_conf  = sum(s.confidence for s in scores)
        if total_conf < 1e-12:
            return sum(s.adjusted for s in scores) / len(scores)
        return sum(s.adjusted * s.confidence for s in scores) / total_conf

    def top_k(
        self,
        tris: List[TriVeinScore],
        k: int = 5,
    ) -> List[Tuple[TriVeinScore, ExpertScore]]:
        """Return top-k (tri, expert_score) pairs sorted by adjusted score."""
        scored = [(t, self.score(t)) for t in tris]
        scored.sort(key=lambda x: x[1].adjusted, reverse=True)
        return scored[:k]
