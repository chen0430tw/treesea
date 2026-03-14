# state.py
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class RuntimeState:
    request_id: str
    step: int
    elapsed_sec: float
    active_candidates: int
    collapse_score: float
    phase_dispersion: float
    attractor_density: float
    quality_signal: float
    resource_load: float
    diagnostics: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
