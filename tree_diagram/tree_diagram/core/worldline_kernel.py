from __future__ import annotations
import itertools
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

from .problem_seed import ProblemSeed
from .background_inference import ProblemBackground


@dataclass
class CandidateWorldline:
    family: str
    template: str
    params: Dict[str, float]
    description: str


@dataclass
class EvaluationResult:
    family: str
    template: str
    params: Dict[str, float]
    feasibility: float
    stability: float
    field_fit: float
    risk: float
    balanced_score: float
    nutrient_gain: float
    branch_status: str


# ---------------------------------------------------------------------------
# Family-specific parameter space
# ---------------------------------------------------------------------------

# City-scale anchor points for large-n batch family.
# These represent realistic population/iteration scales for Academy City
# (2.3M esper network; experiments in the thousands to hundreds of thousands).
_BATCH_LARGE_N_ANCHORS: list = [
    500, 1000, 2000, 5000, 10000, 15000, 20000, 30000, 50000, 100000
]

_FAMILY_PARAMS: Dict[str, Dict[str, list]] = {
    "batch": {
        "n":    [3, 5, 7],
        "rho":  [0.4, 0.6, 0.8],
        "A":    [0.5, 0.7],
        "sigma":[0.2, 0.4],
    },
    "network": {
        "n":    [4, 6, 8],
        "rho":  [0.5, 0.7, 0.9],
        "A":    [0.6, 0.8],
        "sigma":[0.1, 0.3],
    },
    "phase": {
        "n":    [2, 4, 6],
        "rho":  [0.3, 0.5, 0.7],
        "A":    [0.4, 0.6],
        "sigma":[0.3, 0.5],
    },
    "electrical": {
        "n":    [5, 7, 9],
        "rho":  [0.6, 0.8, 1.0],
        "A":    [0.7, 0.9],
        "sigma":[0.1, 0.2],
    },
    "ascetic": {
        "n":    [1, 2, 3],
        "rho":  [0.2, 0.3, 0.4],
        "A":    [0.3, 0.4],
        "sigma":[0.5, 0.7],
    },
    "hybrid": {
        "n":    [4, 6, 8],
        "rho":  [0.4, 0.6, 0.8],
        "A":    [0.5, 0.7],
        "sigma":[0.2, 0.4],
    },
    "composite": {
        "n":    [6, 8, 10],
        "rho":  [0.5, 0.7, 0.9],
        "A":    [0.6, 0.8],
        "sigma":[0.1, 0.3],
    },
}


def _batch_n_opt(seed: ProblemSeed) -> float:
    """Optimal iteration count for large-n batch family via resonance locking.

    Physical model: to lock a population-coupled resonance across a low-noise
    city field, the minimum viable iteration count satisfies

        n_opt = (C × ρ_net × α_aim) / (δ² × (1 − ρ_pop) × η_noise)

    where:
        C        = data_coverage  — required pattern-space completeness
        ρ_net    = network_density — ambient network connectivity
        α_aim    = aim_coupling   — precision of per-iteration targeting
        δ        = marginal_decay — per-iteration marginal gain rate
        ρ_pop    = population_coupling — group field coherence (→1 ⇒ more iters)
        η_noise  = field_noise    — environment precision (low noise ⇒ fine-grained
                                    patterns ⇒ more samples needed for full coverage)
    """
    dc = seed.resources.get("data_coverage", 0.5)
    pc = seed.resources.get("population_coupling", 0.5)
    nd = seed.environment.get("network_density", 0.5)
    md = seed.subject.get("marginal_decay", 0.1)
    fn = seed.environment.get("field_noise", 0.3)
    ac = seed.subject.get("aim_coupling", 0.9)
    denom = (md ** 2) * max(1.0 - pc, 1e-3) * max(fn, 1e-3)
    return (dc * nd * ac) / max(denom, 1e-9)


