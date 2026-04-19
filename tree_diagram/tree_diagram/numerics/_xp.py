"""Array-module dispatch helper (QCU-pattern).

TD numerics default to numpy (matches the anime's CPU-supercomputer identity).
When caller passes cupy arrays instead, get_xp dispatches all downstream ops
to cupy for GPU execution — same physics code, two backends.

Usage:
    from ._xp import get_xp
    def lap(f, DX, DY):
        xp = get_xp(f)
        return (xp.roll(f, -1, axis=1) - 2*f + xp.roll(f, 1, axis=1)) / DX**2 + ...
"""
from __future__ import annotations
import numpy as _np

try:
    import cupy as _cp
    _HAS_CUPY = True
    def get_xp(arr):
        """Return numpy or cupy module based on array type."""
        return _cp.get_array_module(arr)
except ImportError:
    _HAS_CUPY = False
    def get_xp(arr):
        return _np


def has_cupy() -> bool:
    return _HAS_CUPY


def to_numpy(arr):
    """Coerce array to numpy regardless of backend (for reporting/IO)."""
    if _HAS_CUPY and isinstance(arr, _cp.ndarray):
        return _cp.asnumpy(arr)
    return _np.asarray(arr)


def to_cupy(arr):
    """Coerce array to cupy (raises if cupy unavailable)."""
    if not _HAS_CUPY:
        raise RuntimeError("cupy not installed")
    return _cp.asarray(arr)
