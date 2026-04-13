# submit.py
"""
Honkai Core 集群提交入口。

用法：
  python -m honkai_core.cli.submit --config configs/hc_cluster.yaml
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


def submit(config_path: str, partition: str = "normal", account: Optional[str] = None):
    """生成 Slurm 脚本并提交。"""
    config_path = os.path.abspath(config_path)
    if not os.path.exists(config_path):
        print(f"Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    job_name = f"hc_{Path(config_path).stem}"

    sbatch_lines = [
        "#!/bin/bash",
        f"#SBATCH --job-name={job_name}",
        f"#SBATCH --partition={partition}",
        "#SBATCH --nodes=1",
        "#SBATCH --ntasks=1",
        "#SBATCH --cpus-per-task=4",
        "#SBATCH --time=01:00:00",
        f"#SBATCH --output=logs/honkai_core/{job_name}_%j.out",
        f"#SBATCH --error=logs/honkai_core/{job_name}_%j.err",
    ]

    if account:
        sbatch_lines.append(f"#SBATCH --account={account}")

    sbatch_lines += [
        "",
        "set -euo pipefail",
        "",
        f'python -m honkai_core.cli.run_local --config "{config_path}"',
    ]

    script = "\n".join(sbatch_lines) + "\n"

    # 确保日志目录存在
    os.makedirs("logs/honkai_core", exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sbatch", prefix="hc_", delete=False
    ) as f:
        f.write(script)
        script_path = f.name

    print(f"Generated sbatch script: {script_path}")
    print(f"Submitting to partition={partition} ...")

    try:
        result = subprocess.run(
            ["sbatch", script_path],
            capture_output=True, text=True, timeout=30,
        )
        print(result.stdout.strip())
        if result.returncode != 0:
            print(f"sbatch error: {result.stderr.strip()}", file=sys.stderr)
    except FileNotFoundError:
        print("sbatch not found. Are you on a Slurm cluster?", file=sys.stderr)
        print(f"Script saved to: {script_path}")
    finally:
        os.unlink(script_path)


def main():
    parser = argparse.ArgumentParser(description="Honkai Core 集群提交")
    parser.add_argument("--config", required=True, help="场景配置文件路径")
    parser.add_argument("--partition", default="normal", help="Slurm 分区")
    parser.add_argument("--account", default=None, help="Slurm 账户")
    args = parser.parse_args()
    submit(args.config, partition=args.partition, account=args.account)


if __name__ == "__main__":
    main()
