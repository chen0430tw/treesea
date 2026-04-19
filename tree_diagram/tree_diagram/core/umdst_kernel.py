
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SubjectState:
    output_power: float
    control_precision: float
    load_tolerance: float
    aim_coupling: float
    stress_level: float
    phase_proximity: float
    marginal_decay: float
    instability_sensitivity: float

    def to_vector(self) -> List[float]:
        return [
            self.output_power,
            self.control_precision,
            self.load_tolerance,
            self.aim_coupling,
            self.stress_level,
            self.phase_proximity,
            self.marginal_decay,
            self.instability_sensitivity,
        ]

    @classmethod
    def from_vector(cls, x: List[float]) -> "SubjectState":
        return cls(*x)


@dataclass
class PathTemplate:
    name: str
    family: str
    source: str
    parameter_space: Dict[str, List[float]]
    risk_profile: Dict[str, float]
    execution_profile: Dict[str, float]


@dataclass
class PathInstance:
    template_name: str
    family: str
    source: str
    params: Dict[str, float]
    morph_tags: List[str]
    compose_tags: List[str]

    @property
    def path_id(self) -> str:
        parts = [self.template_name]
        for k in sorted(self.params.keys()):
            parts.append(f"{k}={self.params[k]}")
        return "|".join(parts)


@dataclass
class BenchmarkPackage:
    subject_init: SubjectState
    target_phase_threshold: float
    constraints: Dict[str, float]
    path_templates: List[PathTemplate]


@dataclass
class TDOutputs:
    riskfield: List[float]
    graph: List[Tuple[int, int, float]]
    curve: List[float]
    samples: Dict[str, List[float]]
    meta: Dict[str, Any]


@dataclass
class Metrics:
    e_cons_mean: float
    impact_peak: float
    variance_proxy: float
    disagree_proxy: float
    ood_proxy: float
    p_blow_max: float
    phase_max: float
    phase_final: float
    repeatability: float


@dataclass
class GovernanceState:
    state: str
    handshake: bool
    p_blow: float
    reason: str


def clamp(x: float, lo: float = 0.0, hi: float = 1.2) -> float:
    return max(lo, min(hi, x))


