from __future__ import annotations
from cfpai.service.diagnostics_service import run_diagnostics_service

def explain_latest_run(run_dir: str) -> dict:
    return run_diagnostics_service(run_dir)
