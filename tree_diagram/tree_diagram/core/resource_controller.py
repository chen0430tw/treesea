from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Default compute weight per branch status
_STATUS_WEIGHTS: Dict[str, float] = {
    "active":     1.00,
    "restricted": 0.60,
    "starved":    0.20,
    "withered":   0.00,
}


@dataclass
class BranchResource:
    index:          int
    status:         str
    compute_weight: float   # fraction of full compute budget after reflow
    steps_budget:   int     # step count allocated in refinement phase
    nutrient:       float   # accumulated nutrient level


@dataclass
class AngioFlowReport:
    total_branches:  int
    alive_branches:  int
    pruned_branches: int
    reflow_bonus:    float          # per-active-branch bonus from reflow
    resources:       List[BranchResource] = field(default_factory=list)

    def alive_indices(self) -> List[int]:
        """Indices of branches that survived (compute_weight > 0)."""
        return [r.index for r in self.resources if r.compute_weight > 0]

    def pruned_indices(self) -> List[int]:
        """Indices of branches that were pruned (compute_weight == 0)."""
        return [r.index for r in self.resources if r.compute_weight == 0]

    def resource_for(self, index: int) -> Optional[BranchResource]:
        for r in self.resources:
            if r.index == index:
                return r
        return None


class AngioResourceController:
    """Angio-style resource controller.

    Mirrors the biological analogy from the whitepaper:
    - Active branches receive full nutrient flow.
    - Restricted branches receive partial flow (refine channel).
    - Starved branches receive minimal flow (slow channel).
    - Withered branches are cut off and pruned.

    Reflow: compute budget saved from withered/starved branches is
    redistributed (partially) back to active branches, so the main
    world-line gets more refinement steps.
    """

    def __init__(
        self,
        total_steps: int,
        status_weights: Optional[Dict[str, float]] = None,
        reflow_fraction: float = 0.50,
    ):
        self.total_steps     = total_steps
        self.weights         = status_weights or _STATUS_WEIGHTS
        self.reflow_fraction = reflow_fraction

    def allocate(self, statuses: List[str]) -> AngioFlowReport:
        """Assign compute weights and step budgets; apply reflow to active branches."""
        resources: List[BranchResource] = []
        saved = 0.0

        for i, status in enumerate(statuses):
            w     = self.weights.get(status, 0.0)
            steps = max(0, round(self.total_steps * w))
            resources.append(BranchResource(
                index=i, status=status,
                compute_weight=w, steps_budget=steps, nutrient=w,
            ))
            saved += 1.0 - w

        # Reflow: distribute a fraction of saved compute to active branches
        active = [r for r in resources if r.status == "active"]
        reflow_bonus = 0.0
        if active and saved > 0.0:
            bonus        = saved * self.reflow_fraction / len(active)
            reflow_bonus = bonus
            for r in active:
                r.compute_weight = min(1.5, r.compute_weight + bonus)
                r.steps_budget   = min(
                    int(self.total_steps * 1.5),
                    r.steps_budget + max(1, round(self.total_steps * bonus)),
                )
                r.nutrient += bonus

        alive  = sum(1 for r in resources if r.compute_weight > 0)
        pruned = sum(1 for r in resources if r.compute_weight == 0)
        return AngioFlowReport(
            total_branches=len(resources),
            alive_branches=alive,
            pruned_branches=pruned,
            reflow_bonus=reflow_bonus,
            resources=resources,
        )


@dataclass
class ResourceBudget:
    max_candidates: int = 300
    top_k:          int = 12
    max_steps:      int = 240
    n_workers:      int = 1
