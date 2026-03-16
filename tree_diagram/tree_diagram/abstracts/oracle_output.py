"""Abstract protocol for oracle output builders.

Concrete implementation: tree_diagram.core.oracle_output
"""
from __future__ import annotations
from typing import Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class OracleOutputProtocol(Protocol):
    """Builds the oracle summary dict from pipeline components."""

    def oracle_summary_abstract(
        self,
        seed: object,
        bg: object,
        field: Dict[str, float],
        top_results: list,
        hydro: dict,
    ) -> dict:
        """Abstract-mode oracle: uses worldline candidates and background inference."""
        ...

    def oracle_summary_numerical(
        self,
        metrics: List[dict],
        hydro: dict,
        best_name: str,
    ) -> dict:
        """Numerical-mode oracle: uses weather branch metrics."""
        ...

    def merge_oracle(
        self,
        abstract_oracle: dict,
        numerical_oracle: dict,
    ) -> dict:
        """Merge abstract and numerical oracle dicts into integrated summary."""
        ...
