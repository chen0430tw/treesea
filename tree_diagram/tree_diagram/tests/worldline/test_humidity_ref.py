"""Regression: mid-level humidity reference formula.

§11.22 — the rollout's condensation threshold must stay aligned with the
Tetens-based encoding used when initial states are built from surface obs.
Previously `sat = 0.0045 * exp(0.060 * (T - 273.15) / 10)` gave a q pinned
at ~63% of Tetens q_sat. First fix attempt used full q_sat (no RH_crit
multiplier) and overshot to ~100%. Final fix: q_ref at RH_crit=75%.

These tests guard against:
  1. The helper formula drifting from the Tetens reference used in
     td_taipei_forecast.build_taipei_state lines 96-99.
  2. numpy vs torch numerical divergence (silent path drift).
  3. Default rh_pct being re-set to 100 (reintroducing the over-shoot).
"""
import math

import numpy as np
import pytest

from tree_diagram.core.worldline_kernel import (
    _MID_RH_CRIT_PCT, _P_MID_HPA, _q_ref_mid_500hpa,
)


def _expected_q_ref(T_K: float, rh_pct: float) -> float:
    """Direct replication of the four-line Tetens encoding used in
    td_taipei_forecast.build_taipei_state (lines 96-99)."""
    T_C       = T_K - 273.15
    e_sat_hPa = 6.11 * math.exp(17.27 * T_C / (T_C + 237.3))
    e_hPa     = e_sat_hPa * rh_pct / 100.0
    return 0.622 * e_hPa / (_P_MID_HPA - e_hPa)


def test_helper_matches_encoding_formula_numpy():
    # Range bracketing a realistic mid-level rollout (250 K .. 300 K).
    for T_K in (250.0, 268.0, 272.0, 285.0, 300.0):
        arr = np.asarray([T_K], dtype=np.float64)
        got = float(_q_ref_mid_500hpa(arr, xp=np)[0])
        want = _expected_q_ref(T_K, _MID_RH_CRIT_PCT)
        assert math.isclose(got, want, rel_tol=1e-9), (
            f"helper vs encoding mismatch @ T={T_K}: got={got} want={want}"
        )


def test_helper_custom_rh_pct():
    # rh_pct is a parameter; verify the helper honours overrides and
    # defaults to _MID_RH_CRIT_PCT (guards against someone flipping the
    # default back to 100 and reintroducing the §11.22 overshoot).
    T_K = 272.0
    arr = np.asarray([T_K], dtype=np.float64)

    q_default = float(_q_ref_mid_500hpa(arr, xp=np)[0])
    q_explicit = float(_q_ref_mid_500hpa(arr, xp=np, rh_pct=_MID_RH_CRIT_PCT)[0])
    assert q_default == q_explicit, "default rh_pct is not _MID_RH_CRIT_PCT"

    q_sat = float(_q_ref_mid_500hpa(arr, xp=np, rh_pct=100.0)[0])
    q_50  = float(_q_ref_mid_500hpa(arr, xp=np, rh_pct=50.0)[0])
    assert q_50 < q_default < q_sat, (
        f"expected q_50 < q_ref(75%) < q_sat; got {q_50}, {q_default}, {q_sat}"
    )


def test_default_rh_crit_is_75():
    # Explicitly pin the closure constant. If someone bumps it to 100
    # (undoing §11.22) or to some other locale-specific value, this
    # test fails and forces review.
    assert _MID_RH_CRIT_PCT == 75.0, (
        f"_MID_RH_CRIT_PCT drifted to {_MID_RH_CRIT_PCT}; "
        "§11.22 closure value should stay 75% unless explicitly retuned"
    )


def test_numpy_torch_parity():
    torch = pytest.importorskip("torch")

    T_vals = np.asarray([250.0, 268.0, 272.0, 285.0, 300.0], dtype=np.float64)
    q_np   = _q_ref_mid_500hpa(T_vals, xp=np)
    q_tr   = _q_ref_mid_500hpa(torch.as_tensor(T_vals), xp=torch).cpu().numpy()
    assert np.allclose(q_np, q_tr, rtol=1e-6, atol=1e-10), (
        f"numpy/torch helper output diverged: np={q_np}  torch={q_tr}"
    )


def test_helper_shape_preserves_batch():
    # 2D field input (B, H, W) — rollout passes this shape via T_a.
    T_field = 272.0 + np.random.RandomState(0).uniform(-5, 5, size=(4, 8, 6))
    out = _q_ref_mid_500hpa(T_field, xp=np)
    assert out.shape == (4, 8, 6)
    # Monotone in T: at higher T, e_sat grows, q_ref grows.
    T_cold = np.full((2,), 260.0)
    T_warm = np.full((2,), 285.0)
    assert (_q_ref_mid_500hpa(T_warm, xp=np) > _q_ref_mid_500hpa(T_cold, xp=np)).all()
