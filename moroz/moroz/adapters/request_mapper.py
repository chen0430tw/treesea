# request_mapper.py
from __future__ import annotations
from dataclasses import dataclass, field
from moroz.contracts.request import CollapseRequest
from .qcu_mapping_rules import map_candidate_features, choose_profile

@dataclass
class RuntimeConfig:
    request_id: str
    profile: str
    mapped_candidates: list[dict]
    iqpu_config: dict = field(default_factory=dict)
    collapse_policy: dict = field(default_factory=dict)
    readout_policy: dict = field(default_factory=dict)
    opu_policy: dict = field(default_factory=dict)
    budget: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

def map_request(req: CollapseRequest) -> RuntimeConfig:
    mapped_candidates = []
    for idx, cand in enumerate(req.candidates):
        mapped_candidates.append({
            "candidate_id": idx,
            "text": cand.text,
            "base_score": cand.base_score,
            "source_layers": cand.source_layers,
            "mapped": map_candidate_features(cand),
            "meta": cand.meta,
        })

    profile = choose_profile(req.profile)
    return RuntimeConfig(
        request_id=req.request_id,
        profile=profile,
        mapped_candidates=mapped_candidates,
        iqpu_config={"profile": profile},
        collapse_policy={"trace_enabled": req.trace_enabled},
        readout_policy={"top_k": min(len(mapped_candidates), req.budget.max_candidates or len(mapped_candidates))},
        opu_policy={"enable_early_stop": req.stop_policy.enable_early_stop},
        budget={
            "max_candidates": req.budget.max_candidates,
            "max_steps": req.budget.max_steps,
            "max_wall_time_sec": req.budget.max_wall_time_sec,
        },
        meta=req.meta,
    )
