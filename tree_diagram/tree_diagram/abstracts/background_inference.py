"""Abstract protocol for background inference layer.

Concrete implementation: tree_diagram.core.background_inference
"""
from __future__ import annotations
from typing import Dict, List, Protocol, runtime_checkable


@runtime_checkable
class ProblemBackgroundProtocol(Protocol):
    """Read interface for inferred problem background."""

    core_contradiction:  str
    hidden_variables:    Dict[str, float]
    dominant_pressures:  List[str]
    candidate_families:  List[str]
    inferred_goal_axis:  str


@runtime_checkable
class BackgroundInferenceProtocol(Protocol):
    """Callable that maps a seed to its inferred background."""

    def __call__(self, seed: object) -> ProblemBackgroundProtocol: ...
