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
            chunks = [[] for _ in range(size)]
            for i, task in enumerate(tasks):
                chunks[i % size].append(task)
        else:
            chunks = None

        try:
            local_tasks = comm.scatter(chunks, root=0)
        except Exception as exc:
            raise RuntimeError(
                f"[MPIEnsembleRunner] scatter failed on rank {rank}: {exc}"
            ) from exc

        local_results = []
        errors: list = []
        for t in local_tasks:
            try:
                local_results.append(fn(t))
            except Exception as exc:
                errors.append((t, repr(exc)))

        if errors:
            import warnings
            for task, msg in errors:
                warnings.warn(
                    f"[MPIEnsembleRunner] rank {rank} task {task!r} failed: {msg}",
                    RuntimeWarning,
                    stacklevel=2,
                )

        try:
            all_results = comm.gather(local_results, root=0)
        except Exception as exc:
            raise RuntimeError(
                f"[MPIEnsembleRunner] gather failed on rank {rank}: {exc}"
            ) from exc

        if rank == 0:
            if all_results is None:
                raise RuntimeError("[MPIEnsembleRunner] gather returned None on rank 0")
            merged: list = []
            for chunk in all_results:
                merged.extend(chunk)
            return merged
        else:
            return []

    def _run_pool(self, tasks: list, fn: Callable) -> list:
        import multiprocessing
        try:
            with multiprocessing.Pool(processes=self.n_workers) as pool:
                return pool.map(fn, tasks)
        except Exception as exc:
            raise RuntimeError(
                f"[MPIEnsembleRunner] multiprocessing pool failed "
                f"(n_workers={self.n_workers}): {exc}"
            ) from exc
