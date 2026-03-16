from __future__ import annotations

"""llm_bridge/hypothesis_expander.py

Hypothesis expander: generates parameter-space variations from seed hypotheses.

Architecture position:
  llm_bridge layer — third stage.  Takes a small set of LLM-proposed
  "seed hypotheses" (high-level candidate ideas) and expands them into
  a larger grid of concrete candidate dicts for simulation.

The expander applies a configurable expansion strategy:
  - Grid expansion:  enumerate combinations of parameter variations
  - Perturbation:    add ±δ noise around the seed parameters
  - Hybrid:          grid on main axes, perturbation on secondary axes
"""

import itertools
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .candidate_proposer import ProposedCandidate


# ---------------------------------------------------------------------------
# Hypothesis
# ---------------------------------------------------------------------------

@dataclass
class Hypothesis:
    """A single expanded hypothesis candidate."""
    family:     str
    template:   str
    params:     Dict[str, float]
    kind:       str
    source:     str           # "grid" | "perturb" | "seed"
    hypothesis_id: str


# ---------------------------------------------------------------------------
# Expansion strategies
# ---------------------------------------------------------------------------

_GRID_AXES: Dict[str, List[float]] = {
    "n":     [10000.0, 15000.0, 20000.0],
    "rho":   [0.5, 1.0],
    "A":     [0.7, 0.9],
    "sigma": [0.03, 0.07],
}

_WEATHER_GRID_AXES: Dict[str, List[float]] = {
    "Kh":          [240.0, 360.0, 480.0],
    "pg_scale":    [0.90, 1.00, 1.10],
    "humid_couple":[0.90, 1.00, 1.15],
}

_PERTURB_DELTAS: Dict[str, float] = {
    "n":     3000.0,
    "rho":   0.2,
    "A":     0.10,
    "sigma": 0.02,
    "Kh":    60.0,
    "pg_scale": 0.05,
}


# ---------------------------------------------------------------------------
# HypothesisExpander
# ---------------------------------------------------------------------------

class HypothesisExpander:
    """Expand seed hypotheses into concrete candidate parameter sets.

    Usage::

        expander = HypothesisExpander()
        hypotheses = expander.expand(proposed_candidates, max_per_seed=12)
    """

    def __init__(
        self,
        strategy: str = "hybrid",    # "grid" | "perturb" | "hybrid"
        max_per_seed: int = 12,
    ) -> None:
        self.strategy     = strategy
        self.max_per_seed = max_per_seed
        self._counter     = 0

    def expand(
        self,
        seeds: List[ProposedCandidate],
        max_per_seed: Optional[int] = None,
    ) -> List[Hypothesis]:
        """Expand each seed into multiple hypotheses."""
        max_k = max_per_seed if max_per_seed is not None else self.max_per_seed
        result: List[Hypothesis] = []

        for seed in seeds:
            if self.strategy == "grid":
                expanded = self._grid_expand(seed, max_k)
            elif self.strategy == "perturb":
                expanded = self._perturb_expand(seed, max_k)
            else:
                # hybrid: grid for top axes, perturb for rest
                grid_half    = max(1, max_k // 2)
                perturb_half = max_k - grid_half
                expanded = (
                    self._grid_expand(seed, grid_half)
                    + self._perturb_expand(seed, perturb_half)
                )

            # Always include the seed itself
            seed_h = Hypothesis(
                family=seed.family,
                template=seed.template,
                params=dict(seed.params),
                kind=seed.kind,
                source="seed",
                hypothesis_id=self._next_id(seed.family),
            )
            result.append(seed_h)
            result.extend(expanded[:max_k])

        return result

    # ------------------------------------------------------------------
    # Grid expansion
    # ------------------------------------------------------------------

    def _grid_expand(self, seed: ProposedCandidate, max_k: int) -> List[Hypothesis]:
        axes = _WEATHER_GRID_AXES if seed.kind == "weather" else _GRID_AXES
        keys  = list(axes.keys())
        combos = list(itertools.product(*[axes[k] for k in keys]))[:max_k]

        result: List[Hypothesis] = []
        for combo in combos:
            params = dict(seed.params)
            for k, v in zip(keys, combo):
                params[k] = v
            result.append(Hypothesis(
                family=seed.family,
                template=seed.template,
                params=params,
                kind=seed.kind,
                source="grid",
                hypothesis_id=self._next_id(seed.family),
            ))
        return result

    # ------------------------------------------------------------------
    # Perturbation expansion
    # ------------------------------------------------------------------

    def _perturb_expand(self, seed: ProposedCandidate, max_k: int) -> List[Hypothesis]:
        delta_keys = [k for k in _PERTURB_DELTAS if k in seed.params]
        result: List[Hypothesis] = []
        signs = [+1, -1]

        for i in range(max_k):
            params = dict(seed.params)
            # Rotate through delta_keys with alternating sign
            for j, k in enumerate(delta_keys):
                sign = signs[(i + j) % 2]
                delta = _PERTURB_DELTAS[k]
                params[k] = max(0.0, params[k] + sign * delta * (0.5 + 0.5 * (i % 3) / 2.0))

            result.append(Hypothesis(
                family=seed.family,
                template=seed.template,
                params=params,
                kind=seed.kind,
                source="perturb",
                hypothesis_id=self._next_id(seed.family),
            ))

        return result

    # ------------------------------------------------------------------
    # Convert to candidate dicts
    # ------------------------------------------------------------------

    def to_candidate_dicts(self, hypotheses: List[Hypothesis]) -> List[Dict[str, Any]]:
        """Convert Hypothesis list to worldline_kernel candidate format."""
        return [
            {
                "family":   h.family,
                "template": h.template,
                "params":   dict(h.params),
                "kind":     h.kind,
            }
            for h in hypotheses
        ]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _next_id(self, family: str) -> str:
        self._counter += 1
        return f"hyp-{family}-{self._counter:04d}"
