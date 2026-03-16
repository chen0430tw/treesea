"""Abstract protocol for the balance (hydro) layer.

Concrete implementation: tree_diagram.core.balance_layer
"""
from __future__ import annotations
from typing import Dict, List, Protocol, runtime_checkable


@runtime_checkable
class BalanceLayerProtocol(Protocol):
    """Computes hydro pressure summary from evaluation results or metrics."""

    def hydro_adjust_abstract(
        self,
        results: list,
    ) -> Dict[str, float]:
        """Abstract-mode hydro summary (from EvaluationResult pool)."""
        ...

    def hydro_adjust_numerical(
        self,
        metrics: List[dict],
    ) -> Dict[str, float]:
        """Numerical-mode hydro summary (from weather branch metrics)."""
        ...

    def merge_hydro(
        self,
        abstract_hydro: Dict[str, float],
        numerical_hydro: Dict[str, float],
    ) -> Dict[str, float]:
        """Merge abstract and numerical hydro dicts."""
        ...
