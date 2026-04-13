# scenario_loader.py
"""
场景配置加载器。

从 YAML 配置文件加载 Honkai Core 运行场景，包括：
  - 崩坏能模型参数
  - 阈值参数
  - 耦合模型参数
  - 改写/稳定化参数
  - 候选列表
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CandidateSpec:
    """单个候选的规格描述。"""
    candidate_id: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"candidate_id": self.candidate_id, "payload": self.payload}

    @classmethod
    def from_dict(cls, d: dict) -> "CandidateSpec":
        return cls(candidate_id=d["candidate_id"], payload=d.get("payload", {}))


@dataclass
class ScenarioConfig:
    """Honkai Core 运行场景配置。"""
    scenario_id: str
    request_id: str = ""

    # 崩坏能模型参数
    energy_params: Dict[str, float] = field(default_factory=lambda: {
        "base_generation": 1.0,
        "dissipation_coeff": 0.3,
        "coupling_strength": 0.5,
        "volume": 1.0,
    })

    # 阈值参数
    threshold_params: Dict[str, float] = field(default_factory=lambda: {
        "theta_collapse": 0.8,
        "theta_tree": 0.6,
        "theta_honkai": 10.0,
        "alpha_peak": 0.4,
        "alpha_coherence": 0.3,
        "alpha_stability": 0.2,
        "alpha_noise": 0.1,
    })

    # 耦合模型参数
    coupling_params: Dict[str, float] = field(default_factory=lambda: {
        "tree_sea_coupling": 0.5,
        "feedback_strength": 0.2,
        "damping": 0.1,
    })

    # 改写/稳定化参数
    rewrite_params: Dict[str, float] = field(default_factory=lambda: {
        "rewrite_threshold": 0.7,
        "stabilization_budget": 100.0,
        "max_rewrite_depth": 3.0,
    })

    # 候选列表
    candidates: List[CandidateSpec] = field(default_factory=list)

    # 运行时配置
    runtime: Dict[str, Any] = field(default_factory=lambda: {
        "output_dir": "runs/honkai_core",
        "checkpoint_dir": "checkpoints/honkai_core",
        "log_dir": "logs/honkai_core",
        "verbose": False,
    })

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "request_id": self.request_id,
            "energy_params": self.energy_params,
            "threshold_params": self.threshold_params,
            "coupling_params": self.coupling_params,
            "rewrite_params": self.rewrite_params,
            "candidates": [c.to_dict() for c in self.candidates],
            "runtime": self.runtime,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScenarioConfig":
        defaults = cls(scenario_id="")
        return cls(
            scenario_id=d.get("scenario_id", ""),
            request_id=d.get("request_id", ""),
            energy_params={**defaults.energy_params, **d.get("energy_params", {})},
            threshold_params={**defaults.threshold_params, **d.get("threshold_params", {})},
            coupling_params={**defaults.coupling_params, **d.get("coupling_params", {})},
            rewrite_params={**defaults.rewrite_params, **d.get("rewrite_params", {})},
            candidates=[CandidateSpec.from_dict(c) for c in d.get("candidates", [])],
            runtime={**defaults.runtime, **d.get("runtime", {})},
            metadata=d.get("metadata", {}),
        )


def load_scenario(path: str | Path) -> ScenarioConfig:
    """从 YAML 文件加载场景配置。

    Parameters
    ----------
    path : str or Path
        配置文件路径（.yaml / .yml / .json）

    Returns
    -------
    ScenarioConfig
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Scenario config not found: {path}")

    text = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML is required for YAML config files: pip install pyyaml")
        data = yaml.safe_load(text)
    elif path.suffix == ".json":
        import json
        data = json.loads(text)
    else:
        raise ValueError(f"Unsupported config format: {path.suffix}")

    if data is None:
        data = {}

    return ScenarioConfig.from_dict(data)


def load_scenario_from_dict(d: dict) -> ScenarioConfig:
    """从字典直接构建场景配置（用于测试或内嵌调用）。"""
    return ScenarioConfig.from_dict(d)
