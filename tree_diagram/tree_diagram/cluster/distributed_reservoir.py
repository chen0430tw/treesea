from __future__ import annotations

"""cluster/distributed_reservoir.py

Distributed state reservoir for multi-node Tree Diagram execution.

Architecture position:
  cluster layer — provides a shared state pool that aggregates partial
  results from all MPI ranks.  Acts as the distributed equivalent of
  runtime/state_store.py, but designed for in-flight aggregation rather
  than persistence.

The reservoir accumulates:
  - Evaluated candidate results from each rank
  - IPL state snapshots for incremental phase indexing
  - Hydro control signals from distributed sub-runs
  - Governance events for global safety tracking

Results are merged at rank 0 via MPI gather; an in-memory fallback is
provided when mpi4py is not available.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Reservoir entry
# ---------------------------------------------------------------------------

@dataclass
class ReservoirEntry:
    """A single accumulated result entry."""
    rank:        int
    shard_id:    int
    candidate_id: str
    score:       float
    status:      str
    payload:     Dict[str, Any]
    timestamp:   float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# DistributedReservoir
# ---------------------------------------------------------------------------

class DistributedReservoir:
    """Accumulate and merge distributed evaluation results.

    Usage::

        reservoir = DistributedReservoir()
        reservoir.add(rank=0, shard_id=0, entries=[...])
        merged    = reservoir.gather_and_merge()
        top_k     = reservoir.top_k(k=12)
    """

    def __init__(self, rank: int = 0, size: int = 1) -> None:
        self._rank  = rank
        self._size  = size
        self._local: List[ReservoirEntry] = []
        self._comm  = None
        self._ipl_snapshots: List[Dict[str, Any]] = []
        self._hydro_signals: List[Dict[str, Any]] = []
        self._governance_events: List[Dict[str, Any]] = []

        try:
            from mpi4py import MPI
            self._comm = MPI.COMM_WORLD
            self._rank = self._comm.Get_rank()
            self._size = self._comm.Get_size()
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Add local results
    # ------------------------------------------------------------------

    def add(
        self,
        entries: List[ReservoirEntry],
        ipl_snapshot: Optional[Dict[str, Any]] = None,
        hydro_signal: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Accumulate results from the local rank."""
        self._local.extend(entries)
        if ipl_snapshot:
            self._ipl_snapshots.append({**ipl_snapshot, "rank": self._rank})
        if hydro_signal:
            self._hydro_signals.append({**hydro_signal, "rank": self._rank})

    def add_governance_event(self, state: str, p_blow: float, step: int) -> None:
        self._governance_events.append({
            "rank":    self._rank,
            "state":   state,
            "p_blow":  p_blow,
            "step":    step,
            "ts":      time.time(),
        })

    # ------------------------------------------------------------------
    # Gather and merge (rank 0 collects from all ranks)
    # ------------------------------------------------------------------

    def gather_and_merge(self) -> List[ReservoirEntry]:
        """Gather all local entries to rank 0 and return merged list."""
        if self._comm is None or self._size == 1:
            return list(self._local)

        all_locals = self._comm.gather(self._local, root=0)

        if self._rank == 0 and all_locals:
            merged: List[ReservoirEntry] = []
            for chunk in all_locals:
                merged.extend(chunk)
            return merged
        return []

    def gather_hydro(self) -> List[Dict[str, Any]]:
        """Gather hydro signals from all ranks at rank 0."""
        if self._comm is None or self._size == 1:
            return list(self._hydro_signals)

        all_signals = self._comm.gather(self._hydro_signals, root=0)
        if self._rank == 0 and all_signals:
            merged: List[Dict[str, Any]] = []
            for chunk in all_signals:
                merged.extend(chunk)
            return merged
        return []

    def aggregate_hydro(self) -> Dict[str, float]:
        """Compute mean hydro pressure_balance across all signals."""
        signals = self.gather_hydro()
        if not signals:
            return {"pressure_balance": 1.0, "n_signals": 0}
        pb_values = [s.get("pressure_balance", 1.0) for s in signals]
        return {
            "pressure_balance": sum(pb_values) / len(pb_values),
            "n_signals":        len(pb_values),
            "min_pb":           min(pb_values),
            "max_pb":           max(pb_values),
        }

    # ------------------------------------------------------------------
    # Top-k selection
    # ------------------------------------------------------------------

    def top_k(self, k: int = 12) -> List[ReservoirEntry]:
        """Return top-k entries by score from the local store."""
        sorted_entries = sorted(self._local, key=lambda e: e.score, reverse=True)
        return sorted_entries[:k]

    def top_k_merged(self, k: int = 12) -> List[ReservoirEntry]:
        """Gather all entries from all ranks and return top-k at rank 0."""
        merged = self.gather_and_merge()
        return sorted(merged, key=lambda e: e.score, reverse=True)[:k]

    # ------------------------------------------------------------------
    # Worst-case governance
    # ------------------------------------------------------------------

    def worst_governance(self) -> Dict[str, Any]:
        """Return the most severe governance event from all ranks."""
        if self._comm and self._size > 1:
            all_events = self._comm.gather(self._governance_events, root=0)
            if self._rank == 0 and all_events:
                events: List[Dict] = []
                for chunk in all_events:
                    events.extend(chunk)
            else:
                events = []
        else:
            events = list(self._governance_events)

        if not events:
            return {"state": "NORMAL", "p_blow": 0.0}

        priority = {"CRACKDOWN": 2, "NEGOTIATE": 1, "NORMAL": 0}
        worst = max(events, key=lambda e: priority.get(e.get("state", "NORMAL"), 0))
        return {"state": worst["state"], "p_blow": worst["p_blow"]}

    # ------------------------------------------------------------------
    # State summary
    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        return {
            "rank":               self._rank,
            "size":               self._size,
            "local_entries":      len(self._local),
            "ipl_snapshots":      len(self._ipl_snapshots),
            "hydro_signals":      len(self._hydro_signals),
            "governance_events":  len(self._governance_events),
        }

    def clear(self) -> None:
        self._local.clear()
        self._ipl_snapshots.clear()
        self._hydro_signals.clear()
        self._governance_events.clear()
