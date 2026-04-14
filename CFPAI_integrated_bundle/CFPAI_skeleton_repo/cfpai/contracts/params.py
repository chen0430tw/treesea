from __future__ import annotations
from dataclasses import dataclass

@dataclass
class CFPAIParams:
    w_mom: float = 0.8696184893744723
    w_trend: float = 0.19976148226439763
    w_vol: float = 0.326776407279996
    w_volume: float = 0.11553426729661594
    w_dd: float = 0.3635999148972932
    lambda_risk: float = 0.4168828476926169
    persistence_bonus: float = 0.13484669170521332
    max_assets: int = 3
    cash_floor: float = 0.0
