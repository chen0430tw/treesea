# result_adapter.py
from __future__ import annotations
from moroz.contracts.result import CollapseResult, RuntimeStats
from moroz.contracts.types import CollapseCandidate

def adapt_runtime_result(request_id: str, runtime_result: dict) -> CollapseResult:
    ranked = []
    for item in runtime_result.get("ranked", []):
        ranked.append(
            CollapseCandidate(
                text=item["text"],
                base_score=float(item.get("base_score", 0.0)),
                collapse_score=float(item.get("collapse_score", 0.0)),
                final_score=float(item.get("final_score", 0.0)),
                trace_summary=item.get("trace_summary", {}),
                source_layers=item.get("source_layers", []),
                meta=item.get("meta", {}),
            )
        )

    stats = RuntimeStats(
        elapsed_sec=float(runtime_result.get("elapsed_sec", 0.0)),
        steps=int(runtime_result.get("steps", 0)),
        peak_memory_mb=runtime_result.get("peak_memory_mb"),
        avg_resource_load=runtime_result.get("avg_resource_load"),
        effective_candidates=int(runtime_result.get("effective_candidates", len(ranked))),
        converged=bool(runtime_result.get("converged", False)),
        diagnostics=runtime_result.get("diagnostics", {}),
    )

    return CollapseResult(
        request_id=request_id,
        status=runtime_result.get("status", "completed"),
        ranked=ranked,
        runtime_stats=stats,
        stop_reason=runtime_result.get("stop_reason", "unknown"),
        diagnostics=runtime_result.get("diagnostics", {}),
        meta=runtime_result.get("meta", {}),
    )
