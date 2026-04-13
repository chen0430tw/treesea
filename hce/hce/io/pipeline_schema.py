# pipeline_schema.py
"""
HCE 流水线 Schema。

定义 HCE 集成层的数据结构：
  RequestBundle      — 整机入口任务描述
  FinalReportBundle  — 最终汇总输出
  PipelineConfig     — 流水线配置
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RequestBundle:
    """整机入口任务描述。"""
    request_id: str
    task_type: str = "worldline_search"
    mode: str = "tree_then_sea_then_hc"   # 执行模式
    seed: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    budget: Dict[str, Any] = field(default_factory=dict)
    runtime_profile: Dict[str, Any] = field(default_factory=dict)
    output_policy: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "task_type": self.task_type,
            "mode": self.mode,
            "seed": self.seed,
            "constraints": self.constraints,
            "budget": self.budget,
            "runtime_profile": self.runtime_profile,
            "output_policy": self.output_policy,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> "RequestBundle":
        return cls(
            request_id=d["request_id"],
            task_type=d.get("task_type", "worldline_search"),
            mode=d.get("mode", "tree_then_sea_then_hc"),
            seed=d.get("seed", {}),
            constraints=d.get("constraints", {}),
            budget=d.get("budget", {}),
            runtime_profile=d.get("runtime_profile", {}),
            output_policy=d.get("output_policy", {}),
            metadata=d.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, s: str) -> "RequestBundle":
        return cls.from_dict(json.loads(s))


@dataclass
class FinalReportBundle:
    """HCE 最终汇总输出。"""
    request_id: str
    tree_ref: Optional[str] = None
    sea_ref: Optional[str] = None
    hc_ref: Optional[str] = None
    final_selection: Dict[str, Any] = field(default_factory=dict)
    final_ranking: List[Dict[str, Any]] = field(default_factory=list)
    energy_summary: Dict[str, Any] = field(default_factory=dict)
    risk_summary: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    elapsed_sec: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "tree_ref": self.tree_ref,
            "sea_ref": self.sea_ref,
            "hc_ref": self.hc_ref,
            "final_selection": self.final_selection,
            "final_ranking": self.final_ranking,
            "energy_summary": self.energy_summary,
            "risk_summary": self.risk_summary,
            "artifacts": self.artifacts,
            "elapsed_sec": self.elapsed_sec,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> "FinalReportBundle":
        return cls(
            request_id=d["request_id"],
            tree_ref=d.get("tree_ref"),
            sea_ref=d.get("sea_ref"),
            hc_ref=d.get("hc_ref"),
            final_selection=d.get("final_selection", {}),
            final_ranking=d.get("final_ranking", []),
            energy_summary=d.get("energy_summary", {}),
            risk_summary=d.get("risk_summary", {}),
            artifacts=d.get("artifacts", {}),
            elapsed_sec=d.get("elapsed_sec", 0.0),
            metadata=d.get("metadata", {}),
        )

    @classmethod
    def from_json(cls, s: str) -> "FinalReportBundle":
        return cls.from_dict(json.loads(s))


VALID_MODES = [
    "tree_only",
    "sea_only",
    "hc_only",
    "tree_then_sea",
    "tree_then_sea_then_hc",
    "sea_then_tree",
]


@dataclass
class PipelineConfig:
    """流水线配置。"""
    mode: str = "tree_then_sea_then_hc"
    tree_config_path: Optional[str] = None
    qcu_config_path: Optional[str] = None
    hc_config_path: Optional[str] = None
    output_dir: str = "runs/hce"
    checkpoint_dir: str = "checkpoints/hce"
    log_dir: str = "logs/hce"
    result_dir: str = "results/hce"
    writeback_enabled: bool = True
    verbose: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """验证配置，返回错误列表。"""
        errors = []
        if self.mode not in VALID_MODES:
            errors.append(f"Invalid mode: {self.mode}. Valid: {VALID_MODES}")
        if "tree" in self.mode and not self.tree_config_path:
            errors.append(f"Mode {self.mode} requires tree_config_path")
        if "sea" in self.mode and not self.qcu_config_path:
            errors.append(f"Mode {self.mode} requires qcu_config_path")
        if "hc" in self.mode and not self.hc_config_path:
            errors.append(f"Mode {self.mode} requires hc_config_path")
        return errors

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "tree_config_path": self.tree_config_path,
            "qcu_config_path": self.qcu_config_path,
            "hc_config_path": self.hc_config_path,
            "output_dir": self.output_dir,
            "checkpoint_dir": self.checkpoint_dir,
            "log_dir": self.log_dir,
            "result_dir": self.result_dir,
            "writeback_enabled": self.writeback_enabled,
            "verbose": self.verbose,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineConfig":
        return cls(
            mode=d.get("mode", "tree_then_sea_then_hc"),
            tree_config_path=d.get("tree_config_path"),
            qcu_config_path=d.get("qcu_config_path"),
            hc_config_path=d.get("hc_config_path"),
            output_dir=d.get("output_dir", "runs/hce"),
            checkpoint_dir=d.get("checkpoint_dir", "checkpoints/hce"),
            log_dir=d.get("log_dir", "logs/hce"),
            result_dir=d.get("result_dir", "results/hce"),
            writeback_enabled=d.get("writeback_enabled", True),
            verbose=d.get("verbose", False),
            metadata=d.get("metadata", {}),
        )
