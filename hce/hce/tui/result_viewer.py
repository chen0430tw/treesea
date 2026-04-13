# result_viewer.py
"""
TUI 结果浏览面板。

浏览 HCE 最终报告和各阶段中间产物。
"""

from __future__ import annotations

import json
from pathlib import Path


def show_results(result_dir: str = "results/hce"):
    """浏览结果。"""
    print()
    print("━" * 50)
    print("  结果浏览 — Result Viewer")
    print("━" * 50)
    print()

    result_path = Path(result_dir)
    if not result_path.exists():
        print(f"  结果目录不存在: {result_dir}")
        return

    # 列出最终报告
    reports = sorted(
        result_path.glob("hce_final_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not reports:
        print("  无最终报告。")
        return

    print(f"  找到 {len(reports)} 份报告:")
    for i, r in enumerate(reports[:10]):
        try:
            data = json.loads(r.read_text(encoding="utf-8"))
            req_id = data.get("request_id", "?")
            elapsed = data.get("elapsed_sec", 0)
            print(f"    {i+1}. [{req_id}] elapsed={elapsed:.3f}s — {r.name}")
        except (json.JSONDecodeError, OSError):
            print(f"    {i+1}. {r.name} (unreadable)")

    print()

    try:
        idx_str = input("  查看详情 (编号, 0=返回): ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if idx_str == "0" or not idx_str:
        return

    try:
        idx = int(idx_str) - 1
        if idx < 0 or idx >= len(reports):
            print("  无效编号。")
            return
    except ValueError:
        print("  请输入数字。")
        return

    selected = reports[idx]
    _show_report_detail(selected)

    # 检查对应的摘要
    summary_name = selected.name.replace("hce_final_", "hce_summary_").replace(".json", ".txt")
    summary_path = selected.parent / summary_name
    if summary_path.exists():
        print(f"\n  === 摘要: {summary_name} ===")
        print(summary_path.read_text(encoding="utf-8"))


def _show_report_detail(path: Path):
    """显示报告详情。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  读取失败: {e}")
        return

    print(f"\n  === {path.name} ===")

    # 基本信息
    print(f"  Request ID : {data.get('request_id', 'N/A')}")
    print(f"  Elapsed    : {data.get('elapsed_sec', 0):.3f}s")
    print(f"  Tree Ref   : {data.get('tree_ref', 'N/A')}")
    print(f"  Sea Ref    : {data.get('sea_ref', 'N/A')}")
    print(f"  HC Ref     : {data.get('hc_ref', 'N/A')}")

    # 最终选择
    selection = data.get("final_selection", {})
    if selection:
        print(f"\n  --- Final Selection ---")
        for k, v in selection.items():
            print(f"    {k}: {v}")

    # 排名
    ranking = data.get("final_ranking", [])
    if ranking:
        print(f"\n  --- Ranking ({len(ranking)} entries) ---")
        for i, entry in enumerate(ranking[:5]):
            cid = entry.get("candidate_id", "?")
            score = entry.get("composite_score", 0)
            print(f"    #{i+1}: {cid} (score={score:.4f})")

    # 能量摘要
    energy = data.get("energy_summary", {})
    if energy:
        print(f"\n  --- Energy ---")
        for k, v in energy.items():
            print(f"    {k}: {v}")

    # 风险摘要
    risk = data.get("risk_summary", {})
    if risk:
        print(f"\n  --- Risk ---")
        for k, v in risk.items():
            print(f"    {k}: {v}")
