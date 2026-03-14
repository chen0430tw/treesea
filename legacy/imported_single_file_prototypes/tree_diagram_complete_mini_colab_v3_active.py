# tree_diagram_complete_mini_colab_v3_active.py

# Tree Diagram Complete Mini - Colab Version
# Colab-friendly single-file prototype
# By: OpenAI based on user's Tree Diagram / UMDST / VFT / H-UTM direction

from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List
import csv, itertools, json, math, statistics

# =========================
# 0. Data structures
# =========================

@dataclass
class ProblemSeed:
    title: str
    target: str
    constraints: List[str]
    resources: Dict[str, float]
    environment: Dict[str, float]
    subject: Dict[str, float]

@dataclass
class ProblemBackground:
    core_contradiction: str
    hidden_variables: List[str]
    dominant_pressures: List[str]
    candidate_families: List[str]
    inferred_goal_axis: List[str]

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


# =========================
# 1. PBL reverse-route seed
# =========================

def default_seed() -> ProblemSeed:
    return ProblemSeed(
        title="Urban Resonance Upgrade Program",
        target=(
            "Find the most viable route to upgrade a city-scale resonance system "
            "from Level-5-equivalent stability to Level-6-equivalent stability."
        ),
        constraints=[
            "must remain under city-level safety threshold",
            "must avoid irreversible collapse of field stability",
            "must be scalable under limited infrastructure budget",
            "must remain reproducible across repeated trials",
        ],
        resources={
            "budget": 0.62,
            "infrastructure": 0.71,
            "data_coverage": 0.66,
            "population_coupling": 0.83,
        },
        environment={
            "field_noise": 0.34,
            "social_pressure": 0.58,
            "regulatory_friction": 0.47,
            "network_density": 0.76,
            "phase_instability": 0.41,
        },
        subject={
            "output_power": 0.93,
            "control_precision": 0.88,
            "load_tolerance": 0.61,
            "aim_coupling": 0.97,
            "stress_level": 0.22,
            "phase_proximity": 0.69,
            "marginal_decay": 0.11,
            "instability_sensitivity": 0.28,
        }
    )


# =========================
# 2. IPL / background emergence
# =========================

def infer_problem_background(seed: ProblemSeed) -> ProblemBackground:
    env = seed.environment
    res = seed.resources

    hidden = []
    if env["phase_instability"] > 0.35:
        hidden.append("phase leakage between local resonance layer and city-scale carrier field")
    if res["population_coupling"] > 0.75:
        hidden.append("group-field amplification may dominate single-subject optimization")
    if env["regulatory_friction"] > 0.40:
        hidden.append("high-performing routes may still fail due to governance drag")
    if env["network_density"] > 0.70:
        hidden.append("network routes may outperform brute-force local scaling")
    if res["budget"] < 0.70:
        hidden.append("oversized solutions may be structurally attractive but economically fragile")

    candidate_families = ["batch", "network", "phase", "electrical", "ascetic", "hybrid", "composite"]

    pressures = [
        "stability vs speed",
        "city-scale reproducibility vs local peak output",
        "infrastructure realism vs theoretical ceiling",
    ]
    if env["social_pressure"] > 0.5:
        pressures.append("deployment urgency vs safe validation cadence")

    contradiction = (
        "The system needs a route strong enough to reach a higher stability class, "
        "but any route that scales too directly risks destabilizing the surrounding field ecology."
    )

    return ProblemBackground(
        core_contradiction=contradiction,
        hidden_variables=hidden,
        dominant_pressures=pressures,
        candidate_families=candidate_families,
        inferred_goal_axis=[
            "upgrade yield",
            "field stability",
            "resource cost",
            "repeatability",
            "city-scale field compatibility",
        ],
    )


# =========================
# 3. Group field encoder
# =========================

