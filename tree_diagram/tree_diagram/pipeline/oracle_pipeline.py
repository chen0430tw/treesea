from __future__ import annotations
from typing import List, Literal, Optional, Tuple

import numpy as np

from ..numerics.forcing import GridConfig, build_grid, build_topography
from ..numerics.weather_state import WeatherState, build_obs, build_initial_state
from ..numerics.ensemble import run_ensemble
from ..numerics.ranking import rank_ensemble
from ..core.balance_layer import hydro_adjust_numerical
from ..numerics.weather_contract import (
    DEFAULT_BOUNDS, validate_state_arrays, UnsafeTemperatureRead,
    WeatherRegimeReport, WeatherQuantEstimate, WeatherCalibration,
    regime_report_from_ranked, quant_estimate_from_state,
)


class WeatherOraclePipeline:
    def __init__(
        self,
        cfg: Optional[GridConfig] = None,
        n_workers: int = 1,
    ) -> None:
        self.cfg = cfg if cfg is not None else GridConfig()
        self.n_workers = n_workers

    # ──────────────────────────────────────────────────────────────
    # Legacy raw output (kept for backward compatibility)
    # ──────────────────────────────────────────────────────────────
    def run(self, pressure_balance: float = 1.0) -> Tuple[List[dict], List[dict], dict]:
        cfg = self.cfg

        # Stage 1: build grid and topography
        XX, YY, x, y = build_grid(cfg)
        topography = build_topography(XX, YY)

        # Stage 2: build observations and initial state
        obs: WeatherState = build_obs(XX, YY, topography, cfg)
        initial_state: WeatherState = build_initial_state(XX, YY, topography, cfg)

        # Stage 3: run ensemble
        raw_results: List[dict] = run_ensemble(
            initial_state=initial_state,
            obs=obs,
            topography=topography,
            cfg=cfg,
            pressure_balance=pressure_balance,
            n_workers=self.n_workers,
        )

        # Stage 4: rank
        ranked_metrics: List[dict] = rank_ensemble(raw_results)

        # Stage 5: numerical hydro control
        numerical_hydro = hydro_adjust_numerical(ranked_metrics)

        # Strip state arrays from ranked_metrics for the metrics list
        metrics_only = []
        states = []
        for r in ranked_metrics:
            state_dict = r.get("state", {})
            states.append({"name": r.get("name", ""), "state": state_dict})
            m = {k: v for k, v in r.items() if k != "state"}
            metrics_only.append(m)

        return states, metrics_only, numerical_hydro

    # ──────────────────────────────────────────────────────────────
    # Safe output API — mode-gated, physically validated
    # ──────────────────────────────────────────────────────────────
    def run_safe(
        self,
        *,
        mode: Literal["regime_only", "calibrated_quant"] = "regime_only",
        initial_state: Optional[WeatherState] = None,
        obs: Optional[WeatherState] = None,
        topography=None,
        pressure_balance: float = 1.0,
        calibration: Optional[WeatherCalibration] = None,
    ):
        """Safe entry point with output semantic separation and physical gating.

        Returns:
            (regime_report, quant_estimate_or_None, diagnostics)

        - `regime_report` is always a WeatherRegimeReport (safe qualitative).
        - `quant_estimate_or_None` is a WeatherQuantEstimate only when
          mode='calibrated_quant' AND calibration is provided AND state
          passed physical validation.
        - `diagnostics` contains hydro and raw ensemble metrics.

        The internal integrator's T/h/q are internal thermodynamic variables,
        not 2-meter observables. Only a calibration layer (fitted against
        real observations) can translate them. See weather_contract.WeatherCalibration.
        """
        cfg = self.cfg
        XX, YY, x, y = build_grid(cfg)
        topo = topography if topography is not None else build_topography(XX, YY)
        _obs = obs if obs is not None else build_obs(XX, YY, topo, cfg)
        _init = initial_state if initial_state is not None else build_initial_state(XX, YY, topo, cfg)

        raw_results = run_ensemble(
            initial_state=_init,
            obs=_obs,
            topography=topo,
            cfg=cfg,
            pressure_balance=pressure_balance,
            n_workers=self.n_workers,
        )
        ranked_metrics = rank_ensemble(raw_results)
        numerical_hydro = hydro_adjust_numerical(ranked_metrics)

        # Validate the top-ranked state
        top_state_dict = ranked_metrics[0].get("state", {})
        validation = validate_state_arrays(
            h=top_state_dict["h"],
            u=top_state_dict["u"],
            v=top_state_dict["v"],
            T=top_state_dict["T"],
            q=top_state_dict["q"],
            bounds=DEFAULT_BOUNDS,
        )

        regime_report = regime_report_from_ranked(ranked_metrics, validation)

        quant_estimate = None
        if mode == "calibrated_quant":
            if calibration is None:
                raise UnsafeTemperatureRead(
                    "mode='calibrated_quant' requires a WeatherCalibration. "
                    "Without it, only regime output is permitted."
                )
            # Center of grid (treat as target location)
            cy = int(np.argmin(np.abs(YY[:, 0])))
            cx = int(np.argmin(np.abs(XX[0, :])))
            quant_estimate = quant_estimate_from_state(
                state_dict=top_state_dict,
                validation=validation,
                calibration=calibration,
                center_xy=(cy, cx),
            )
        elif mode == "regime_only":
            pass
        else:
            raise ValueError(f"Unknown mode: {mode!r}. Use 'regime_only' or 'calibrated_quant'.")

        diagnostics = {
            "hydro": numerical_hydro,
            "ensemble_metrics": [
                {k: v for k, v in r.items() if k != "state"}
                for r in ranked_metrics
            ],
            "mode": mode,
            "calibrated": calibration is not None,
        }

        return regime_report, quant_estimate, diagnostics
