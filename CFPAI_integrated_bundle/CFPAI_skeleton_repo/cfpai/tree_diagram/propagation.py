from __future__ import annotations

import numpy as np
import pandas as pd


def apply_identity_like_propagation(weight_df: pd.DataFrame) -> pd.DataFrame:
    """恒等传播：当前版本直接透传权重，不做图传播。

    未来扩展方向：
    - 加入 Tree Diagram 的 VFT（Vein Flow Transport）传播
    - 让相邻时间步的权重相互影响（平滑化）
    - 加入 H-UTM 水文控制层的稳态约束
    """
    return weight_df.copy()


def smooth_propagation(
    weight_df: pd.DataFrame,
    alpha: float = 0.3,
) -> pd.DataFrame:
    """指数平滑传播：当前权重 = alpha * 新权重 + (1-alpha) * 前一步权重。

    减少权重的剧烈跳动，模拟 Tree Diagram 的主河道稳定机制。
    """
    result = weight_df.copy()
    cols = [c for c in result.columns if c != "Date"]

    for i in range(1, len(result)):
        for c in cols:
            prev = result.at[i - 1, c]
            curr = result.at[i, c]
            result.at[i, c] = alpha * curr + (1 - alpha) * prev

    return result


def momentum_propagation(
    weight_df: pd.DataFrame,
    lookback: int = 5,
    momentum_weight: float = 0.2,
) -> pd.DataFrame:
    """动量传播：权重受过去 lookback 步的趋势影响。

    如果某资产权重持续上升，给予额外加成；持续下降，给予惩罚。
    """
    result = weight_df.copy()
    cols = [c for c in result.columns if c != "Date"]

    for i in range(lookback, len(result)):
        for c in cols:
            past = result[c].iloc[i - lookback:i].values
            trend = (past[-1] - past[0]) / max(lookback, 1)
            result.at[i, c] = result.at[i, c] + momentum_weight * trend

    # 归一化：确保每行权重和 <= 1
    for i in range(len(result)):
        vals = np.array([max(0.0, result.at[i, c]) for c in cols])
        total = vals.sum()
        if total > 1.0:
            for j, c in enumerate(cols):
                result.at[i, c] = vals[j] / total

    return result
