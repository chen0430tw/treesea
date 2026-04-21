"""Regression: _merge_states must actually merge cohort updates on BOTH
numpy and torch paths.

§11.20 — the torch branch used to silently fall through `return b`, so
chunked refinement on GPU never propagated cohort results into the full-B
state. Test builds a fake UnifiedState, calls _merge_states on a cohort
subset, and asserts that cohort slots pick up the new values while
non-cohort slots are preserved.
"""
import numpy as np
import pytest

from tree_diagram.core.worldline_kernel import UnifiedState, _merge_states


B      = 6
H, W   = 4, 5
COHORT = [1, 3, 5]
NON    = [0, 2, 4]


def _make_state(xp, fill_value: float) -> UnifiedState:
    """Build a UnifiedState where batched fields are filled with `fill_value`
    per candidate (actually per-candidate = fill_value + index so we can tell
    cohort slots apart)."""
    def batched(shape, offset):
        arr = xp.zeros(shape, dtype=xp.float32)
        for i in range(shape[0]):
            arr[i] = fill_value + offset + i
        return arr

    def shared(shape, val):
        return xp.full(shape, val, dtype=xp.float32)

    return UnifiedState(
        h=batched((B, H, W),   0.0),
        T=batched((B, H, W), 100.0),
        q=batched((B, H, W), 200.0),
        u=batched((B, H, W), 300.0),
        v=batched((B, H, W), 400.0),
        phase=batched((B,),    500.0),
        stress=batched((B,),   600.0),
        instability=batched((B,), 700.0),
        obs_h=shared((H, W), -1.0),
        obs_T=shared((H, W), -2.0),
        obs_q=shared((H, W), -3.0),
        obs_u=shared((H, W), -4.0),
        obs_v=shared((H, W), -5.0),
        topography=shared((H, W), -6.0),
    )


def _cohort_state(xp, source: UnifiedState) -> UnifiedState:
    """Build a replacement state with len(COHORT) candidates, distinct values."""
    k = len(COHORT)

    def mk(shape, offset):
        arr = xp.zeros(shape, dtype=xp.float32)
        for i in range(shape[0]):
            arr[i] = 9000.0 + offset + i
        return arr

    return UnifiedState(
        h=mk((k, H, W),   0.0),
        T=mk((k, H, W), 100.0),
        q=mk((k, H, W), 200.0),
        u=mk((k, H, W), 300.0),
        v=mk((k, H, W), 400.0),
        phase=mk((k,),    500.0),
        stress=mk((k,),   600.0),
        instability=mk((k,), 700.0),
        obs_h=source.obs_h, obs_T=source.obs_T, obs_q=source.obs_q,
        obs_u=source.obs_u, obs_v=source.obs_v, topography=source.topography,
    )


def _to_float(x):
    """Uniform scalar extraction from numpy/torch."""
    if hasattr(x, "cpu"):
        return float(x.cpu().numpy())
    return float(x)


def _check_merge(merged: UnifiedState, base: UnifiedState, cohort_new: UnifiedState):
    # Cohort slots should have been overwritten by cohort_new values.
    for k, cand_idx in enumerate(COHORT):
        assert np.isclose(_to_float(merged.phase[cand_idx]),
                          _to_float(cohort_new.phase[k])), (
            f"phase[cand {cand_idx}] not merged; got {merged.phase[cand_idx]}"
        )
        assert np.isclose(_to_float(merged.stress[cand_idx]),
                          _to_float(cohort_new.stress[k]))
        # 3D field — check one cell
        assert np.isclose(_to_float(merged.h[cand_idx, 0, 0]),
                          _to_float(cohort_new.h[k, 0, 0]))

    # Non-cohort slots preserved from base.
    for cand_idx in NON:
        assert np.isclose(_to_float(merged.phase[cand_idx]),
                          _to_float(base.phase[cand_idx])), (
            f"phase[cand {cand_idx}] mutated (should be preserved)"
        )
        assert np.isclose(_to_float(merged.h[cand_idx, 0, 0]),
                          _to_float(base.h[cand_idx, 0, 0]))

    # Shared obs fields unchanged.
    assert np.isclose(_to_float(merged.obs_h[0, 0]), -1.0)
    assert np.isclose(_to_float(merged.topography[0, 0]), -6.0)


def test_merge_states_numpy():
    base       = _make_state(np, fill_value=0.0)
    cohort_new = _cohort_state(np, base)
    merged     = _merge_states(base, cohort_new, COHORT, B)
    _check_merge(merged, base, cohort_new)


def test_merge_states_torch():
    torch = pytest.importorskip("torch")

    class TorchXP:
        """Minimal xp-like shim so _make_state can build torch tensors."""
        float32 = torch.float32
        @staticmethod
        def zeros(shape, dtype):
            return torch.zeros(*shape, dtype=dtype)
        @staticmethod
        def full(shape, val, dtype):
            return torch.full(shape, val, dtype=dtype)

    base       = _make_state(TorchXP, fill_value=0.0)
    cohort_new = _cohort_state(TorchXP, base)
    merged     = _merge_states(base, cohort_new, COHORT, B)
    _check_merge(merged, base, cohort_new)
    # Tensor identity check: cohort slot 1 should equal cohort_new row 0
    import torch as _t
    assert _t.allclose(merged.h[1], cohort_new.h[0])
    assert _t.allclose(merged.h[0], base.h[0])  # untouched
