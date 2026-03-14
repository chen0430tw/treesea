# request.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .types import FrontierCandidate

@dataclass
class BudgetSpec:
    max_candidates: int | None = None
    max_steps: int | None = None
    max_wall_time_sec: float | None = None
    max_memory_mb: int | None = None
    max_gpu_time_sec: float | None = None
    shard_id: str | None = None
    priority: int = 0

@dataclass
class StopPolicy:
    enable_early_stop: bool = True
    convergence_threshold: float | None = None
    plateau_patience: int | None = None
    min_effective_candidates: int | None = None
    stop_on_first_strong_peak: bool = False
    require_stable_topk: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

@dataclass
class CollapseRequest:
    request_id: str
    task_id: str
    profile: str
    candidates: list[FrontierCandidate]
    budget: BudgetSpec
    mapping_policy: str = "default"
    stop_policy: StopPolicy = field(default_factory=StopPolicy)
    issuer: str = "moroz"
    trace_enabled: bool = False
    diagnostics_level: int = 1
    meta: dict[str, Any] = field(default_factory=dict)
