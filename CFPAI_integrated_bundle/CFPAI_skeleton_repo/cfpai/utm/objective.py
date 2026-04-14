from __future__ import annotations

import numpy as np

def tuning_objective(stats: dict) -> float:
    sharpe = 0.0 if np.isnan(stats["sharpe"]) else stats["sharpe"]
    return float(stats["ann_return"] + 0.30 * sharpe - 0.50 * abs(stats["max_dd"]))
