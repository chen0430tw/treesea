"""Abstract protocol for group field encoding.

Concrete implementation: tree_diagram.core.group_field
"""
from __future__ import annotations
from typing import Dict, Protocol, runtime_checkable


# The five canonical group-field axes produced by encode_group_field.
GROUP_FIELD_AXES = (
    "field_coherence",
    "network_amplification",
    "governance_drag",
    "phase_turbulence",
    "resource_elasticity",
)


@runtime_checkable
class GroupFieldEncoderProtocol(Protocol):
    """Callable: seed → normalised [0,1] group-field dict."""

    def __call__(self, seed: object) -> Dict[str, float]: ...
