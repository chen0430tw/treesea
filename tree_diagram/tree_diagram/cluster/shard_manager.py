from __future__ import annotations

"""cluster/shard_manager.py

Candidate shard manager for distributed cluster execution.

Architecture position:
  cluster layer — responsible for partitioning the candidate set into
  named shards, tracking shard status (pending/running/complete/failed),
  and reassigning failed shards.

A "shard" is a contiguous slice of the candidate list assigned to a
specific worker (rank or process).  ShardManager provides deterministic
partitioning so results can be reassembled in original candidate order.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Shard
# ---------------------------------------------------------------------------

@dataclass
class CandidateShard:
    """A contiguous slice of the candidate list for one worker."""
    shard_id:    int
    worker_id:   int               # MPI rank or thread index
    candidates:  List[Any]         # list of candidate dicts
    status:      str = "pending"   # "pending" | "running" | "complete" | "failed"
    results:     List[Any] = field(default_factory=list)
    retry_count: int = 0

    @property
    def size(self) -> int:
        return len(self.candidates)

    def is_done(self) -> bool:
        return self.status in ("complete", "failed")


# ---------------------------------------------------------------------------
# ShardManager
# ---------------------------------------------------------------------------

class ShardManager:
    """Partition candidates into shards and track execution status.

    Usage::

        sm     = ShardManager(n_workers=4)
        shards = sm.create_shards(candidates)
        # ... distribute shards ...
        sm.mark_complete(shard_id=0, results=[...])
        all_done = sm.all_complete()
        ordered  = sm.collect_ordered()
    """

    def __init__(
        self,
        n_workers:       int = 1,
        max_retries:     int = 2,
        balance_strategy: str = "round_robin",  # "round_robin" | "chunked"
    ) -> None:
        self.n_workers       = n_workers
        self.max_retries     = max_retries
        self.balance_strategy = balance_strategy
        self._shards:        Dict[int, CandidateShard] = {}
        self._original_order: List[Any] = []

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create_shards(self, candidates: List[Any]) -> List[CandidateShard]:
        """Partition candidates into shards, one per worker."""
        self._original_order = list(candidates)
        self._shards.clear()

        n = self.n_workers
        if self.balance_strategy == "chunked":
            chunk_size = max(1, len(candidates) // n)
            slices = [candidates[i:i + chunk_size] for i in range(0, len(candidates), chunk_size)]
        else:
            # Round-robin assignment
            slices = [[] for _ in range(n)]
            for i, c in enumerate(candidates):
                slices[i % n].append(c)

        shards: List[CandidateShard] = []
        for worker_id, bucket in enumerate(slices):
            if not bucket:
                continue
            shard = CandidateShard(
                shard_id=worker_id,
                worker_id=worker_id,
                candidates=bucket,
            )
            self._shards[worker_id] = shard
            shards.append(shard)

        return shards

    # ------------------------------------------------------------------
    # Status updates
    # ------------------------------------------------------------------

    def mark_running(self, shard_id: int) -> None:
        if shard_id in self._shards:
            self._shards[shard_id].status = "running"

    def mark_complete(self, shard_id: int, results: List[Any]) -> None:
        if shard_id in self._shards:
            s = self._shards[shard_id]
            s.results = results
            s.status = "complete"

    def mark_failed(self, shard_id: int, retry: bool = True) -> bool:
        """Mark a shard as failed.  Returns True if it will be retried."""
        if shard_id not in self._shards:
            return False
        s = self._shards[shard_id]
        s.retry_count += 1
        if retry and s.retry_count <= self.max_retries:
            s.status = "pending"
            return True
        s.status = "failed"
        return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def all_complete(self) -> bool:
        return all(s.is_done() for s in self._shards.values())

    def pending_shards(self) -> List[CandidateShard]:
        return [s for s in self._shards.values() if s.status == "pending"]

    def failed_shards(self) -> List[CandidateShard]:
        return [s for s in self._shards.values() if s.status == "failed"]

    def progress(self) -> Dict[str, int]:
        counts: Dict[str, int] = {"pending": 0, "running": 0, "complete": 0, "failed": 0}
        for s in self._shards.values():
            counts[s.status] = counts.get(s.status, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Result collection (order-preserving)
    # ------------------------------------------------------------------

    def collect_ordered(self) -> List[Any]:
        """Return all results in original candidate order.

        Completed shards contribute their results; failed shards contribute
        empty placeholders.
        """
        # Build a mapping: candidate index → result
        result_map: Dict[int, Any] = {}
        candidate_idx = 0

        for shard_id in sorted(self._shards.keys()):
            shard = self._shards[shard_id]
            for local_i, cand in enumerate(shard.candidates):
                if shard.status == "complete" and local_i < len(shard.results):
                    result_map[candidate_idx] = shard.results[local_i]
                else:
                    result_map[candidate_idx] = None
                candidate_idx += 1

        return [result_map.get(i) for i in range(candidate_idx)]

    def shard_summary(self) -> List[Dict]:
        return [
            {
                "shard_id":   s.shard_id,
                "worker_id":  s.worker_id,
                "size":       s.size,
                "status":     s.status,
                "retry_count": s.retry_count,
                "n_results":  len(s.results),
            }
            for s in sorted(self._shards.values(), key=lambda x: x.shard_id)
        ]
