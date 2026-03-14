from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List
import json
from pathlib import Path


@dataclass
class ProblemSeed:
    title: str
    target: str
    constraints: List[str]
    resources: Dict[str, float]
    environment: Dict[str, float]
    subject: Dict[str, float]

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> "ProblemSeed":
        return cls(**d)

    @classmethod
    def from_json(cls, s: str) -> "ProblemSeed":
        return cls.from_dict(json.loads(s))

    @classmethod
    def from_file(cls, path: str | Path) -> "ProblemSeed":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


def default_seed() -> ProblemSeed:
    return ProblemSeed(
        title="Urban Resonance Upgrade Program",
        target=(
            "Find the most viable route to upgrade a city-scale resonance system "
            "from Level-5-equivalent stability to Level-6-equivalent stability."
        ),
        constraints=[
            "must remain under city-level safety threshold",
            "must avoid irreversible collapse of field stability",
            "must be scalable under limited infrastructure budget",
            "must remain reproducible across repeated trials",
        ],
        resources={
            "budget": 0.62,
            "infrastructure": 0.71,
            "data_coverage": 0.66,
            "population_coupling": 0.83,
        },
        environment={
            "field_noise": 0.34,
            "social_pressure": 0.58,
            "regulatory_friction": 0.47,
            "network_density": 0.76,
            "phase_instability": 0.41,
        },
        subject={
            "output_power": 0.93,
            "control_precision": 0.88,
            "load_tolerance": 0.61,
            "aim_coupling": 0.97,
            "stress_level": 0.22,
            "phase_proximity": 0.69,
            "marginal_decay": 0.11,
            "instability_sensitivity": 0.28,
        },
    )
