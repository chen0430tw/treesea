# energy_report_writer.py
"""
崩坏能报告写入器。

将 HCReportBundle 写出到文件系统：
  - JSON Bundle 落盘
  - JSONL 事件流追加
  - 人可读文本摘要
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .risk_schema import HCReportBundle


def write_bundle(bundle: HCReportBundle, output_dir: str | Path) -> Path:
    """将 HCReportBundle 写入 JSON 文件。

    Parameters
    ----------
    bundle : HCReportBundle
    output_dir : str or Path

    Returns
    -------
    Path
        写入的文件路径
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"hc_report_{bundle.hc_run_id}.json"
    filepath = output_dir / filename

    filepath.write_text(bundle.to_json(indent=2), encoding="utf-8")
    return filepath


def append_event(event: dict, log_dir: str | Path, stream_name: str = "hc_events") -> Path:
    """向 JSONL 事件流追加一条记录。

    Parameters
    ----------
    event : dict
    log_dir : str or Path
    stream_name : str

    Returns
    -------
    Path
        JSONL 文件路径
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    filepath = log_dir / f"{stream_name}.jsonl"
    event_with_ts = {"timestamp": datetime.utcnow().isoformat(), **event}

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(event_with_ts, ensure_ascii=False) + "\n")

    return filepath


def write_summary(bundle: HCReportBundle, output_dir: str | Path) -> Path:
    """写出人可读的文本摘要。

    Parameters
    ----------
    bundle : HCReportBundle
    output_dir : str or Path

    Returns
    -------
    Path
        摘要文件路径
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filepath = output_dir / f"hc_summary_{bundle.hc_run_id}.txt"

    e = bundle.energy_estimate
    t = bundle.threshold_assessment
    rec = bundle.recommendation

    lines = [
        f"=== Honkai Core Report: {bundle.hc_run_id} ===",
        f"Request ID : {bundle.request_id}",
        f"Elapsed    : {bundle.elapsed_sec:.3f}s",
        "",
        "--- Energy Estimate ---",
        f"  Total Energy (E_H)   : {e.total_energy:.6f}",
        f"  Generation Rate (G_H): {e.generation_rate:.6f}",
        f"  Dissipation Rate (D_H): {e.dissipation_rate:.6f}",
        f"  Gain Factor (Gamma_H): {e.gain_factor:.4f}",
        f"  Density (rho_H)      : {e.density:.6f}",
        f"  State                : {e.state}",
        "",
        "--- Threshold Assessment ---",
        f"  Collapse Threshold   : {t.theta_collapse:.4f}",
        f"  Current Maturity     : {t.current_maturity:.4f}",
        f"  Collapse Margin      : {t.margin_collapse:+.4f}",
        f"  Honkai Margin        : {t.margin_honkai:+.4f}",
        f"  Breach               : {'YES' if t.breach else 'no'}",
        f"  Breach Type          : {t.breach_type or 'N/A'}",
        "",
        f"--- Risk Entries ({len(bundle.risk_entries)}) ---",
    ]

    for r in bundle.risk_entries:
        lines.append(
            f"  [{r.risk_level:8s}] {r.candidate_id}: "
            f"score={r.risk_score:.3f} density={r.honkai_density:.4f} "
            f"margin={r.threshold_margin:+.4f}"
        )

    lines += [
        "",
        "--- Rewrite Assessment ---",
        f"  Feasible : {bundle.rewrite_assessment.rewrite_feasible}",
        f"  Risk     : {bundle.rewrite_assessment.rewrite_risk:.3f}",
        f"  Action   : {bundle.rewrite_assessment.recommended_action}",
        "",
        "--- Recommendation ---",
        f"  Action   : {rec.action}",
        f"  Confidence: {rec.confidence:.3f}",
        f"  Writeback : {'allowed' if rec.writeback_allowed else 'BLOCKED'}",
        f"  Reason   : {rec.reason}",
        "",
    ]

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath
