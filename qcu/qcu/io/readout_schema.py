# readout_schema.py
"""
QCU 读出 Bundle Schema。

定义从 QCU 输出的标准可交换数据结构：
  ReadoutBundleEntry  — 单次运行的读出快照
  SeaOutputBundle     — 多次运行汇总（与 HCE/MOROZ 的接口契约）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ReadoutBundleEntry:
    """单次 QCL v6 运行的读出数据。"""
    run_id: str
    label: str
    DIM: int
    C_end: float
    dtheta_end: float
    N_end: Optional[float]
    final_sz: List[float]
    final_n: List[float]
    final_rel_phase: List[float]
    elapsed_sec: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "label": self.label,
            "DIM": self.DIM,
            "C_end": self.C_end,
            "dtheta_end": self.dtheta_end,
            "N_end": self.N_end,
            "final_sz": self.final_sz,
            "final_n": self.final_n,
            "final_rel_phase": self.final_rel_phase,
            "elapsed_sec": self.elapsed_sec,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReadoutBundleEntry":
        return cls(
            run_id=d["run_id"],
            label=d["label"],
            DIM=d["DIM"],
            C_end=d["C_end"],
            dtheta_end=d["dtheta_end"],
            N_end=d.get("N_end"),
            final_sz=d["final_sz"],
            final_n=d["final_n"],
            final_rel_phase=d["final_rel_phase"],
            elapsed_sec=d["elapsed_sec"],
            metadata=d.get("metadata", {}),
        )


@dataclass
class SeaOutputBundle:
    """QCU 输出 Bundle（海端输出契约）。

    作为与 HCE / MOROZ 交互的标准 JSON 可序列化数据包。
    只包含聚合统计量和各运行读出条目，不含内部密度矩阵。
    """
    request_id: str
    qcu_session_id: str
    entries: List[ReadoutBundleEntry]
    total_elapsed_sec: float
    summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "qcu_session_id": self.qcu_session_id,
            "entries": [e.to_dict() for e in self.entries],
            "total_elapsed_sec": self.total_elapsed_sec,
            "summary": self.summary,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SeaOutputBundle":
        return cls(
            request_id=d["request_id"],
            qcu_session_id=d["qcu_session_id"],
            entries=[ReadoutBundleEntry.from_dict(e) for e in d["entries"]],
            total_elapsed_sec=d["total_elapsed_sec"],
            summary=d.get("summary", {}),
            metadata=d.get("metadata", {}),
        )
