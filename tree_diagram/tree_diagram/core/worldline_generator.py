"""
Worldline Generator — whitepaper Layer 4: UMDST Worldline Kernel entry-point.

Provides the public API for candidate worldline generation and evaluation.
Heavy lifting is in worldline_kernel.py; this module exposes the
whitepaper-named surface so import paths match the spec.
"""
from __future__ import annotations
from typing import List, Tuple

from .problem_seed import ProblemSeed
from .background_inference import ProblemBackground
from .worldline_kernel import (
    EvaluationResult,
    generate_candidates,
    prepare_candidate_arrays,
    unified_rollout,
    score_candidates,
    classify_relative,
    run_tree_diagram,
)


def generate(seed: ProblemSeed, bg: ProblemBackground) -> list:
    """Return the flat list of all plan + weather candidate dicts."""
    return generate_candidates(seed, bg)


def run(
    seed: ProblemSeed,
    bg: ProblemBackground,
    NX: int = 28,
    NY: int = 21,
    steps: int = 20,
    top_k: int = 12,
    dt: float = 45.0,
) -> Tuple[List[EvaluationResult], dict]:
    """
    Full worldline generation + evaluation pipeline.

    Returns (top_results, hydro_control_state).
    """
    return run_tree_diagram(seed, bg, NX=NX, NY=NY, steps=steps, top_k=top_k, dt=dt)


__all__ = [
    "generate",
    "run",
    "generate_candidates",
    "prepare_candidate_arrays",
    "unified_rollout",
    "score_candidates",
    "classify_relative",
    "run_tree_diagram",
    "EvaluationResult",
]
