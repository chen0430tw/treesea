from __future__ import annotations

import numpy as np
import pandas as pd

from cfpai.contracts.params import CFPAIParams


def build_weight_grid(candidate_df: pd.DataFrame, asset_prefixes: list[str], params: CFPAIParams) -> pd.DataFrame:
    rows = []
    prev_top = None
    for i in range(len(candidate_df)):
        adjusted = {}
        for a in asset_prefixes:
            base = float(candidate_df.at[i, a])
            bonus = params.persistence_bonus if prev_top == a else 0.0
            adjusted[a] = base + bonus

        ranked = sorted(adjusted.items(), key=lambda kv: kv[1], reverse=True)
        prev_top = ranked[0][0]
        chosen = ranked[:params.max_assets]

        pos = np.array([max(v, 0.0) for _, v in chosen], dtype=float)
        out = {a: 0.0 for a in asset_prefixes}
        if pos.sum() > 1e-12:
            pos = pos / pos.sum()
            scale = max(0.0, 1.0 - params.cash_floor)

            # 单资产上限 cap
            cap = getattr(params, "max_single_weight", 1.0)
            for (a, _), w in zip(chosen, pos):
                out[a] = float(min(scale * w, cap))

            # cap 后重新归一化（溢出部分分配给其他资产）
            total = sum(out.values())
            if total > scale and scale > 0:
                for a in out:
                    out[a] = out[a] / total * scale

        rows.append({"Date": candidate_df.at[i, "Date"], **out})
    return pd.DataFrame(rows)
