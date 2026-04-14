from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketState:
    """单时刻的市场状态表示。"""
    timestamp: str = ""
    flow_state: dict[str, float] = field(default_factory=dict)
    risk_state: dict[str, float] = field(default_factory=dict)
    rotation_state: dict[str, float] = field(default_factory=dict)
    liquidity_state: dict[str, float] = field(default_factory=dict)
    latent_vector: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "flow_state": self.flow_state,
            "risk_state": self.risk_state,
            "rotation_state": self.rotation_state,
            "liquidity_state": self.liquidity_state,
            "latent_vector": self.latent_vector,
            "metadata": self.metadata,
        }