def _batch_large_n_fp(seed: ProblemSeed) -> Dict[str, list]:
    """Parameter grid for batch family in the large-n (high-coupling) regime.

    Entered when population_coupling >= 0.90 and data_coverage >= 0.85.
    Candidate n values are drawn from city-scale anchors within
    [n_opt × 0.25, n_opt × 4].  At this scale the batch route can sustain
    high rho, high A, and low sigma (industrialised clone production).
    """
    n_opt = _batch_n_opt(seed)
    lo, hi = n_opt * 0.25, n_opt * 4.0
    candidates = sorted(n for n in _BATCH_LARGE_N_ANCHORS if lo <= n <= hi)
    if not candidates:
        candidates = [max(1, int(round(n_opt)))]
    return {
        "n":     candidates,
        "rho":   [0.8, 0.9, 1.0],
        "A":     [0.7, 0.8, 0.9],
        "sigma": [0.1, 0.15],
    }


def generate_worldlines(
    seed: ProblemSeed,
    bg: ProblemBackground,
) -> List[CandidateWorldline]:
    worldlines: List[CandidateWorldline] = []
    pc = seed.resources.get("population_coupling", 0.5)
    dc = seed.resources.get("data_coverage", 0.5)
    for family in bg.candidate_families:
        if family == "batch" and pc >= 0.90 and dc >= 0.85:
            fp = _batch_large_n_fp(seed)
        else:
            fp = _FAMILY_PARAMS.get(family, _FAMILY_PARAMS["batch"])
        keys = list(fp.keys())
        values = [fp[k] for k in keys]
        for combo in itertools.product(*values):
            params = dict(zip(keys, combo))
            template = f"{family}_n{params['n']}_rho{params['rho']}"
            description = (
                f"{family.capitalize()} worldline with "
                + ", ".join(f"{k}={v}" for k, v in params.items())
            )
            worldlines.append(
                CandidateWorldline(
                    family=family,
                    template=template,
                    params=params,
                    description=description,
                )
            )
    return worldlines


# ---------------------------------------------------------------------------
# Family lock sigmoid
# ---------------------------------------------------------------------------

_FAMILY_NC: Dict[str, float] = {
    "batch":      5.0,
    "network":    6.0,
    "phase":      4.0,
    "electrical": 7.0,
    "ascetic":    2.0,
    "hybrid":     5.5,
    "composite":  8.0,
}

_FAMILY_SHARP: Dict[str, float] = {
    "batch":      1.5,
    "network":    1.2,
    "phase":      1.8,
    "electrical": 1.0,
    "ascetic":    2.5,
    "hybrid":     1.4,
    "composite":  0.9,
}


def family_lock(family: str, n: float) -> float:
    nc = _FAMILY_NC.get(family, 5.0)
    sharp = _FAMILY_SHARP.get(family, 1.5)
    return 1.0 / (1.0 + math.exp(-(n - nc) / sharp))


# ---------------------------------------------------------------------------
# Evaluate a single worldline
# ---------------------------------------------------------------------------

