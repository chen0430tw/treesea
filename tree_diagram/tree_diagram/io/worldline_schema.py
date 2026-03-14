from __future__ import annotations
import csv
from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass
class WorldlineRecord:
    family: str
    template: str
    params: str  # JSON-encoded string of params dict
    feasibility: float
    stability: float
    field_fit: float
    risk: float
    balanced_score: float
    nutrient_gain: float
    branch_status: str

    def to_dict(self) -> dict:
        return asdict(self)


def records_to_csv(records: List[WorldlineRecord], path: str) -> None:
    if not records:
        return
    fieldnames = list(records[0].to_dict().keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            writer.writerow(rec.to_dict())
