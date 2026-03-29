# qcu/otal/oscillatory_direction.py
"""
振荡指向数（Oscillatory Direction Number）工具函数。

振荡指向数 D_i(t) ∈ ℂ，满足：
    D_i(t + T_i) ≈ D_i(t)     （局部周期性）

这是 QCU 项目内正式的数学变量，不是普通 phase label。
"""

from __future__ import annotations

import math
import cmath
from typing import List, Optional

import numpy as np

from .graph_state import OTALNode, OTALState


def init_directions(
    state:   OTALState,
    rng:     Optional[np.random.Generator] = None,
    amplitude: float = 1.0,
) -> None:
    """为所有节点初始化振荡指向数（随机相位，固定幅度）。

    D_i(0) = amplitude · e^{i·θ₀}，θ₀ ~ Uniform[0, 2π)
    """
    if rng is None:
        rng = np.random.default_rng()
    phases = rng.uniform(0.0, 2 * math.pi, len(state.nodes))
    for node, theta in zip(state.nodes, phases):
        node.direction = amplitude * cmath.exp(1j * theta)
        node.phase     = theta


def phase_diff(a: complex, b: complex) -> float:
    """计算两个振荡指向数之间的相位差 Δθ ∈ (-π, π]。"""
    return cmath.phase(a * b.conjugate())


def direction_alignment(a: complex, b: complex) -> float:
    """归一化方向一致性 ∈ [0, 1]。

    alignment = (cos(Δθ) + 1) / 2
    1.0 表示完全同相，0.0 表示完全反相。
    """
    delta = phase_diff(a, b)
    return (math.cos(delta) + 1.0) / 2.0


def local_phase_concentration(directions: List[complex]) -> float:
    """计算一组振荡指向数的相位集中度（Kuramoto 同步序参量）。

    R = |Σ e^{iθ_k}| / N    ∈ [0, 1]
    R=1 表示完全相位锁定，R=0 表示均匀分布。
    """
    if not directions:
        return 0.0
    n = len(directions)
    total = sum(d / abs(d) if abs(d) > 1e-12 else 0 + 0j for d in directions)
    return abs(total) / n


def advance_phase(node: OTALNode, dt: float) -> None:
    """根据节点周期推进相位：θ += 2π·dt / T_i。"""
    delta = 2 * math.pi * dt / max(node.period, 1e-12)
    node.phase    = (node.phase + delta) % (2 * math.pi)
    node.direction = abs(node.direction) * cmath.exp(1j * node.phase)