def evaluate_worldline(
    seed: ProblemSeed,
    field: Dict[str, float],
    w: CandidateWorldline,
) -> EvaluationResult:
    n = w.params.get("n", 1.0)
    rho = w.params.get("rho", 0.5)
    A = w.params.get("A", 0.5)
    sigma = w.params.get("sigma", 0.3)

    fc = field.get("field_coherence", 0.5)
    na = field.get("network_amplification", 0.5)
    gd = field.get("governance_drag", 0.5)
    pt = field.get("phase_turbulence", 0.5)
    re = field.get("resource_elasticity", 0.5)

    lock = family_lock(w.family, n)

    # Feasibility: resource + amplification + lock alignment
    feasibility = (
        0.30 * re
        + 0.25 * (1.0 - gd)
        + 0.20 * na * rho
        + 0.15 * lock
        + 0.10 * A
    )
    feasibility = max(0.0, min(1.0, feasibility))

    # Stability: coherence + low turbulence + low sigma
    stability = (
        0.35 * fc
        + 0.25 * (1.0 - pt)
        + 0.20 * (1.0 - sigma)
        + 0.20 * (1.0 - gd * 0.5)
    )
    stability = max(0.0, min(1.0, stability))

    # Field fit: how well params match field conditions
    field_fit = (
        0.30 * fc * A
        + 0.25 * na * rho
        + 0.25 * (1.0 - pt) * (1.0 - sigma)
        + 0.20 * re * lock
    )
    field_fit = max(0.0, min(1.0, field_fit))

    # Coverage depth bonus: resonance alignment for large-n batch family.
    # Rewards n values near the seed-derived optimal iteration count n_opt.
    # Gaussian in log-n space (log_sigma=0.8 ≈ ±2× factor tolerance).
    pc_val = seed.resources.get("population_coupling", 0.0)
    dc_val = seed.resources.get("data_coverage", 0.0)
    if w.family == "batch" and pc_val >= 0.90 and dc_val >= 0.85:
        n_opt_v = _batch_n_opt(seed)
        if n_opt_v > 50:
            log_ratio = math.log(max(n, 1.0) / n_opt_v)
            coverage_depth = math.exp(-0.5 * (log_ratio / 0.8) ** 2)
            field_fit = min(1.0, field_fit + 0.10 * coverage_depth)

    # Risk: high turbulence, low stability, high sigma, low resources
    risk = (
        0.30 * pt
        + 0.25 * sigma
        + 0.25 * gd
        + 0.20 * (1.0 - re)
    )
    risk = max(0.0, min(1.0, risk))

    # Raw score
    raw = 0.30 * feasibility + 0.30 * stability + 0.25 * field_fit - 0.15 * risk

    # Penalize by spread (using population standard deviation of the three positive metrics)
    vals = [feasibility, stability, field_fit]
    mean_v = sum(vals) / 3.0
    pstdev = math.sqrt(sum((v - mean_v) ** 2 for v in vals) / 3.0)
    balanced_score = raw - 0.25 * pstdev

    # Nutrient gain: route bonus based on family and field
    nutrient_gain = _compute_nutrient_gain(w.family, n, rho, field)

    # Branch status based on thresholds
    branch_status = _classify_branch_status(balanced_score, risk, feasibility)

    return EvaluationResult(
        family=w.family,
        template=w.template,
        params=w.params,
        feasibility=feasibility,
        stability=stability,
        field_fit=field_fit,
        risk=risk,
        balanced_score=balanced_score,
        nutrient_gain=nutrient_gain,
        branch_status=branch_status,
    )


def _compute_nutrient_gain(
    family: str,
    n: float,
    rho: float,
    field: Dict[str, float],
) -> float:
    na = field.get("network_amplification", 0.5)
    re = field.get("resource_elasticity", 0.5)
    fc = field.get("field_coherence", 0.5)

    base = rho * 0.5 + re * 0.3 + fc * 0.2

    route_bonus: Dict[str, float] = {
        "network":    0.12 * na,
        "composite":  0.10 * na * rho,
        "hybrid":     0.08 * (na + re) * 0.5,
        "electrical": 0.09 * rho,
        "batch":      0.06 * re,
        "phase":      0.05 * (1.0 - field.get("phase_turbulence", 0.5)),
        "ascetic":    0.04 * (1.0 - field.get("governance_drag", 0.5)),
    }
    bonus = route_bonus.get(family, 0.05)
    return max(0.0, min(1.0, base + bonus))


def _classify_branch_status(
    balanced_score: float,
    risk: float,
    feasibility: float,
) -> str:
    if balanced_score >= 0.45 and risk <= 0.45:
        return "active"
    elif balanced_score >= 0.30 and risk <= 0.60:
        return "restricted"
    elif balanced_score >= 0.15 or feasibility >= 0.25:
        return "starved"
    else:
        return "withered"
