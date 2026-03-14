from __future__ import annotations
from typing import List, Optional, Tuple

from ..numerics.forcing import GridConfig, build_grid, build_topography
from ..numerics.weather_state import WeatherState, build_obs, build_initial_state
from ..numerics.ensemble import run_ensemble
from ..numerics.ranking import rank_ensemble
from ..core.balance_layer import hydro_adjust_numerical


class WeatherOraclePipeline:
    def __init__(
        self,
        cfg: Optional[GridConfig] = None,
        n_workers: int = 1,
    ) -> None:
        self.cfg = cfg if cfg is not None else GridConfig()
        self.n_workers = n_workers

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
