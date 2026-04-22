from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

from .problem_seed import ProblemSeed


@dataclass
class ProblemBackground:
    core_contradiction: str
    hidden_variables: Dict[str, float]
    dominant_pressures: List[str]
    candidate_families: List[str]
    inferred_goal_axis: str


def infer_problem_background(seed: ProblemSeed) -> ProblemBackground:
    env = seed.environment
    res = seed.resources
    sub = seed.subject

    # Build hidden variables from environment and resource thresholds
    hidden_variables: Dict[str, float] = {}

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

    hidden_variables["latent_stress"] = (
        0.4 * social_pressure + 0.3 * phase_instability + 0.3 * stress_level
    )
    hidden_variables["resource_ceiling"] = (
        0.35 * budget + 0.35 * infrastructure + 0.30 * data_coverage
    )
    hidden_variables["coupling_depth"] = (
        0.5 * population_coupling + 0.3 * network_density + 0.2 * aim_coupling
    )
    hidden_variables["phase_edge_proximity"] = (
        0.5 * phase_instability + 0.3 * phase_proximity + 0.2 * field_noise
    )
    hidden_variables["decay_risk"] = (
        0.5 * marginal_decay + 0.3 * instability_sensitivity + 0.2 * (1.0 - load_tolerance)
    )
    hidden_variables["control_capacity"] = (
        0.5 * control_precision + 0.3 * output_power + 0.2 * (1.0 - regulatory_friction)
    )

    # Determine dominant pressures based on thresholds
    dominant_pressures: List[str] = []
    if social_pressure > 0.5:
        dominant_pressures.append("social_pressure_dominant")
    if regulatory_friction > 0.4:
        dominant_pressures.append("regulatory_friction_present")
    if field_noise > 0.3:
        dominant_pressures.append("field_noise_elevated")
    if phase_instability > 0.35:
        dominant_pressures.append("phase_instability_moderate")
    if hidden_variables["resource_ceiling"] < 0.6:
        dominant_pressures.append("resource_constrained")
    if hidden_variables["coupling_depth"] > 0.7:
        dominant_pressures.append("high_coupling_amplification")
    if hidden_variables["decay_risk"] > 0.2:
        dominant_pressures.append("decay_risk_nonzero")
    if not dominant_pressures:
        dominant_pressures.append("no_dominant_pressure")

    # Candidate families
    #
    # Keep the original governance / subject families, but also expose the
    # weather-oriented variants defined in worldline_kernel.  The Taipei weather
    # forecast stack consumes the same ProblemBackground contract; if these
    # families are omitted here, the forecast candidate pool can never explore
    # stronger pressure-gradient or humidity-biased regimes and every survivor
    # ends up with the same underpowered wind amplitude.
    candidate_families = [
        "batch",
        "strong_pg",
        "balanced",
        "high_mix",
        "network",
        "humid_bias",
        "phase",
        "electrical",
        "terrain_lock",
        "ascetic",
        "weak_mix",
        "hybrid",
        "composite",
    ]

    # Core contradiction
    if hidden_variables["phase_edge_proximity"] > 0.5:
        core_contradiction = (
            "High phase proximity combined with resource constraints creates "
            "tension between stability requirements and upgrade ambition."
        )
    elif hidden_variables["coupling_depth"] > 0.7 and hidden_variables["resource_ceiling"] < 0.6:
        core_contradiction = (
            "Strong network coupling amplifies both opportunity and risk "
            "while resource ceiling limits achievable trajectory."
        )
    else:
        core_contradiction = (
            "Governance drag and field noise resist the transition "
            "while subject output power and coupling create upgrade pressure."
        )

    # Inferred goal axis
    if hidden_variables["control_capacity"] > 0.7:
        inferred_goal_axis = "precision_upgrade_via_control_dominance"
    elif hidden_variables["coupling_depth"] > 0.6:
        inferred_goal_axis = "network_amplified_resonance_escalation"
    elif hidden_variables["phase_edge_proximity"] > 0.45:
        inferred_goal_axis = "phase_boundary_managed_transition"
    else:
        inferred_goal_axis = "balanced_resource_stability_optimization"

    return ProblemBackground(
        core_contradiction=core_contradiction,
        hidden_variables=hidden_variables,
        dominant_pressures=dominant_pressures,
        candidate_families=candidate_families,
        inferred_goal_axis=inferred_goal_axis,
    )
