from __future__ import annotations

"""cluster/mpi_dispatch.py

MPI rank dispatcher for cluster-level candidate distribution.

Architecture position:
  cluster layer — provides explicit MPI rank management on top of
  distributed/mpi_adapter.MPIEnsembleRunner.  While mpi_adapter.py
  handles generic task lists, MPIDispatcher is specialised for
  Tree Diagram candidate batches with structured scatter/gather.

Features:
  - Rank-aware candidate partitioning (deterministic shard assignment)
  - Barrier synchronisation before gather
  - Rank-0 aggregation and result ordering
  - Graceful degradation to single-process if mpi4py is absent
"""

from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Rank info
# ---------------------------------------------------------------------------

def _get_mpi_info() -> Tuple[int, int, Any]:
    """Return (rank, size, comm).  Falls back to (0, 1, None) without mpi4py."""
    try:
        from mpi4py import MPI
        comm = MPI.COMM_WORLD
        return comm.Get_rank(), comm.Get_size(), comm
    except ImportError:
        return 0, 1, None


# ---------------------------------------------------------------------------
# MPIDispatcher
# ---------------------------------------------------------------------------

class MPIDispatcher:
    """Distribute candidate evaluation across MPI ranks.

    Usage::

        dispatcher = MPIDispatcher()
        results    = dispatcher.dispatch(candidates, eval_fn)
    """

    def __init__(self, fallback_workers: int = 1) -> None:
        self._fallback_workers = fallback_workers
        self._rank, self._size, self._comm = _get_mpi_info()

    @property
    def rank(self) -> int:
        return self._rank

    @property
    def size(self) -> int:
        return self._size

    @property
    def is_root(self) -> bool:
        return self._rank == 0

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    def dispatch(
        self,
        candidates: List[Any],
        eval_fn:    Callable[[List[Any]], List[Any]],
    ) -> List[Any]:
        """Distribute candidates to all ranks, evaluate, and gather at rank 0.

        eval_fn receives a *list* of candidates (the local shard) and must
        return a list of the same length with evaluated results.

        Returns the full gathered list at rank 0; returns [] at other ranks.
        """
        if self._comm is None or self._size == 1:
            return self._serial_dispatch(candidates, eval_fn)

        return self._mpi_dispatch(candidates, eval_fn)

    # ------------------------------------------------------------------
    # MPI dispatch
    # ------------------------------------------------------------------

    def _mpi_dispatch(
        self,
        candidates: List[Any],
        eval_fn:    Callable[[List[Any]], List[Any]],
    ) -> List[Any]:
        comm = self._comm

        # Root partitions candidates into shards
        if self._rank == 0:
            shards = self._partition(candidates, self._size)
        else:
            shards = None

        # Scatter shards to all ranks
        local_shard = comm.scatter(shards, root=0)

        # Each rank evaluates its shard
        local_results = eval_fn(local_shard)

        # Barrier
        comm.Barrier()

        # Gather at root
        all_results = comm.gather(local_results, root=0)

        if self._rank == 0 and all_results:
            merged: List[Any] = []
            for chunk in all_results:
                merged.extend(chunk)
            return merged
        return []

    # ------------------------------------------------------------------
    # Serial fallback (with optional multiprocessing)
    # ------------------------------------------------------------------

    def _serial_dispatch(
        self,
        candidates: List[Any],
        eval_fn:    Callable[[List[Any]], List[Any]],
    ) -> List[Any]:
        if self._fallback_workers > 1:
            import multiprocessing
            shards = self._partition(candidates, self._fallback_workers)
            with multiprocessing.Pool(processes=self._fallback_workers) as pool:
                results = pool.map(eval_fn, shards)
            merged: List[Any] = []
            for chunk in results:
                merged.extend(chunk)
            return merged
        # Single-process
        return eval_fn(candidates)

    # ------------------------------------------------------------------
    # Partitioning
    # ------------------------------------------------------------------

    @staticmethod
    def _partition(items: List[Any], n: int) -> List[List[Any]]:
        """Split items into n roughly equal shards."""
        shards: List[List[Any]] = [[] for _ in range(n)]
        for i, item in enumerate(items):
            shards[i % n].append(item)
        return shards

    # ------------------------------------------------------------------
    # Broadcast helpers
    # ------------------------------------------------------------------

    def broadcast(self, obj: Any, root: int = 0) -> Any:
        """Broadcast an object from root to all ranks."""
        if self._comm is None:
            return obj
        return self._comm.bcast(obj, root=root)

    def barrier(self) -> None:
        """Synchronise all ranks."""
        if self._comm is not None:
            self._comm.Barrier()

MPIDispatch = MPIDispatcher  # alias for test compatibility
