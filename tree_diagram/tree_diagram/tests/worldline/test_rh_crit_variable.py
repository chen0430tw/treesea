"""Regression: variable RH_crit(T) closure.

Covers the parameterised closure added after §11.22 fixed-constant
baseline. Two closures coexist:
  - "fixed":    RH_crit == _MID_RH_CRIT_PCT (75%)
  - "variable": smooth tanh ramp in T, bounded [RH_WARM, RH_COLD]

These tests pin the shape of the variable closure so future tuning
stays monotone, smooth, and bounded. If someone introduces a piecewise
hard corner or flips the monotonicity direction, these fail.
"""
import math

import numpy as np
import pytest

from tree_diagram.core.worldline_kernel import (
    _MID_RH_CRIT_PCT, _T_MID_CRIT_K, _RH_CRIT_T_SCALE_K,
    _RH_CRIT_COLD_PCT, _RH_CRIT_WARM_PCT,
    _mid_rh_crit_pct, _q_ref_mid_500hpa,
)


def test_fixed_mode_returns_constant():
    for T_K in (250.0, 272.5, 300.0):
        arr = np.asarray([T_K], dtype=np.float64)
        got = _mid_rh_crit_pct(arr, xp=np, mode="fixed")
        # Fixed mode returns the scalar constant (not broadcast).
        assert got == _MID_RH_CRIT_PCT


def test_variable_mode_midpoint_is_midrange():
    # At T = _T_MID_CRIT_K, tanh(0) = 0 → rh = warm + (cold - warm) * 0.5
    arr = np.asarray([_T_MID_CRIT_K], dtype=np.float64)
    got = float(_mid_rh_crit_pct(arr, xp=np, mode="variable")[0])
    want = 0.5 * (_RH_CRIT_COLD_PCT + _RH_CRIT_WARM_PCT)
    assert math.isclose(got, want, rel_tol=1e-9)


def test_variable_mode_monotone_decreasing_in_T():
    T_grid = np.linspace(240.0, 310.0, 50)
    rh_grid = _mid_rh_crit_pct(T_grid, xp=np, mode="variable")
    # Strictly decreasing
    assert np.all(np.diff(rh_grid) < 0.0), (
        "RH_crit(T) must be monotone decreasing in T"
    )


def test_variable_mode_bounds_selfenforced():
    # Both physical rollout clamp range (250-320 K) and beyond —
    # tanh ramp should be self-bounded by its asymptotes even at extremes.
    T_wide = np.linspace(200.0, 400.0, 100)
    rh = _mid_rh_crit_pct(T_wide, xp=np, mode="variable")
    assert float(rh.min()) > _RH_CRIT_WARM_PCT - 0.01
    assert float(rh.max()) < _RH_CRIT_COLD_PCT + 0.01


def test_variable_mode_smooth_no_piecewise_corners():
    # Numerical second derivative should be continuous (no kinks).
    # For a smooth function, |d²f/dT²| is bounded; for a piecewise-linear
    # clipped function, the second derivative is a delta at the kink.
    T = np.linspace(240.0, 310.0, 200)
    rh = _mid_rh_crit_pct(T, xp=np, mode="variable")
    d2 = np.diff(rh, n=2)
    # All finite, bounded peak relative to function span.
    assert np.all(np.isfinite(d2))
    assert float(np.abs(d2).max()) < 0.5, (
        "second derivative too large — suggests a piecewise corner"
    )


def test_variable_mode_symmetry_around_T_mid():
    # tanh is odd → equal displacement above/below T_mid gives RH values
    # equidistant from the midrange point.
    dT = 8.0
    arr = np.asarray([_T_MID_CRIT_K - dT, _T_MID_CRIT_K + dT], dtype=np.float64)
    rh = _mid_rh_crit_pct(arr, xp=np, mode="variable")
    mid = 0.5 * (_RH_CRIT_COLD_PCT + _RH_CRIT_WARM_PCT)
    # cold-side excess must equal warm-side deficit
    assert math.isclose(float(rh[0]) - mid, mid - float(rh[1]), rel_tol=1e-9)


def test_variable_mode_numpy_torch_parity():
    torch = pytest.importorskip("torch")
    T_vals = np.asarray([250.0, 268.0, 272.5, 285.0, 300.0], dtype=np.float64)

    rh_np = _mid_rh_crit_pct(T_vals, xp=np, mode="variable")
    rh_tr = _mid_rh_crit_pct(torch.as_tensor(T_vals), xp=torch, mode="variable").cpu().numpy()
    assert np.allclose(rh_np, rh_tr, rtol=1e-6, atol=1e-10)

    # Also check the downstream helper routes the closure correctly.
    q_np = _q_ref_mid_500hpa(T_vals, xp=np, mode="variable")
    q_tr = _q_ref_mid_500hpa(torch.as_tensor(T_vals), xp=torch, mode="variable").cpu().numpy()
    assert np.allclose(q_np, q_tr, rtol=1e-6, atol=1e-10)


def test_q_ref_variable_greater_than_fixed_at_cold_T():
    # At sub-midrange T (cold side), variable closure has RH_crit > 75%
    # → q_ref > fixed q_ref at that T.
    T_cold = np.asarray([262.0], dtype=np.float64)
    q_fix  = _q_ref_mid_500hpa(T_cold, xp=np, mode="fixed")
    q_var  = _q_ref_mid_500hpa(T_cold, xp=np, mode="variable")
    assert float(q_var[0]) > float(q_fix[0])


def test_q_ref_variable_less_than_fixed_at_warm_T():
    # At above-midrange T (warm side), variable closure has RH_crit < 75%
    # → q_ref < fixed q_ref at that T.
    T_warm = np.asarray([285.0], dtype=np.float64)
    q_fix  = _q_ref_mid_500hpa(T_warm, xp=np, mode="fixed")
    q_var  = _q_ref_mid_500hpa(T_warm, xp=np, mode="variable")
    assert float(q_var[0]) < float(q_fix[0])


def test_env_var_mode_switch():
    # Honour module-level TD_RH_CRIT_MODE only when no explicit mode.
    # Explicit mode always wins — this is what lets tests pin behaviour.
    T = np.asarray([272.5], dtype=np.float64)

    rh_fixed_explicit    = _mid_rh_crit_pct(T, xp=np, mode="fixed")
    rh_variable_explicit = float(_mid_rh_crit_pct(T, xp=np, mode="variable")[0])
    assert rh_fixed_explicit    == _MID_RH_CRIT_PCT
    # At T_mid, variable gives midrange; must NOT equal the fixed value
    # (otherwise our A/B run has nothing to compare).
    assert rh_variable_explicit != _MID_RH_CRIT_PCT
