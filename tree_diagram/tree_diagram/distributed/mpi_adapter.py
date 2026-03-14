from __future__ import annotations
from typing import Callable, List


class MPIEnsembleRunner:
    def __init__(self, n_workers: int = 1) -> None:
        self.n_workers = n_workers
        self.comm = None
        try:
            from mpi4py import MPI
            self.comm = MPI.COMM_WORLD
            self.use_mpi = True
        except ImportError:
            self.use_mpi = False

    def run(self, tasks: list, fn: Callable) -> list:
        if self.use_mpi and self.comm is not None and self.comm.Get_size() > 1:
            return self._run_mpi(tasks, fn)
        elif self.n_workers > 1:
            return self._run_pool(tasks, fn)
        else:
            return [fn(t) for t in tasks]

    def _run_mpi(self, tasks: list, fn: Callable) -> list:
        from mpi4py import MPI
        comm = self.comm
        rank = comm.Get_rank()
        size = comm.Get_size()

        if rank == 0:
            # Scatter tasks
            chunks = [[] for _ in range(size)]
            for i, task in enumerate(tasks):
                chunks[i % size].append(task)
        else:
            chunks = None

        local_tasks = comm.scatter(chunks, root=0)
        local_results = [fn(t) for t in local_tasks]
        all_results = comm.gather(local_results, root=0)

        if rank == 0:
            merged: list = []
            for chunk in all_results:
                merged.extend(chunk)
            return merged
        else:
            return []

    def _run_pool(self, tasks: list, fn: Callable) -> list:
        import multiprocessing
        with multiprocessing.Pool(processes=self.n_workers) as pool:
            return pool.map(fn, tasks)
