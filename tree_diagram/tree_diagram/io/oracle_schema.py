from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List


@dataclass
class TreeOutputBundle:
    seed_title: str
    mode: str  # "candidate" | "weather" | "integrated"
    best_worldline: dict
    hydro_control: dict
    branch_histogram: dict
    oracle_details: dict
    elapsed_sec: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, default=_json_default)

    @classmethod
    def from_dict(cls, d: dict) -> "TreeOutputBundle":
        return cls(
            seed_title=d["seed_title"],
            mode=d["mode"],
            best_worldline=d["best_worldline"],
            hydro_control=d["hydro_control"],
            branch_histogram=d["branch_histogram"],
            oracle_details=d["oracle_details"],
            elapsed_sec=d.get("elapsed_sec", 0.0),
        )

    @classmethod
    def from_json(cls, s: str) -> "TreeOutputBundle":
        return cls.from_dict(json.loads(s))


def _json_default(obj):
    try:
        import numpy as np
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
    except ImportError:
        pass
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
