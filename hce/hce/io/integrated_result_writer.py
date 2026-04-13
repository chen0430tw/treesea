# integrated_result_writer.py
"""
HCE 集成结果写入器。

将 FinalReportBundle 及各阶段中间产物写出到文件系统。
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .pipeline_schema import FinalReportBundle


def write_final_report(bundle: FinalReportBundle, output_dir: str | Path) -> Path:
    """将 FinalReportBundle 写入 JSON 文件。"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"hce_final_{bundle.request_id}.json"
    filepath = output_dir / filename
    filepath.write_text(bundle.to_json(indent=2), encoding="utf-8")
    return filepath


def write_stage_artifact(
    stage_name: str,
    data: dict,
    output_dir: str | Path,
    request_id: str,
) -> Path:
    """写出单个阶段的中间产物。"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"hce_stage_{stage_name}_{request_id}.json"
    filepath = output_dir / filename
    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return filepath


def append_pipeline_event(
    event: dict,
    log_dir: str | Path,
    stream_name: str = "hce_pipeline",
) -> Path:
    """向 JSONL 事件流追加一条流水线事件。"""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    filepath = log_dir / f"{stream_name}.jsonl"
    event_with_ts = {"timestamp": datetime.utcnow().isoformat(), **event}

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(event_with_ts, ensure_ascii=False) + "\n")

    return filepath


def write_final_summary(bundle: FinalReportBundle, output_dir: str | Path) -> Path:
    """写出人可读的最终摘要。"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filepath = output_dir / f"hce_summary_{bundle.request_id}.txt"

    lines = [
        f"=== HCE Final Report: {bundle.request_id} ===",
        f"Elapsed    : {bundle.elapsed_sec:.3f}s",
        f"Tree Ref   : {bundle.tree_ref or 'N/A'}",
        f"Sea Ref    : {bundle.sea_ref or 'N/A'}",
        f"HC Ref     : {bundle.hc_ref or 'N/A'}",
        "",
    ]

    if bundle.final_selection:
        lines.append("--- Final Selection ---")
        for k, v in bundle.final_selection.items():
            lines.append(f"  {k}: {v}")
        lines.append("")

    if bundle.final_ranking:
        lines.append(f"--- Final Ranking ({len(bundle.final_ranking)} entries) ---")
        for i, entry in enumerate(bundle.final_ranking):
            lines.append(f"  #{i+1}: {entry}")
        lines.append("")

    if bundle.energy_summary:
        lines.append("--- Energy Summary ---")
        for k, v in bundle.energy_summary.items():
            lines.append(f"  {k}: {v}")
        lines.append("")

    if bundle.risk_summary:
        lines.append("--- Risk Summary ---")
        for k, v in bundle.risk_summary.items():
            lines.append(f"  {k}: {v}")
        lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath
