from __future__ import annotations

"""llm_bridge/input_translator.py

LLM input translator: JSON / natural-language text → ProblemSeed.

Architecture position:
  llm_bridge layer — first stage of the LLM pipeline.  Accepts raw
  LLM output (structured JSON or free text) and normalises it into
  a ProblemSeed ready for the Tree Diagram core.

Supported input formats:
  1. dict  — pre-parsed JSON (used when LLM returns structured output)
  2. str   — JSON string (parsed then mapped)
  3. str   — free text (heuristic extraction of key-value pairs)
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..core.problem_seed import ProblemSeed, default_seed


# ---------------------------------------------------------------------------
# Translation result
# ---------------------------------------------------------------------------

@dataclass
class TranslationResult:
    """Result of input translation."""
    seed:          ProblemSeed
    confidence:    float        # [0, 1]; 1 = exact JSON match, lower for heuristic
    warnings:      List[str]
    raw_input:     str


# ---------------------------------------------------------------------------
# InputTranslator
# ---------------------------------------------------------------------------

class InputTranslator:
    """Translate LLM input into ProblemSeed.

    Usage::

        t = InputTranslator()
        r = t.translate(llm_output_str)
        seed = r.seed
    """

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def translate(self, raw: Any) -> TranslationResult:
        """Auto-detect format and translate to ProblemSeed."""
        raw_str = json.dumps(raw) if isinstance(raw, dict) else str(raw)

        if isinstance(raw, dict):
            return self._from_dict(raw, raw_str)

        if isinstance(raw, str):
            stripped = raw.strip()
            if stripped.startswith("{"):
                try:
                    d = json.loads(stripped)
                    return self._from_dict(d, raw_str)
                except json.JSONDecodeError:
                    pass
            return self._from_text(stripped, raw_str)

        # Fallback: default seed with low confidence
        return TranslationResult(
            seed=default_seed(),
            confidence=0.0,
            warnings=["Could not parse input; using default seed."],
            raw_input=raw_str,
        )

    # ------------------------------------------------------------------
    # Dict translation
    # ------------------------------------------------------------------

    def _from_dict(self, d: Dict[str, Any], raw_str: str) -> TranslationResult:
        warnings: List[str] = []
        confidence = 1.0

        title  = str(d.get("title",  d.get("name", "Untitled Problem")))
        target = str(d.get("target", d.get("goal", d.get("objective", ""))))

        constraints = d.get("constraints", [])
        if isinstance(constraints, str):
            constraints = [constraints]
        constraints = [str(c) for c in constraints]

        resources = self._extract_float_dict(d.get("resources", {}))
        environment = self._extract_float_dict(d.get("environment", {}))
        subject = self._extract_float_dict(d.get("subject", d.get("esper", {})))

        if not target:
            warnings.append("No 'target' field found; using empty string.")
            confidence -= 0.10
        if not resources:
            warnings.append("No 'resources' field; using defaults.")
            resources = {"budget": 0.50, "infrastructure": 0.50,
                         "data_coverage": 0.50, "population_coupling": 0.50}
            confidence -= 0.05
        if not subject:
            ds = default_seed()
            subject = ds.subject
            warnings.append("No 'subject' field; using default subject state.")
            confidence -= 0.10

        try:
            seed = ProblemSeed(
                title=title,
                target=target,
                constraints=constraints,
                resources=resources,
                environment=environment,
                subject=subject,
            )
        except Exception as exc:
            warnings.append(f"ProblemSeed construction error: {exc}; using default.")
            seed = default_seed()
            confidence = 0.1

        return TranslationResult(
            seed=seed,
            confidence=max(0.0, min(1.0, confidence)),
            warnings=warnings,
            raw_input=raw_str,
        )

    # ------------------------------------------------------------------
    # Free-text heuristic translation
    # ------------------------------------------------------------------

    def _from_text(self, text: str, raw_str: str) -> TranslationResult:
        warnings: List[str] = []

        # Attempt to extract a title line
        title_match = re.search(r"(?:title|problem|task)[\s:]+([^\n]+)", text, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else text[:60].strip()

        # Extract numeric values via heuristic pattern
        kv_pattern = re.compile(r"([a-z_][a-z0-9_]*)[\s:=]+([0-9]\.[0-9]+|0|1)", re.IGNORECASE)
        kv: Dict[str, float] = {}
        for m in kv_pattern.finditer(text):
            kv[m.group(1).lower()] = float(m.group(2))

        resource_keys  = {"budget", "infrastructure", "data_coverage", "population_coupling"}
        env_keys       = {"field_noise", "social_pressure", "regulatory_friction",
                          "network_density", "phase_instability"}
        subject_keys   = {"output_power", "control_precision", "load_tolerance",
                          "aim_coupling", "stress_level", "phase_proximity",
                          "marginal_decay", "instability_sensitivity"}

        resources   = {k: v for k, v in kv.items() if k in resource_keys}
        environment = {k: v for k, v in kv.items() if k in env_keys}
        subject     = {k: v for k, v in kv.items() if k in subject_keys}

        ds = default_seed()
        for store, defaults in ((resources, ds.resources), (environment, ds.environment), (subject, ds.subject)):
            for k, v in defaults.items():
                store.setdefault(k, v)

        confidence = 0.40 if kv else 0.20
        warnings.append("Free-text translation used; confidence may be low.")

        seed = ProblemSeed(
            title=title,
            target=text[:200],
            constraints=[],
            resources=resources,
            environment=environment,
            subject=subject,
        )
        return TranslationResult(
            seed=seed,
            confidence=confidence,
            warnings=warnings,
            raw_input=raw_str,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_float_dict(d: Any) -> Dict[str, float]:
        if not isinstance(d, dict):
            return {}
        result: Dict[str, float] = {}
        for k, v in d.items():
            try:
                result[str(k)] = float(v)
            except (TypeError, ValueError):
                pass
        return result
