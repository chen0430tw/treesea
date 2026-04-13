# run_local.py
"""
Honkai Core 本地运行入口。

用法：
  python -m honkai_core.cli.run_local --config configs/hc_local_debug.yaml
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional


def run_local(config_path: str, output_dir: Optional[str] = None):
    """本地运行 Honkai Core 分析。"""
    from ..io.scenario_loader import load_scenario
    from ..io.energy_report_writer import write_bundle, write_summary
    from ..runtime.runner import HonkaiCoreRunner

    config = load_scenario(config_path)

    if output_dir is None:
        output_dir = config.runtime.get("output_dir", "runs/honkai_core")

    runner = HonkaiCoreRunner(config)
    bundle = runner.run()

    # 落盘
    out = Path(output_dir)
    bundle_path = write_bundle(bundle, out)
    summary_path = write_summary(bundle, out)

    print(f"Bundle  : {bundle_path}")
    print(f"Summary : {summary_path}")
    print(f"Elapsed : {bundle.elapsed_sec:.3f}s")
    print(f"Action  : {bundle.recommendation.action}")
    print(f"State   : {bundle.energy_estimate.state}")


def main():
    parser = argparse.ArgumentParser(description="Honkai Core 本地运行")
    parser.add_argument("--config", required=True, help="场景配置文件路径")
    parser.add_argument("--output-dir", default=None, help="输出目录")
    args = parser.parse_args()
    run_local(args.config, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