def encode_group_field(seed: ProblemSeed) -> Dict[str, float]:
    env = seed.environment
    res = seed.resources
    subj = seed.subject

    return {
        "field_coherence": max(0.0, min(1.0,
            0.42 * subj["aim_coupling"] +
            0.18 * subj["control_precision"] +
            0.12 * subj["phase_proximity"] +
            0.18 * res["population_coupling"] +
            0.06 * res["data_coverage"] -
            0.14 * env["field_noise"] -
            0.08 * env["phase_instability"]
        )),
        "network_amplification": max(0.0, min(1.0,
            0.60 * env["network_density"] +
            0.20 * res["infrastructure"] +
            0.20 * res["data_coverage"]
        )),
        "governance_drag": max(0.0, min(1.0,
            0.65 * env["regulatory_friction"] +
            0.35 * env["social_pressure"]
        )),
        "phase_turbulence": max(0.0, min(1.0,
            0.75 * env["phase_instability"] +
            0.25 * env["field_noise"]
        )),
        "resource_elasticity": max(0.0, min(1.0,
            0.60 * res["budget"] +
            0.40 * res["infrastructure"]
        )),
    }


# =========================
# 4. Worldline generator
# =========================

def generate_worldlines(seed: ProblemSeed, bg: ProblemBackground) -> List[CandidateWorldline]:
    family_params = {
        "batch":      {"n": [12000, 18000, 20000, 24000], "rho": [0.5, 1.0], "A": [0.7, 0.9], "sigma": [0.01, 0.03]},
        "network":    {"n": [10000, 16000, 20000],       "rho": [0.8, 1.2], "A": [0.6, 0.8], "sigma": [0.02]},
        "phase":      {"n": [10000, 18000],              "rho": [0.5, 1.0], "A": [0.6, 0.75], "sigma": [0.04]},
        "electrical": {"n": [10000, 16000, 20000],       "rho": [0.6, 1.0], "A": [0.7],       "sigma": [0.05]},
        "ascetic":    {"n": [10000, 20000],              "rho": [0.2, 0.4], "A": [0.4, 0.55], "sigma": [0.03]},
        "hybrid":     {"n": [14000, 18000, 22000],       "rho": [0.7, 1.0], "A": [0.75],      "sigma": [0.08]},
        "composite":  {"n": [18000, 22000],              "rho": [0.8, 1.0], "A": [0.8],       "sigma": [0.04]},
    }

    desc_map = {
        "batch": "scale through standardized repeated upgrade packets",
        "network": "use network resonance and city-scale coupling to spread load",
        "phase": "use phase-alignment correction to reduce leakage before scaling",
        "electrical": "use direct pulse-like forcing with strict envelope control",
        "ascetic": "use low-rate low-noise convergence with long stabilization tail",
        "hybrid": "combine field amplification with controlled forcing",
        "composite": "stack two-stage routes to leverage complementary advantages",
    }

    out: List[CandidateWorldline] = []
    for fam in bg.candidate_families:
        spec = family_params[fam]
        for n, rho, A, sigma in itertools.product(spec["n"], spec["rho"], spec["A"], spec["sigma"]):
            out.append(CandidateWorldline(
                family=fam,
                template=f"{fam}_route",
                params={"n": float(n), "rho": float(rho), "A": float(A), "sigma": float(sigma)},
                description=desc_map[fam]
            ))
    return out


# =========================
# 5. Mini UMDST kernel
# =========================

def family_lock(family: str, n: float) -> float:
    nc_map = {
        "batch": 18000.0, "network": 15000.0, "phase": 17000.0,
        "electrical": 16000.0, "ascetic": 20000.0, "hybrid": 18000.0,
        "composite": 18500.0
    }
    sharp_map = {
        "batch": 2200.0, "network": 2000.0, "phase": 2400.0,
        "electrical": 2200.0, "ascetic": 2600.0, "hybrid": 2300.0,
        "composite": 2500.0
    }
    x = (n - nc_map[family]) / sharp_map[family]
    return 1.0 / (1.0 + math.exp(-x))

