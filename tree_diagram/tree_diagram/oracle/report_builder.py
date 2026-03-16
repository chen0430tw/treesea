from __future__ import annotations

"""oracle/report_builder.py

Structured report builder for oracle output.

Architecture position:
  oracle layer — consumes oracle dicts (from core/oracle_output.py or
  oracle/oracle_output.OracleEnvelope) and produces OracleReport objects
  suitable for serialisation, display, and LLM bridge consumption.

OracleReport is a structured dataclass that normalises the raw oracle dict
into typed, named fields — removing the need for dict key access downstream.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .oracle_output import OracleEnvelope


# ---------------------------------------------------------------------------
# Structured report
# ---------------------------------------------------------------------------

@dataclass
class OracleReport:
    """Normalised, structured output from a Tree Diagram run."""

    # Identity
    seed_title:      str
    run_id:          str
    mode:            str
    version:         str

    # Best result
    best_family:     str
    best_template:   str
    best_params:     Dict[str, Any]
    best_score:      float
    best_feasibility: float
    best_stability:  float
    best_risk:       float

    # Background
    core_contradiction:     str
    inferred_goal_axis:     str
    dominant_pressures:     List[str]
    background_emerged:     Optional[bool]

    # Hydro control
    pressure_balance: float
    active_ratio:     float
    wither_ratio:     float
    hydro_state_raw:  Dict[str, Any]

    # Branch distribution
    branch_histogram: Dict[str, int]
    total_evaluated:  int

    # Governance (from best worldline if available)
    governance_state: str
    p_blow:           float

    # Metadata
    elapsed_ms:      float
    warnings:        List[str]
    top_families:    List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def is_safe(self) -> bool:
        return self.governance_state == "NORMAL" and self.p_blow < 0.60

    def summary_line(self) -> str:
        return (
            f"[{self.mode.upper()}] {self.seed_title} | "
            f"best={self.best_family}/{self.best_template} "
            f"score={self.best_score:.4f} | "
            f"governance={self.governance_state} p_blow={self.p_blow:.4f}"
        )


# ---------------------------------------------------------------------------
# ReportBuilder
# ---------------------------------------------------------------------------

class ReportBuilder:
    """Build an OracleReport from an OracleEnvelope.

    Usage::

        env    = OracleEnvelope(...)
        report = ReportBuilder().build(env)
    """

    def build(self, envelope: OracleEnvelope) -> OracleReport:
        """Extract all fields from the envelope's oracle dict."""
        o   = envelope.oracle
        bw  = o.get("best_worldline", {})
        bwm = bw.get("best_weather_metric", {}) if "best_weather_branch" in o else {}
        hydro = envelope.hydro_state

        # Best worldline fields
        best_family    = bw.get("family",   o.get("best_weather_branch", ""))
        best_template  = bw.get("template", "")
        best_params    = bw.get("params",   {})
        best_score     = float(bw.get("balanced_score",
                                bw.get("final_balanced_score", 0.0)))
        best_feas      = float(bw.get("feasibility",  0.0))
        best_stab      = float(bw.get("stability",    0.0))
        best_risk      = float(bw.get("risk",         0.0))

        # Governance from best worldline or default
        gov_state      = "NORMAL"
        p_blow         = 0.0
        # Abstract oracle doesn't embed governance directly; use hydro as proxy
        pb             = float(hydro.get("pressure_balance", 1.0))
        if pb >= 1.15:
            gov_state = "CRACKDOWN"
            p_blow    = min(1.0, pb - 1.0)
        elif pb < 0.85:
            gov_state = "NEGOTIATE"
            p_blow    = max(0.0, 1.0 - pb)

        # Branch histogram
        hist  = envelope.branch_histogram
        total = o.get("total_evaluated", o.get("total_worldlines_evaluated", sum(hist.values())))

        return OracleReport(
            seed_title=       envelope.seed_title,
            run_id=           envelope.run_id,
            mode=             envelope.mode,
            version=          envelope.version,

            best_family=      best_family,
            best_template=    best_template,
            best_params=      dict(best_params),
            best_score=       best_score,
            best_feasibility= best_feas,
            best_stability=   best_stab,
            best_risk=        best_risk,

            core_contradiction=  o.get("core_contradiction", ""),
            inferred_goal_axis=  o.get("inferred_goal_axis", ""),
            dominant_pressures=  list(o.get("dominant_pressures", [])),
            background_emerged=  o.get("background_naturally_emerged"),

            pressure_balance= pb,
            active_ratio=     float(hydro.get("active_ratio", 0.0)),
            wither_ratio=     float(hydro.get("wither_ratio", 0.0)),
            hydro_state_raw=  dict(hydro),

            branch_histogram= dict(hist),
            total_evaluated=  int(total),

            governance_state= gov_state,
            p_blow=           p_blow,

            elapsed_ms=       envelope.elapsed_ms,
            warnings=         list(envelope.warnings),
            top_families=     list(o.get("top_families", [])),
        )

    def build_from_dict(
        self,
        oracle_dict: Dict[str, Any],
        mode: str = "abstract",
        run_id: str = "",
        elapsed_ms: float = 0.0,
    ) -> OracleReport:
        """Convenience: build from a raw oracle dict."""
        env = OracleEnvelope(
            mode=mode,
            oracle=oracle_dict,
            run_id=run_id,
            elapsed_ms=elapsed_ms,
        )
        return self.build(env)
