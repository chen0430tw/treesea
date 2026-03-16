from __future__ import annotations

"""core/cbf_balancer.py

CBF (Control Budget Flow) zero-net-drive balancer.

Architecture position:
  core layer — wraps cbf_lite() and evaluate_nrp() from umdst_kernel.
  Provides higher-level balance logic used by vein and control layers.

Responsibilities:
  - CBF allocation computation (cheap / refine / slow buckets)
  - NRP (No-Runaway-Path) governance evaluation
  - Zero-net-drive invariant enforcement: ensure sum(allocation) == 1
  - Aggregate CBF over multiple candidate results
  - Budget clamping and rebalancing under governance state
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .umdst_kernel import (
    Metrics,
    GovernanceState,
    cbf_lite,
    evaluate_nrp,
)


# ---------------------------------------------------------------------------
# Extended allocation dataclass
# ---------------------------------------------------------------------------

@dataclass
class CBFAllocation:
    """Extended CBF allocation with governance context."""
    cheap:          float
    refine:         float
    slow:           float
    governance:     str           # "NORMAL" | "NEGOTIATE" | "CRACKDOWN"
    p_blow:         float
    reason:         str
    net_drive:      float         # should be ~0.0 after normalisation


# ---------------------------------------------------------------------------
# Core balancer
# ---------------------------------------------------------------------------

def compute_cbf_allocation(
    metrics: Metrics,
    constraints: Dict[str, float],
) -> CBFAllocation:
    """Evaluate NRP governance and compute CBF allocation.

    Guarantees the zero-net-drive invariant: cheap + refine + slow == 1.0
    """
    governance = evaluate_nrp(metrics, constraints)
    raw = cbf_lite(metrics, governance)

    cheap  = raw["cheap"]
    refine = raw["refine"]
    slow   = raw["slow"]

    # Normalise to enforce zero-net-drive
    total = cheap + refine + slow
    if total < 1e-12:
        cheap, refine, slow = 1.0, 0.0, 0.0
    else:
        cheap  /= total
        refine /= total
        slow   /= total

    net_drive = cheap + refine + slow - 1.0   # should be ~0

    return CBFAllocation(
        cheap=cheap,
        refine=refine,
        slow=slow,
        governance=governance.state,
        p_blow=governance.p_blow,
        reason=governance.reason,
        net_drive=net_drive,
    )


# ---------------------------------------------------------------------------
# Aggregate CBF over a candidate pool
# ---------------------------------------------------------------------------

def aggregate_cbf(
    metrics_list: List[Metrics],
    constraints: Dict[str, float],
) -> Dict[str, float]:
    """Compute mean CBF allocation across a set of candidates.

    Returns a dict with keys: cheap, refine, slow, mean_p_blow,
    crackdown_ratio, negotiate_ratio, normal_ratio.
    """
    if not metrics_list:
        return {
            "cheap": 1.0, "refine": 0.0, "slow": 0.0,
            "mean_p_blow": 0.0,
            "crackdown_ratio": 0.0,
            "negotiate_ratio": 0.0,
            "normal_ratio": 1.0,
        }

    allocs = [compute_cbf_allocation(m, constraints) for m in metrics_list]
    n = len(allocs)

    mean_cheap  = sum(a.cheap  for a in allocs) / n
    mean_refine = sum(a.refine for a in allocs) / n
    mean_slow   = sum(a.slow   for a in allocs) / n
    mean_p_blow = sum(a.p_blow for a in allocs) / n

    state_counts: Dict[str, int] = {"NORMAL": 0, "NEGOTIATE": 0, "CRACKDOWN": 0}
    for a in allocs:
        state_counts[a.governance] = state_counts.get(a.governance, 0) + 1

    return {
        "cheap":             mean_cheap,
        "refine":            mean_refine,
        "slow":              mean_slow,
        "mean_p_blow":       mean_p_blow,
        "crackdown_ratio":   state_counts.get("CRACKDOWN", 0) / n,
        "negotiate_ratio":   state_counts.get("NEGOTIATE", 0) / n,
        "normal_ratio":      state_counts.get("NORMAL", 0) / n,
    }


# ---------------------------------------------------------------------------
# NRP governance summary
# ---------------------------------------------------------------------------

def evaluate_pool_governance(
    metrics_list: List[Metrics],
    constraints: Dict[str, float],
) -> GovernanceState:
    """Return a single GovernanceState representing the worst-case in the pool.

    Priority: CRACKDOWN > NEGOTIATE > NORMAL
    """
    if not metrics_list:
        return GovernanceState("NORMAL", True, 0.0, "empty pool")

    states = [evaluate_nrp(m, constraints) for m in metrics_list]
    for s in states:
        if s.state == "CRACKDOWN":
            return s
    for s in states:
        if s.state == "NEGOTIATE":
            return s
    return states[0]


# ---------------------------------------------------------------------------
# Budget clamping
# ---------------------------------------------------------------------------

def clamp_allocation(
    alloc: CBFAllocation,
    min_cheap: float = 0.05,
    max_slow: float = 0.80,
) -> CBFAllocation:
    """Apply policy clamping to a CBFAllocation and renormalise."""
    cheap  = max(min_cheap, alloc.cheap)
    slow   = min(max_slow,  alloc.slow)
    refine = max(0.0, 1.0 - cheap - slow)

    total = cheap + refine + slow
    if total < 1e-12:
        cheap, refine, slow = 1.0, 0.0, 0.0
    else:
        cheap  /= total
        refine /= total
        slow   /= total

    return CBFAllocation(
        cheap=cheap,
        refine=refine,
        slow=slow,
        governance=alloc.governance,
        p_blow=alloc.p_blow,
        reason=alloc.reason,
        net_drive=cheap + refine + slow - 1.0,
    )


# ---------------------------------------------------------------------------
# CBF pressure signal
# ---------------------------------------------------------------------------

def cbf_pressure(alloc: CBFAllocation) -> float:
    """Compute a scalar CBF pressure signal in [0, 1].

    High slow weight + high p_blow → pressure close to 1.
    Used by control layer for hydro stabilisation decisions.
    """
    return min(1.0, 0.55 * alloc.slow + 0.45 * alloc.p_blow)


# ---------------------------------------------------------------------------
# High-level façade class (used by tests and control layer)
# ---------------------------------------------------------------------------

class CBFBalancer:
    """Façade: derive CBF channel allocations from a ProblemSeed + ProblemBackground.

    Wraps compute_cbf_allocation() with sensible defaults derived from the
    seed's governance/resource fields.
    """

    def __init__(self, seed=None, background=None) -> None:
        self._seed = seed
        self._bg   = background

    def allocate(self, top_results=None) -> CBFAllocation:
        """Compute CBF allocation from seed fields and optional top results."""
        if top_results:
            return compute_cbf_allocation(top_results)
        # Fallback: synthesise a minimal EvaluationResult-like proxy from seed
        if self._seed is not None:
            subj = self._seed.subject
            phase  = float(subj.get("phase_proximity", 0.7))
            stress = float(subj.get("stress_level", 0.2))
            instab = float(subj.get("instability_sensitivity", 0.28))
            # create a minimal proxy list
            class _Proxy:
                def __init__(self):
                    self.balanced_score = phase
                    self.feasibility    = max(0.0, 1.0 - stress)
                    self.stability      = max(0.0, 1.0 - instab)
                    self.risk           = (stress + instab) / 2.0
                    self.branch_status  = "active"
            return compute_cbf_allocation([_Proxy()])
        return CBFAllocation(cheap=0.34, refine=0.33, slow=0.33, p_blow=0.5, governance="NORMAL")
