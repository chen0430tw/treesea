from __future__ import annotations

"""oracle/audit_logger.py

Computation audit logger for Tree Diagram oracle runs.

Architecture position:
  oracle layer — records all significant oracle events (run start/end,
  governance state changes, hydro alerts, branch withering) to an
  in-memory audit trail and supports serialisation to JSON.

The audit log is append-only; entries are never modified after insertion.
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .report_builder import OracleReport


# ---------------------------------------------------------------------------
# Audit entry
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    """A single immutable audit record."""
    timestamp:   float          # Unix epoch seconds
    level:       str            # "INFO" | "WARN" | "ERROR" | "EVENT"
    category:    str            # "run" | "governance" | "hydro" | "branch" | "oracle"
    message:     str
    details:     Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def iso_time(self) -> str:
        import datetime
        return datetime.datetime.utcfromtimestamp(self.timestamp).isoformat() + "Z"


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------

class AuditLogger:
    """Append-only audit logger for oracle computation events.

    Usage::

        logger = AuditLogger()
        logger.log_run_start("my-run-01", seed_title="Urban Resonance")
        logger.log_governance("NORMAL", p_blow=0.42, step=5)
        logger.log_report(report)
        entries = logger.entries
        data    = logger.to_dict()
    """

    def __init__(self, run_id: str = "") -> None:
        self.run_id: str = run_id
        self._entries: List[AuditEntry] = []

    # ------------------------------------------------------------------
    # Core append
    # ------------------------------------------------------------------

    def _append(
        self,
        level: str,
        category: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            timestamp=time.time(),
            level=level,
            category=category,
            message=message,
            details=details or {},
        )
        self._entries.append(entry)
        return entry

    # ------------------------------------------------------------------
    # Convenience log methods
    # ------------------------------------------------------------------

    def info(self, category: str, message: str, **details: Any) -> None:
        self._append("INFO", category, message, details)

    def warn(self, category: str, message: str, **details: Any) -> None:
        self._append("WARN", category, message, details)

    def error(self, category: str, message: str, **details: Any) -> None:
        self._append("ERROR", category, message, details)

    def event(self, category: str, message: str, **details: Any) -> None:
        self._append("EVENT", category, message, details)

    # ------------------------------------------------------------------
    # Structured log methods
    # ------------------------------------------------------------------

    def log_run_start(
        self,
        run_id: str = "",
        seed_title: str = "",
        **kwargs: Any,
    ) -> None:
        self.run_id = run_id
        self._append("INFO", "run", f"Run started: {run_id}",
                     {"seed_title": seed_title, "run_id": run_id, **kwargs})

    def log_run_end(
        self,
        run_id: str = "",
        elapsed_ms: float = 0.0,
        **kwargs: Any,
    ) -> None:
        self._append("INFO", "run", f"Run completed: {run_id}",
                     {"run_id": run_id, "elapsed_ms": elapsed_ms, **kwargs})

    def log_governance(
        self,
        state: str,
        p_blow: float = 0.0,
        step: int = 0,
        reason: str = "",
    ) -> None:
        level = "WARN" if state == "NEGOTIATE" else ("ERROR" if state == "CRACKDOWN" else "INFO")
        self._append(level, "governance",
                     f"Governance → {state}: {reason or 'p_blow=' + f'{p_blow:.4f}'}",
                     {"state": state, "p_blow": p_blow, "step": step, "reason": reason})

    def log_hydro(
        self,
        hydro_state: str,
        pressure_balance: float,
        **kwargs: Any,
    ) -> None:
        level = "WARN" if hydro_state != "FLOW" else "INFO"
        self._append(level, "hydro",
                     f"Hydro: {hydro_state} (pb={pressure_balance:.4f})",
                     {"hydro_state": hydro_state, "pressure_balance": pressure_balance, **kwargs})

    def log_branch_wither(self, family: str, template: str, reason: str = "") -> None:
        self._append("WARN", "branch",
                     f"Branch withered: {family}/{template}",
                     {"family": family, "template": template, "reason": reason})

    def log_report(self, report: OracleReport) -> None:
        level = "ERROR" if not report.is_safe() else "INFO"
        self._append(level, "oracle",
                     f"Oracle report: {report.summary_line()}",
                     {
                         "seed_title":      report.seed_title,
                         "best_family":     report.best_family,
                         "best_score":      report.best_score,
                         "governance":      report.governance_state,
                         "p_blow":          report.p_blow,
                         "pressure_balance": report.pressure_balance,
                     })

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def entries(self) -> List[AuditEntry]:
        return list(self._entries)

    def filter_level(self, level: str) -> List[AuditEntry]:
        return [e for e in self._entries if e.level == level]

    def filter_category(self, category: str) -> List[AuditEntry]:
        return [e for e in self._entries if e.category == category]

    def has_errors(self) -> bool:
        return any(e.level == "ERROR" for e in self._entries)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id":  self.run_id,
            "n_entries": len(self._entries),
            "has_errors": self.has_errors(),
            "entries": [e.to_dict() for e in self._entries],
        }

    def clear(self) -> None:
        self._entries.clear()
