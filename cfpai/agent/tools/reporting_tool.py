from __future__ import annotations
from cfpai.service.reporting_service import run_reporting_service

def build_report(run_dir: str, format: str = "markdown") -> str:
    result = run_reporting_service(run_dir)
    return result.get("report", "")
