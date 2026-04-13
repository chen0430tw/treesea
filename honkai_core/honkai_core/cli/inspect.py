# inspect.py
"""
Honkai Core 结果查看入口。

用法：
  python -m honkai_core.cli.inspect --run-id hc_abcd1234
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def inspect_run(run_id: str, result_dir: str = "results/honkai_core"):
    """查看指定运行 ID 的结果。"""
    result_path = Path(result_dir)

    # 搜索 Bundle 文件
    pattern = f"hc_report_{run_id}.json"
    matches = list(result_path.rglob(pattern))

    if not matches:
        # 尝试模糊匹配
        matches = list(result_path.rglob(f"*{run_id}*.json"))

    if not matches:
        print(f"No results found for run_id={run_id} in {result_dir}", file=sys.stderr)
        print(f"Searched pattern: {pattern}")
        sys.exit(1)

    for m in matches:
        print(f"\n=== {m} ===")
        data = json.loads(m.read_text(encoding="utf-8"))
        print(json.dumps(data, indent=2, ensure_ascii=False))

    # 也检查摘要文件
    summary_pattern = f"hc_summary_{run_id}.txt"
    summaries = list(result_path.rglob(summary_pattern))
    if not summaries:
        summaries = list(result_path.rglob(f"*{run_id}*.txt"))

    for s in summaries:
        print(f"\n=== {s} ===")
        print(s.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Honkai Core 结果查看")
    parser.add_argument("--run-id", required=True, help="运行 ID")
    parser.add_argument("--result-dir", default="results/honkai_core", help="结果目录")
    args = parser.parse_args()
    inspect_run(args.run_id, result_dir=args.result_dir)


if __name__ == "__main__":
    main()
