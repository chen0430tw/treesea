"""Abstract protocol for branch ecology operations.

Concrete implementation: tree_diagram.core.branch_ecology
"""
from __future__ import annotations
from typing import Dict, List, Protocol, Tuple, runtime_checkable


@runtime_checkable
class BranchEcologyProtocol(Protocol):
    """Operations on the pool of evaluated worldline candidates."""

    def compress_to_main_branches(
        self,
        results: list,
        top_k: int = 12,
    ) -> list:
        """Deduplicate by (family, n) and return top-k survivors."""
        ...

    def prune_withered(
        self,
        results: list,
    ) -> Tuple[list, int]:
        """Remove withered branches; return (survivors, pruned_count)."""
        ...

    def reflow_summary(self, results: list) -> Dict[str, float]:
        """Fractional resource distribution across branch statuses."""
        ...

    def branch_status_histogram(self, results: list) -> Dict[str, int]:
        """Count of each branch status in the pool."""
        ...
