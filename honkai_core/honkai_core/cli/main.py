# main.py
"""
Honkai Core CLI 主入口。

用法：
  python -m honkai_core.cli.main [run_local|submit|inspect] [--config ...]
"""

from __future__ import annotations

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="honkai_core",
        description="Honkai Core - 崩坏能理论与风险评估系统",
    )
    sub = parser.add_subparsers(dest="command")

    # run_local
    p_run = sub.add_parser("run_local", help="本地运行")
    p_run.add_argument("--config", required=True, help="场景配置文件路径")
    p_run.add_argument("--output-dir", default=None, help="输出目录")

    # submit
    p_sub = sub.add_parser("submit", help="集群提交")
    p_sub.add_argument("--config", required=True, help="场景配置文件路径")
    p_sub.add_argument("--partition", default="normal", help="Slurm 分区")
    p_sub.add_argument("--account", default=None, help="Slurm 账户")

    # inspect
    p_ins = sub.add_parser("inspect", help="查看运行结果")
    p_ins.add_argument("--run-id", required=True, help="运行 ID")
    p_ins.add_argument("--result-dir", default="results/honkai_core", help="结果目录")

    args = parser.parse_args()

    if args.command == "run_local":
        from .run_local import run_local
        run_local(args.config, output_dir=args.output_dir)
    elif args.command == "submit":
        from .submit import submit
        submit(args.config, partition=args.partition, account=args.account)
    elif args.command == "inspect":
        from .inspect import inspect_run
        inspect_run(args.run_id, result_dir=args.result_dir)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