def evaluate_worldline(seed: ProblemSeed, field: Dict[str, float], w: CandidateWorldline) -> EvaluationResult:
    s = seed.subject
    p = w.params
    fam = w.family
    lock = family_lock(fam, p["n"])

    family_bias = {
        "batch":      {"yield": 0.16, "stability": 0.08, "risk": 0.02},
        "network":    {"yield": 0.12, "stability": 0.11, "risk": -0.01},
        "phase":      {"yield": 0.09, "stability": 0.12, "risk": -0.02},
        "electrical": {"yield": 0.11, "stability": 0.04, "risk": 0.08},
        "ascetic":    {"yield": 0.05, "stability": 0.13, "risk": -0.03},
        "hybrid":     {"yield": 0.13, "stability": 0.06, "risk": 0.04},
        "composite":  {"yield": 0.14, "stability": 0.09, "risk": 0.03},
    }[fam]

    feasibility = (
        0.25 * s["output_power"] +
        0.18 * s["aim_coupling"] +
        0.12 * field["resource_elasticity"] +
        0.18 * p["A"] +
        0.15 * lock +
        family_bias["yield"] -
        0.08 * p["sigma"]
    )
    feasibility = max(0.0, min(1.2, feasibility))

    stability = (
        0.28 * s["control_precision"] +
        0.18 * s["load_tolerance"] +
        0.20 * field["field_coherence"] +
        0.15 * (1.0 - field["phase_turbulence"]) +
        0.12 * (1.0 - p["sigma"]) +
        family_bias["stability"]
    )
    stability = max(0.0, min(1.2, stability))

    field_fit = (
        0.32 * field["network_amplification"] * (1.2 if fam == "network" else 1.0) +
        0.22 * field["field_coherence"] +
        0.18 * s["phase_proximity"] +
        0.10 * p["rho"] +
        0.08 * lock -
        0.10 * field["governance_drag"]
    )
    field_fit = max(0.0, min(1.2, field_fit))

    risk = (
        0.18 * field["phase_turbulence"] +
        0.14 * field["governance_drag"] +
        0.12 * s["instability_sensitivity"] +
        0.10 * s["stress_level"] +
        0.08 * p["sigma"] +
        0.05 * max(0.0, (p["n"] - 20000.0) / 10000.0) +
        family_bias["risk"]
    )
    risk = max(0.0, min(1.2, risk))

    raw = 1.15 * feasibility + 1.00 * stability + 0.95 * field_fit - 1.10 * risk

    # CBF-like balancing penalty
    spread = statistics.pstdev([feasibility, stability, field_fit])
    balanced_score = raw - 0.25 * spread

    route_bonus = 0.0
    if fam == "network":
        route_bonus += 0.14 * field["network_amplification"] + 0.06 * field["field_coherence"]
    if fam == "phase":
        route_bonus += 0.07 * (1.0 - field["phase_turbulence"])
    if fam == "batch" and abs(p["n"] - 20000.0) <= 1e-6:
        route_bonus += 0.05
    if abs(p["n"] - 20000.0) <= 1e-6:
        route_bonus += 0.06
    if balanced_score >= 2.20:
        route_bonus += 0.03
    if fam == "network" and abs(p["n"] - 20000.0) <= 1e-6 and p["rho"] >= 1.0:
        route_bonus += 0.05

    nutrient_gain = (
        1.00 * max(0.0, feasibility - 0.82) +
        0.88 * max(0.0, stability - 0.80) +
        0.84 * max(0.0, field_fit - 0.68) +
        route_bonus -
        0.74 * risk -
        0.05 * max(0.0, (p["n"] - 20000.0) / 5000.0)
    )

    if nutrient_gain > 0.10 and balanced_score > 2.05:
        status = "active"
    elif nutrient_gain > -0.01:
        status = "restricted"
    elif nutrient_gain > -0.12:
        status = "starved"
    else:
        status = "withered"

    return EvaluationResult(
        family=fam,
        template=w.template,
        params=w.params,
        feasibility=round(feasibility, 6),
        stability=round(stability, 6),
        field_fit=round(field_fit, 6),
        risk=round(risk, 6),
        balanced_score=round(balanced_score, 6),
        nutrient_gain=round(nutrient_gain, 6),
        branch_status=status,
    )


# =========================
# 6. VFT-like compression
# =========================

def compress_to_main_branches(results: List[EvaluationResult], top_k: int = 12) -> List[EvaluationResult]:
    return sorted(results, key=lambda x: x.balanced_score, reverse=True)[:top_k]


# =========================
# 7. Mini H-UTM
# =========================

