# rewrite_model.py
"""
结构重排与规则改写评估。

评估是否可以安全地执行主线回写 / 规则重排：
  - 改写可行性判定
  - 改写风险估计
  - 稳定化代价计算
  - 行动建议生成
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..io.risk_schema import RewriteAssessment, EnergyEstimate, ThresholdAssessment


@dataclass
class RewriteModelConfig:
    """改写模型配置。"""
    rewrite_threshold: float = 0.7        # 改写风险阈值（超过则不建议）
    stabilization_budget: float = 100.0   # 稳定化预算上限
    max_rewrite_depth: float = 3.0        # 最大改写深度
    energy_cost_factor: float = 0.5       # 崩坏能消耗系数
    risk_weight_energy: float = 0.4       # 风险中崩坏能权重
    risk_weight_threshold: float = 0.3    # 风险中阈值越限权重
    risk_weight_coupling: float = 0.3     # 风险中耦合强度权重

    @classmethod
    def from_dict(cls, d: dict) -> "RewriteModelConfig":
        return cls(
            rewrite_threshold=d.get("rewrite_threshold", 0.7),
            stabilization_budget=d.get("stabilization_budget", 100.0),
            max_rewrite_depth=d.get("max_rewrite_depth", 3.0),
            energy_cost_factor=d.get("energy_cost_factor", 0.5),
            risk_weight_energy=d.get("risk_weight_energy", 0.4),
            risk_weight_threshold=d.get("risk_weight_threshold", 0.3),
            risk_weight_coupling=d.get("risk_weight_coupling", 0.3),
        )


class RewriteModel:
    """改写评估器。

    Parameters
    ----------
    cfg : RewriteModelConfig
    """

    def __init__(self, cfg: Optional[RewriteModelConfig] = None) -> None:
        self.cfg = cfg or RewriteModelConfig()

    def assess(
        self,
        energy: EnergyEstimate,
        threshold: ThresholdAssessment,
        coupling_strength: float = 0.5,
    ) -> RewriteAssessment:
        """评估改写可行性与风险。

        Parameters
        ----------
        energy : EnergyEstimate
            崩坏能估计
        threshold : ThresholdAssessment
            阈值评估
        coupling_strength : float
            当前耦合强度

        Returns
        -------
        RewriteAssessment
        """
        # 改写风险 = 加权组合
        energy_risk = min(1.0, energy.density / max(threshold.theta_honkai, 1e-12))
        threshold_risk = 1.0 if threshold.breach else max(
            0.0, 1.0 - threshold.margin_collapse / max(threshold.theta_collapse, 1e-12)
        )
        coupling_risk = min(1.0, coupling_strength)

        rewrite_risk = (
            self.cfg.risk_weight_energy * energy_risk
            + self.cfg.risk_weight_threshold * threshold_risk
            + self.cfg.risk_weight_coupling * coupling_risk
        )

        # 稳定化代价
        stabilization_cost = (
            self.cfg.energy_cost_factor * energy.total_energy
            + coupling_strength * 10.0
        )

        # 可行性
        feasible = (
            rewrite_risk < self.cfg.rewrite_threshold
            and stabilization_cost <= self.cfg.stabilization_budget
            and not threshold.breach
        )

        # 建议
        if threshold.breach:
            action = "abort"
        elif rewrite_risk >= self.cfg.rewrite_threshold:
            action = "contain"
        elif stabilization_cost > self.cfg.stabilization_budget * 0.8:
            action = "defer"
        else:
            action = "proceed"

        return RewriteAssessment(
            rewrite_feasible=feasible,
            rewrite_risk=rewrite_risk,
            stabilization_cost=stabilization_cost,
            recommended_action=action,
            detail={
                "energy_risk": energy_risk,
                "threshold_risk": threshold_risk,
                "coupling_risk": coupling_risk,
            },
        )
