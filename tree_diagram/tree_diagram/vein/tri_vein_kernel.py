from __future__ import annotations

"""vein/tri_vein_kernel.py

Three-channel (yield / stability / risk) vein score kernel.

Architecture position:
  vein layer — computes a structured three-channel representation
  for each candidate branch.  Used by VeinletExperts and the
  oracle/report layers for multi-axis analysis.

The three channels mirror the core UMDST dimensions:
  yield     — expected output gain (phase_max, nutrient_gain, feasibility)
  stability — resistance to blow-up (stability, 1-p_blow, repeatability)
  risk      — downside exposure (risk, p_blow, ood_proxy)
"""

import math
from dataclasses import dataclass
from typing import List, Optional

from ..core.worldline_kernel import EvaluationResult


# ---------------------------------------------------------------------------
# TriVeinScore
# ---------------------------------------------------------------------------

@dataclass
class TriVeinScore:
    """Three-channel vein score for a single candidate."""
    family:    str
    template:  str
    yield_:    float     # renamed from "yield" to avoid keyword clash
    stability: float
    risk:      float
    composite: float     # weighted combination

    @property
    def channel_vector(self) -> List[float]:
        return [self.yield_, self.stability, self.risk]

    def dominates(self, other: "TriVeinScore") -> bool:
        """Pareto dominance: self >= other on all channels and > on at least one."""
        return (
            self.yield_    >= other.yield_
            and self.stability >= other.stability
            and self.risk      <= other.risk
            and (
                self.yield_    > other.yield_
                or self.stability > other.stability
                or self.risk      < other.risk
            )
        )


# ---------------------------------------------------------------------------
# Channel weight defaults
# ---------------------------------------------------------------------------

DEFAULT_YIELD_WEIGHT    = 0.45
DEFAULT_STABILITY_WEIGHT = 0.35
DEFAULT_RISK_WEIGHT      = 0.20


# ---------------------------------------------------------------------------
# Score computation from EvaluationResult
# ---------------------------------------------------------------------------

def compute_tri_vein(
    result: EvaluationResult,
    yield_w:     float = DEFAULT_YIELD_WEIGHT,
    stability_w: float = DEFAULT_STABILITY_WEIGHT,
    risk_w:      float = DEFAULT_RISK_WEIGHT,
) -> TriVeinScore:
    """Compute a TriVeinScore from an EvaluationResult.

    yield     = 0.35 * feasibility + 0.25 * nutrient_gain + 0.15 * field_fit
              + 0.25 * balanced_score
    stability = 0.6 * stability   + 0.4 * (1 - risk)
    risk      = result.risk (direct; note: lower is better)
    composite = yield_w * yield - risk_w * risk + stability_w * stability

    balanced_score carries the n_penalty signal from worldline_kernel,
    ensuring the V-shaped penalty (|n - 20000| / 10000) propagates through
    the Vein layer and preserves the n=20000 alignment fixed point.
    """
    balanced = max(0.0, min(1.0, result.balanced_score))
    yield_score    = (0.35 * result.feasibility
                      + 0.25 * result.nutrient_gain
                      + 0.15 * result.field_fit
                      + 0.25 * balanced)
    stability_score = (0.60 * result.stability
                       + 0.40 * max(0.0, 1.0 - result.risk))
    risk_score      = result.risk

    # Clamp to [0, 1]
    yield_score     = max(0.0, min(1.0, yield_score))
    stability_score = max(0.0, min(1.0, stability_score))
    risk_score      = max(0.0, min(1.0, risk_score))

    composite = (
        yield_w     * yield_score
        + stability_w * stability_score
        - risk_w      * risk_score
    )

    return TriVeinScore(
        family=result.family,
        template=result.template,
        yield_=yield_score,
        stability=stability_score,
        risk=risk_score,
        composite=composite,
    )


# ---------------------------------------------------------------------------
# Batch computation
# ---------------------------------------------------------------------------

def compute_tri_vein_batch(
    results: List[EvaluationResult],
    yield_w:     float = DEFAULT_YIELD_WEIGHT,
    stability_w: float = DEFAULT_STABILITY_WEIGHT,
    risk_w:      float = DEFAULT_RISK_WEIGHT,
) -> List[TriVeinScore]:
    """Compute TriVeinScore for each EvaluationResult in a list."""
    return [compute_tri_vein(r, yield_w, stability_w, risk_w) for r in results]


# ---------------------------------------------------------------------------
# Pareto front extraction
# ---------------------------------------------------------------------------

def pareto_front(scores: List[TriVeinScore]) -> List[TriVeinScore]:
    """Return the Pareto-dominant subset of TriVeinScores.

    A score is Pareto-dominant if no other score dominates it.
    """
    front: List[TriVeinScore] = []
    for candidate in scores:
        dominated = any(other.dominates(candidate) for other in scores if other is not candidate)
        if not dominated:
            front.append(candidate)
    return sorted(front, key=lambda s: s.composite, reverse=True)


# ---------------------------------------------------------------------------
# Channel statistics
# ---------------------------------------------------------------------------

def tri_vein_stats(scores: List[TriVeinScore]) -> dict:
    """Compute per-channel mean, max, min statistics."""
    if not scores:
        return {}
    n = len(scores)
    yields     = [s.yield_    for s in scores]
    stabs      = [s.stability for s in scores]
    risks      = [s.risk      for s in scores]
    composites = [s.composite for s in scores]

    def _stats(vals: List[float]) -> dict:
        return {
            "mean": sum(vals) / n,
            "max":  max(vals),
            "min":  min(vals),
        }

    return {
        "yield":     _stats(yields),
        "stability": _stats(stabs),
        "risk":      _stats(risks),
        "composite": _stats(composites),
        "pareto_size": len(pareto_front(scores)),
    }
