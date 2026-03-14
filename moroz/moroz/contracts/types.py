# types.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal

LayerName = Literal["common_char", "common_pinyin", "whois_domain", "personal", "context", "external"]

@dataclass
class FrontierCandidate:
    text: str
    base_score: float
    source_layers: list[LayerName] = field(default_factory=list)
    features: dict[str, float] = field(default_factory=dict)
    template_tags: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

@dataclass
class CollapseCandidate:
    text: str
    base_score: float
    collapse_score: float
    final_score: float
    trace_summary: dict[str, Any] = field(default_factory=dict)
    source_layers: list[LayerName] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
