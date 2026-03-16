from __future__ import annotations

"""vein/vein_backbone.py

Low-rank main-branch extractor for top-k evaluation results.

Architecture position:
  vein layer — processes output of worldline_kernel.run_tree_diagram()
  and branch_ecology.compress_to_main_branches().  Sits between the
  numerical core and the control/oracle layers.

Responsibilities:
  - Low-rank approximation: collapse redundant parameter variations into
    a compact set of representative branches
  - Per-family branch selection with diversity preservation
  - Backbone score computation (weighted composite of core metrics)
  - Adjacency structure for the vein graph
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..core.worldline_kernel import EvaluationResult
from ..core.branch_ecology import compress_to_main_branches


# ---------------------------------------------------------------------------
# Backbone node
# ---------------------------------------------------------------------------

@dataclass
class BackboneNode:
    """A representative branch in the vein backbone."""
    family:          str
    template:        str
    params:          Dict
    backbone_score:  float     # composite low-rank score
    feasibility:     float
    stability:       float
    risk:            float
    nutrient_gain:   float
    branch_status:   str
    rank:            int       # position in backbone (0 = best)


# ---------------------------------------------------------------------------
# Low-rank scoring
# ---------------------------------------------------------------------------

def _backbone_score(r: EvaluationResult) -> float:
    """Compute a low-rank backbone score from an EvaluationResult.

    Weights emphasise feasibility and stability over raw balanced_score
    to retain structurally sound branches even with moderate scores.
    """
    base = (
        0.35 * r.feasibility
        + 0.30 * r.stability
        + 0.20 * r.nutrient_gain
        - 0.25 * r.risk
        + 0.10 * r.balanced_score
    )
    # Boost active branches
    if r.branch_status == "active":
        base += 0.05
    elif r.branch_status == "withered":
        base -= 0.10
    return base


# ---------------------------------------------------------------------------
# Family diversity selection
# ---------------------------------------------------------------------------

def _select_diverse(
    results: List[EvaluationResult],
    top_k: int,
    max_per_family: int = 2,
) -> List[EvaluationResult]:
    """Select top_k results with at most max_per_family per family."""
    family_count: Dict[str, int] = {}
    selected: List[EvaluationResult] = []
    sorted_r = sorted(results, key=lambda r: r.balanced_score, reverse=True)

    for r in sorted_r:
        if len(selected) >= top_k:
            break
        cnt = family_count.get(r.family, 0)
        if cnt < max_per_family:
            selected.append(r)
            family_count[r.family] = cnt + 1

    return selected


# ---------------------------------------------------------------------------
# VeinBackbone
# ---------------------------------------------------------------------------

class VeinBackbone:
    """Low-rank backbone of the candidate vein structure.

    Usage::

        backbone = VeinBackbone.from_results(top_results, top_k=8)
        nodes = backbone.nodes
        best  = backbone.best_node()
    """

    def __init__(self, nodes: List[BackboneNode]) -> None:
        self.nodes = nodes

    @classmethod
    def from_results(
        cls,
        results: List[EvaluationResult],
        top_k: int = 8,
        max_per_family: int = 2,
    ) -> "VeinBackbone":
        """Construct backbone from a list of EvaluationResults."""
        compressed = compress_to_main_branches(results, top_k=top_k * 2)
        diverse    = _select_diverse(compressed, top_k, max_per_family)

        nodes: List[BackboneNode] = []
        for rank, r in enumerate(diverse):
            nodes.append(BackboneNode(
                family=r.family,
                template=r.template,
                params=dict(r.params),
                backbone_score=_backbone_score(r),
                feasibility=r.feasibility,
                stability=r.stability,
                risk=r.risk,
                nutrient_gain=r.nutrient_gain,
                branch_status=r.branch_status,
                rank=rank,
            ))

        # Re-sort by backbone_score
        nodes.sort(key=lambda n: n.backbone_score, reverse=True)
        for i, n in enumerate(nodes):
            n.rank = i

        return cls(nodes)

    def best_node(self) -> Optional[BackboneNode]:
        return self.nodes[0] if self.nodes else None

    def families_present(self) -> List[str]:
        seen: List[str] = []
        for n in self.nodes:
            if n.family not in seen:
                seen.append(n.family)
        return seen

    def mean_stability(self) -> float:
        if not self.nodes:
            return 0.0
        return sum(n.stability for n in self.nodes) / len(self.nodes)

    def mean_risk(self) -> float:
        if not self.nodes:
            return 0.0
        return sum(n.risk for n in self.nodes) / len(self.nodes)

    def adjacency(self) -> List[Tuple[int, int, float]]:
        """Return a simple adjacency list: edges between consecutive backbone nodes.

        Edge weight is the cosine similarity of [feasibility, stability, nutrient_gain].
        """
        edges: List[Tuple[int, int, float]] = []
        for i in range(len(self.nodes) - 1):
            a = self.nodes[i]
            b = self.nodes[i + 1]
            va = [a.feasibility, a.stability, a.nutrient_gain]
            vb = [b.feasibility, b.stability, b.nutrient_gain]
            dot = sum(x * y for x, y in zip(va, vb))
            na  = math.sqrt(sum(x * x for x in va)) + 1e-12
            nb  = math.sqrt(sum(x * x for x in vb)) + 1e-12
            edges.append((i, i + 1, dot / (na * nb)))
        return edges

    def to_dict(self) -> dict:
        return {
            "nodes": [
                {
                    "rank":           n.rank,
                    "family":         n.family,
                    "template":       n.template,
                    "backbone_score": round(n.backbone_score, 6),
                    "feasibility":    round(n.feasibility, 4),
                    "stability":      round(n.stability, 4),
                    "risk":           round(n.risk, 4),
                    "nutrient_gain":  round(n.nutrient_gain, 4),
                    "branch_status":  n.branch_status,
                }
                for n in self.nodes
            ],
            "mean_stability": round(self.mean_stability(), 4),
            "mean_risk":      round(self.mean_risk(), 4),
            "families":       self.families_present(),
        }


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def extract_main_branches(
    results: List[EvaluationResult],
    top_k: int = 8,
) -> VeinBackbone:
    """Shortcut: build a VeinBackbone from evaluation results."""
    return VeinBackbone.from_results(results, top_k=top_k)
