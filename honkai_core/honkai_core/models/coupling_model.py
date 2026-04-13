# coupling_model.py
"""
耦合建模。

对树海耦合强度进行建模与评估：
  - 树端 ↔ 海端的耦合强度量化
  - 耦合引发的崩坏能增益/衰减
  - 耦合稳定性与反馈回路分析
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CouplingModelConfig:
    """耦合模型配置。"""
    tree_sea_coupling: float = 0.5   # 树海基础耦合强度
    feedback_strength: float = 0.2   # 反馈回路强度
    damping: float = 0.1             # 阻尼系数
    resonance_threshold: float = 0.8 # 共振阈值

    @classmethod
    def from_dict(cls, d: dict) -> "CouplingModelConfig":
        return cls(
            tree_sea_coupling=d.get("tree_sea_coupling", 0.5),
            feedback_strength=d.get("feedback_strength", 0.2),
            damping=d.get("damping", 0.1),
            resonance_threshold=d.get("resonance_threshold", 0.8),
        )


@dataclass
class CouplingResult:
    """耦合分析结果。"""
    coupling_strength: float     # 有效耦合强度
    energy_transfer: float       # 能量传递量（树→海为正）
    feedback_gain: float         # 反馈增益
    resonance: bool              # 是否进入共振
    stability_index: float       # 耦合稳定性 0~1
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "coupling_strength": self.coupling_strength,
            "energy_transfer": self.energy_transfer,
            "feedback_gain": self.feedback_gain,
            "resonance": self.resonance,
            "stability_index": self.stability_index,
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CouplingResult":
        return cls(
            coupling_strength=d["coupling_strength"],
            energy_transfer=d["energy_transfer"],
            feedback_gain=d["feedback_gain"],
            resonance=d["resonance"],
            stability_index=d["stability_index"],
            detail=d.get("detail", {}),
        )


class CouplingModel:
    """树海耦合分析器。

    Parameters
    ----------
    cfg : CouplingModelConfig
    """

    def __init__(self, cfg: Optional[CouplingModelConfig] = None) -> None:
        self.cfg = cfg or CouplingModelConfig()

    def analyze(
        self,
        tree_scores: List[float],
        sea_scores: List[float],
        stabilities: Optional[List[float]] = None,
    ) -> CouplingResult:
        """分析树海耦合状态。

        Parameters
        ----------
        tree_scores : list of float
            各候选的树端分数
        sea_scores : list of float
            各候选的海端坍缩分数
        stabilities : list of float, optional
            各候选的稳定性

        Returns
        -------
        CouplingResult
        """
        n = max(len(tree_scores), 1)
        if stabilities is None:
            stabilities = [0.5] * n

        # 有效耦合强度：基础耦合 * 树海分歧度
        divergence = sum(
            abs(t - s) for t, s in zip(tree_scores, sea_scores)
        ) / n
        effective_coupling = self.cfg.tree_sea_coupling * (1.0 + divergence)

        # 能量传递：树端平均 - 海端平均（正=树向海传递）
        tree_mean = sum(tree_scores) / n if tree_scores else 0.0
        sea_mean = sum(sea_scores) / n if sea_scores else 0.0
        energy_transfer = (tree_mean - sea_mean) * effective_coupling

        # 反馈增益
        feedback_gain = self.cfg.feedback_strength * effective_coupling

        # 共振判定
        resonance = effective_coupling >= self.cfg.resonance_threshold

        # 稳定性：受阻尼和耦合强度共同影响
        raw_stability = sum(stabilities) / n
        stability_index = raw_stability * math.exp(-self.cfg.damping * effective_coupling)
        stability_index = max(0.0, min(1.0, stability_index))

        return CouplingResult(
            coupling_strength=effective_coupling,
            energy_transfer=energy_transfer,
            feedback_gain=feedback_gain,
            resonance=resonance,
            stability_index=stability_index,
            detail={
                "divergence": divergence,
                "tree_mean": tree_mean,
                "sea_mean": sea_mean,
                "n_candidates": n,
            },
        )
