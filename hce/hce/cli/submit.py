# submit.py
"""
HCE 集群提交入口。

用法：
  python -m hce.cli.submit --config configs/hce_cluster.yaml
"""

from __future__ import annotations

import argparse
from typing import Optional


def submit(
    config_path: str,
    partition: str = "normal",
    account: Optional[str] = None,
    nodes: int = 1,
):
    """生成 Slurm 脚本并提交。"""
    from ..runtime.launcher import launch_slurm
    launch_slurm(config_path, partition=partition, account=account, nodes=nodes)


def main():
    parser = argparse.ArgumentParser(description="HCE 集群提交")
    parser.add_argument("--config", required=True, help="流水线配置文件路径")
    parser.add_argument("--partition", default="normal", help="Slurm 分区")
    parser.add_argument("--account", default=None, help="Slurm 账户")
    parser.add_argument("--nodes", type=int, default=1, help="节点数")
    args = parser.parse_args()
    submit(args.config, partition=args.partition, account=args.account, nodes=args.nodes)


if __name__ == "__main__":
    main()
