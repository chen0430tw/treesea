from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ResourceBudget:
    max_candidates: int = 300
    top_k: int = 12
    max_steps: int = 240
    n_workers: int = 1
