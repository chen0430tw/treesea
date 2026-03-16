"""Run profiles for Tree Diagram.

Each profile is a dict of kwargs forwarded to CandidatePipeline.
"""
from __future__ import annotations
from typing import Dict, Any

PROFILES: Dict[str, Dict[str, Any]] = {
    "quick": {
        "NX": 32, "NY": 24, "steps": 30,
        "top_k": 12,
        "_desc": "Fast smoke-test (~1s CPU, <0.1s GPU)",
    },
    "default": {
        "NX": 128, "NY": 96, "steps": 300,
        "top_k": 12,
        "_desc": "Standard run (~2s H100, ~10s CPU)",
    },
    "cluster": {
        "NX": 512, "NY": 384, "steps": 1000,
        "top_k": 20,
        "_desc": "Full-resolution cluster run (~90s H100)",
    },
    "deep": {
        "NX": 512, "NY": 384, "steps": 3000,
        "top_k": 20,
        "_desc": "Deep forecast (~270s H100, submit via Slurm)",
    },
}

def get_profile(name: str) -> Dict[str, Any]:
    if name not in PROFILES:
        raise ValueError(f"Unknown profile '{name}'. Available: {list(PROFILES)}")
    return {k: v for k, v in PROFILES[name].items() if not k.startswith("_")}
