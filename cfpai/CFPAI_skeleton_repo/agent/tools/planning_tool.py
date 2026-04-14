from __future__ import annotations
from typing import Any
from cfpai.service.planning_service import run_planning_service

def run_planning(symbols=None, start=None, end=None, mode="multiasset", config=None):
    out_folder = None if config is None else config.get("out_folder")
    return run_planning_service(symbols=symbols, start=start, end=end, out_folder=out_folder)
