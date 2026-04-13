# run_local.py
"""
HCE 本地运行入口。

用法：
  python -m hce.cli.run_local --config configs/hce_local_debug.yaml
"""

from __future__ import annotations

import argparse
from typing import Optional


def run_local(config_path: str, request_id: Optional[str] = None, output_dir: Optional[str] = None):
    """本地运行 HCE 流水线。"""
    from ..runtime.launcher import launch_local
    launch_local(config_path, request_id=request_id, output_dir=output_dir)


def main():
    parser = argparse.ArgumentParser(description="HCE 本地运行")
    parser.add_argument("--config", required=True, help="流水线配置文件路径")
    parser.add_argument("--request-id", default=None, help="请求 ID")
    parser.add_argument("--output-dir", default=None, help="输出目录")
    args = parser.parse_args()
    run_local(args.config, request_id=args.request_id, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
