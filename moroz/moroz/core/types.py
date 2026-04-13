"""MOROZ-Core 核心类型定义。对位迁移自 archive/uploads/MOROZ代码.txt。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

LayerName = Literal[
    "common_char",
    "common_pinyin",
    "whois_domain",
    "personal",
    "context",
]


@dataclass(frozen=True)
class SourceToken:
    text: str
    layer: LayerName
    prior: float = 1.0
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Candidate:
    tokens: tuple[SourceToken, ...]

    @property
    def text(self) -> str:
        return "".join(t.text for t in self.tokens)

    def extend(self, token: SourceToken) -> "Candidate":
        return Candidate(tokens=self.tokens + (token,))

    def __lt__(self, other: "Candidate") -> bool:
        return self.text < other.text


@dataclass
class FeatureWeights:
    freq: float = 1.0
    domain: float = 1.0
    personal: float = 1.0
    context: float = 1.0
    syntax: float = 1.0


@dataclass
class ScoreBreakdown:
    freq: float
    domain: float
    personal: float
    context: float
    syntax: float
    total: float


@dataclass
class SearchMetrics:
    expanded: int = 0
    reject_prefix: int = 0
    reject_full: int = 0
    reject_structure: int = 0
    reject_bound: int = 0
    accepted: int = 0
