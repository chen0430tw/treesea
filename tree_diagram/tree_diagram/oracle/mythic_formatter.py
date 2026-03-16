from __future__ import annotations

"""oracle/mythic_formatter.py

Mythic-style narrative text formatter (Academy City aesthetic).

Architecture position:
  oracle layer — converts OracleReport / oracle dicts into dramatic,
  Academy City-flavoured narrative text for LLM display and user-facing
  output.

The formatter does not perform any computation — it only renders
pre-computed results into styled natural-language strings.
"""

from typing import Any, Dict, List, Optional

from .report_builder import OracleReport


# ---------------------------------------------------------------------------
# Tone presets
# ---------------------------------------------------------------------------

_GOVERNANCE_FLAVOUR = {
    "NORMAL":     "The system resonates within the stable band.",
    "NEGOTIATE":  "Yellow zone detected — Judgment is deliberating.",
    "CRACKDOWN":  "DEFCON RED. Tree Diagram has declared a suppression order.",
}

_ZONE_FLAVOUR = {
    "LOCKED":     "Phase lock confirmed. Esper output is sustained at resonance.",
    "RESONANT":   "Near-resonance detected. Phase coupling is strong.",
    "DRIFTING":   "Phase drift in progress. Coherence is degrading.",
    "UNSTABLE":   "Critical instability. Recommend immediate suppression.",
}

_BRANCH_STATUS_FLAVOUR = {
    "active":     "Branch is active — nutrient flow nominal.",
    "restricted": "Branch is restricted — under observation.",
    "starved":    "Branch is starved — emergency supply route required.",
    "withered":   "Branch has withered — prune from the calculation tree.",
}

_HYDRO_STATE_FLAVOUR = {
    "FLOW":    "Hydrology nominal. Main river channel stable.",
    "DROUGHT": "Hydro drought — supply pressure falling below safe threshold.",
    "FLOOD":   "Hydro overflow — excess pressure building in tributary network.",
}


# ---------------------------------------------------------------------------
# MythicFormatter
# ---------------------------------------------------------------------------

class MythicFormatter:
    """Render oracle results as Academy City-style narrative text.

    Usage::

        fmt  = MythicFormatter()
        text = fmt.format_report(report)
        line = fmt.headline(report)
    """

    SEPARATOR = "─" * 60

    # ------------------------------------------------------------------
    # Full report
    # ------------------------------------------------------------------

    def format_report(self, report: OracleReport) -> str:
        """Render a full oracle report as a narrative text block."""
        lines: List[str] = []

        lines.append(self.SEPARATOR)
        lines.append("TREE DIAGRAM — ORACLE DECLARATION")
        lines.append(self.SEPARATOR)
        lines.append(f"Subject: {report.seed_title}")
        lines.append(f"Run ID:  {report.run_id or '—'}")
        lines.append(f"Mode:    {report.mode.upper()}")
        lines.append("")

        # Background
        if report.core_contradiction:
            lines.append(f"Core Contradiction: {report.core_contradiction}")
        if report.inferred_goal_axis:
            lines.append(f"Goal Axis: {report.inferred_goal_axis}")
        if report.dominant_pressures:
            lines.append(f"Dominant Pressures: {', '.join(report.dominant_pressures)}")
        lines.append("")

        # Best worldline
        lines.append("── Optimal Worldline ──")
        lines.append(f"  Family:      {report.best_family}")
        lines.append(f"  Template:    {report.best_template}")
        lines.append(f"  Score:       {report.best_score:.6f}")
        lines.append(f"  Feasibility: {report.best_feasibility:.4f}")
        lines.append(f"  Stability:   {report.best_stability:.4f}")
        lines.append(f"  Risk:        {report.best_risk:.4f}")
        lines.append("")

        # Governance
        gov_text = _GOVERNANCE_FLAVOUR.get(
            report.governance_state,
            f"Governance state: {report.governance_state}"
        )
        lines.append(f"── Governance: {report.governance_state} ──")
        lines.append(f"  {gov_text}")
        lines.append(f"  Blow-up probability: {report.p_blow:.4f}")
        lines.append("")

        # Hydro
        pb = report.pressure_balance
        hydro_state = "FLOW" if 0.85 <= pb <= 1.15 else ("FLOOD" if pb > 1.15 else "DROUGHT")
        lines.append(f"── Hydro Control: {hydro_state} ──")
        lines.append(f"  {_HYDRO_STATE_FLAVOUR[hydro_state]}")
        lines.append(f"  Pressure balance: {pb:.4f}  |  Active: {report.active_ratio:.2f}  |  Withered: {report.wither_ratio:.2f}")
        lines.append("")

        # Branch histogram
        hist = report.branch_histogram
        lines.append(f"── Branch Distribution (N={report.total_evaluated}) ──")
        for status in ("active", "restricted", "starved", "withered"):
            n = hist.get(status, 0)
            bar = "█" * n
            lines.append(f"  {status:12s} {n:3d}  {bar}")
        lines.append("")

        # Top families
        if report.top_families:
            lines.append("── Top Families ──")
            for i, tf in enumerate(report.top_families[:5]):
                score_key = "final_balanced_score" if "final_balanced_score" in tf else "balanced_score"
                sc = tf.get(score_key, 0.0)
                lines.append(f"  [{i+1}] {tf.get('family','?'):15s}  score={sc:.5f}  status={tf.get('branch_status','?')}")
            lines.append("")

        lines.append(self.SEPARATOR)
        if report.warnings:
            lines.append("WARNINGS:")
            for w in report.warnings:
                lines.append(f"  ⚠  {w}")
            lines.append(self.SEPARATOR)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Single-line headline
    # ------------------------------------------------------------------

    def headline(self, report: OracleReport) -> str:
        """Compact single-line summary."""
        return (
            f"[TREE DIAGRAM] {report.seed_title} | "
            f"{report.best_family}/{report.best_template} "
            f"score={report.best_score:.4f} "
            f"gov={report.governance_state} "
            f"pb={report.pressure_balance:.3f}"
        )

    # ------------------------------------------------------------------
    # Fragment renderers
    # ------------------------------------------------------------------

    def render_governance(self, state: str) -> str:
        return _GOVERNANCE_FLAVOUR.get(state, f"[{state}]")

    def render_branch_status(self, status: str) -> str:
        return _BRANCH_STATUS_FLAVOUR.get(status, f"Status: {status}")

    def render_zone(self, zone: str) -> str:
        return _ZONE_FLAVOUR.get(zone, f"Zone: {zone}")

    def render_hydro(self, hydro_state: str) -> str:
        return _HYDRO_STATE_FLAVOUR.get(hydro_state, f"Hydro: {hydro_state}")
