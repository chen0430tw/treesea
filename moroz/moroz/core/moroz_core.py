"""MOROZ-Core — 串起 MSCM + K-Warehouse + ISSC 的最小闭环。

不碰 HCE。对位迁移自 archive/uploads/MOROZ代码.txt。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterable

from .issc import ISSC, ISSCResult
from .k_warehouse import KWConfig, KWResult, KWarehouse
from .mscm import MSCM
from .types import Candidate

PrefixGate = Callable[[Candidate], bool]
FullGate = Callable[[Candidate], bool]
StructureFn = Callable[[Candidate], bool]
SeedBuilder = Callable[[], Iterable[Candidate]]


@dataclass
class MOROZCoreConfig:
    max_len: int
    budget: int = 10000
    top_k: int = 50
    collapse_q: int = 5


@dataclass
class MOROZCoreResult:
    kw_result: KWResult
    issc_result: ISSCResult
    elapsed_seconds: float


class MOROZCore:
    """
    MOROZ-Core = MSCM -> K-Warehouse -> ISSC

    责任边界：
    - MSCM: 多源候选建模与评分
    - K-Warehouse: 候选压缩、搜索、Top-K
    - ISSC: 收缩统计与原地坍缩观测
    """

    def __init__(
        self,
        mscm: MSCM,
        config: MOROZCoreConfig,
        prefix_gate: PrefixGate,
        full_gate: FullGate,
        structure_valid: StructureFn,
        seed_builder: SeedBuilder | None = None,
    ) -> None:
        self.mscm = mscm
        self.config = config
        self.prefix_gate = prefix_gate
        self.full_gate = full_gate
        self.structure_valid = structure_valid
        self.seed_builder = seed_builder or self._default_seed_builder

    def run(self) -> MOROZCoreResult:
        """
        运行完整 MOROZ-Core 闭环：
        1) MSCM 构建 source pool
        2) K-Warehouse 做压缩搜索
        3) ISSC 做收缩统计
        """
        t0 = time.perf_counter()

        source_pool = self.mscm.build_source_pool()

        kw = KWarehouse(
            source_pool=source_pool,
            score_fn=self._score_fn,
            upper_bound_fn=self._upper_bound_fn,
            prefix_gate=self.prefix_gate,
            full_gate=self.full_gate,
            structure_valid=self.structure_valid,
            config=KWConfig(
                max_len=self.config.max_len,
                budget=self.config.budget,
                top_k=self.config.top_k,
            ),
        )

        seeds = list(self.seed_builder())
        kw_result = kw.run(seeds=seeds)

        t1 = time.perf_counter()

        issc = ISSC(q=self.config.collapse_q)
        issc_result = issc.collapse(
            ranked=kw_result.top,
            metrics=kw_result.metrics,
            elapsed_seconds=t1 - t0,
        )

        return MOROZCoreResult(
            kw_result=kw_result,
            issc_result=issc_result,
            elapsed_seconds=t1 - t0,
        )

    def explain_candidate(self, candidate: Candidate) -> dict:
        """给单个候选输出 MSCM 五层评分拆解。"""
        breakdown = self.mscm.score(candidate)
        return {
            "text": candidate.text,
            "freq": breakdown.freq,
            "domain": breakdown.domain,
            "personal": breakdown.personal,
            "context": breakdown.context,
            "syntax": breakdown.syntax,
            "total": breakdown.total,
            "weight": self.mscm.weight(candidate),
        }

    def _score_fn(self, candidate: Candidate) -> float:
        return self.mscm.score(candidate).total

    def _upper_bound_fn(self, candidate: Candidate) -> float:
        current = self._score_fn(candidate)
        remain = max(0, self.config.max_len - len(candidate.tokens))
        max_gain_per_step = 1.0
        return current + remain * max_gain_per_step

    def _default_seed_builder(self) -> Iterable[Candidate]:
        yield Candidate(tokens=())
