# job_submit.py
"""
TUI 任务提交面板。

引导用户选择配置并提交作业。
"""

from __future__ import annotations

import os
from pathlib import Path


def show_job_submit(configs_dir: str = "configs"):
    """引导用户选择配置并提交。"""
    print()
    print("━" * 50)
    print("  任务提交 — Job Submit")
    print("━" * 50)
    print()

    # 列出可用配置
    config_path = Path(configs_dir)
    if not config_path.exists():
        print(f"  配置目录不存在: {configs_dir}")
        print("  请先创建配置文件。")
        return

    configs = list(config_path.glob("hce_*.yaml")) + list(config_path.glob("hce_*.yml"))
    configs += list(config_path.glob("hce_*.json"))

    if not configs:
        print("  未找到 HCE 配置文件 (hce_*.yaml / hce_*.json)")
        print(f"  请在 {configs_dir}/ 目录创建配置。")
        return

    print("  可用配置:")
    for i, c in enumerate(configs):
        print(f"    {i+1}. {c.name}")
    print()

    try:
        idx_str = input("  选择配置编号 (0=取消): ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if idx_str == "0" or not idx_str:
        return

    try:
        idx = int(idx_str) - 1
        if idx < 0 or idx >= len(configs):
            print("  无效编号。")
            return
    except ValueError:
        print("  请输入数字。")
        return

    selected = configs[idx]
    print(f"\n  选择: {selected}")

    try:
        mode = input("  运行模式 [local/slurm] (默认 local): ").strip() or "local"
    except (EOFError, KeyboardInterrupt):
        return

    if mode == "local":
        print(f"\n  提交本地运行: python -m hce.cli.run_local --config {selected}")
        try:
            confirm = input("  确认提交? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if confirm == "y":
            from ..cli.run_local import run_local
            run_local(str(selected))
    elif mode == "slurm":
        print(f"\n  提交集群作业: python -m hce.cli.submit --config {selected}")
        try:
            partition = input("  分区 (默认 normal): ").strip() or "normal"
            confirm = input("  确认提交? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if confirm == "y":
            from ..cli.submit import submit
            submit(str(selected), partition=partition)
    else:
        print("  无效模式。")
