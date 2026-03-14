# qcu_mapping_rules.py
from __future__ import annotations
from moroz.contracts.types import FrontierCandidate

def map_candidate_features(candidate: FrontierCandidate) -> dict:
    text = candidate.text
    return {
        "freq_hint": candidate.features.get("freq", candidate.base_score),
        "domain_hint": 1.0 if any(k in text for k in ["mail", "cloud", "site"]) else 0.0,
        "personal_hint": 1.0 if any(k in text for k in ["mimi", "luna"]) else 0.0,
        "context_hint": 1.0 if any(k in text for k in ["photo", "home", "cat", "kitty", "kitten"]) else 0.0,
        "syntax_hint": candidate.features.get("syntax", 1.0),
    }

def choose_profile(profile: str) -> str:
    return profile if profile in {"toy", "benchmark", "real"} else "benchmark"
