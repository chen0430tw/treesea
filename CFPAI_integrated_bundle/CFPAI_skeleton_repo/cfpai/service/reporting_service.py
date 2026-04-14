from __future__ import annotations
from pathlib import Path

def run_reporting_service(run_dir: str) -> dict:
    run_path = Path(run_dir)
    report_path = run_path / "report.md"
    if report_path.exists():
        return {"status": "ok", "run_dir": str(run_path), "report": report_path.read_text(encoding="utf-8")}
    return {"status": "error", "run_dir": str(run_path), "report": f"# CFPAI Report\n\nNo report found in `{run_path}`.\n"}
