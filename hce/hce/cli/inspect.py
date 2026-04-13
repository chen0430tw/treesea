# inspect.py
"""
HCE 结果查看入口。

用法：
  python -m hce.cli.inspect --request-id req_001
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def inspect_run(request_id: str, result_dir: str = "results/hce"):
    """查看指定请求的结果。"""
    result_path = Path(result_dir)

    # 搜索最终报告
    matches = list(result_path.rglob(f"*{request_id}*.json"))
    if not matches:
        print(f"No results found for request_id={request_id} in {result_dir}", file=sys.stderr)
        sys.exit(1)

    for m in matches:
        print(f"\n=== {m} ===")
        data = json.loads(m.read_text(encoding="utf-8"))
        print(json.dumps(data, indent=2, ensure_ascii=False))

    # 检查摘要
    summaries = list(result_path.rglob(f"*{request_id}*.txt"))
    for s in summaries:
        print(f"\n=== {s} ===")
        print(s.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="HCE 结果查看")
    parser.add_argument("--request-id", required=True, help="请求 ID")
    parser.add_argument("--result-dir", default="results/hce", help="结果目录")
    args = parser.parse_args()
    inspect_run(args.request_id, result_dir=args.result_dir)


if __name__ == "__main__":
    main()
