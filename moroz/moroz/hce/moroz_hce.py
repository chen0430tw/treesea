"""MOROZ-HCE — 运行时编排层。

职责：分片、调度、checkpoint、runs/logs/results、恢复、全局汇总。
不碰 MSCM/K-Warehouse/ISSC 本体。对位迁移自 archive/uploads/MOROZ代码.txt。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from moroz.core.moroz_core import MOROZCore, MOROZCoreConfig, MOROZCoreResult


@dataclass
class ShardConfig:
    mode: str = "prefix"   # "prefix" / "template" / "hash-range"
    num_shards: int = 4


@dataclass
class RuntimeConfig:
    max_retries: int = 2


@dataclass
class ShardSpec:
    shard_id: int
    seeds: list  # list of seed Candidates for this shard


@dataclass
class HCEResult:
    run_id: str
    run_dir: str
    global_top: list
    shard_results: list
    elapsed_seconds: float


class MOROZHCE:
    """
    MOROZ-HCE = 分片 -> 调度 -> MOROZ-Core -> checkpoint -> 全局汇总

    使用方式：
        hce = MOROZHCE(core_factory=..., base_dir="moroz/runs")
        result = hce.run(shards=..., runtime_config=...)
    """

    def __init__(
        self,
        core_factory,  # Callable[[ShardSpec], MOROZCore]
        base_dir: str = "moroz/runs",
    ) -> None:
        self.core_factory = core_factory
        self.base_dir = Path(base_dir)

    def run(
        self,
        shards: Sequence[ShardSpec],
        runtime_config: RuntimeConfig = RuntimeConfig(),
    ) -> HCEResult:
        # Stage 0: 初始化运行目录
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        run_dir = self.base_dir / run_id
        for subdir in ["logs", "results", "checkpoints", "metrics"]:
            (run_dir / subdir).mkdir(parents=True, exist_ok=True)

        t0 = time.perf_counter()
        global_top = []
        shard_results = []

        # Stage 1-2: 调度每个 shard
        for shard in shards:
            # 恢复检查点
            state = self._try_restore_checkpoint(run_dir, shard)

            # 执行 MOROZ-Core
            retries = 0
            result = None
            while retries <= runtime_config.max_retries:
                try:
                    core = self.core_factory(shard)
                    result = core.run()
                    break
                except Exception as e:
                    retries += 1
                    if retries > runtime_config.max_retries:
                        self._mark_failed(run_dir, shard, str(e))
                        break

            if result is None:
                continue

            # 落盘
            self._save_checkpoint(run_dir, shard, result)
            self._save_results(run_dir, shard, result)
            shard_results.append(result)

            # 汇总到全局 top
            for score, cand in result.issc_result.ranked:
                global_top.append((score, cand))

        # Stage 3: 全局排序
        global_top.sort(key=lambda x: x[0], reverse=True)

        elapsed = time.perf_counter() - t0

        # 写 summary
        summary = {
            "run_id": run_id,
            "num_shards": len(shards),
            "completed": len(shard_results),
            "global_top_k": len(global_top),
            "elapsed_seconds": elapsed,
        }
        with open(run_dir / "summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        return HCEResult(
            run_id=run_id,
            run_dir=str(run_dir),
            global_top=global_top,
            shard_results=shard_results,
            elapsed_seconds=elapsed,
        )

    def _try_restore_checkpoint(self, run_dir: Path, shard: ShardSpec):
        ckpt = run_dir / "checkpoints" / f"shard_{shard.shard_id}.json"
        if ckpt.exists():
            with open(ckpt) as f:
                return json.load(f)
        return None

    def _save_checkpoint(self, run_dir: Path, shard: ShardSpec, result: MOROZCoreResult):
        ckpt = run_dir / "checkpoints" / f"shard_{shard.shard_id}.json"
        data = {
            "shard_id": shard.shard_id,
            "accepted": result.kw_result.metrics.accepted,
            "elapsed": result.elapsed_seconds,
            "top_count": len(result.issc_result.ranked),
        }
        with open(ckpt, "w") as f:
            json.dump(data, f, indent=2)

    def _save_results(self, run_dir: Path, shard: ShardSpec, result: MOROZCoreResult):
        out = run_dir / "results" / f"shard_{shard.shard_id}.json"
        data = {
            "shard_id": shard.shard_id,
            "top": [(s, c.text) for s, c in result.issc_result.ranked],
            "stats": {
                "entropy": result.issc_result.stats.entropy,
                "top_q_coverage": result.issc_result.stats.top_q_coverage,
                "retention_ratio": result.issc_result.stats.retention_ratio,
                "theta_eff": result.issc_result.stats.theta_eff,
            },
            "elapsed": result.elapsed_seconds,
        }
        with open(out, "w") as f:
            json.dump(data, f, indent=2)

    def _mark_failed(self, run_dir: Path, shard: ShardSpec, error: str):
        fail = run_dir / "logs" / f"shard_{shard.shard_id}_FAILED.txt"
        with open(fail, "w") as f:
            f.write(f"shard_id: {shard.shard_id}\nerror: {error}\n")
