from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from cfpai.contracts.params import CFPAIParams


def save_run(out_folder: str | Path, symbols: list[str], params: CFPAIParams, result: pd.DataFrame, stats: dict, scores: pd.DataFrame, candidates: pd.DataFrame, paths: pd.DataFrame, weights: pd.DataFrame) -> Path:
    out = Path(out_folder)
    out.mkdir(parents=True, exist_ok=True)

    result.to_csv(out / "multiasset_signals.csv", index=False, encoding="utf-8-sig")
    scores.to_csv(out / "anchor_scores.csv", index=False, encoding="utf-8-sig")
    candidates.to_csv(out / "candidate_scores.csv", index=False, encoding="utf-8-sig")
    paths.to_csv(out / "paths.csv", index=False, encoding="utf-8-sig")
    weights.to_csv(out / "weights.csv", index=False, encoding="utf-8-sig")

    (out / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "params.json").write_text(json.dumps(asdict(params), indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "symbols.json").write_text(json.dumps(symbols, indent=2, ensure_ascii=False), encoding="utf-8")

    plt.figure(figsize=(10, 6))
    plt.plot(result["Date"], result["equity"])
    plt.yscale("log")
    plt.title("CFPAI Equity Curve")
    plt.tight_layout()
    plt.savefig(out / "equity_curve.png", dpi=160)
    plt.close()

    last_w = weights.iloc[-1].drop(labels=["Date"]).sort_values(ascending=False)
    plt.figure(figsize=(10, 5))
    plt.bar(last_w.index, last_w.values)
    plt.xticks(rotation=45, ha="right")
    plt.title("Latest CFPAI Asset Weights")
    plt.tight_layout()
    plt.savefig(out / "latest_weights.png", dpi=160)
    plt.close()

    report = f"# CFPAI Report\n\n## Symbols\n{', '.join(symbols)}\n\n## Stats\n```json\n{json.dumps(stats, indent=2, ensure_ascii=False)}\n```\n"
    (out / "report.md").write_text(report, encoding="utf-8")
    return out
