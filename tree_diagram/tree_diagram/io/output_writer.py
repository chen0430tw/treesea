from __future__ import annotations
import json
import csv
from pathlib import Path
from typing import List

from .oracle_schema import TreeOutputBundle
from .worldline_schema import WorldlineRecord
from ..core.worldline_kernel import EvaluationResult


def write_oracle_json(bundle: TreeOutputBundle, path: str) -> None:
    Path(path).write_text(bundle.to_json(indent=2), encoding="utf-8")


def write_worldlines_csv(results: List[EvaluationResult], path: str) -> None:
    if not results:
        return

    import json as _json

    records: List[WorldlineRecord] = []
    for r in results:
        records.append(
            WorldlineRecord(
                family=r.family,
                template=r.template,
                params=_json.dumps(r.params),
                feasibility=r.feasibility,
                stability=r.stability,
                field_fit=r.field_fit,
                risk=r.risk,
                balanced_score=r.balanced_score,
                nutrient_gain=r.nutrient_gain,
                branch_status=r.branch_status,
            )
        )

    fieldnames = list(records[0].to_dict().keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            writer.writerow(rec.to_dict())


def write_state_npz(state, obs, topography, path: str) -> None:
    import numpy as np
    np.savez(
        path,
        h=state.h,
        u=state.u,
        v=state.v,
        T=state.T,
        q=state.q,
        obs_h=obs.h,
        obs_u=obs.u,
        obs_v=obs.v,
        obs_T=obs.T,
        obs_q=obs.q,
        topography=topography,
    )
