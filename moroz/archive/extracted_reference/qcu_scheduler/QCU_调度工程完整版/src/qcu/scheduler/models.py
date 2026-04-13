from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

RunBackend = Literal["local", "multiprocess", "slurm"]

@dataclass
class Candidate:
    candidate_id: str
    payload: dict[str, Any]
    priority: float = 0.0
    resource_weight: float = 1.0
    oracle_hint: dict[str, Any] = field(default_factory=dict)

@dataclass
class CandidateCluster:
    cluster_id: str
    candidates: list[Candidate]
    cluster_priority: float = 0.0
    budget_hint: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class CollapseRequest:
    request_id: str
    qcu_session_id: str
    clusters: list[CandidateCluster]
    qcu_profile: str = "default"
    budget: dict[str, Any] = field(default_factory=dict)
    termination_policy: dict[str, Any] = field(default_factory=dict)
    output_policy: dict[str, Any] = field(default_factory=dict)
    backend: RunBackend = "local"
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ClusterExecutionPlan:
    cluster_id: str
    candidate_ids: list[str]
    step_budget: int
    readout_interval: int
    checkpoint_interval: int
    backend: RunBackend
    priority: float
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class CollapsePlan:
    request_id: str
    qcu_session_id: str
    cluster_plans: list[ClusterExecutionPlan]
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class FeedbackAction:
    tighten: bool = False
    relax: bool = False
    suppress_evict: bool = False
    gate_level: int = 0
    quality_alarm: bool = False
    trace: dict[str, Any] = field(default_factory=dict)
