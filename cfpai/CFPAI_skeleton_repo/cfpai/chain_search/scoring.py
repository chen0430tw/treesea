from __future__ import annotations

import numpy as np
import pandas as pd

from cfpai.contracts.params import CFPAIParams


def persistence_adjusted_score(
    base_score: float,
    previous_asset: str | None,
    current_asset: str,
    bonus: float,
) -> float:
    """持仓延续性加分：连续持有同一资产时给予 bonus。"""
    return float(base_score + (bonus if previous_asset == current_asset else 0.0))


def rank_candidates(
    candidate_df: pd.DataFrame,
    params: CFPAIParams,
) -> pd.DataFrame:
    """对每一行的候选资产评分并排名。

    返回 DataFrame 增加 rank_1, rank_2, rank_1_score, rank_2_score 列。
    """
    rows = []
    for i in range(len(candidate_df)):
        scores = candidate_df.iloc[i].drop(labels=["Date"]).sort_values(ascending=False)
        r1 = scores.index[0]
        r2 = scores.index[1] if len(scores) > 1 else r1
        rows.append({
            "Date": candidate_df.at[i, "Date"],
            "rank_1": r1,
            "rank_1_score": float(scores.iloc[0]),
            "rank_2": r2,
            "rank_2_score": float(scores.iloc[1]) if len(scores) > 1 else 0.0,
            "spread": float(scores.iloc[0] - scores.iloc[1]) if len(scores) > 1 else float(scores.iloc[0]),
        })
    return pd.DataFrame(rows)


def compute_transition_cost(
    previous_asset: str | None,
    new_asset: str,
    lambda_risk: float = 0.4,
) -> float:
    """计算资产切换的隐含成本。

    切换资产有摩擦成本（交易费 + 滑点 + 信号延迟），
    lambda_risk 越高，越不愿意频繁切换。
    """
    if previous_asset is None or previous_asset == new_asset:
        return 0.0
    return lambda_risk * 0.1  # 简化模型：固定比例成本
