"""MSCM — Multi-Source Semantic Collapse Model.

职责：组织多源候选、建立分层来源、计算语义特征、输出统一加权候选空间。
不做搜索。对位迁移自 archive/uploads/MOROZ代码.txt。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Sequence

from .types import Candidate, FeatureWeights, ScoreBreakdown, SourceToken

FeatureFn = Callable[[Candidate], float]


@dataclass
class MSCMConfig:
    beta: float = 1.0
    source_top_n: int | None = None


@dataclass
class MSCM:
    common_char: Sequence[SourceToken]
    common_pinyin: Sequence[SourceToken]
    whois_domain: Sequence[SourceToken]
    personal: Sequence[SourceToken]
    context: Sequence[SourceToken]
    weights: FeatureWeights
    phi_freq: FeatureFn
    phi_domain: FeatureFn
    phi_personal: FeatureFn
    phi_context: FeatureFn
    phi_syntax: FeatureFn
    config: MSCMConfig = field(default_factory=MSCMConfig)

    def build_source_pool(self) -> list[SourceToken]:
        """把五层源层合并成统一池，保留层标签，按 prior 降序。"""
        pool = (
            list(self.common_char)
            + list(self.common_pinyin)
            + list(self.whois_domain)
            + list(self.personal)
            + list(self.context)
        )
        pool.sort(key=lambda x: x.prior, reverse=True)
        if self.config.source_top_n is not None:
            pool = pool[: self.config.source_top_n]
        return pool

    def score(self, candidate: Candidate) -> ScoreBreakdown:
        """五层特征加权评分。"""
        f = self.phi_freq(candidate)
        d = self.phi_domain(candidate)
        p = self.phi_personal(candidate)
        c = self.phi_context(candidate)
        s = self.phi_syntax(candidate)

        total = (
            self.weights.freq * f
            + self.weights.domain * d
            + self.weights.personal * p
            + self.weights.context * c
            + self.weights.syntax * s
        )
        return ScoreBreakdown(
            freq=f, domain=d, personal=p, context=c, syntax=s, total=total,
        )

    def weight(self, candidate: Candidate) -> float:
        """温度缩放指数权重。"""
        return math.exp(self.config.beta * self.score(candidate).total)
