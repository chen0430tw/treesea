# serialization.py
from __future__ import annotations
from dataclasses import asdict
from .request import CollapseRequest, BudgetSpec, StopPolicy
from .result import CollapseResult, RuntimeStats
from .types import FrontierCandidate, CollapseCandidate

def to_dict(obj):
    return asdict(obj)

def request_from_dict(data: dict) -> CollapseRequest:
    candidates = [FrontierCandidate(**c) for c in data["candidates"]]
    budget = BudgetSpec(**data["budget"])
    stop_policy = StopPolicy(**data.get("stop_policy", {}))
    return CollapseRequest(
        request_id=data["request_id"],
        task_id=data["task_id"],
        profile=data["profile"],
        candidates=candidates,
        budget=budget,
        mapping_policy=data.get("mapping_policy", "default"),
        stop_policy=stop_policy,
        issuer=data.get("issuer", "moroz"),
        trace_enabled=data.get("trace_enabled", False),
        diagnostics_level=data.get("diagnostics_level", 1),
        meta=data.get("meta", {}),
    )

def result_from_dict(data: dict) -> CollapseResult:
    ranked = [CollapseCandidate(**c) for c in data["ranked"]]
    runtime_stats = RuntimeStats(**data["runtime_stats"])
    return CollapseResult(
        request_id=data["request_id"],
        status=data["status"],
        ranked=ranked,
        runtime_stats=runtime_stats,
        stop_reason=data.get("stop_reason", "unknown"),
        diagnostics=data.get("diagnostics", {}),
        meta=data.get("meta", {}),
    )
