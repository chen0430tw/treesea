from __future__ import annotations
from typing import Dict

from .problem_seed import ProblemSeed


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def encode_group_field(seed: ProblemSeed) -> Dict[str, float]:
    env = seed.environment
    res = seed.resources
    sub = seed.subject

    field_noise = env.get("field_noise", 0.0)
    social_pressure = env.get("social_pressure", 0.0)
    regulatory_friction = env.get("regulatory_friction", 0.0)
    network_density = env.get("network_density", 0.0)
    phase_instability = env.get("phase_instability", 0.0)

    budget = res.get("budget", 0.0)
    infrastructure = res.get("infrastructure", 0.0)
    data_coverage = res.get("data_coverage", 0.0)
    population_coupling = res.get("population_coupling", 0.0)

    output_power = sub.get("output_power", 0.0)
    control_precision = sub.get("control_precision", 0.0)
    load_tolerance = sub.get("load_tolerance", 0.0)
    aim_coupling = sub.get("aim_coupling", 0.0)
    stress_level = sub.get("stress_level", 0.0)
    phase_proximity = sub.get("phase_proximity", 0.0)
    marginal_decay = sub.get("marginal_decay", 0.0)
    instability_sensitivity = sub.get("instability_sensitivity", 0.0)

    # field_coherence: how well-aligned the subject is internally
    field_coherence = _clamp(
        0.30 * output_power
        + 0.25 * control_precision
        + 0.20 * aim_coupling
        + 0.15 * (1.0 - stress_level)
        + 0.10 * (1.0 - marginal_decay)
    )

    # network_amplification: density and coupling boost
    network_amplification = _clamp(
        0.40 * network_density
        + 0.35 * population_coupling
        + 0.25 * aim_coupling
    )

    # governance_drag: friction and regulatory burden
    governance_drag = _clamp(
        0.45 * regulatory_friction
        + 0.30 * social_pressure
        + 0.15 * (1.0 - budget)
        + 0.10 * (1.0 - infrastructure)
    )

    # phase_turbulence: instability and noise contributions
    phase_turbulence = _clamp(
        0.35 * phase_instability
        + 0.25 * field_noise
        + 0.20 * phase_proximity
        + 0.20 * instability_sensitivity
    )

    # resource_elasticity: how much slack remains in resources
    resource_elasticity = _clamp(
        0.35 * budget
        + 0.30 * infrastructure
        + 0.20 * data_coverage
        + 0.15 * load_tolerance
    )

    return {
        "field_coherence": field_coherence,
        "network_amplification": network_amplification,
        "governance_drag": governance_drag,
        "phase_turbulence": phase_turbulence,
        "resource_elasticity": resource_elasticity,
    }
