# app.py
"""
HCE TUI 主入口。

基于标准库的终端交互前端，提供：
  - 流水线状态总览
  - 配置选择与作业提交
  - 队列与日志查看
  - 阶段结果浏览
"""

from __future__ import annotations

import os
import sys

from .dashboard import show_dashboard
from .job_submit import show_job_submit
from .job_status import show_job_status
from .result_viewer import show_results


def run_tui():
    """启动 TUI 交互循环。"""
    print("=" * 60)
    print("  HCE - 崩坏能演算器 中央演算中枢")
    print("  Honkai Computation Engine — Central Operations Console")
    print("=" * 60)
    print()

    while True:
        print("┌─── 主菜单 ───┐")
        print("│ 1. 状态总览   │")
        print("│ 2. 提交任务   │")
        print("│ 3. 队列状态   │")
        print("│ 4. 查看结果   │")
        print("│ 0. 退出       │")
        print("└──────────────┘")
        print()

        try:
            choice = input("选择操作 [0-4]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n退出。")
            break

        if choice == "0":
            print("中央演算中枢已关闭。")
            break
        elif choice == "1":
            show_dashboard()
        elif choice == "2":
            show_job_submit()
        elif choice == "3":
            show_job_status()
        elif choice == "4":
            show_results()
        else:
            print("无效选择。")
        print()


if __name__ == "__main__":
    run_tui()
