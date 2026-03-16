"""tree-diagram submit  — generate and optionally submit a Slurm job.

Usage:
    python -m tree_diagram.cli.submit [OPTIONS]
    python -m tree_diagram submit [OPTIONS]

Options:
    --config    YAML config file (configs/td_*.yaml)
    --job       Job definition YAML (jobs/td_*.yaml) — includes Slurm params
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

Note: CLI flags take precedence over --job / --config values.
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
    parser.add_argument("--config",    default=None,
                        help="YAML config file (configs/td_*.yaml)")
    parser.add_argument("--job",       default=None,
                        help="Job definition YAML (jobs/td_*.yaml)")
    parser.add_argument("--profile",   default=None,
                        choices=["quick", "default", "cluster", "deep"],
                        help="Compute profile (default: cluster)")
    parser.add_argument("--account",   default=None,
                        help="Slurm account")
    parser.add_argument("--partition", default=None,
                        choices=["normal", "normal2"],
                        help="Slurm partition")
    parser.add_argument("--nodes",     type=int, default=None,
                        help="Number of nodes")
    parser.add_argument("--gpus",      type=int, default=None,
                        help="GPUs per node")
    parser.add_argument("--time",      default=None,
                        help="Wall-clock limit")
    parser.add_argument("--out-dir",   default=None,
                        help="Output directory on cluster")
    parser.add_argument("--work-dir",  default=None,
                        help="Working directory on cluster")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Print script only, do not submit")
    parser.add_argument("--title",     default=None,
                        help="Override problem title")
    parser.add_argument("--top-k",     type=int, default=None,
                        help="Override top_k from profile")
    args = parser.parse_args(argv)

    # --- Load YAML (job file takes priority over config file) ---
    cfg_slurm:   dict = {}
    cfg_profile_name: str | None = None
    cfg_title:   str | None = None
    yaml_source = args.job or args.config
    if yaml_source:
        from ..io.input_loader import load_run_config
        cfg = load_run_config(yaml_source)
        cfg_slurm        = cfg.get("slurm") or {}
        cfg_profile_name = (cfg.get("profile") or {}).get("name")
        cfg_title        = (cfg.get("seed") or {}).get("title")

    # --- Resolve each parameter: CLI > YAML > hardcoded default ---
    def _resolve(cli_val, yaml_val, default):
        if cli_val is not None:
            return cli_val
        if yaml_val is not None:
            return yaml_val
        return default

    _DEFAULT_DIR = "/work/twsuday816/treesea/tree_diagram"
    profile   = _resolve(args.profile,   cfg_profile_name,               "cluster")
    account   = _resolve(args.account,   cfg_slurm.get("account"),       "ENT114035")
    partition = _resolve(args.partition, cfg_slurm.get("partition"),      "normal")
    nodes     = _resolve(args.nodes,     cfg_slurm.get("nodes"),         1)
    gpus      = _resolve(args.gpus,      cfg_slurm.get("gpus"),          8)
    wall_time = _resolve(args.time,      cfg_slurm.get("time"),          "02:00:00")
    out_dir   = _resolve(args.out_dir,   cfg_slurm.get("out_dir"),       _DEFAULT_DIR)
    work_dir  = _resolve(args.work_dir,  cfg_slurm.get("work_dir"),      _DEFAULT_DIR)
    title     = _resolve(args.title,     cfg_title,                      None)

    extra_parts = []
    if title:
        extra_parts.append(f'--title "{title}"')
    if args.top_k is not None:
        extra_parts.append(f"--top-k {args.top_k}")
    extra_args = " \\\n    ".join(extra_parts)

    script = _SCRIPT_TEMPLATE.format(
        profile=profile,
        account=account,
        partition=partition,
        nodes=nodes,
        gpus=gpus,
        time=wall_time,
        out_dir=out_dir,
        work_dir=work_dir,
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
        print(f"[td-submit] output:  tail -f {out_dir}/td_{profile}_{job_id}.out")
    except FileNotFoundError:
        print("[td-submit] sbatch not found — run this on the cluster login node")
        print(f"[td-submit] script saved to {tmp_path}")
    except subprocess.CalledProcessError as e:
        print(f"[td-submit] sbatch failed: {e.stderr}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