def logistic(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def default_benchmark() -> BenchmarkPackage:
    subject = SubjectState(
        output_power=0.92,
        control_precision=0.95,
        load_tolerance=0.88,
        aim_coupling=0.91,
        stress_level=0.30,
        phase_proximity=0.42,
        marginal_decay=0.10,
        instability_sensitivity=0.35,
    )
    templates = [
        PathTemplate(
            name="phase_base",
            family="phase",
            source="theory",
            parameter_space={
                "n": [1000, 5000, 10000, 20000, 30000],
                "rho": [0.5, 1.0, 2.0],
                "A": [0.6, 0.8, 1.0],
                "sigma": [0.05, 0.10, 0.20],
            },
            risk_profile={"base_risk": 0.22},
            execution_profile={"infra": 0.40, "compute": 0.35},
        ),
        PathTemplate(
            name="sister_batch_like",
            family="batch",
            source="experiment",
            parameter_space={
                "n": [5000, 10000, 15000, 20000, 25000],
                "rho": [1.0, 2.0],
                "A": [0.7, 0.9],
                "sigma": [0.01, 0.03, 0.05],
            },
            risk_profile={"base_risk": 0.18},
            execution_profile={"infra": 0.55, "compute": 0.30},
        ),
        PathTemplate(
            name="drug_battle_mix",
            family="hybrid",
            source="underground",
            parameter_space={
                "n": [1000, 5000, 10000],
                "rho": [0.5, 1.0],
                "A": [0.8, 1.0],
                "sigma": [0.10, 0.20],
            },
            risk_profile={"base_risk": 0.38},
            execution_profile={"infra": 0.65, "compute": 0.45},
        ),
    ]
    constraints = {
        "max_steps": 240,
        "max_risk": 0.85,
        "p0": 0.60,
        "p1": 0.85,
        "e_cons_threshold": 0.25,
    }
    return BenchmarkPackage(subject, 0.95, constraints, templates)


def load_benchmark(path: Optional[str]) -> BenchmarkPackage:
    if path is None:
        return default_benchmark()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    subject = SubjectState(**data["subject_init"])
    templates = [PathTemplate(**tpl) for tpl in data["path_templates"]]
    return BenchmarkPackage(subject, data["target_state"]["phase_threshold"], data["constraints"], templates)


def expand_paths(path_templates: List[PathTemplate], max_instances: Optional[int] = None) -> List[PathInstance]:
    out: List[PathInstance] = []
    for tpl in path_templates:
        keys = list(tpl.parameter_space.keys())
        values = [tpl.parameter_space[k] for k in keys]
        for combo in itertools.product(*values):
            params = {k: float(v) for k, v in zip(keys, combo)}
            morph_tags: List[str] = []
            if tpl.family == "batch" and params.get("sigma", 1.0) <= 0.03:
                morph_tags.append("standardized")
            if tpl.family == "hybrid":
                morph_tags.append("composed")
            out.append(PathInstance(tpl.name, tpl.family, tpl.source, params, morph_tags, []))
            if max_instances is not None and len(out) >= max_instances:
                return out
    return out


def family_coeffs(family: str) -> Dict[str, float]:
    return {
        "phase":  {"gain": 0.050, "precision": 0.018, "coupling": 0.020, "stress": 0.022, "decay": 0.010},
        "batch":  {"gain": 0.060, "precision": 0.020, "coupling": 0.026, "stress": 0.018, "decay": 0.008},
        "hybrid": {"gain": 0.055, "precision": 0.014, "coupling": 0.024, "stress": 0.035, "decay": 0.018},
    }.get(family, {"gain": 0.045, "precision": 0.015, "coupling": 0.018, "stress": 0.025, "decay": 0.012})


def simulate_path(subject_init: SubjectState, path: PathInstance, max_steps: int = 240) -> Tuple[List[SubjectState], TDOutputs]:
    coeff = family_coeffs(path.family)
    x = subject_init.to_vector()

    n = max(1.0, path.params["n"])
    rho = max(0.01, path.params["rho"])
    A = max(0.01, path.params["A"])
    sigma = max(0.0, path.params["sigma"])
    steps = min(max_steps, max(24, int(24 + math.sqrt(n) * 1.2 + 18 * rho)))
    standardization = math.exp(-4.0 * sigma)

    states = [SubjectState.from_vector(x[:])]
    phase_series, stress_series, instability_series, gain_curve = [], [], [], []

    for t in range(steps):
        progress = (t + 1) / steps
        output_power, control_precision, load_tolerance, aim_coupling, stress_level, phase_proximity, marginal_decay, instability = x

        gain = (
            coeff["gain"] * A * (0.55 + 0.45 * rho) * standardization
            * (0.7 + 0.3 * aim_coupling)
            * math.exp(-1.8 * marginal_decay)
            * (1.0 - 0.35 * stress_level)
        )
        precision_gain = coeff["precision"] * A * (1.0 - 0.4 * sigma) * (1.0 - 0.35 * stress_level)
        coupling_gain = coeff["coupling"] * A * standardization * (0.8 + 0.2 * output_power)

        if path.family == "batch":
            gain *= 1.0 + 0.16 * logistic(10 * (phase_proximity - 0.55))
        elif path.family == "phase":
            gain *= 1.0 + 0.10 * progress
        elif path.family == "hybrid":
            gain *= 1.0 + 0.12 * math.sin(progress * math.pi)

        stress_up = coeff["stress"] * A * (0.8 + 0.4 * rho) * (0.55 + 0.45 * sigma)
        stress_down = 0.010 + 0.014 * load_tolerance
        decay_up = coeff["decay"] * rho * (0.6 + 0.4 * A)
        instability_up = 0.012 * A + 0.010 * sigma + 0.014 * stress_level
        instability_down = 0.008 * load_tolerance

        x[0] = clamp(output_power + 0.35 * gain - 0.012 * stress_level)
        x[1] = clamp(control_precision + precision_gain - 0.008 * sigma)
        x[2] = clamp(load_tolerance + 0.010 * A - 0.014 * stress_level)
        x[3] = clamp(aim_coupling + coupling_gain - 0.006 * stress_level)
        x[4] = clamp(stress_level + stress_up - stress_down, 0.0, 1.5)
        x[5] = clamp(
            phase_proximity + gain + 0.20 * precision_gain + 0.16 * coupling_gain
            - 0.05 * instability - 0.04 * stress_level, 0.0, 1.2
        )
        x[6] = clamp(marginal_decay + decay_up - 0.006 * standardization, 0.0, 1.2)
        x[7] = clamp(instability + instability_up - instability_down, 0.0, 1.5)

        phase_series.append(x[5]); stress_series.append(x[4]); instability_series.append(x[7]); gain_curve.append(gain)
        states.append(SubjectState.from_vector(x[:]))

    bins = 16
    counts = [0] * bins
    transitions: Dict[Tuple[int, int], int] = {}
    prev_bin: Optional[int] = None
    for value in phase_series:
        idx = min(bins - 1, max(0, int(value * bins / 1.2)))
        counts[idx] += 1
        if prev_bin is not None:
            transitions[(prev_bin, idx)] = transitions.get((prev_bin, idx), 0) + 1
        prev_bin = idx

    total = sum(counts) or 1
    riskfield = [c / total for c in counts]
    graph = [(u, v, float(w)) for (u, v), w in sorted(transitions.items(), key=lambda kv: kv[1], reverse=True)]

    td_outputs = TDOutputs(
        riskfield=riskfield,
        graph=graph,
        curve=gain_curve,
        samples={"phase": phase_series, "stress": stress_series, "instability": instability_series},
        meta={
            "path_id": path.path_id,
            "steps": steps,
            "phase_max": max(phase_series) if phase_series else subject_init.phase_proximity,
            "phase_final": phase_series[-1] if phase_series else subject_init.phase_proximity,
        },
    )
    return states, td_outputs


def build_ipl(td: TDOutputs, prev_ipl: Optional[Dict[str, Any]] = None, alpha: float = 0.35) -> Dict[str, Any]:
    mean_p = sum(td.riskfield) / len(td.riskfield)
    var_p = statistics.pvariance(td.riskfield) if len(td.riskfield) > 1 else 0.0
    mean_c = sum(td.curve) / len(td.curve) if td.curve else 0.0
    peak_c = max(td.curve) if td.curve else 0.0
    z = [mean_p, var_p, mean_c, peak_c]
    if prev_ipl is None:
        z_s = z[:]
    else:
        z_prev = prev_ipl["z_s"]
        z_s = [(1.0 - alpha) * a + alpha * b for a, b in zip(z_prev, z)]
    keys = {"coarse": int(min(9, max(0, z_s[2] * 10))), "variance_bin": int(min(9, max(0, z_s[1] * 500)))}
    return {"z": z, "z_s": z_s, "keys": keys}


def graph_to_transition(td: TDOutputs, bins: int = 16) -> List[List[float]]:
    mat = [[0.0 for _ in range(bins)] for _ in range(bins)]
    for u, v, w in td.graph:
        if 0 <= u < bins and 0 <= v < bins:
            mat[u][v] += w
    for u in range(bins):
        s = sum(mat[u])
        if s > 0:
            mat[u] = [x / s for x in mat[u]]
    return mat


def compute_metrics(td: TDOutputs, prev_td: Optional[TDOutputs] = None) -> Metrics:
    bins = len(td.riskfield)
    T = graph_to_transition(td, bins=bins)

    pred = [0.0 for _ in range(bins)]
    for u in range(bins):
        for v in range(bins):
            pred[v] += td.riskfield[u] * T[u][v]
    e_cons = sum(abs(a - b) for a, b in zip(pred, td.riskfield))

    impact = 0.0
    if prev_td is not None:
        T_prev = graph_to_transition(prev_td, bins=bins)
        for u in range(bins):
            for v in range(bins):
                p = T_prev[u][v]
                q = T[u][v]
                if p > 0 and q > 1e-12:
                    impact += p * math.log(p / q)
                elif p > 0 and q <= 1e-12:
                    impact += p * 8.0
        impact /= bins

    phase = td.samples["phase"]
    stress = td.samples["stress"]
    instability = td.samples["instability"]

    variance_proxy = statistics.pvariance(phase) if len(phase) > 1 else 0.0
    disagree_proxy = (statistics.mean(stress) if stress else 0.0) * 0.25 + (statistics.mean(instability) if instability else 0.0) * 0.25
    ood_proxy = max(0.0, td.meta["phase_max"] - 1.0) + max(0.0, statistics.mean(instability) - 0.8)

    p_blow_series = []
    for ph, st, ins in zip(phase, stress, instability):
        raw = 2.2 * e_cons + 1.8 * impact + 1.6 * st + 1.9 * ins + 0.6 * max(0.0, ph - 1.0)
        p_blow_series.append(logistic(raw - 1.8))
    p_blow_max = max(p_blow_series) if p_blow_series else 0.0

    repeatability = max(0.0, 1.0 - (variance_proxy + 0.5 * (instability[-1] if instability else 0.0)))

    return Metrics(
        e_cons_mean=e_cons,
        impact_peak=impact,
        variance_proxy=variance_proxy,
        disagree_proxy=disagree_proxy,
        ood_proxy=ood_proxy,
        p_blow_max=p_blow_max,
        phase_max=td.meta["phase_max"],
        phase_final=td.meta["phase_final"],
        repeatability=repeatability,
    )


def evaluate_nrp(metrics: Metrics, constraints: Dict[str, float]) -> GovernanceState:
    # p-blow thresholds (calibrated; stable band is p < p0)
    p0 = constraints.get("p0", 0.60)                    # NEGOTIATE entry
    p1 = constraints.get("p1", 0.85)                    # CRACKDOWN entry
    # e_cons_mean in current pipeline is r.risk. Previous default 0.25 forced
    # essentially every real scenario into CRACKDOWN. 0.80 was the first fix
    # but it went too far the other way — WW4 / Singularity-Probe p_blow=0.74
    # still never crossed it. Calibrated against the full scenario library:
    #   e_cons > 0.70 → CRACKDOWN (WW4, Singularity-Probe trigger here)
    #   e_cons > 0.50 → NEGOTIATE (AI/COVID post states trigger here)
    #   e_cons ≤ 0.50 → NORMAL     (healthy / stable baseline)
    e_cons_crackdown = constraints.get("e_cons_crackdown", 0.70)
    e_cons_negotiate = constraints.get("e_cons_negotiate", 0.50)

    # Hard reds first
    if metrics.p_blow_max >= p1:
        return GovernanceState("CRACKDOWN", False, metrics.p_blow_max, "blow-up risk beyond red line")
    if metrics.e_cons_mean > e_cons_crackdown:
        return GovernanceState("CRACKDOWN", False, metrics.p_blow_max, "conservation inconsistency beyond red line")

    # Yellow zone
    if metrics.p_blow_max >= p0:
        return GovernanceState("NEGOTIATE", False, metrics.p_blow_max, "blow-up risk in yellow zone")
    if metrics.e_cons_mean > e_cons_negotiate:
        return GovernanceState("NEGOTIATE", False, metrics.p_blow_max, "conservation soft warning")

    return GovernanceState("NORMAL", True, metrics.p_blow_max, "within stable band")


def cbf_lite(metrics: Metrics, governance: GovernanceState) -> Dict[str, float]:
    cheap = max(0.0, 1.0 - (metrics.p_blow_max + metrics.e_cons_mean + metrics.impact_peak))
    refine = max(0.0, 0.40 * metrics.e_cons_mean + 0.40 * metrics.impact_peak + 0.20 * metrics.variance_proxy)
    slow = max(0.0, metrics.p_blow_max + 0.50 * metrics.ood_proxy)

    if governance.state == "NEGOTIATE":
        cheap *= 0.6
        refine *= 1.2
        slow *= 1.1
    elif governance.state == "CRACKDOWN":
        cheap *= 0.2
        refine *= 1.1
        slow *= 1.8

    total = cheap + refine + slow
    if total <= 1e-12:
        return {"cheap": 1.0, "refine": 0.0, "slow": 0.0}
    return {"cheap": cheap / total, "refine": refine / total, "slow": slow / total}


def evaluate_score(path: PathInstance, metrics: Metrics) -> float:
    n = path.params["n"]
    n_penalty = min(1.0, n / 30000.0)
    U = metrics.variance_proxy + metrics.disagree_proxy + metrics.ood_proxy

    score = (
        1.80 * metrics.phase_max
        - 1.35 * metrics.p_blow_max
        - 0.55 * n_penalty
        - 0.80 * U
        + 0.50 * metrics.repeatability
    )
    if path.family == "batch":
        score += 0.08
    return score


def run_umdst(benchmark: BenchmarkPackage, max_instances: Optional[int] = None) -> Dict[str, Any]:
    candidates = expand_paths(benchmark.path_templates, max_instances=max_instances)
    results = []
    prev_td = None
    prev_ipl = None

    for path in candidates:
        _, td = simulate_path(benchmark.subject_init, path, max_steps=int(benchmark.constraints.get("max_steps", 240)))
        ipl = build_ipl(td, prev_ipl)
        metrics = compute_metrics(td, prev_td)
        governance = evaluate_nrp(metrics, benchmark.constraints)
        allocation = cbf_lite(metrics, governance)
        score = evaluate_score(path, metrics)

        results.append({
            "path": path,
            "td": td,
            "ipl": ipl,
            "metrics": metrics,
            "governance": governance,
            "allocation": allocation,
            "score": score,
        })

        prev_td = td
        prev_ipl = ipl

    results.sort(key=lambda r: r["score"], reverse=True)
    best = results[0]

    top_k = []
    for item in results[:5]:
        top_k.append({
            "name": item["path"].template_name,
            "family": item["path"].family,
            "params": item["path"].params,
            "score": round(item["score"], 6),
            "state": item["governance"].state,
        })

    report = {
        "algorithm": "UMDST v0.1",
        "best_path": {
            "template_name": best["path"].template_name,
            "family": best["path"].family,
            "params": best["path"].params,
            "score": round(best["score"], 6),
        },
        "top_k": top_k,
        "metrics": asdict(best["metrics"]),
        "governance": asdict(best["governance"]),
        "allocation": best["allocation"],
        "prediction": {
            "riskfield": best["td"].riskfield,
            "graph": best["td"].graph,
            "curve": best["td"].curve,
            "samples": best["td"].samples,
            "meta": best["td"].meta,
        },
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run UMDST v0.1 benchmark search.")
    parser.add_argument("--benchmark", type=str, default=None, help="Path to benchmark JSON. If omitted, use built-in benchmark.")
    parser.add_argument("--max-instances", type=int, default=None, help="Optional cap on expanded path instances.")
    parser.add_argument("--out", type=str, default="umdst_report.json", help="Output report JSON path.")
    args = parser.parse_args()

    benchmark = load_benchmark(args.benchmark)
    report = run_umdst(benchmark, max_instances=args.max_instances)

    out_path = Path(args.out)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("UMDST finished")
    print(f"Best path: {report['best_path']['template_name']} | score={report['best_path']['score']}")
    print(f"Params: {report['best_path']['params']}")
    print(f"Governance: {report['governance']['state']} | p_blow={report['governance']['p_blow']:.4f}")
    print(f"Saved report: {out_path}")


if __name__ == "__main__":
    main()
