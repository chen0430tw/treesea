from __future__ import annotations

"""runtime/scheduler_adapter.py

Scheduler adapter: Slurm / local dispatch abstraction.

Architecture position:
  runtime layer — provides a unified interface for job submission
  regardless of whether the environment is a local workstation,
  a Slurm cluster, or an in-process thread pool.

Supported backends:
  "local"  — direct in-process execution (default)
  "slurm"  — submit via sbatch (requires cluster environment)
  "thread" — ThreadPoolExecutor for I/O-bound tasks
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Job specification
# ---------------------------------------------------------------------------

@dataclass
class JobSpec:
    """Specification for a single scheduled job."""
    name:         str
    command:      str                    # shell command to execute
    n_cpus:       int   = 1
    n_gpus:       int   = 0
    memory_gb:    int   = 8
    time_limit:   str   = "01:00:00"     # HH:MM:SS
    partition:    str   = "debug"
    account:      str   = ""
    env:          Dict[str, str] = field(default_factory=dict)
    output_file:  str   = ""
    error_file:   str   = ""


@dataclass
class JobResult:
    """Result of a job submission."""
    job_id:  str
    backend: str
    success: bool
    message: str


# ---------------------------------------------------------------------------
# SchedulerAdapter
# ---------------------------------------------------------------------------

class SchedulerAdapter:
    """Unified scheduler adapter for local, thread, and Slurm backends.

    Usage::

        adapter = SchedulerAdapter(backend="local")
        result  = adapter.submit(job_spec)
    """

    def __init__(
        self,
        backend: str = "local",
        slurm_sbatch: str = "sbatch",
    ) -> None:
        self.backend      = backend
        self.slurm_sbatch = slurm_sbatch

    # ------------------------------------------------------------------
    # Auto-detect backend
    # ------------------------------------------------------------------

    @classmethod
    def auto(cls) -> "SchedulerAdapter":
        """Auto-detect backend: Slurm if sbatch available, else local."""
        try:
            r = subprocess.run(["which", "sbatch"], capture_output=True, timeout=2)
            if r.returncode == 0:
                return cls(backend="slurm")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return cls(backend="local")

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit(self, job: JobSpec) -> JobResult:
        """Submit a job to the configured backend."""
        if self.backend == "slurm":
            return self._submit_slurm(job)
        elif self.backend == "thread":
            return self._submit_thread(job)
        else:
            return self._submit_local(job)

    def submit_many(self, jobs: List[JobSpec]) -> List[JobResult]:
        """Submit multiple jobs."""
        return [self.submit(j) for j in jobs]

    # ------------------------------------------------------------------
    # Backends
    # ------------------------------------------------------------------

    def _submit_local(self, job: JobSpec) -> JobResult:
        """Run job in-process (blocking)."""
        env = {**os.environ, **job.env}
        try:
            proc = subprocess.run(
                job.command, shell=True, env=env,
                capture_output=True, text=True, timeout=3600,
            )
            success = proc.returncode == 0
            return JobResult(
                job_id=f"local-{job.name}",
                backend="local",
                success=success,
                message=proc.stdout[-500:] if success else proc.stderr[-500:],
            )
        except subprocess.TimeoutExpired:
            return JobResult(job_id=f"local-{job.name}", backend="local",
                             success=False, message="Timeout exceeded.")

    def _submit_slurm(self, job: JobSpec) -> JobResult:
        """Generate a batch script and submit via sbatch."""
        script = self._build_slurm_script(job)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh",
                                         delete=False, prefix=f"td_{job.name}_") as f:
            f.write(script)
            script_path = f.name

        try:
            proc = subprocess.run(
                [self.slurm_sbatch, script_path],
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode == 0:
                # Extract job ID from "Submitted batch job XXXXX"
                job_id = proc.stdout.strip().split()[-1]
                return JobResult(job_id=job_id, backend="slurm",
                                 success=True, message=proc.stdout.strip())
            else:
                return JobResult(job_id="", backend="slurm",
                                 success=False, message=proc.stderr.strip())
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return JobResult(job_id="", backend="slurm",
                             success=False, message=str(e))
        finally:
            try:
                Path(script_path).unlink()
            except OSError:
                pass

    def _submit_thread(self, job: JobSpec) -> JobResult:
        """Submit via ThreadPoolExecutor (non-blocking)."""
        from concurrent.futures import ThreadPoolExecutor
        env = {**os.environ, **job.env}

        def _run() -> str:
            proc = subprocess.run(job.command, shell=True, env=env,
                                  capture_output=True, text=True, timeout=3600)
            return proc.stdout if proc.returncode == 0 else proc.stderr

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run)
            # Do not wait — return immediately
        return JobResult(job_id=f"thread-{job.name}", backend="thread",
                         success=True, message="Submitted to thread pool.")

    # ------------------------------------------------------------------
    # Slurm script builder
    # ------------------------------------------------------------------

    def _build_slurm_script(self, job: JobSpec) -> str:
        lines = ["#!/bin/bash"]
        lines.append(f"#SBATCH --job-name={job.name}")
        lines.append(f"#SBATCH --cpus-per-task={job.n_cpus}")
        lines.append(f"#SBATCH --mem={job.memory_gb}G")
        lines.append(f"#SBATCH --time={job.time_limit}")
        lines.append(f"#SBATCH --partition={job.partition}")
        if job.account:
            lines.append(f"#SBATCH --account={job.account}")
        if job.n_gpus > 0:
            lines.append(f"#SBATCH --gpus-per-node={job.n_gpus}")
        if job.output_file:
            lines.append(f"#SBATCH --output={job.output_file}")
        if job.error_file:
            lines.append(f"#SBATCH --error={job.error_file}")
        for k, v in job.env.items():
            lines.append(f"export {k}={v}")
        lines.append("")
        lines.append(job.command)
        lines.append("")
        return "\n".join(lines)
