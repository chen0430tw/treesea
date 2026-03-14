# scan_schema.py
"""
QCU collapse_scan 结果 Schema。

ScanRowRecord   — CollapseRow 的 JSON 兼容表示
ScanResultBundle — 完整扫描结果集合
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ScanRowRecord:
    """单个扫描点的结果记录。"""
    boost_duration: float
    eps_boost: float
    gamma_pcm: float
    C_end: float
    dtheta_end: float
    N_end: Optional[float]
    elapsed_sec: float
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "boost_duration": self.boost_duration,
            "eps_boost": self.eps_boost,
            "gamma_pcm": self.gamma_pcm,
            "C_end": self.C_end,
            "dtheta_end": self.dtheta_end,
            "N_end": self.N_end,
            "elapsed_sec": self.elapsed_sec,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScanRowRecord":
        return cls(
            boost_duration=d["boost_duration"],
            eps_boost=d["eps_boost"],
            gamma_pcm=d["gamma_pcm"],
            C_end=d["C_end"],
            dtheta_end=d["dtheta_end"],
            N_end=d.get("N_end"),
            elapsed_sec=d["elapsed_sec"],
            extra=d.get("extra", {}),
        )


@dataclass
class ScanResultBundle:
    """完整 collapse_scan 扫描结果。"""
    scan_id: str
    rows: List[ScanRowRecord]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "rows": [r.to_dict() for r in self.rows],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScanResultBundle":
        return cls(
            scan_id=d["scan_id"],
            rows=[ScanRowRecord.from_dict(r) for r in d["rows"]],
            metadata=d.get("metadata", {}),
        )
