# dashboard.py
"""
TUI 状态总览面板。

显示 HCE 系统状态、最近运行、检查点等信息。
"""

from __future__ import annotations

import json
from pathlib import Path


def show_dashboard(
    result_dir: str = "results/hce",
    checkpoint_dir: str = "checkpoints/hce",
    log_dir: str = "logs/hce",
):
    """显示系统状态总览。"""
    print()
    print("━" * 50)
    print("  状态总览 — HCE Dashboard")
    print("━" * 50)
    print()

    # 检查结果目录
    result_path = Path(result_dir)
    if result_path.exists():
        reports = list(result_path.glob("hce_final_*.json"))
        print(f"  最终报告数量 : {len(reports)}")
        if reports:
            latest = max(reports, key=lambda p: p.stat().st_mtime)
            print(f"  最新报告     : {latest.name}")
            try:
                data = json.loads(latest.read_text(encoding="utf-8"))
                print(f"    Request ID : {data.get('request_id', 'N/A')}")
                print(f"    Elapsed    : {data.get('elapsed_sec', 0):.3f}s")
            except (json.JSONDecodeError, OSError):
                pass
    else:
        print(f"  结果目录不存在: {result_dir}")

    print()

    # 检查检查点
    ckpt_path = Path(checkpoint_dir)
    if ckpt_path.exists():
        ckpts = list(ckpt_path.glob("ckpt_*.json"))
        print(f"  活动检查点   : {len(ckpts)}")
        for c in ckpts[:5]:
            req_id = c.stem.replace("ckpt_", "")
            print(f"    - {req_id}")
    else:
        print(f"  检查点目录不存在: {checkpoint_dir}")

    print()

    # 检查日志
    log_path = Path(log_dir)
    if log_path.exists():
        logs = list(log_path.glob("*.jsonl"))
        print(f"  日志流数量   : {len(logs)}")
        for lg in logs[:5]:
            # 统计行数
            try:
                n_lines = sum(1 for _ in open(lg, encoding="utf-8"))
                print(f"    - {lg.name}: {n_lines} events")
            except OSError:
                print(f"    - {lg.name}: (unreadable)")
    else:
        print(f"  日志目录不存在: {log_dir}")

    print()
    print("━" * 50)
