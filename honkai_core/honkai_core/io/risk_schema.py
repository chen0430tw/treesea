# risk_schema.py
"""
Honkai Core 风险分级 Schema。

定义崩坏能演算中的风险评估数据结构：
  RiskEntry        — 单个候选/区域的风险评估条目
  RiskSurface      — 风险曲面（多维风险指标聚合）
  HCReportBundle   — Honkai Core 对外标准输出 Bundle
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RiskEntry:
    """单个候选或局部区域的风险评估。"""
    candidate_id: str
    risk_level: str          # "safe" | "warning" | "critical" | "terminal"
    risk_score: float        # 0.0 ~ 1.0
    honkai_density: float    # 崩坏能密度 rho_H
    threshold_margin: float  # 距阈值的余量（正=安全，负=越限）
    herrscherization_risk: float  # 律者化风险 0.0 ~ 1.0
    rewrite_risk: float      # 规则改写风险 0.0 ~ 1.0
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "honkai_density": self.honkai_density,
            "threshold_margin": self.threshold_margin,
            "herrscherization_risk": self.herrscherization_risk,
            "rewrite_risk": self.rewrite_risk,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RiskEntry":
        return cls(
            candidate_id=d["candidate_id"],
            risk_level=d["risk_level"],
            risk_score=d["risk_score"],
            honkai_density=d["honkai_density"],
            threshold_margin=d["threshold_margin"],
            herrscherization_risk=d["herrscherization_risk"],
            rewrite_risk=d["rewrite_risk"],
            detail=d.get("detail", {}),
        )


@dataclass
class RiskSurface:
    """风险曲面：多维风险指标的空间分布。"""
    dimensions: List[str]
    grid_shape: List[int]
    risk_values: List[float]
    peak_risk: float
    peak_location: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "dimensions": self.dimensions,
            "grid_shape": self.grid_shape,
            "risk_values": self.risk_values,
            "peak_risk": self.peak_risk,
            "peak_location": self.peak_location,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RiskSurface":
        return cls(
            dimensions=d["dimensions"],
            grid_shape=d["grid_shape"],
            risk_values=d["risk_values"],
            peak_risk=d["peak_risk"],
            peak_location=d["peak_location"],
            metadata=d.get("metadata", {}),
        )


@dataclass
class EnergyEstimate:
    """崩坏能估计结果。"""
    total_energy: float          # E_H 总量
    generation_rate: float       # G_H 产生率
    dissipation_rate: float      # D_H 消耗率
    gain_factor: float           # Gamma_H = G_H / D_H
    density: float               # rho_H 密度
    state: str                   # "gain" | "steady" | "depletion"
    components: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_energy": self.total_energy,
            "generation_rate": self.generation_rate,
            "dissipation_rate": self.dissipation_rate,
            "gain_factor": self.gain_factor,
            "density": self.density,
            "state": self.state,
            "components": self.components,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EnergyEstimate":
        return cls(
            total_energy=d["total_energy"],
            generation_rate=d["generation_rate"],
            dissipation_rate=d["dissipation_rate"],
            gain_factor=d["gain_factor"],
            density=d["density"],
            state=d["state"],
            components=d.get("components", {}),
        )


@dataclass
class ThresholdAssessment:
    """阈值评估结果。"""
    theta_collapse: float    # 坍缩阈值 Theta_c
    theta_tree: float        # 树端阈值 theta_T
    theta_honkai: float      # 崩坏能密度上限
    current_maturity: float  # 当前成熟度 M(U_i)
    margin_collapse: float   # 距坍缩阈值余量
    margin_honkai: float     # 距崩坏能上限余量
    breach: bool             # 是否越限
    breach_type: Optional[str] = None  # "collapse" | "honkai" | "herrscher" | None
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "theta_collapse": self.theta_collapse,
            "theta_tree": self.theta_tree,
            "theta_honkai": self.theta_honkai,
            "current_maturity": self.current_maturity,
            "margin_collapse": self.margin_collapse,
            "margin_honkai": self.margin_honkai,
            "breach": self.breach,
            "breach_type": self.breach_type,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ThresholdAssessment":
        return cls(
            theta_collapse=d["theta_collapse"],
            theta_tree=d["theta_tree"],
            theta_honkai=d["theta_honkai"],
            current_maturity=d["current_maturity"],
            margin_collapse=d["margin_collapse"],
            margin_honkai=d["margin_honkai"],
            breach=d["breach"],
            breach_type=d.get("breach_type"),
            detail=d.get("detail", {}),
        )


@dataclass
class RewriteAssessment:
    """结构重排 / 规则改写评估。"""
    rewrite_feasible: bool
    rewrite_risk: float          # 0.0 ~ 1.0
    stabilization_cost: float    # 稳定化所需代价
    recommended_action: str      # "proceed" | "defer" | "abort" | "contain"
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rewrite_feasible": self.rewrite_feasible,
            "rewrite_risk": self.rewrite_risk,
            "stabilization_cost": self.stabilization_cost,
            "recommended_action": self.recommended_action,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RewriteAssessment":
        return cls(
            rewrite_feasible=d["rewrite_feasible"],
            rewrite_risk=d["rewrite_risk"],
            stabilization_cost=d["stabilization_cost"],
            recommended_action=d["recommended_action"],
            detail=d.get("detail", {}),
        )


@dataclass
class Recommendation:
    """Honkai Core 综合建议。"""
    action: str              # "proceed" | "limit" | "contain" | "abort" | "degrade"
    confidence: float        # 0.0 ~ 1.0
    energy_limit: Optional[float] = None
    writeback_allowed: bool = True
    reason: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "energy_limit": self.energy_limit,
            "writeback_allowed": self.writeback_allowed,
            "reason": self.reason,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Recommendation":
        return cls(
            action=d["action"],
            confidence=d["confidence"],
            energy_limit=d.get("energy_limit"),
            writeback_allowed=d.get("writeback_allowed", True),
            reason=d.get("reason", ""),
            detail=d.get("detail", {}),
        )


@dataclass
class HCReportBundle:
    """Honkai Core 对外标准输出 Bundle。

    作为与 HCE 交互的标准 JSON 可序列化数据包。
    包含崩坏能估计、阈值评估、风险评估、改写评估与综合建议。
    """
    request_id: str
    hc_run_id: str
    energy_estimate: EnergyEstimate
    threshold_assessment: ThresholdAssessment
    risk_entries: List[RiskEntry]
    risk_surface: Optional[RiskSurface]
    rewrite_assessment: RewriteAssessment
    recommendation: Recommendation
    elapsed_sec: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "hc_run_id": self.hc_run_id,
            "energy_estimate": self.energy_estimate.to_dict(),
            "threshold_assessment": self.threshold_assessment.to_dict(),
            "risk_entries": [r.to_dict() for r in self.risk_entries],
            "risk_surface": self.risk_surface.to_dict() if self.risk_surface else None,
            "rewrite_assessment": self.rewrite_assessment.to_dict(),
            "recommendation": self.recommendation.to_dict(),
            "elapsed_sec": self.elapsed_sec,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> "HCReportBundle":
        return cls(
            request_id=d["request_id"],
            hc_run_id=d["hc_run_id"],
            energy_estimate=EnergyEstimate.from_dict(d["energy_estimate"]),
            threshold_assessment=ThresholdAssessment.from_dict(d["threshold_assessment"]),
            risk_entries=[RiskEntry.from_dict(r) for r in d["risk_entries"]],
            risk_surface=RiskSurface.from_dict(d["risk_surface"]) if d.get("risk_surface") else None,
            rewrite_assessment=RewriteAssessment.from_dict(d["rewrite_assessment"]),
            recommendation=Recommendation.from_dict(d["recommendation"]),
            elapsed_sec=d.get("elapsed_sec", 0.0),
            metadata=d.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, s: str) -> "HCReportBundle":
        return cls.from_dict(json.loads(s))
