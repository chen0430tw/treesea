"""K-Warehouse — 候选压缩与分层调度框架。

职责：SKU 精选、前缀扩展、Gate 剪枝、上界估计、Top-K 排序、预算控制。
不做运行时资产管理。对位迁移自 archive/uploads/MOROZ代码.txt。
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from .types import Candidate, SearchMetrics, SourceToken

PrefixGate = Callable[[Candidate], bool]
FullGate = Callable[[Candidate], bool]
UpperBoundFn = Callable[[Candidate], float]
StructureFn = Callable[[Candidate], bool]
ScoreFn = Callable[[Candidate], float]


@dataclass
class KWConfig:
    max_len: int
    budget: int = 10000
    top_k: int = 50


@dataclass
class KWResult:
    top: list[tuple[float, Candidate]]
    metrics: SearchMetrics


class KWarehouse:
    def __init__(
        self,
        source_pool: Sequence[SourceToken],
        score_fn: ScoreFn,
        upper_bound_fn: UpperBoundFn,
        prefix_gate: PrefixGate,
        full_gate: FullGate,
        structure_valid: StructureFn,
        config: KWConfig,
    ) -> None:
        self.source_pool = list(source_pool)
        self.score_fn = score_fn
        self.upper_bound_fn = upper_bound_fn
        self.prefix_gate = prefix_gate
        self.full_gate = full_gate
        self.structure_valid = structure_valid
        self.config = config

    def run(self, seeds: Iterable[Candidate] | None = None) -> KWResult:
        """Best-first 搜索主循环。"""
        pq: list[tuple[float, int, Candidate]] = []
        top: list[tuple[float, Candidate]] = []
        metrics = SearchMetrics()
        counter = 0

        if seeds is None:
            seeds = [Candidate(tokens=())]

        for seed in seeds:
            ub = self.upper_bound_fn(seed)
            heapq.heappush(pq, (-ub, counter, seed))
            counter += 1

        while pq and metrics.accepted < self.config.budget:
            _, _, cand = heapq.heappop(pq)

            # Prefix gate (ISSC: fail-fast)
            if not self.prefix_gate(cand):
                metrics.reject_prefix += 1
                continue

            # Complete candidate: full scoring
            if len(cand.tokens) >= self.config.max_len:
                if not self.full_gate(cand):
                    metrics.reject_full += 1
                    continue
                score = self.score_fn(cand)
                self._push_top(top, score, cand)
                metrics.accepted += 1
                continue

            # Prefix expansion
            for token in self.source_pool:
                child = cand.extend(token)
                if not self.structure_valid(child):
                    metrics.reject_structure += 1
                    continue

                ub = self.upper_bound_fn(child)

                # K-Warehouse: prune branches that can't enter top-K
                if len(top) >= self.config.top_k and ub < top[0][0]:
                    metrics.reject_bound += 1
                    continue

                heapq.heappush(pq, (-ub, counter, child))
                counter += 1
                metrics.expanded += 1

        top.sort(key=lambda x: x[0], reverse=True)
        return KWResult(top=top, metrics=metrics)

    def _push_top(
        self, top: list[tuple[float, Candidate]], score: float, cand: Candidate
    ) -> None:
        if len(top) < self.config.top_k:
            heapq.heappush(top, (score, cand))
        elif score > top[0][0]:
            heapq.heapreplace(top, (score, cand))
