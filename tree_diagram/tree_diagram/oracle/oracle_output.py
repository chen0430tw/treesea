from __future__ import annotations

"""oracle/oracle_output.py

Engineering oracle output layer — re-exports core oracle functions and
adds structured envelope wrapping for downstream consumers.

Architecture position:
  oracle layer — thin wrapper above core/oracle_output.py.
  Provides OracleEnvelope dataclass and convenience constructors for
  the report_builder and mythic_formatter.

The heavy logic lives in core/oracle_output.py; this module only adds
engineering-level formatting and envelope structures.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Re-export core oracle functions so consumers can import from oracle layer
from ..core.oracle_output import (  # noqa: F401
    oracle_summary_abstract,
    oracle_summary_numerical,
    merge_oracle,
)


# ---------------------------------------------------------------------------
# Oracle envelope
# ---------------------------------------------------------------------------

@dataclass
class OracleEnvelope:
    """Top-level container for oracle output with metadata.

    Wraps the raw oracle dict produced by oracle_summary_* functions and
    adds version/mode/run metadata for serialisation and audit.
    """
    mode:       str               # "abstract" | "numerical" | "integrated"
    oracle:     Dict[str, Any]
    version:    str  = "tree-diagram-v1"
    run_id:     str  = ""
    elapsed_ms: float = 0.0
    warnings:   List[str] = field(default_factory=list)

    # Convenience accessors
    @property
    def best_worldline(self) -> Dict:
        return self.oracle.get("best_worldline", {})

    @property
    def hydro_state(self) -> Dict:
        return self.oracle.get("hydro_control_state", self.oracle.get("abstract_hydro", {}))

    @property
    def branch_histogram(self) -> Dict:
        return self.oracle.get("branch_histogram",
               self.oracle.get("abstract_branch_histogram", {}))

    @property
    def seed_title(self) -> str:
        return self.oracle.get("seed_title", "")

    def has_warning(self) -> bool:
        return len(self.warnings) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version":    self.version,
            "mode":       self.mode,
            "run_id":     self.run_id,
            "elapsed_ms": self.elapsed_ms,
            "warnings":   self.warnings,
            "oracle":     self.oracle,
        }


# ---------------------------------------------------------------------------
# Envelope constructors
# ---------------------------------------------------------------------------

def wrap_abstract(
    oracle_dict: Dict[str, Any],
    run_id: str = "",
    elapsed_ms: float = 0.0,
) -> OracleEnvelope:
    """Wrap an abstract oracle dict in an OracleEnvelope."""
    return OracleEnvelope(
        mode="abstract",
        oracle=oracle_dict,
        run_id=run_id,
        elapsed_ms=elapsed_ms,
    )


def wrap_numerical(
    oracle_dict: Dict[str, Any],
    run_id: str = "",
    elapsed_ms: float = 0.0,
) -> OracleEnvelope:
    """Wrap a numerical oracle dict in an OracleEnvelope."""
    return OracleEnvelope(
        mode="numerical",
        oracle=oracle_dict,
        run_id=run_id,
        elapsed_ms=elapsed_ms,
    )


def wrap_integrated(
    oracle_dict: Dict[str, Any],
    run_id: str = "",
    elapsed_ms: float = 0.0,
) -> OracleEnvelope:
    """Wrap a merged/integrated oracle dict in an OracleEnvelope."""
    return OracleEnvelope(
        mode="integrated",
        oracle=oracle_dict,
        run_id=run_id,
        elapsed_ms=elapsed_ms,
    )