def hydro_adjust_top_candidates(results: List[EvaluationResult]) -> Dict[str, float]:
    active = sum(1 for r in results if r.branch_status == "active")
    withered = sum(1 for r in results if r.branch_status == "withered")
    restricted = sum(1 for r in results if r.branch_status == "restricted")
    avg_risk = statistics.mean(r.risk for r in results)
    avg_score = statistics.mean(r.balanced_score for r in results)

    # If the top pool is high-quality but not fully active yet, increase main-channel pressure mildly.
    pressure_balance = 1.0 + 0.18 * max(0.0, avg_score - 1.7) - 0.18 * max(0.0, avg_risk - 0.35)
    pressure_balance += 0.08 * (restricted / max(1, len(results)))
    pressure_balance = round(max(0.92, min(1.25, pressure_balance)), 4)

    return {
        "pressure_balance": pressure_balance,
        "wither_ratio": round(withered / max(1, len(results)), 4),
        "active_ratio": round(active / max(1, len(results)), 4),
        "restricted_ratio": round(restricted / max(1, len(results)), 4),
        "mean_balanced_score": round(avg_score, 4),
        "mean_risk": round(avg_risk, 4),
    }


# =========================
# 8. Oracle layer
# =========================

def oracle_summary(
    seed: ProblemSeed,
    bg: ProblemBackground,
    field: Dict[str, float],
    top_results: List[EvaluationResult],
    hydro: Dict[str, float]
) -> Dict[str, object]:
    best = top_results[0]

    background_naturally_emerged = (
        len(bg.hidden_variables) >= 4 and
        len(bg.dominant_pressures) >= 3 and
        field["field_coherence"] >= 0.75 and
        best.balanced_score >= 2.15
    )

    branch_hist = {
        "active": sum(1 for x in top_results if x.branch_status == "active"),
        "restricted": sum(1 for x in top_results if x.branch_status == "restricted"),
        "starved": sum(1 for x in top_results if x.branch_status == "starved"),
        "withered": sum(1 for x in top_results if x.branch_status == "withered"),
    }

    return {
        "seed_title": seed.title,
        "core_contradiction": bg.core_contradiction,
        "hidden_variables": bg.hidden_variables,
        "dominant_pressures": bg.dominant_pressures,
        "urban_field": field,
        "background_naturally_emerged": background_naturally_emerged,
        "best_worldline": {
            "family": best.family,
            "template": best.template,
            "params": best.params,
            "balanced_score": best.balanced_score,
            "risk": best.risk,
            "branch_status": best.branch_status,
        },
        "hydro_control_state": hydro,
        "branch_histogram": branch_hist,
        "main_worldline_alive": best.branch_status in ("active", "restricted"),
        "main_worldline_active": best.branch_status == "active",
        "top_families": [asdict(x) for x in top_results[:5]],
    }


# =========================
# 9. Runner
# =========================

def run_prototype(out_dir: Path) -> Dict[str, object]:
    seed = default_seed()
    bg = infer_problem_background(seed)
    field = encode_group_field(seed)
    worldlines = generate_worldlines(seed, bg)
    evals = [evaluate_worldline(seed, field, w) for w in worldlines]
    top = compress_to_main_branches(evals, top_k=12)
    hydro = hydro_adjust_top_candidates(top)
    oracle = oracle_summary(seed, bg, field, top, hydro)

    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "problem_seed.json").write_text(
        json.dumps(asdict(seed), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "problem_background.json").write_text(
        json.dumps(asdict(bg), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "group_field.json").write_text(
        json.dumps(field, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "oracle_output.json").write_text(
        json.dumps(oracle, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with (out_dir / "top_worldlines.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "family", "template", "n", "rho", "A", "sigma",
                "feasibility", "stability", "field_fit", "risk",
                "balanced_score", "nutrient_gain", "branch_status"
            ]
        )
        writer.writeheader()
        for r in top:
            writer.writerow({
                "family": r.family,
                "template": r.template,
                "n": r.params["n"],
                "rho": r.params["rho"],
                "A": r.params["A"],
                "sigma": r.params["sigma"],
                "feasibility": r.feasibility,
                "stability": r.stability,
                "field_fit": r.field_fit,
                "risk": r.risk,
                "balanced_score": r.balanced_score,
                "nutrient_gain": r.nutrient_gain,
                "branch_status": r.branch_status,
            })

    return oracle


# =========================
# 10. Colab entry
# =========================

if __name__ == "__main__":
    out_dir = Path("./tree_diagram_complete_mini_out")
    oracle = run_prototype(out_dir)
    print(json.dumps(oracle, ensure_ascii=False, indent=2))