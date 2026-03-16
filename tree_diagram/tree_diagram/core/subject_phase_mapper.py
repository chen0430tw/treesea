from __future__ import annotations

"""core/subject_phase_mapper.py

Bidirectional mapper between SubjectState and group field dicts.

Architecture position:
  core layer — bridges umdst_kernel.SubjectState and the group_field
  encoding used by the abstract pipeline.

Responsibilities:
  - SubjectState → field dict (for oracle / hydro layers)
  - field dict → SubjectState (for initialisation from seed)
  - Phase proximity normalisation and clamping
  - Partial-field application (update only specified keys)
"""

from dataclasses import asdict
from typing import Dict, Optional

from .umdst_kernel import SubjectState


# ---------------------------------------------------------------------------
# Field key definitions
# ---------------------------------------------------------------------------

SUBJECT_FIELD_KEYS = (
    "output_power",
    "control_precision",
    "load_tolerance",
    "aim_coupling",
    "stress_level",
    "phase_proximity",
    "marginal_decay",
    "instability_sensitivity",
)

# Phase-related keys used for zone classification
PHASE_KEY    = "phase_proximity"
STRESS_KEY   = "stress_level"
INSTAB_KEY   = "instability_sensitivity"


# ---------------------------------------------------------------------------
# SubjectState → field dict
# ---------------------------------------------------------------------------

def subject_to_field(state: SubjectState) -> Dict[str, float]:
    """Convert a SubjectState to a flat field dict.

    All values are preserved as-is; callers may normalise separately.
    """
    return asdict(state)


def subject_to_normalised_field(state: SubjectState, hi: float = 1.2) -> Dict[str, float]:
    """Convert SubjectState to a field dict with values clamped to [0, 1].

    Useful when downstream components expect unit-range inputs.
    """
    raw = asdict(state)
    return {k: max(0.0, min(1.0, v / hi)) for k, v in raw.items()}


# ---------------------------------------------------------------------------
# field dict → SubjectState
# ---------------------------------------------------------------------------

def field_to_subject(field: Dict[str, float]) -> SubjectState:
    """Reconstruct a SubjectState from a field dict.

    Missing keys default to neutral values.
    """
    return SubjectState(
        output_power=           float(field.get("output_power",            0.80)),
        control_precision=      float(field.get("control_precision",       0.80)),
        load_tolerance=         float(field.get("load_tolerance",          0.70)),
        aim_coupling=           float(field.get("aim_coupling",            0.85)),
        stress_level=           float(field.get("stress_level",            0.25)),
        phase_proximity=        float(field.get("phase_proximity",         0.50)),
        marginal_decay=         float(field.get("marginal_decay",          0.10)),
        instability_sensitivity=float(field.get("instability_sensitivity", 0.30)),
    )


def field_to_subject_clamped(
    field: Dict[str, float],
    lo: float = 0.0,
    hi: float = 1.2,
) -> SubjectState:
    """Reconstruct SubjectState with clamping to [lo, hi]."""
    def _c(key: str, default: float) -> float:
        return max(lo, min(hi, float(field.get(key, default))))

    return SubjectState(
        output_power=           _c("output_power",            0.80),
        control_precision=      _c("control_precision",       0.80),
        load_tolerance=         _c("load_tolerance",          0.70),
        aim_coupling=           _c("aim_coupling",            0.85),
        stress_level=           _c("stress_level",            0.25),
        phase_proximity=        _c("phase_proximity",         0.50),
        marginal_decay=         _c("marginal_decay",          0.10),
        instability_sensitivity=_c("instability_sensitivity", 0.30),
    )


# ---------------------------------------------------------------------------
# Partial-field update
# ---------------------------------------------------------------------------

def apply_field_patch(
    state: SubjectState,
    patch: Dict[str, float],
) -> SubjectState:
    """Return a new SubjectState with selected fields updated from patch dict.

    Only keys that appear in both the SubjectState schema and the patch are
    updated; unknown keys are silently ignored.
    """
    current = asdict(state)
    for k in SUBJECT_FIELD_KEYS:
        if k in patch:
            current[k] = float(patch[k])
    return SubjectState(**current)


# ---------------------------------------------------------------------------
# Phase normalisation helpers
# ---------------------------------------------------------------------------

def phase_normalise(state: SubjectState, target_max: float = 1.0) -> SubjectState:
    """Scale phase_proximity so that phase_proximity == target_max → 1.0.

    Other fields are unchanged.
    """
    if target_max <= 1e-12:
        return state
    raw = asdict(state)
    raw["phase_proximity"] = min(1.2, state.phase_proximity / target_max)
    return SubjectState(**raw)


def phase_distance(a: SubjectState, b: SubjectState) -> float:
    """Euclidean distance between two SubjectStates in the phase-related subspace.

    Uses: phase_proximity, stress_level, instability_sensitivity.
    """
    dp = a.phase_proximity        - b.phase_proximity
    ds = a.stress_level           - b.stress_level
    di = a.instability_sensitivity - b.instability_sensitivity
    return (dp * dp + ds * ds + di * di) ** 0.5


def phase_alignment_score(state: SubjectState, target_phase: float = 0.95) -> float:
    """Score in [0, 1] measuring how aligned state is with target phase.

    Considers phase proximity (higher = better), stress and instability (lower = better).
    """
    phase_score   = max(0.0, min(1.0, state.phase_proximity / max(target_phase, 1e-9)))
    stress_pen    = 0.3 * max(0.0, min(1.0, state.stress_level))
    instab_pen    = 0.2 * max(0.0, min(1.0, state.instability_sensitivity))
    return max(0.0, phase_score - stress_pen - instab_pen)


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------

def subjects_to_field_matrix(states: list) -> list:
    """Convert a list of SubjectStates to a list of field dicts."""
    return [subject_to_field(s) for s in states]


def mean_subject_state(states: list) -> Optional[SubjectState]:
    """Return the component-wise mean of a list of SubjectStates."""
    if not states:
        return None
    n = len(states)
    vectors = [s.to_vector() for s in states]
    mean_vec = [sum(v[i] for v in vectors) / n for i in range(len(vectors[0]))]
    return SubjectState.from_vector(mean_vec)


# ---------------------------------------------------------------------------
# High-level façade class (used by tests and oracle layer)
# ---------------------------------------------------------------------------

class SubjectPhaseMapper:
    """Façade: derive a normalised phase-field snapshot from a seed + background.

    Constructs a SubjectState from the seed's subject dict, converts it to a
    normalised field dict, and adds phase-zone metadata derived from the
    group-field encoding.
    """

    def __init__(self, seed, background) -> None:
        self._seed = seed
        self._bg   = background

    def map(self) -> Dict[str, float]:
        """Return a normalised subject field dict with phase metadata."""
        subj = self._seed.subject
        state = SubjectState(
            output_power            = float(subj.get("aim_coupling", 0.9)),
            control_precision       = float(subj.get("control_precision", 0.8)),
            load_tolerance          = float(subj.get("phase_proximity", 0.7)),
            aim_coupling            = float(subj.get("aim_coupling", 0.9)),
            stress_level            = float(subj.get("stress_level", 0.2)),
            phase_proximity         = float(subj.get("phase_proximity", 0.7)),
            marginal_decay          = float(subj.get("marginal_decay", 0.1)),
            instability_sensitivity = float(subj.get("instability_sensitivity", 0.28)),
        )
        field = subject_to_normalised_field(state)
        field["phase_alignment_score"] = phase_alignment_score(state)
        return field
