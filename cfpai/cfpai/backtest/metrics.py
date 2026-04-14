from __future__ import annotations

import numpy as np
import pandas as pd


def perf_stats(returns: pd.Series) -> tuple[dict, pd.Series]:
    returns = returns.fillna(0.0)
    equity = (1 + returns).cumprod()
    total_return = equity.iloc[-1] - 1
    ann_return = equity.iloc[-1] ** (252 / len(returns)) - 1
    ann_vol = returns.std() * np.sqrt(252)
    sharpe = ann_return / ann_vol if ann_vol > 1e-12 else np.nan
    dd = equity / equity.cummax() - 1
    max_dd = dd.min()
    return {
        "total_return": float(total_return),
        "ann_return": float(ann_return),
        "ann_vol": float(ann_vol),
        "sharpe": float(sharpe) if np.isfinite(sharpe) else np.nan,
        "max_dd": float(max_dd),
    }, equity
