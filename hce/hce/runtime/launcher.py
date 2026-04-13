# launcher.py
"""
HCE 启动器。

负责从配置文件构建 HCERunner 并启动流水线。
支持本地运行和集群提交两种模式。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

from ..io.pipeline_schema import PipelineConfig, RequestBundle


def load_pipeline_config(config_path: str | Path) -> PipelineConfig:
    """从 YAML/JSON 加载流水线配置。"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Pipeline config not found: {path}")

    text = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required: pip install pyyaml")
        data = yaml.safe_load(text) or {}
    elif path.suffix == ".json":
        data = json.loads(text)
    else:
        raise ValueError(f"Unsupported format: {path.suffix}")

    return PipelineConfig.from_dict(data)


def launch_local(
    config_path: str,
    request_id: Optional[str] = None,
    output_dir: Optional[str] = None,
):
    """本地启动 HCE 流水线。

    Parameters
    ----------
    config_path : str
    request_id : str, optional
    output_dir : str, optional
    """
    from .runner import HCERunner

    config = load_pipeline_config(config_path)
    if output_dir:
        config.result_dir = output_dir

    errors = config.validate()
    if errors:
        print("Configuration errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    request = RequestBundle(
        request_id=request_id or f"req_{os.getpid()}",
        mode=config.mode,
    )

    runner = HCERunner(config)
    bundle = runner.run(request)

    print(f"Pipeline complete: {bundle.request_id}")
    print(f"  Elapsed : {bundle.elapsed_sec:.3f}s")
    print(f"  Mode    : {config.mode}")
    print(f"  Results : {config.result_dir}")

    return bundle


def launch_slurm(
    config_path: str,
    partition: str = "normal",
    account: Optional[str] = None,
    nodes: int = 1,
):
    """生成 Slurm 脚本并提交。"""
    import subprocess
    import tempfile

    config_path = os.path.abspath(config_path)
    job_name = f"hce_{Path(config_path).stem}"

    sbatch_lines = [
        "#!/bin/bash",
        f"#SBATCH --job-name={job_name}",
        f"#SBATCH --partition={partition}",
        f"#SBATCH --nodes={nodes}",
        "#SBATCH --ntasks=1",
        "#SBATCH --cpus-per-task=4",
        "#SBATCH --time=04:00:00",
        f"#SBATCH --output=logs/hce/{job_name}_%j.out",
        f"#SBATCH --error=logs/hce/{job_name}_%j.err",
    ]

    if account:
        sbatch_lines.append(f"#SBATCH --account={account}")

    sbatch_lines += [
        "",
        "set -euo pipefail",
        "",
        f'python -m hce.cli.run_local --config "{config_path}"',
    ]

    script = "\n".join(sbatch_lines) + "\n"
    os.makedirs("logs/hce", exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sbatch", prefix="hce_", delete=False
    ) as f:
        f.write(script)
        script_path = f.name

    print(f"Generated: {script_path}")

    try:
        result = subprocess.run(
            ["sbatch", script_path],
            capture_output=True, text=True, timeout=30,
        )
        print(result.stdout.strip())
        if result.returncode != 0:
            print(f"Error: {result.stderr.strip()}", file=sys.stderr)
    except FileNotFoundError:
        print("sbatch not found. Script saved to:", script_path, file=sys.stderr)
    finally:
        os.unlink(script_path)
