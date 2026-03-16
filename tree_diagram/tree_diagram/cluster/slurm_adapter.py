from __future__ import annotations

"""cluster/slurm_adapter.py

Slurm job submission adapter for Tree Diagram cluster execution.

Architecture position:
  cluster layer — wraps sbatch/squeue/scancel for Tree Diagram workloads.
  Provides a higher-level interface than runtime/scheduler_adapter.py:
  specifically handles multi-node MPI jobs, GPU allocation, and job arrays
  for parameter sweeps.

This adapter targets the nano5.nchc.org.tw H100 cluster configuration
but is general enough for any Slurm installation.
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Job specification
# ---------------------------------------------------------------------------

@dataclass
class SlurmJobSpec:
    """Slurm job specification for Tree Diagram workloads."""
    job_name:       str
    command:        str
    n_nodes:        int   = 1
    n_tasks:        int   = 1
    n_gpus:         int   = 0
    cpus_per_task:  int   = 4
    memory_gb:      int   = 32
    time_limit:     str   = "01:00:00"
    partition:      str   = "normal"
    account:        str   = ""
    output_file:    str   = "job_%j.out"
    error_file:     str   = "job_%j.err"
    work_dir:       str   = ""
    modules:        List[str] = field(default_factory=list)
    env_vars:       Dict[str, str] = field(default_factory=dict)
    array:          str   = ""             # e.g. "0-7" for job arrays
    exclusive:      bool  = False


@dataclass
class SlurmJobStatus:
    """Status of a submitted Slurm job."""
    job_id:    str
    state:     str     # "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "UNKNOWN"
    nodes:     str
    reason:    str


# ---------------------------------------------------------------------------
# SlurmAdapter
# ---------------------------------------------------------------------------

class SlurmAdapter:
    """Submit, monitor, and cancel Slurm jobs for Tree Diagram.

    Usage::

        adapter = SlurmAdapter(sbatch="sbatch", squeue="squeue")
        spec    = SlurmJobSpec(job_name="td_run", command="python train.py", n_gpus=8)
        job_id  = adapter.submit(spec)
        status  = adapter.status(job_id)
    """

    def __init__(
        self,
        sbatch:  str = "sbatch",
        squeue:  str = "squeue",
        scancel: str = "scancel",
    ) -> None:
        self.sbatch  = sbatch
        self.squeue  = squeue
        self.scancel = scancel

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit(self, spec: SlurmJobSpec) -> Optional[str]:
        """Submit a job and return the Slurm job ID string, or None on failure."""
        script  = self._build_script(spec)
        tmp_dir = spec.work_dir or tempfile.gettempdir()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", prefix=f"td_{spec.job_name}_",
            dir=tmp_dir, delete=False,
        ) as f:
            f.write(script)
            script_path = f.name

        try:
            proc = subprocess.run(
                [self.sbatch, script_path],
                capture_output=True, text=True, timeout=30,
            )
            if proc.returncode == 0:
                # "Submitted batch job 12345"
                parts = proc.stdout.strip().split()
                return parts[-1] if parts else ""
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        finally:
            try:
                Path(script_path).unlink()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self, job_id: str) -> SlurmJobStatus:
        """Query job status via squeue."""
        try:
            proc = subprocess.run(
                [self.squeue, "-j", job_id, "-o", "%.18i %.9T %.12R %.8D", "--noheader"],
                capture_output=True, text=True, timeout=10,
            )
            line = proc.stdout.strip()
            if not line:
                return SlurmJobStatus(job_id=job_id, state="UNKNOWN", nodes="", reason="not in queue")
            parts = line.split()
            state  = parts[1] if len(parts) > 1 else "UNKNOWN"
            reason = parts[2] if len(parts) > 2 else ""
            nodes  = parts[3] if len(parts) > 3 else ""
            return SlurmJobStatus(job_id=job_id, state=state, nodes=nodes, reason=reason)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return SlurmJobStatus(job_id=job_id, state="UNKNOWN", nodes="", reason="squeue error")

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def cancel(self, job_id: str) -> bool:
        """Cancel a job.  Returns True on success."""
        try:
            proc = subprocess.run(
                [self.scancel, job_id],
                capture_output=True, text=True, timeout=10,
            )
            return proc.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    # ------------------------------------------------------------------
    # Script builder
    # ------------------------------------------------------------------

    def _build_script(self, spec: SlurmJobSpec) -> str:
        lines = ["#!/bin/bash"]
        lines.append(f"#SBATCH --job-name={spec.job_name}")
        lines.append(f"#SBATCH --nodes={spec.n_nodes}")
        lines.append(f"#SBATCH --ntasks={spec.n_tasks}")
        lines.append(f"#SBATCH --cpus-per-task={spec.cpus_per_task}")
        lines.append(f"#SBATCH --mem={spec.memory_gb}G")
        lines.append(f"#SBATCH --time={spec.time_limit}")
        lines.append(f"#SBATCH --partition={spec.partition}")
        if spec.account:
            lines.append(f"#SBATCH --account={spec.account}")
        if spec.n_gpus > 0:
            lines.append(f"#SBATCH --gpus-per-node={spec.n_gpus}")
        lines.append(f"#SBATCH --output={spec.output_file}")
        lines.append(f"#SBATCH --error={spec.error_file}")
        if spec.work_dir:
            lines.append(f"#SBATCH --chdir={spec.work_dir}")
        if spec.array:
            lines.append(f"#SBATCH --array={spec.array}")
        if spec.exclusive:
            lines.append("#SBATCH --exclusive")

        lines.append("")
        for mod in spec.modules:
            lines.append(f"module load {mod}")
        for k, v in spec.env_vars.items():
            lines.append(f"export {k}={v}")

        lines.append("")
        lines.append(spec.command)
        lines.append("")
        return "\n".join(lines)
