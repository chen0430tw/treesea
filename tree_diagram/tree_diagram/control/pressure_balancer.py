from __future__ import annotations

"""control/pressure_balancer.py

Pressure balance computation for the control layer.

Architecture position:
  control layer — computes scalar pressure signals from hydro and vein
  states, used by UTMHydrologyController and oracle layers to determine
  system-level load balance.

Responsibilities:
  - Compute normalised pressure from hydro dict
  - Aggregate per-branch pressure contributions
  - Detect pressure imbalance (too high / too low)
  - Generate rebalancing recommendations
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..core.worldline_kernel import EvaluationResult


# ---------------------------------------------------------------------------
# Pressure report
# ---------------------------------------------------------------------------

@dataclass
class PressureReport:
    """System-level pressure analysis."""
    raw_pressure:       float     # directly from hydro pressure_balance
    normalised:         float     # remapped to [-1, 1]; 0 = perfectly balanced
    imbalance_severity: float     # [0, 1]; 0 = balanced, 1 = critically imbalanced
    direction:          str       # "balanced" | "over" | "under"
    recommendation:     str


# ---------------------------------------------------------------------------
# PressureBalancer
# ---------------------------------------------------------------------------

class PressureBalancer:
    """Compute and interpret system pressure from hydro and candidate states.

    The target pressure_balance is 1.0 (set by balance_layer conventions).
    Values above 1.15 indicate overflow risk; below 0.85 indicate drought.

    Usage::

        balancer = PressureBalancer()
        report   = balancer.analyse(hydro_dict, top_results)
    """

    TARGET    = 1.0
    OVER_TH   = 1.15
    UNDER_TH  = 0.85

    def __init__(
        self,
        target:   float = 1.0,
        over_th:  float = 1.15,
        under_th: float = 0.85,
    ) -> None:
        self.target   = target
        self.over_th  = over_th
        self.under_th = under_th

    # ------------------------------------------------------------------
    # Single-source analysis
    # ------------------------------------------------------------------

    def analyse(
        self,
        hydro: Dict,
        results: Optional[List[EvaluationResult]] = None,
    ) -> PressureReport:
        """Produce a PressureReport from a hydro dict and optional results."""
        raw = float(hydro.get("pressure_balance", 1.0))
        normalised = (raw - self.target) / max(self.over_th - self.under_th, 1e-9) * 2.0
        normalised = max(-1.0, min(1.0, normalised))

        imbalance = abs(raw - self.target) / max(
            abs(self.over_th - self.target),
            abs(self.target - self.under_th),
            1e-9,
        )
        imbalance = min(1.0, imbalance)

        if raw > self.over_th:
            direction = "over"
            recommendation = self._over_recommendation(raw, results)
        elif raw < self.under_th:
            direction = "under"
            recommendation = self._under_recommendation(raw, results)
        else:
            direction = "balanced"
            recommendation = "System pressure within normal band — no action required."

        return PressureReport(
            raw_pressure=raw,
            normalised=normalised,
            imbalance_severity=imbalance,
            direction=direction,
            recommendation=recommendation,
        )

    # ------------------------------------------------------------------
    # Aggregation across multiple hydro dicts
    # ------------------------------------------------------------------

    def aggregate(self, hydro_list: List[Dict]) -> PressureReport:
        """Aggregate pressure from multiple hydro dicts (weighted mean)."""
        if not hydro_list:
            return self.analyse({})
        mean_pb = sum(h.get("pressure_balance", 1.0) for h in hydro_list) / len(hydro_list)
        return self.analyse({"pressure_balance": mean_pb})

    # ------------------------------------------------------------------
    # Per-branch pressure contribution
    # ------------------------------------------------------------------

    def branch_pressure_vector(
        self,
        results: List[EvaluationResult],
    ) -> List[float]:
        """Return a pressure contribution per branch based on risk and stability."""
        contributions: List[float] = []
        for r in results:
            # High risk + low stability → high pressure contribution
            p = 0.6 * r.risk + 0.4 * (1.0 - r.stability)
            contributions.append(max(0.0, min(2.0, p)))
        return contributions

    def total_pressure(self, results: List[EvaluationResult]) -> float:
        """Sum of per-branch pressure contributions."""
        return sum(self.branch_pressure_vector(results))

    # ------------------------------------------------------------------
    # Internal recommendation helpers
    # ------------------------------------------------------------------

    def _over_recommendation(
        self,
        raw: float,
        results: Optional[List[EvaluationResult]],
    ) -> str:
        severity = "moderate" if raw < 1.30 else "severe"
        n_active = sum(1 for r in results if r.branch_status == "active") if results else "?"
        return (
            f"Over-pressure ({severity}, pb={raw:.3f}): consider throttling {n_active} "
            f"active branches or reducing nutrient supply."
        )

    def _under_recommendation(
        self,
        raw: float,
        results: Optional[List[EvaluationResult]],
    ) -> str:
        n_withered = sum(1 for r in results if r.branch_status == "withered") if results else "?"
        return (
            f"Under-pressure (pb={raw:.3f}): {n_withered} withered branches may be "
            f"starving the supply pool.  Consider pruning or increasing resource budget."
        )

    def balance(self, metrics: list) -> dict:
        """Convenience alias: accepts a raw metrics list (dicts) and returns a summary dict."""
        hydro = {
            "pressure_balance": sum(m.get("balanced_score", 0.5) for m in metrics) / max(1, len(metrics)),
        }
        report = self.analyse(hydro)
        return {
            "pressure_balance": report.raw_pressure,
            "direction": report.direction,
            "recommendation": report.recommendation,
        }
