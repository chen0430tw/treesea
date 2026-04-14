from __future__ import annotations
import json
from pathlib import Path
import pandas as pd


def run_diagnostics_service(run_dir: str) -> dict:
    run_path = Path(run_dir)
    result = {"status": "ok" if run_path.exists() else "error", "run_dir": str(run_path), "anchors": [], "paths": [], "weights": {}, "risk_budget": None}
    if not run_path.exists():
        result["message"] = "Run directory does not exist."
        return result

    weights_path = run_path / "weights.csv"
    paths_path = run_path / "paths.csv"
    anchors_path = run_path / "anchor_scores.csv"
    stats_json = run_path / "stats.json"

    if weights_path.exists():
        w = pd.read_csv(weights_path)
        if len(w) > 0:
            latest = w.iloc[-1].to_dict()
            latest.pop("Date", None)
            result["weights"] = latest
            result["risk_budget"] = float(max(0.0, 1.0 - max(latest.values(), default=0.0)))

    if paths_path.exists():
        p = pd.read_csv(paths_path)
        if len(p) > 0:
            row = p.iloc[-1].to_dict()
            result["paths"] = [row.get("path")]
            result["anchor_asset"] = row.get("anchor_asset")
            result["secondary_asset"] = row.get("secondary_asset")

    if anchors_path.exists():
        a = pd.read_csv(anchors_path)
        if len(a) > 0:
            row = a.iloc[-1].drop(labels=["Date"]).sort_values(ascending=False)
            result["anchors"] = list(row.index[:3])

    if stats_json.exists():
        result["stats"] = json.loads(stats_json.read_text(encoding="utf-8"))
    return result
