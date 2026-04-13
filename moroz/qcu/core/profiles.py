# profiles.py
"""
IQPU 运行 profile 定义。

IQPUFastProfile  快搜模式：complex64，稀疏观测，关闭纠缠监测
IQPUFullProfile  高保真模式：complex128，完整读出，可开纠缠监测

apply_profile()  将 profile 设置写入 IQPUConfig
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state_repr import IQPUConfig


@dataclass
class IQPUFastProfile:
    """快搜模式 profile。

    适用于：候选结构搜索、hash/prefix-zero 预筛、局部峰值显形。
    """
    name: str = "fast_search"
    obs_every: int = 8
    negativity_every: int = 0
    track_entanglement: bool = False
    dtype: str = "complex64"
    backend: str = "cpu"   # 可改为 "cuda"


@dataclass
class IQPUFullProfile:
    """高保真模式 profile。

    适用于：论文图、完整 Lindblad 验证、gate window / negativity 监控。
    """
    name: str = "full_physics"
    obs_every: int = 1
    negativity_every: int = 8
    track_entanglement: bool = True
    dtype: str = "complex128"
    backend: str = "cpu"   # 可改为 "cuda"


def apply_profile(cfg: "IQPUConfig", profile) -> "IQPUConfig":
    """将 profile 设置写入 cfg 并返回。

    Parameters
    ----------
    cfg : IQPUConfig
        待修改的配置（原地修改）
    profile : IQPUFastProfile | IQPUFullProfile
        profile 对象

    Returns
    -------
    IQPUConfig
        已写入 profile 的配置
    """
    cfg.profile            = profile.name
    cfg.obs_every          = profile.obs_every
    cfg.negativity_every   = profile.negativity_every
    cfg.track_entanglement = profile.track_entanglement
    cfg.dtype              = profile.dtype
    cfg.device             = profile.backend
    return cfg
