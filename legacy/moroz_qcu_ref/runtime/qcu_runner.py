# qcu_runner.py
from __future__ import annotations
import time
from qcu.runtime.state import RuntimeState
from qcu.opu.controller import OPUController

def run_qcu(runtime_cfg) -> dict:
    controller = OPUController()
    candidates = list(runtime_cfg.mapped_candidates)
    started = time.perf_counter()
    ranked = []

    for step in range(1, 1 + (3 if runtime_cfg.profile == "toy" else 5 if runtime_cfg.profile == "benchmark" else 7)):
        scored = []
        for item in candidates:
            mapped = item["mapped"]
            collapse_score = (
                1.0 * float(item["base_score"])
                + 0.5 * mapped["domain_hint"]
                + 0.7 * mapped["personal_hint"]
                + 0.8 * mapped["context_hint"]
                + 0.6 * mapped["syntax_hint"]
            )
            scored.append((collapse_score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score = scored[0][0] if scored else 0.0

        state = RuntimeState(
            request_id=runtime_cfg.request_id,
            step=step,
            elapsed_sec=time.perf_counter() - started,
            active_candidates=len(scored),
            collapse_score=best_score,
            phase_dispersion=max(0.0, 1.0 - best_score / 10.0),
            attractor_density=min(1.0, 0.4 + len(scored[:3]) / max(len(scored), 1)),
            quality_signal=min(1.0, 0.5 + best_score / 10.0),
            resource_load=min(1.0, len(scored) / 100.0),
        )
        action = controller.tick(state)

        if action.early_stop:
            candidates = [item for _, item in scored[: min(10, len(scored))]]
            break

        candidates = [item for _, item in scored[: max(3, len(scored)//2)]]

    for final_score, item in sorted([( 
        1.0 * float(it["base_score"])
        + 0.5 * it["mapped"]["domain_hint"]
        + 0.7 * it["mapped"]["personal_hint"]
        + 0.8 * it["mapped"]["context_hint"]
        + 0.6 * it["mapped"]["syntax_hint"], it) for it in candidates], key=lambda x: x[0], reverse=True):
        ranked.append({
            "text": item["text"],
            "base_score": item["base_score"],
            "collapse_score": final_score,
            "final_score": final_score,
            "trace_summary": {"profile": runtime_cfg.profile},
            "source_layers": item["source_layers"],
            "meta": item["meta"],
        })

    elapsed = time.perf_counter() - started
    return {
        "status": "completed",
        "ranked": ranked,
        "elapsed_sec": elapsed,
        "steps": step,
        "effective_candidates": len(candidates),
        "converged": True,
        "stop_reason": "early_stop" if action.early_stop else "converged",
        "diagnostics": {"profile": runtime_cfg.profile},
    }
