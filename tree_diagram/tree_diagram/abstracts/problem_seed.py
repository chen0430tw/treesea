"""Abstract protocol for ProblemSeed.

Concrete implementation: tree_diagram.core.problem_seed.ProblemSeed
"""
from __future__ import annotations
from typing import Dict, List, Protocol, runtime_checkable


@runtime_checkable
class ProblemSeedProtocol(Protocol):
    """Minimal read interface required by all downstream Tree Diagram components."""

    title: str
    target: str
    constraints: List[str]
    resources: Dict[str, float]
    environment: Dict[str, float]
    subject: Dict[str, float]

    def to_dict(self) -> dict: ...
    def to_json(self, indent: int = 2) -> str: ...
