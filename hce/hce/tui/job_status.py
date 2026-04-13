# job_status.py
"""
TUI 作业状态面板。

显示 Slurm 队列状态和最近的作业日志。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def show_job_status(log_dir: str = "logs/hce"):
    """显示作业状态。"""
    print()
    print("━" * 50)
    print("  队列状态 — Job Status")
    print("━" * 50)
    print()

    # 尝试查询 Slurm 队列
    _show_slurm_queue()

    # 显示最近的日志
    _show_recent_logs(log_dir)


def _show_slurm_queue():
    """查询 Slurm 队列。"""
    try:
        result = subprocess.run(
            ["squeue", "-u", "$USER", "-o", "%.18i %.9P %.30j %.2t %.10M %.6D %R"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            print("  === Slurm Queue ===")
            print(result.stdout)
        else:
            print("  Slurm 队列为空或不可用。")
    except FileNotFoundError:
        print("  squeue 不可用（非 Slurm 集群环境）。")
    except subprocess.TimeoutExpired:
        print("  squeue 查询超时。")
    print()


def _show_recent_logs(log_dir: str):
    """显示最近的日志事件。"""
    log_path = Path(log_dir)
    if not log_path.exists():
        print(f"  日志目录不存在: {log_dir}")
        return

    # 查找最近的 JSONL 日志
    logs = sorted(log_path.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        print("  无日志文件。")
        return

    latest = logs[0]
    print(f"  === 最近日志: {latest.name} ===")
    try:
        lines = latest.read_text(encoding="utf-8").strip().split("\n")
        # 显示最后 10 条
        for line in lines[-10:]:
            print(f"    {line}")
    except OSError as e:
        print(f"    读取失败: {e}")

    # 显示 .out / .err 文件
    out_files = sorted(log_path.glob("*.out"), key=lambda p: p.stat().st_mtime, reverse=True)
    err_files = sorted(log_path.glob("*.err"), key=lambda p: p.stat().st_mtime, reverse=True)

    if out_files:
        latest_out = out_files[0]
        print(f"\n  === 最近 stdout: {latest_out.name} ===")
        try:
            text = latest_out.read_text(encoding="utf-8")
            for line in text.strip().split("\n")[-5:]:
                print(f"    {line}")
        except OSError:
            pass

    if err_files:
        latest_err = err_files[0]
        print(f"\n  === 最近 stderr: {latest_err.name} ===")
        try:
            text = latest_err.read_text(encoding="utf-8")
            for line in text.strip().split("\n")[-5:]:
                print(f"    {line}")
        except OSError:
            pass
