# result.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal
from .types import CollapseCandidate

CollapseStatus = Literal["queued", "running", "completed", "stopped", "failed"]
StopReason = Literal["budget_exhausted", "early_stop", "converged", "manual_stop", "runtime_error", "unknown"]

@dataclass
class RuntimeStats:
    elapsed_sec: float = 0.0
    steps: int = 0
    peak_memory_mb: float | None = None
    avg_resource_load: float | None = None
    effective_candidates: int = 0
    converged: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)

@dataclass
class CollapseResult:
    request_id: str
    status: CollapseStatus
    ranked: list[CollapseCandidate]
    runtime_stats: RuntimeStats
    stop_reason: StopReason = "unknown"
    diagnostics: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
