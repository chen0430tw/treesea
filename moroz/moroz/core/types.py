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
    "external",
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


# ================================================================
# Leet Speak 替换规则
# ================================================================

LEET_MAP: dict[str, list[str]] = {
    "o": ["0"],
    "O": ["0"],
    "0": ["o", "O"],
    "i": ["1", "l", "I"],
    "I": ["1", "l", "i"],
    "l": ["1", "I", "i"],
    "1": ["l", "I", "i"],
    "e": ["3"],
    "E": ["3"],
    "3": ["e", "E"],
    "a": ["@", "4"],
    "A": ["@", "4"],
    "s": ["$", "5"],
    "S": ["$", "5"],
    "t": ["7"],
    "T": ["7"],
    "g": ["9"],
    "G": ["9"],
    "b": ["8"],
    "B": ["8"],
}


def leet_variants(text: str, max_variants: int = 8) -> list[str]:
    """生成 leet speak 变体。

    单字符替换：每次只替换一个位置，避免组合爆炸。
    例如 "look" → ["l00k", "1ook"]
    """
    variants: list[str] = []
    for i, ch in enumerate(text):
        for replacement in LEET_MAP.get(ch, []):
            v = text[:i] + replacement + text[i + 1:]
            if v != text and v not in variants:
                variants.append(v)
                if len(variants) >= max_variants:
                    return variants
    return variants


@dataclass
class FeatureWeights:
    freq: float = 1.0
    domain: float = 1.0
    personal: float = 1.0
    context: float = 1.0
    syntax: float = 1.0
    gate_alpha: float = 0.6      # 门控幅度：gate ∈ [1-alpha, 1+alpha]
    gate_neutral: float = 0.5    # 模糊对称中性点：quality == neutral → gate = 1.0


@dataclass
class ScoreBreakdown:
    freq: float
    domain: float
    personal: float
    context: float
    syntax: float
    quality: float = 0.0         # 候选质量信号（跨层 + 多样性）
    gate: float = 1.0            # 模糊对称门控值
    total: float = 0.0


@dataclass
class SearchMetrics:
    expanded: int = 0
    reject_prefix: int = 0
    reject_full: int = 0
    reject_structure: int = 0
    reject_bound: int = 0
    accepted: int = 0


# ================================================================
# Core ↔ Contracts 类型桥接
# ================================================================

@dataclass
class FrontierCandidate:
    """协议层候选（API 输入输出格式）。

    与 core.Candidate 的区别：
    - FrontierCandidate 是扁平的（text + score + features），适合序列化
    - Candidate 是结构化的（tokens 元组），适合搜索树
    """
    text: str
    base_score: float
    source_layers: list[str] = field(default_factory=list)
    features: dict[str, float] = field(default_factory=dict)
    template_tags: list[str] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)


@dataclass
class CollapseCandidate:
    """协议层坍缩结果（ISSC 输出格式）。"""
    text: str
    base_score: float
    collapse_score: float
    final_score: float
    trace_summary: dict = field(default_factory=dict)
    source_layers: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def candidate_to_frontier(candidate: Candidate, score: float = 0.0) -> FrontierCandidate:
    """Core Candidate → 协议层 FrontierCandidate。"""
    layers = list({t.layer for t in candidate.tokens})
    provenance = {}
    for i, t in enumerate(candidate.tokens):
        provenance[f"token_{i}"] = {"text": t.text, "layer": t.layer, "prior": t.prior}
        if t.meta:
            provenance[f"token_{i}"]["meta"] = t.meta
    return FrontierCandidate(
        text=candidate.text,
        base_score=score,
        source_layers=layers,
        features={},
        provenance=provenance,
        meta={},
    )


def frontier_to_candidate(fc: FrontierCandidate) -> Candidate:
    """协议层 FrontierCandidate → Core Candidate。

    注意：FrontierCandidate 是扁平的，无法完美还原 token 序列。
    将整个 text 作为单个 SourceToken，层取 source_layers[0]。
    """
    layer = fc.source_layers[0] if fc.source_layers else "external"
    token = SourceToken(
        text=fc.text,
        layer=layer,
        prior=fc.base_score,
        meta=fc.meta,
    )
    return Candidate(tokens=(token,))


def ranked_to_collapse(
    ranked: list[tuple[float, Candidate]],
    score_fn=None,
) -> list[CollapseCandidate]:
    """ISSC ranked 结果 → 协议层 CollapseCandidate 列表。"""
    results = []
    for score, cand in ranked:
        base = sum(t.prior for t in cand.tokens) / max(len(cand.tokens), 1)
        results.append(CollapseCandidate(
            text=cand.text,
            base_score=round(base, 4),
            collapse_score=round(score, 4),
            final_score=round(score, 4),
            source_layers=list({t.layer for t in cand.tokens}),
            meta={},
        ))
    return results
