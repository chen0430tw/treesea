from __future__ import annotations

"""llm_bridge/explanation_layer.py

Oracle result explanation layer for LLM consumption.

Architecture position:
  llm_bridge layer — final stage.  Takes OracleReport / OracleEnvelope
  and produces LLM-friendly explanations: structured JSON summaries and
  natural-language commentary suitable for inclusion in LLM prompts or
  downstream API responses.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..oracle.report_builder import OracleReport
from ..oracle.oracle_output import OracleEnvelope


# ---------------------------------------------------------------------------
# Explanation output
# ---------------------------------------------------------------------------

@dataclass
class ExplanationOutput:
    """Structured explanation of oracle results for LLM consumption."""
    summary:      str           # one-paragraph plain-text summary
    key_findings: List[str]     # bullet-point findings
    warnings:     List[str]     # risk warnings
    json_payload: Dict[str, Any]  # machine-readable structured summary
    confidence:   float           # overall explanation confidence [0, 1]


# ---------------------------------------------------------------------------
# ExplanationLayer
# ---------------------------------------------------------------------------

class ExplanationLayer:
    """Generate LLM-ready explanations from oracle results.

    Usage::

        explainer = ExplanationLayer()
        exp = explainer.explain(report)
        print(exp.summary)
        print(json.dumps(exp.json_payload, indent=2))
    """

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def explain(self, report: OracleReport) -> ExplanationOutput:
        """Generate a full explanation for an OracleReport."""
        summary      = self._build_summary(report)
        key_findings = self._build_findings(report)
        warnings     = self._build_warnings(report)
        payload      = self._build_payload(report)
        confidence   = self._estimate_confidence(report)

        return ExplanationOutput(
            summary=summary,
            key_findings=key_findings,
            warnings=warnings,
            json_payload=payload,
            confidence=confidence,
        )

    def explain_envelope(self, envelope: OracleEnvelope) -> ExplanationOutput:
        """Convenience: explain from an OracleEnvelope directly."""
        from ..oracle.report_builder import ReportBuilder
        report = ReportBuilder().build(envelope)
        return self.explain(report)

    # ------------------------------------------------------------------
    # Summary paragraph
    # ------------------------------------------------------------------

    def _build_summary(self, r: OracleReport) -> str:
        gov_desc = {
            "NORMAL":    "within the safe operating band",
            "NEGOTIATE": "in the yellow zone and under increased scrutiny",
            "CRACKDOWN": "in the red zone with suppression measures active",
        }.get(r.governance_state, f"in state {r.governance_state}")

        hydro_desc = ""
        pb = r.pressure_balance
        if pb > 1.15:
            hydro_desc = " Hydro pressure is elevated (overflow risk)."
        elif pb < 0.85:
            hydro_desc = " Hydro pressure is low (drought condition)."

        return (
            f"Tree Diagram analysis of '{r.seed_title}' identified "
            f"the '{r.best_family}' family (template: {r.best_template}) "
            f"as the optimal path with a score of {r.best_score:.4f}. "
            f"The system is {gov_desc} (blow-up probability: {r.p_blow:.4f}).{hydro_desc} "
            f"Out of {r.total_evaluated} evaluated candidates, "
            f"{r.branch_histogram.get('active', 0)} are active and "
            f"{r.branch_histogram.get('withered', 0)} have withered."
        )

    # ------------------------------------------------------------------
    # Key findings
    # ------------------------------------------------------------------

    def _build_findings(self, r: OracleReport) -> List[str]:
        findings: List[str] = []

        findings.append(
            f"Best path: {r.best_family}/{r.best_template}, "
            f"score={r.best_score:.4f}, "
            f"feasibility={r.best_feasibility:.4f}, "
            f"stability={r.best_stability:.4f}, "
            f"risk={r.best_risk:.4f}."
        )

        if r.core_contradiction:
            findings.append(f"Core contradiction: {r.core_contradiction}")
        if r.inferred_goal_axis:
            findings.append(f"Goal axis: {r.inferred_goal_axis}")
        if r.dominant_pressures:
            findings.append(f"Dominant pressures: {', '.join(r.dominant_pressures[:3])}.")

        hist = r.branch_histogram
        total = r.total_evaluated or 1
        findings.append(
            f"Branch distribution: "
            f"active={hist.get('active', 0)}/{total}, "
            f"restricted={hist.get('restricted', 0)}/{total}, "
            f"starved={hist.get('starved', 0)}/{total}, "
            f"withered={hist.get('withered', 0)}/{total}."
        )

        if r.top_families:
            fam_names = [tf.get("family", "?") for tf in r.top_families[:3]]
            findings.append(f"Top-3 families: {', '.join(fam_names)}.")

        return findings

    # ------------------------------------------------------------------
    # Warnings
    # ------------------------------------------------------------------

    def _build_warnings(self, r: OracleReport) -> List[str]:
        warnings: List[str] = list(r.warnings)

        if r.governance_state == "CRACKDOWN":
            warnings.append(
                f"CRACKDOWN: blow-up probability {r.p_blow:.4f} exceeds red-line threshold."
            )
        elif r.governance_state == "NEGOTIATE":
            warnings.append(
                f"NEGOTIATE: system in yellow zone (p_blow={r.p_blow:.4f}). Reduce throughput."
            )

        if r.pressure_balance > 1.15:
            warnings.append(
                f"Over-pressure (pb={r.pressure_balance:.4f}). "
                "Consider throttling active branches."
            )
        elif r.pressure_balance < 0.85:
            warnings.append(
                f"Under-pressure (pb={r.pressure_balance:.4f}). "
                "Supply may be insufficient."
            )

        wither_ratio = r.branch_histogram.get("withered", 0) / max(r.total_evaluated, 1)
        if wither_ratio > 0.40:
            warnings.append(
                f"High wither ratio ({wither_ratio:.0%}): many branches are starved."
            )

        return warnings

    # ------------------------------------------------------------------
    # JSON payload
    # ------------------------------------------------------------------

    def _build_payload(self, r: OracleReport) -> Dict[str, Any]:
        return {
            "seed_title":          r.seed_title,
            "mode":                r.mode,
            "best": {
                "family":          r.best_family,
                "template":        r.best_template,
                "score":           round(r.best_score, 6),
                "feasibility":     round(r.best_feasibility, 4),
                "stability":       round(r.best_stability, 4),
                "risk":            round(r.best_risk, 4),
                "params":          r.best_params,
            },
            "governance": {
                "state":           r.governance_state,
                "p_blow":          round(r.p_blow, 4),
            },
            "hydro": {
                "pressure_balance": round(r.pressure_balance, 4),
                "active_ratio":    round(r.active_ratio, 4),
                "wither_ratio":    round(r.wither_ratio, 4),
            },
            "branch_histogram":    r.branch_histogram,
            "total_evaluated":     r.total_evaluated,
            "top_families":        r.top_families[:5],
        }

    # ------------------------------------------------------------------
    # Confidence estimate
    # ------------------------------------------------------------------

    def _estimate_confidence(self, r: OracleReport) -> float:
        """Estimate explanation confidence based on report quality signals."""
        conf = 1.0
        if r.total_evaluated < 5:
            conf -= 0.20
        if r.best_score < 0.01:
            conf -= 0.15
        if r.governance_state == "CRACKDOWN":
            conf -= 0.10
        if r.best_family == "":
            conf -= 0.30
        return max(0.0, min(1.0, conf))
