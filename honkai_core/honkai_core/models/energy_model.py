# energy_model.py
"""
崩坏能估计模型。

实现白皮书 §8.3 崩坏能动力学：
  dE_H/dt = G_H(t) - D_H(t)

核心职责：
  - 计算崩坏能总量 E_H
  - 计算产生率 G_H 与消耗率 D_H
  - 判定增益态 / 稳态 / 衰竭态
  - 计算崩坏能密度 rho_H 与增益因子 Gamma_H
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..io.risk_schema import EnergyEstimate


@dataclass
class EnergyModelConfig:
    """崩坏能模型配置。"""
    base_generation: float = 1.0     # 基础产生率
    dissipation_coeff: float = 0.3   # 耗散系数
    coupling_strength: float = 0.5   # 树海耦合强度（影响 G_H）
    volume: float = 1.0              # 系统体积（用于密度计算）
    noise_scale: float = 0.01        # 涨落噪声尺度

    @classmethod
    def from_dict(cls, d: dict) -> "EnergyModelConfig":
        return cls(
            base_generation=d.get("base_generation", 1.0),
            dissipation_coeff=d.get("dissipation_coeff", 0.3),
            coupling_strength=d.get("coupling_strength", 0.5),
            volume=d.get("volume", 1.0),
            noise_scale=d.get("noise_scale", 0.01),
        )


class EnergyModel:
    """崩坏能估计器。

    给定候选集的统计量（树端分数、海端坍缩分数、稳定性等），
    计算系统当前的崩坏能状态。

    Parameters
    ----------
    cfg : EnergyModelConfig
    """

    def __init__(self, cfg: Optional[EnergyModelConfig] = None) -> None:
        self.cfg = cfg or EnergyModelConfig()

    def estimate(self, candidates: List[Dict[str, Any]]) -> EnergyEstimate:
        """对候选集执行崩坏能估计。

        Parameters
        ----------
        candidates : list of dict
            每个 candidate 至少包含：
              - candidate_id: str
              - tree_score: float    — 树端价值 P(gamma_i)
              - collapse_score: float — 海端坍缩分数
              - stability: float     — 稳定性 0~1

        Returns
        -------
        EnergyEstimate
        """
        if not candidates:
            return EnergyEstimate(
                total_energy=0.0,
                generation_rate=0.0,
                dissipation_rate=0.0,
                gain_factor=0.0,
                density=0.0,
                state="depletion",
            )

        # 崩坏能产生率：树海耦合冲突越强 → G_H 越高
        # G_H = base_gen * coupling * sum(|tree_score - collapse_score|)
        conflict_sum = sum(
            abs(c.get("tree_score", 0.0) - c.get("collapse_score", 0.0))
            for c in candidates
        )
        g_h = self.cfg.base_generation * self.cfg.coupling_strength * conflict_sum

        # 崩坏能消耗率：D_H = dissipation * sum(stability)
        stability_sum = sum(c.get("stability", 0.5) for c in candidates)
        d_h = self.cfg.dissipation_coeff * stability_sum

        # 总崩坏能 E_H = G_H - D_H（单步增量近似）
        e_h = max(0.0, g_h - d_h)

        # 密度
        rho_h = e_h / max(self.cfg.volume, 1e-12)

        # 增益因子
        gamma_h = g_h / max(d_h, 1e-12)

        # 状态判定
        if gamma_h > 1.05:
            state = "gain"
        elif gamma_h < 0.95:
            state = "depletion"
        else:
            state = "steady"

        # 分项贡献
        components: Dict[str, float] = {}
        for c in candidates:
            cid = c.get("candidate_id", "unknown")
            conflict = abs(c.get("tree_score", 0.0) - c.get("collapse_score", 0.0))
            components[cid] = self.cfg.base_generation * self.cfg.coupling_strength * conflict

        return EnergyEstimate(
            total_energy=e_h,
            generation_rate=g_h,
            dissipation_rate=d_h,
            gain_factor=gamma_h,
            density=rho_h,
            state=state,
            components=components,
        )
