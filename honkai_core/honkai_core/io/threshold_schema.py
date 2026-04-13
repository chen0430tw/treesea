# threshold_schema.py
"""
阈值扫描 Schema。

定义阈值扫描过程中的数据结构：
  ThresholdScanPoint  — 单个扫描点
  ThresholdScanResult — 扫描结果集合
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ThresholdScanPoint:
    """阈值扫描的单个采样点。"""
    param_name: str
    param_value: float
    maturity: float          # M(U_i)
    honkai_density: float    # rho_H
    gain_factor: float       # Gamma_H
    breach: bool
    risk_level: str          # "safe" | "warning" | "critical" | "terminal"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "param_name": self.param_name,
            "param_value": self.param_value,
            "maturity": self.maturity,
            "honkai_density": self.honkai_density,
            "gain_factor": self.gain_factor,
            "breach": self.breach,
            "risk_level": self.risk_level,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ThresholdScanPoint":
        return cls(
            param_name=d["param_name"],
            param_value=d["param_value"],
            maturity=d["maturity"],
            honkai_density=d["honkai_density"],
            gain_factor=d["gain_factor"],
            breach=d["breach"],
            risk_level=d["risk_level"],
            metadata=d.get("metadata", {}),
        )


@dataclass
class ThresholdScanResult:
    """阈值扫描结果集合。"""
    scan_id: str
    param_name: str
    param_range: List[float]     # [start, end, step]
    points: List[ThresholdScanPoint]
    critical_value: Optional[float] = None   # 临界点参数值
    safe_range: Optional[List[float]] = None  # 安全区间
    elapsed_sec: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "param_name": self.param_name,
            "param_range": self.param_range,
            "points": [p.to_dict() for p in self.points],
            "critical_value": self.critical_value,
            "safe_range": self.safe_range,
            "elapsed_sec": self.elapsed_sec,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ThresholdScanResult":
        return cls(
            scan_id=d["scan_id"],
            param_name=d["param_name"],
            param_range=d["param_range"],
            points=[ThresholdScanPoint.from_dict(p) for p in d["points"]],
            critical_value=d.get("critical_value"),
            safe_range=d.get("safe_range"),
            elapsed_sec=d.get("elapsed_sec", 0.0),
            metadata=d.get("metadata", {}),
        )
