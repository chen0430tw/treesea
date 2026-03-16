"""
Group Field Encoder — whitepaper Layer 3: Group Field Compression Layer.

Thin re-export wrapper so the whitepaper-mandated filename exists as an
independent entry-point.  All logic lives in group_field.py.
"""
from __future__ import annotations
from typing import Dict

from .problem_seed import ProblemSeed
from .group_field import encode_group_field


def encode(seed: ProblemSeed) -> Dict[str, float]:
    """Encode a ProblemSeed into a compressed group-field snapshot."""
    return encode_group_field(seed)


__all__ = ["encode", "encode_group_field"]
