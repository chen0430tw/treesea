"""tree-diagram submit  — generate and optionally submit a Slurm job.

Usage:
    python -m tree_diagram.cli.submit [OPTIONS]
    python -m tree_diagram submit [OPTIONS]

Options:
    --profile   quick | default | cluster | deep  (default: cluster)
    --account   Slurm account  (default: ENT114035)
    --partition normal | normal2  (default: normal)
    --nodes     Number of nodes  (default: 1)
    --gpus      GPUs per node  (default: 8)
    --time      Wall-clock limit  (default: 02:00:00)
    --out-dir   Output directory on cluster  (default: /work/twsuday816/treesea/tree_diagram)
    --dry-run   Print script only, do not submit
    --title     Problem title override
    --top-k     Override top_k from profile
"""
from __future__ import annotations
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


_SCRIPT_TEMPLATE = """\
#!/bin/bash
#SBATCH --job-name=td_{profile}
#SBATCH --account={account}
#SBATCH --partition={partition}
#SBATCH --nodes={nodes}
#SBATCH --gpus-per-node={gpus}
#SBATCH --time={time}
#SBATCH --output={out_dir}/td_{profile}_%j.out
#SBATCH --error={out_dir}/td_{profile}_%j.err

set -e
module load miniconda3/24.11.1

cd {work_dir}

echo "[td-submit] job=$SLURM_JOB_ID  profile={profile}  nodes=$SLURM_NNODES"
echo "[td-submit] node list: $SLURM_NODELIST"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

python3 -m tree_diagram.cli.run_local \\
    --profile {profile} \\
    --out {out_dir}/td_result_{profile}_$SLURM_JOB_ID.json \\
    {extra_args}

echo "[td-submit] done"
"""


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="tree-diagram submit",
        description="Generate and submit a Slurm job for Tree Diagram",
    )
    parser.add_argument("--profile",   default="cluster",
                        choices=["quick", "default", "cluster", "deep"],
                        help="Compute profile (default: cluster)")
    parser.add_argument("--account",   default="ENT114035",
                        help="Slurm account (default: ENT114035)")
    parser.add_argument("--partition", default="normal",
                        choices=["normal", "normal2"],
                        help="Slurm partition (default: normal)")
    parser.add_argument("--nodes",     type=int, default=1,
                        help="Number of nodes (default: 1)")
    parser.add_argument("--gpus",      type=int, default=8,
                        help="GPUs per node (default: 8)")
    parser.add_argument("--time",      default="02:00:00",
                        help="Wall-clock limit (default: 02:00:00)")
    parser.add_argument("--out-dir",   default="/work/twsuday816/treesea/tree_diagram",
                        help="Output directory on cluster")
    parser.add_argument("--work-dir",  default="/work/twsuday816/treesea/tree_diagram",
                        help="Working directory on cluster")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Print script only, do not submit")
    parser.add_argument("--title",     default=None,
                        help="Override problem title")
    parser.add_argument("--top-k",     type=int, default=None,
                        help="Override top_k from profile")
    args = parser.parse_args(argv)

    extra_parts = []
    if args.title:
        extra_parts.append(f'--title "{args.title}"')
    if args.top_k is not None:
        extra_parts.append(f"--top-k {args.top_k}")
    extra_args = " \\\n    ".join(extra_parts)

    script = _SCRIPT_TEMPLATE.format(
        profile=args.profile,
        account=args.account,
        partition=args.partition,
        nodes=args.nodes,
        gpus=args.gpus,
        time=args.time,
        out_dir=args.out_dir,
        work_dir=args.work_dir,
        extra_args=extra_args,
    )

    if args.dry_run:
        print(script)
        return 0

    # Write to temp file and sbatch
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh",
                                     delete=False, prefix="td_submit_") as f:
        f.write(script)
        tmp_path = f.name

    print(f"[td-submit] script written to {tmp_path}")
    print(script)

    try:
        result = subprocess.run(
            ["sbatch", tmp_path],
            capture_output=True, text=True, check=True,
        )
        print(result.stdout.strip())
        job_id = result.stdout.strip().split()[-1]
        print(f"[td-submit] submitted job {job_id}")
        print(f"[td-submit] monitor: squeue -j {job_id}")
        print(f"[td-submit] output:  tail -f {args.out_dir}/td_{args.profile}_{job_id}.out")
    except FileNotFoundError:
        print("[td-submit] sbatch not found — run this on the cluster login node")
        print(f"[td-submit] script saved to {tmp_path}")
    except subprocess.CalledProcessError as e:
        print(f"[td-submit] sbatch failed: {e.stderr}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
