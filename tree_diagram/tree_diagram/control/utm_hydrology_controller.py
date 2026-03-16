from __future__ import annotations

"""control/utm_hydrology_controller.py

H-UTM (Hydrology-coupled UTM) main-channel stability controller.

Architecture position:
  control layer — implements the hydro-adjusted UTM logic described
  in the v3_active prototype (hydro_adjust_top_candidates) and the
  abstract form in balance_layer.hydro_adjust_abstract().

Responsibilities:
  - Main-river (top-scoring) branch preservation under pressure
  - Tributary throttling when pressure_balance is low
  - Hydro state transitions (FLOW / DROUGHT / FLOOD)
  - Integration with UTMController for governance coupling
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..core.balance_layer import hydro_adjust_abstract, hydro_adjust_numerical, merge_hydro
from ..core.worldline_kernel import EvaluationResult
from .utm_controller import UTMController, UTMState


# ---------------------------------------------------------------------------
# Hydro state
# ---------------------------------------------------------------------------

HYDRO_FLOW    = "FLOW"       # pressure_balance ≈ 1.0 ± 0.15 — normal
HYDRO_DROUGHT = "DROUGHT"    # pressure_balance < 0.85 — supply insufficient
HYDRO_FLOOD   = "FLOOD"      # pressure_balance > 1.15 — overflow risk


def _classify_hydro(pressure_balance: float) -> str:
    if pressure_balance < 0.85:
        return HYDRO_DROUGHT
    if pressure_balance > 1.15:
        return HYDRO_FLOOD
    return HYDRO_FLOW


# ---------------------------------------------------------------------------
# Adjustment result
# ---------------------------------------------------------------------------

@dataclass
class HydroAdjustment:
    hydro_state:       str
    pressure_balance:  float
    main_channel_ids:  List[int]    # indices into results list
    throttled_ids:     List[int]
    utm_state:         str
    merged_hydro:      Dict


# ---------------------------------------------------------------------------
# H-UTM controller
# ---------------------------------------------------------------------------

class UTMHydrologyController:
    """Hydrology-coupled UTM main-channel stability controller.

    Combines abstract hydro (from EvaluationResult branch_status) and
    numerical hydro (from metric dicts) into a merged hydro signal,
    then drives main-channel selection and tributary throttling.

    Usage::

        ctrl = UTMHydrologyController()
        adj  = ctrl.adjust(top_results, metrics_list, utm_p_blow=0.45)
    """

    def __init__(
        self,
        utm: Optional[UTMController] = None,
        main_channel_k: int = 3,
    ) -> None:
        self.utm = utm if utm is not None else UTMController()
        self.main_channel_k = main_channel_k

    # ------------------------------------------------------------------
    # Main adjustment pass
    # ------------------------------------------------------------------

    def adjust(
        self,
        results:      List[EvaluationResult],
        metrics_list: Optional[List[dict]] = None,
        utm_p_blow:   float = 0.0,
        step:         int   = 0,
    ) -> HydroAdjustment:
        """Compute hydro adjustment for a set of evaluated candidates.

        Parameters
        ----------
        results : list of EvaluationResult
            Top evaluated candidates (already sorted by score, best first).
        metrics_list : list of dicts, optional
            Raw metric dicts for numerical hydro.  If None, uses abstract only.
        utm_p_blow : float
            Current blow-up probability for UTM state update.
        step : int
            Current simulation step (for UTM event log).
        """
        # --- Abstract hydro ---
        abstract_h = hydro_adjust_abstract(results)

        # --- Numerical hydro ---
        if metrics_list:
            numerical_h = hydro_adjust_numerical(metrics_list)
        else:
            numerical_h = hydro_adjust_numerical([])

        # --- Merge ---
        merged = merge_hydro(abstract_h, numerical_h)
        pb = merged.get("pressure_balance", 1.0)
        hydro_state = _classify_hydro(pb)

        # --- UTM state ---
        utm_s = self.utm.update(utm_p_blow, step=step, reason=f"hydro={hydro_state}")

        # --- Main channel selection ---
        # Active branches first, then by balanced_score
        sorted_idx = sorted(
            range(len(results)),
            key=lambda i: (
                1 if results[i].branch_status == "active" else 0,
                results[i].balanced_score,
            ),
            reverse=True,
        )
        main_k = self.main_channel_k

        if utm_s == UTMState.CRACKDOWN:
            # Preserve only top-1 during crackdown
            main_k = 1
        elif utm_s == UTMState.NEGOTIATE:
            main_k = max(1, main_k - 1)

        main_ids     = sorted_idx[:main_k]
        throttled_ids = sorted_idx[main_k:]

        # During drought, restrict further
        if hydro_state == HYDRO_DROUGHT:
            throttled_ids = list(set(throttled_ids) | set(sorted_idx[max(1, main_k // 2):]))
            main_ids = sorted_idx[:max(1, main_k // 2)]

        return HydroAdjustment(
            hydro_state=hydro_state,
            pressure_balance=pb,
            main_channel_ids=main_ids,
            throttled_ids=throttled_ids,
            utm_state=utm_s.value,
            merged_hydro=merged,
        )

    # ------------------------------------------------------------------
    # Standalone pressure check
    # ------------------------------------------------------------------

    def pressure_check(self, results: List[EvaluationResult]) -> float:
        """Return the pressure_balance signal for a result set."""
        h = hydro_adjust_abstract(results)
        return float(h.get("pressure_balance", 1.0))
