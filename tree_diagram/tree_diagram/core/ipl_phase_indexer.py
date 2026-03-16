from __future__ import annotations

"""core/ipl_phase_indexer.py

IPL (Influence-Propagation Layer) phase indexer.

Architecture position:
  core layer — sits above umdst_kernel, below pipeline.
  Wraps build_ipl() from umdst_kernel and provides addressable,
  phase-partitioned index structures for downstream routing decisions.

Responsibilities:
  - Incremental IPL index construction via build_ipl()
  - Phase-partition slicing (coarse / fine bins)
  - Key-based address lookup for cache / dispatcher layers
  - Phase-zone labelling (stable / transition / critical)
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .umdst_kernel import TDOutputs, build_ipl


# ---------------------------------------------------------------------------
# Phase zone boundaries
# ---------------------------------------------------------------------------
ZONE_STABLE     = (0.0,  0.55)
ZONE_TRANSITION = (0.55, 0.85)
ZONE_CRITICAL   = (0.85, 1.20)

COARSE_BINS  = 10
FINE_BINS    = 20


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class IPLEntry:
    """Single index entry representing one evaluated path."""
    path_id:       str
    z:             List[float]   # raw IPL coordinates [mean_p, var_p, mean_c, peak_c]
    z_s:           List[float]   # smoothed IPL coordinates
    coarse_key:    int           # coarse bin index [0, COARSE_BINS)
    variance_key:  int           # variance bin index [0, 10)
    phase_zone:    str           # "stable" | "transition" | "critical"
    phase_final:   float
    phase_max:     float


@dataclass
class IPLIndex:
    """Full IPL index over a candidate set."""
    entries:      List[IPLEntry] = field(default_factory=list)
    _by_coarse:   Dict[int, List[int]] = field(default_factory=dict, repr=False)
    _by_zone:     Dict[str, List[int]] = field(default_factory=dict, repr=False)

    def _rebuild(self) -> None:
        self._by_coarse = {}
        self._by_zone = {}
        for i, e in enumerate(self.entries):
            self._by_coarse.setdefault(e.coarse_key, []).append(i)
            self._by_zone.setdefault(e.phase_zone, []).append(i)

    def lookup_coarse(self, key: int) -> List[IPLEntry]:
        return [self.entries[i] for i in self._by_coarse.get(key, [])]

    def lookup_zone(self, zone: str) -> List[IPLEntry]:
        return [self.entries[i] for i in self._by_zone.get(zone, [])]

    def top_by_smoothed_gain(self, k: int = 5) -> List[IPLEntry]:
        """Return k entries with highest smoothed mean gain (z_s[2])."""
        return sorted(self.entries, key=lambda e: e.z_s[2], reverse=True)[:k]


# ---------------------------------------------------------------------------
# Phase zone classifier
# ---------------------------------------------------------------------------

def classify_phase_zone(phase_final: float) -> str:
    """Map a scalar phase value to a named zone."""
    if phase_final < ZONE_STABLE[1]:
        return "stable"
    if phase_final < ZONE_TRANSITION[1]:
        return "transition"
    return "critical"


# ---------------------------------------------------------------------------
# Fine-grained phase partitioning
# ---------------------------------------------------------------------------

def phase_fine_bin(phase_value: float, n_bins: int = FINE_BINS) -> int:
    """Map phase_value in [0, 1.2] to a fine bin index."""
    lo, hi = 0.0, 1.2
    frac = max(0.0, min(1.0, (phase_value - lo) / (hi - lo)))
    return min(n_bins - 1, int(frac * n_bins))


def phase_partition(
    entries: List[IPLEntry],
    n_bins: int = FINE_BINS,
) -> Dict[int, List[IPLEntry]]:
    """Partition entries into fine-grained phase bins."""
    buckets: Dict[int, List[IPLEntry]] = {}
    for e in entries:
        b = phase_fine_bin(e.phase_final, n_bins)
        buckets.setdefault(b, []).append(e)
    return buckets


# ---------------------------------------------------------------------------
# Index builder
# ---------------------------------------------------------------------------

def build_ipl_entry(
    path_id: str,
    td: TDOutputs,
    prev_ipl: Optional[Dict[str, Any]] = None,
    alpha: float = 0.35,
) -> Tuple[IPLEntry, Dict[str, Any]]:
    """Build one IPLEntry from a TDOutputs and return (entry, raw_ipl_dict).

    The raw ipl dict is the format expected by umdst_kernel.build_ipl and can
    be passed as prev_ipl on the next call for incremental smoothing.
    """
    ipl_dict = build_ipl(td, prev_ipl=prev_ipl, alpha=alpha)
    z   = ipl_dict["z"]
    z_s = ipl_dict["z_s"]
    keys = ipl_dict["keys"]

    phase_final = td.meta.get("phase_final", z_s[2])
    phase_max   = td.meta.get("phase_max",   z_s[2])

    entry = IPLEntry(
        path_id=path_id,
        z=z,
        z_s=z_s,
        coarse_key=keys["coarse"],
        variance_key=keys["variance_bin"],
        phase_zone=classify_phase_zone(phase_final),
        phase_final=phase_final,
        phase_max=phase_max,
    )
    return entry, ipl_dict


def build_ipl_index(
    path_ids: List[str],
    td_list: List[TDOutputs],
    alpha: float = 0.35,
) -> IPLIndex:
    """Build a full IPLIndex from a sequence of (path_id, TDOutputs) pairs.

    IPL smoothing is applied incrementally across the sequence, so order matters:
    earlier entries serve as the 'prev_ipl' context for later ones.
    """
    if len(path_ids) != len(td_list):
        raise ValueError("path_ids and td_list must have the same length")

    index = IPLIndex()
    prev_ipl: Optional[Dict[str, Any]] = None

    for pid, td in zip(path_ids, td_list):
        entry, prev_ipl = build_ipl_entry(pid, td, prev_ipl=prev_ipl, alpha=alpha)
        index.entries.append(entry)

    index._rebuild()
    return index


# ---------------------------------------------------------------------------
# Address lookup helpers
# ---------------------------------------------------------------------------

def address_from_ipl(ipl_dict: Dict[str, Any]) -> Tuple[int, int]:
    """Extract (coarse_key, variance_key) address from a raw ipl dict."""
    keys = ipl_dict.get("keys", {})
    return keys.get("coarse", 0), keys.get("variance_bin", 0)


def smoothed_gain_centroid(index: IPLIndex) -> float:
    """Compute the mean smoothed gain centroid across all index entries."""
    if not index.entries:
        return 0.0
    return sum(e.z_s[2] for e in index.entries) / len(index.entries)


def phase_spread(index: IPLIndex) -> float:
    """Return the spread (max - min) of phase_final values across the index."""
    if not index.entries:
        return 0.0
    phases = [e.phase_final for e in index.entries]
    return max(phases) - min(phases)


def zone_summary(index: IPLIndex) -> Dict[str, int]:
    """Count entries per phase zone."""
    summary: Dict[str, int] = {"stable": 0, "transition": 0, "critical": 0}
    for e in index.entries:
        summary[e.phase_zone] = summary.get(e.phase_zone, 0) + 1
    return summary


# ---------------------------------------------------------------------------
# High-level façade class (used by tests and oracle layer)
# ---------------------------------------------------------------------------

class IPLPhaseIndexer:
    """Thin façade that builds an IPLIndex from a ProblemSeed + ProblemBackground.

    Runs a minimal single-step UMDST simulation to obtain a TDOutputs object,
    then constructs a one-entry IPLIndex.  Sufficient for smoke-testing and
    for the oracle report layer to obtain zone / phase-address info without
    a full rollout.
    """

    def __init__(self, seed, background) -> None:
        self._seed = seed
        self._bg   = background

    def build_index(self) -> Dict[str, Any]:
        """Return a summary dict of the IPL phase index for the seed."""
        from .umdst_kernel import TDOutputs

        subj = self._seed.subject
        phase = float(subj.get("phase_proximity", 0.7))

        # Minimal TDOutputs with a one-bin riskfield / curve
        td = TDOutputs(
            riskfield=[phase],
            graph=[],
            curve=[phase],
            samples={},
            meta={"source": "IPLPhaseIndexer"},
        )

        entry, _ = build_ipl_entry("seed", td, prev_ipl=None, alpha=0.35)
        index = IPLIndex()
        index.entries.append(entry)
        index._rebuild()

        return {
            "phase_zone": entry.phase_zone,
            "phase_final": entry.phase_final,
            "phase_max": entry.phase_max,
            "coarse_key": entry.coarse_key,
            "zone_summary": zone_summary(index),
            "smoothed_gain_centroid": smoothed_gain_centroid(index),
            "phase_spread": phase_spread(index),
        }
