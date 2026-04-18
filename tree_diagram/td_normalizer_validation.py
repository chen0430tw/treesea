"""Validate SeedNormalizer: the original zombie-named seeds should,
after normalization, produce results close to the hand-crafted calibration seeds."""
from __future__ import annotations

from tree_diagram.pipeline.candidate_pipeline import CandidatePipeline
from tree_diagram.core.problem_seed import ProblemSeed
from tree_diagram.core.seed_normalizer import normalize_seed


# ────────────────────────────────────────────────────────────────────
# 原版 zombie 自定义字段 seed（之前跑不出区分度的版本）
# ────────────────────────────────────────────────────────────────────
raw_q1 = ProblemSeed(
    title="Q1_raw", target="infection pathway", constraints=[],
    resources={
        "detection_budget": 0.30,
        "log_coverage": 0.75,
        "trace_granularity": 0.82,
    },
    environment={
        "numeric_overflow_pressure": 0.72,
        "mixed_precision_fraction": 0.55,
        "clamp_density": 0.40,
        "silent_propagation_risk": 0.88,
        "contract_enforcement": 0.25,
    },
    subject={
        "gradient_stability": 0.31,
        "loss_sanity_checks": 0.18,
        "direction_consistency": 0.42,
        "early_exit_discipline": 0.22,
        "nan_guard_coverage": 0.15,
        "field_validation_strictness": 0.28,
        "error_amplification_factor": 0.81,
        "silent_failure_propensity": 0.89,
    },
)

raw_q2 = ProblemSeed(
    title="Q2_raw", target="persistence", constraints=[],
    resources={
        "monitoring_frequency": 0.55,
        "log_retention": 0.70,
        "anomaly_detector_budget": 0.45,
        "human_in_loop_rate": 0.20,
    },
    environment={
        "checkpoint_frequency": 0.38,
        "dashboard_visibility": 0.50,
        "alert_noise_floor": 0.65,
        "operator_attention_decay": 0.73,
        "normalization_masking": 0.58,
    },
    subject={
        "infection_severity": 0.85,
        "symptom_visibility": 0.35,
        "output_plausibility": 0.78,
        "clamp_rescue_rate": 0.62,
        "metric_numerical_survivability": 0.81,
        "detection_evasion": 0.71,
        "decay_rate_under_observation": 0.23,
        "zombie_lifespan_tolerance": 0.66,
    },
)

raw_q3 = ProblemSeed(
    title="Q3_raw", target="healthy conditions", constraints=[],
    resources={
        "compute_budget": 0.70,
        "hyperparameter_search_budget": 0.55,
        "validation_set_coverage": 0.80,
        "monitoring_granularity": 0.72,
    },
    environment={
        "learning_rate_stability": 0.78,
        "batch_size_adequacy": 0.82,
        "data_quality": 0.75,
        "gradient_clipping_active": 0.88,
        "loss_scaling_correct": 0.85,
        "mixed_precision_safety": 0.65,
    },
    subject={
        "gradient_norm_band": 0.83,
        "direction_consistency": 0.86,
        "loss_monotonic_decrease": 0.74,
        "metric_monotonic_increase": 0.77,
        "fitness_stability_margin": 0.80,
        "early_stopping_discipline": 0.69,
        "anti_frozen_signal": 0.72,
        "anti_fake_plateau_signal": 0.66,
        "anti_drift_correlation": 0.78,
    },
)


# ────────────────────────────────────────────────────────────────────
# 标定数据：之前跑出来的 Q1/Q2/Q3（手工映射版）
# ────────────────────────────────────────────────────────────────────
CALIBRATION = {
    "Q1": {"top_score": 0.184, "risk": 0.672, "feas": 0.397, "stab": 0.377, "zone": "stable"},
    "Q2": {"top_score": 0.251, "risk": 0.559, "feas": 0.459, "stab": 0.452, "zone": "stable"},
    "Q3": {"top_score": 0.554, "risk": 0.308, "feas": 0.880, "stab": 0.653, "zone": "transition"},
}


def run_normalized(label: str, raw_seed: ProblemSeed):
    print(f"\n{'=' * 70}")
    print(f"[{label}] normalize({raw_seed.title})")
    print(f"{'=' * 70}")

    normalized, trace = normalize_seed(raw_seed)

    print(f"Normalization trace:")
    print(f"  preserved: {sum(len(v) for v in trace.preserved.values())} fields")
    print(f"  aliased:   {len(trace.aliased)}")
    print(f"  routed:    {len(trace.routed)}")
    print(f"  unmatched: {len(trace.unmatched)}  {trace.unmatched if trace.unmatched else ''}")
    print(f"  merged:    {trace.merged_fields}")
    print()
    print(f"Post-normalize kernel-field values:")
    for sec in ("subject", "environment", "resources"):
        vals = getattr(normalized, sec)
        if vals:
            print(f"  {sec}: {dict(sorted(vals.items()))}")

    pipe = CandidatePipeline(
        seed=normalized, top_k=5, NX=32, NY=24, steps=60, dt=45.0, n_workers=1,
    )
    top, hydro, oracle = pipe.run()

    s0 = top[0]
    score0 = float(getattr(s0, 'final_balanced_score', s0.balanced_score))
    zone = hydro.get("ipl_index", {}).get("top_zone", "?")

    cal = CALIBRATION[label]
    print(f"\nResult vs calibration:")
    print(f"  score: {score0:.4f}  (cal={cal['top_score']:.4f}, Δ={score0 - cal['top_score']:+.4f})")
    print(f"  risk:  {s0.risk:.3f}   (cal={cal['risk']:.3f}, Δ={s0.risk - cal['risk']:+.3f})")
    print(f"  feas:  {s0.feasibility:.3f}   (cal={cal['feas']:.3f}, Δ={s0.feasibility - cal['feas']:+.3f})")
    print(f"  stab:  {s0.stability:.3f}   (cal={cal['stab']:.3f}, Δ={s0.stability - cal['stab']:+.3f})")
    print(f"  zone:  {zone}  (cal={cal['zone']})")
    return score0, s0.risk, s0.feasibility, s0.stability, zone


if __name__ == "__main__":
    res_q1 = run_normalized("Q1", raw_q1)
    res_q2 = run_normalized("Q2", raw_q2)
    res_q3 = run_normalized("Q3", raw_q3)

    print(f"\n{'=' * 70}")
    print("Validation summary:")
    print(f"{'=' * 70}")
    print("Calibration order:   Q1 < Q2 < Q3 (by top_score)")
    print(f"Normalized order:    {res_q1[0]:.4f} < {res_q2[0]:.4f} < {res_q3[0]:.4f}")
    ordering_ok = res_q1[0] < res_q2[0] < res_q3[0]
    print(f"Ordering preserved:  {'YES' if ordering_ok else 'NO'}")
