from __future__ import annotations

"""oracle — output, reporting, and audit layer.

Architecture position:
  Top layer above control.  Consumes oracle dicts produced by
  core/oracle_output.py and generates structured reports, mythic-style
  narrative text, and audit logs.

Public exports:
  OracleOutput (re-export of core oracle functions)
  ReportBuilder, OracleReport
  MythicFormatter
  AuditLogger
"""

from .oracle_output import (
    oracle_summary_abstract,
    oracle_summary_numerical,
    merge_oracle,
    OracleEnvelope,
)
from .report_builder import ReportBuilder, OracleReport
from .mythic_formatter import MythicFormatter
from .audit_logger import AuditLogger, AuditEntry

__all__ = [
    "oracle_summary_abstract",
    "oracle_summary_numerical",
    "merge_oracle",
    "OracleEnvelope",
    "ReportBuilder",
    "OracleReport",
    "MythicFormatter",
    "AuditLogger",
    "AuditEntry",
]
