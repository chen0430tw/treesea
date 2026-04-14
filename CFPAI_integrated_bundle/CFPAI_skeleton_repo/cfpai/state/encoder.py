from __future__ import annotations

import pandas as pd

from cfpai.contracts.state_types import MarketState


def encode_states(df: pd.DataFrame, asset_prefixes: list[str]) -> list[MarketState]:
    out: list[MarketState] = []
    for _, row in df.iterrows():
        flow = {a: float(row[f"{a}_volume_z"]) for a in asset_prefixes}
        risk = {a: float(row[f"{a}_vol_20"]) for a in asset_prefixes}
        rotation = {a: float(row[f"{a}_trend_gap"]) for a in asset_prefixes}
        liquidity = {a: float(row[f"{a}_Volume"]) for a in asset_prefixes}
        latent = list(flow.values()) + list(risk.values()) + list(rotation.values())
        out.append(MarketState(
            timestamp=str(row["Date"]),
            flow_state=flow,
            risk_state=risk,
            rotation_state=rotation,
            liquidity_state=liquidity,
            latent_vector=latent,
        ))
    return out
