"""MSCM — Multi-Source Semantic Collapse Model.

职责：组织多源候选、建立分层来源、计算语义特征、输出统一加权候选空间。
不做搜索。对位迁移自 archive/uploads/MOROZ代码.txt。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Sequence

from .types import Candidate, FeatureWeights, ScoreBreakdown, SourceToken, leet_variants

FeatureFn = Callable[[Candidate], float]


@dataclass
class MSCMConfig:
    beta: float = 1.0
    source_top_n: int | None = None
    leet_expand: bool = True          # 是否展开 leet speak 变体
    leet_prior_decay: float = 0.7     # 变体的先验衰减（原始 prior × decay）
    leet_max_per_token: int = 4       # 每个 token 最多产生几个变体


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
        """把五层源层合并成统一池，展开 leet 变体，保留层标签，按 prior 降序。"""
        pool = (
            list(self.common_char)
            + list(self.common_pinyin)
            + list(self.whois_domain)
            + list(self.personal)
            + list(self.context)
        )

        # Leet speak 变体展开
        if self.config.leet_expand:
            leet_tokens: list[SourceToken] = []
            seen: set[str] = {t.text for t in pool}
            for token in pool:
                for variant_text in leet_variants(token.text, self.config.leet_max_per_token):
                    if variant_text not in seen:
                        seen.add(variant_text)
                        leet_tokens.append(SourceToken(
                            text=variant_text,
                            layer=token.layer,
                            prior=token.prior * self.config.leet_prior_decay,
                            meta={**token.meta, "leet_origin": token.text},
                        ))
            pool.extend(leet_tokens)

        pool.sort(key=lambda x: x.prior, reverse=True)
        if self.config.source_top_n is not None:
            pool = pool[: self.config.source_top_n]
        return pool

    def score(self, candidate: Candidate) -> ScoreBreakdown:
        """五层特征加权评分 × 模糊对称门控。

        门控设计（Fuzzy Symmetric Gate）：

            将候选的结构质量映射为一个乘法门控值 gate ∈ [1-α, 1+α]。
            gate > 1 放大好候选，gate < 1 压制差候选，gate = 1 中性。

            quality = 跨层覆盖率 × 多样性
            gate = 1 + α × tanh(β × (quality - neutral))

            对称性：放大和压制是关于 gate=1.0 的镜像。
            模糊性：tanh 平滑，无硬门槛，连续可导。

            好候选（多层 + 不重复）→ quality 高 → gate > 1 → 分数放大
            差候选（单层 + 重复）→ quality 低 → gate < 1 → 分数压制

        这是 CFPAI Maxwell Demon 的镜像设计：
            Maxwell Demon：momentum × vol_asymmetry → gate → linear × gate
            Fuzzy Symmetric Gate：cross_layer × diversity → gate → linear × gate
        """
        f = self.phi_freq(candidate)
        d = self.phi_domain(candidate)
        p = self.phi_personal(candidate)
        c = self.phi_context(candidate)
        s = self.phi_syntax(candidate)

        linear = (
            self.weights.freq * f
            + self.weights.domain * d
            + self.weights.personal * p
            + self.weights.context * c
            + self.weights.syntax * s
        )

        # 候选质量信号
        if candidate.tokens:
            # 跨层覆盖率：n_layers / max_possible_layers，归一化到 [0, 1]
            layers_present = {t.layer for t in candidate.tokens}
            cross_ratio = len(layers_present) / 5.0  # 5 层满分

            # 多样性：不同 token / 总 token，[0, 1]
            unique_texts = {t.text for t in candidate.tokens}
            diversity = len(unique_texts) / len(candidate.tokens)

            # quality = 两者的几何平均，[0, 1]
            quality = math.sqrt(cross_ratio * diversity)
        else:
            quality = 0.0

        # 模糊对称门控
        alpha = self.weights.gate_alpha
        neutral = self.weights.gate_neutral
        beta = 3.0  # tanh 陡峭度
        gate = 1.0 + alpha * math.tanh(beta * (quality - neutral))

        total = linear * gate

        return ScoreBreakdown(
            freq=f, domain=d, personal=p, context=c, syntax=s,
            quality=round(quality, 4), gate=round(gate, 4),
            total=total,
        )

    def weight(self, candidate: Candidate) -> float:
        """温度缩放指数权重。"""
        return math.exp(self.config.beta * self.score(candidate).total)
