"""Abstract protocol for worldline evaluation primitives.

Concrete implementation: tree_diagram.core.worldline_kernel
"""
from __future__ import annotations
from typing import Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class EvaluationResultProtocol(Protocol):
    """Read interface for a single worldline candidate's evaluation output."""

    family:         str
    template:       str
    params:         Dict
    feasibility:    float
    stability:      float
    field_fit:      float
    risk:           float
    balanced_score: float
    nutrient_gain:  float
    branch_status:  str

    # Optional physics-layer fields (set after UTM Hydro pass)
    weather_score:        Optional[float]
    weather_alignment:    Optional[float]
    final_balanced_score: Optional[float]


@runtime_checkable
class WorldlineKernelProtocol(Protocol):
    """Run protocol: accepts a ProblemSeed and returns ranked results."""

    def run_tree_diagram(
        self,
        seed: object,
        *,
        NX: int,
        NY: int,
        steps: int,
        top_k: int,
        device: Optional[str],
    ) -> tuple[List[EvaluationResultProtocol], dict, dict]:
        """
        Returns
        -------
        results : List[EvaluationResultProtocol]
            Ranked candidates (index 0 = best).
        hydro : dict
            UTM hydro state summary.
        oracle : dict
            Oracle summary including background inference.
        """
        ...
