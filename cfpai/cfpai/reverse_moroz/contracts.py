from __future__ import annotations
from dataclasses import dataclass

@dataclass
class ReverseMorozSnapshot:
    date: str
    scores: dict[str, float]
    candidates: dict[str, float]
