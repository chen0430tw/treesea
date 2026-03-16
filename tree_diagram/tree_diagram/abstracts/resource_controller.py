"""Abstract protocol for the Angio resource controller.

Concrete implementation: tree_diagram.core.resource_controller
"""
from __future__ import annotations
from typing import Dict, List, Optional, Protocol, runtime_checkable


# Canonical branch statuses used throughout the system
BRANCH_STATUSES = ("active", "restricted", "starved", "withered")


@runtime_checkable
class BranchResourceProtocol(Protocol):
    """Per-branch allocation record produced by the resource controller."""

    index:          int
    status:         str
    compute_weight: float
    steps_budget:   int
    nutrient:       float


@runtime_checkable
class FlowReportProtocol(Protocol):
    """Aggregate allocation report returned by allocate()."""

    total_branches:  int
    alive_branches:  int
    pruned_branches: int
    reflow_bonus:    float
    resources:       List[BranchResourceProtocol]

    def alive_indices(self) -> List[int]: ...
    def pruned_indices(self) -> List[int]: ...
    def resource_for(self, index: int) -> Optional[BranchResourceProtocol]: ...


@runtime_checkable
class ResourceControllerProtocol(Protocol):
    """Angio-style resource allocation controller."""

    total_steps:     int
    reflow_fraction: float

    def allocate(self, statuses: List[str]) -> FlowReportProtocol:
        """Assign compute weights and step budgets; apply reflow to active branches."""
        ...
