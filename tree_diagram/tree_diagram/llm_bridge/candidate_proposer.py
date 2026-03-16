from __future__ import annotations

"""llm_bridge/candidate_proposer.py

LLM candidate proposer: LLM output → CandidateWorldline list.

Architecture position:
  llm_bridge layer — second stage.  Takes structured LLM proposals
  (family name + parameter overrides) and maps them to a list of
  candidate dicts compatible with worldline_kernel.generate_candidates().

The proposer does NOT run any simulation; it only translates LLM-native
"candidate ideas" into Tree Diagram candidate format.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Known families and default parameters
# ---------------------------------------------------------------------------

_KNOWN_FAMILIES = {
    "batch", "phase", "hybrid", "network", "electrical",
    "ascetic", "composite",
    "weak_mix", "balanced", "high_mix", "humid_bias", "strong_pg", "terrain_lock",
}

_DEFAULT_PLAN_PARAMS: Dict[str, float] = {
    "n": 15000.0, "rho": 0.7, "A": 0.7, "sigma": 0.05,
    "aim_coupling": 0.85, "marginal_decay": 0.10,
}

_DEFAULT_WEATHER_PARAMS: Dict[str, float] = {
    "Kh": 300.0, "Kt": 150.0, "Kq": 125.0,
    "drag": 1.5e-5, "humid_couple": 1.0,
    "nudging": 1.5e-4, "pg_scale": 1.0,
}

_WEATHER_FAMILIES = {"weak_mix", "balanced", "high_mix", "humid_bias", "strong_pg", "terrain_lock"}


# ---------------------------------------------------------------------------
# Proposed candidate
# ---------------------------------------------------------------------------

@dataclass
class ProposedCandidate:
    """A candidate proposed by the LLM."""
    family:       str
    template:     str
    params:       Dict[str, float]
    kind:         str            # "plan" | "weather"
    llm_rationale: str           # raw LLM justification string


# ---------------------------------------------------------------------------
# CandidateProposer
# ---------------------------------------------------------------------------

class CandidateProposer:
    """Translate LLM proposals into Tree Diagram candidate dicts.

    Usage::

        proposer = CandidateProposer()
        candidates = proposer.propose(llm_response_str)
    """

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def propose(self, llm_output: Any) -> List[ProposedCandidate]:
        """Parse LLM output and return a list of ProposedCandidates.

        Accepts:
          - list of dicts with "family" / "params" keys
          - single dict
          - JSON string
          - free-text with family names
        """
        if isinstance(llm_output, str):
            llm_output = llm_output.strip()
            if llm_output.startswith("[") or llm_output.startswith("{"):
                try:
                    llm_output = json.loads(llm_output)
                except json.JSONDecodeError:
                    return self._from_text(llm_output)

        if isinstance(llm_output, list):
            return [self._parse_one(item) for item in llm_output if isinstance(item, dict)]

        if isinstance(llm_output, dict):
            return [self._parse_one(llm_output)]

        if isinstance(llm_output, str):
            return self._from_text(llm_output)

        return []

    # ------------------------------------------------------------------
    # Single candidate parsing
    # ------------------------------------------------------------------

    def _parse_one(self, d: Dict[str, Any]) -> ProposedCandidate:
        family = str(d.get("family", d.get("type", "batch"))).lower()
        if family not in _KNOWN_FAMILIES:
            family = "batch"   # fallback

        kind = "weather" if family in _WEATHER_FAMILIES else "plan"
        template = str(d.get("template", f"{family}_route"))

        # Start from defaults, apply overrides
        base = dict(_DEFAULT_WEATHER_PARAMS if kind == "weather" else _DEFAULT_PLAN_PARAMS)
        raw_params = d.get("params", d.get("parameters", {}))
        if isinstance(raw_params, dict):
            for k, v in raw_params.items():
                try:
                    base[str(k)] = float(v)
                except (TypeError, ValueError):
                    pass

        rationale = str(d.get("rationale", d.get("reason", d.get("justification", ""))))

        # Merge both param sets so every candidate carries full keys
        if kind == "plan":
            for k, v in _DEFAULT_WEATHER_PARAMS.items():
                base.setdefault(k, v)
        else:
            for k, v in _DEFAULT_PLAN_PARAMS.items():
                base.setdefault(k, v)

        return ProposedCandidate(
            family=family,
            template=template,
            params=base,
            kind=kind,
            llm_rationale=rationale,
        )

    # ------------------------------------------------------------------
    # Free-text fallback
    # ------------------------------------------------------------------

    def _from_text(self, text: str) -> List[ProposedCandidate]:
        """Extract family mentions from free text."""
        import re
        found: List[ProposedCandidate] = []
        for family in _KNOWN_FAMILIES:
            if re.search(r"\b" + re.escape(family) + r"\b", text, re.IGNORECASE):
                kind = "weather" if family in _WEATHER_FAMILIES else "plan"
                base = dict(_DEFAULT_WEATHER_PARAMS if kind == "weather" else _DEFAULT_PLAN_PARAMS)
                if kind == "plan":
                    for k, v in _DEFAULT_WEATHER_PARAMS.items():
                        base.setdefault(k, v)
                else:
                    for k, v in _DEFAULT_PLAN_PARAMS.items():
                        base.setdefault(k, v)
                found.append(ProposedCandidate(
                    family=family,
                    template=f"{family}_route",
                    params=base,
                    kind=kind,
                    llm_rationale=f"Extracted from free text: '{family}'",
                ))
        return found

    # ------------------------------------------------------------------
    # Convert to worldline_kernel candidate format
    # ------------------------------------------------------------------

    def to_candidate_dicts(
        self,
        proposed: List[ProposedCandidate],
    ) -> List[Dict[str, Any]]:
        """Convert ProposedCandidates to the flat dict format used by
        worldline_kernel.prepare_candidate_arrays()."""
        return [
            {
                "family":   p.family,
                "template": p.template,
                "params":   dict(p.params),
                "kind":     p.kind,
            }
            for p in proposed
        ]
