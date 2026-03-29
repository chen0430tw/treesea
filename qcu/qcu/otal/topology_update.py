# qcu/otal/topology_update.py
"""
拓扑传播更新：按 Section 6 更新规则推进 OTALState 一步。

更新规则：
    D_i(t+Δt) = (1-λ)·D_i(t)
              + λ · Σ_{j∈N(i)} w̃_ij(t)·D_j(t)
              + η_i(t)

其中：
    w̃_ij  = w_ij / Σ_k w_ik    （归一化边权）
    η_i    ~ Normal(0, σ)·e^{iφ}  （可选扰动项）
"""

from __future__ import annotations

import cmath
import math
from typing import Optional

import numpy as np

from .graph_state import OTALState
from .oscillatory_direction import advance_phase


def topology_step(
    state:      OTALState,
    dt:         float = 0.01,
    lam:        float = 0.3,     # λ：邻域耦合系数
    sigma:      float = 0.01,    # 扰动项标准差（0 = 关闭）
    rng:        Optional[np.random.Generator] = None,
    update_edge_weights: bool = True,
    weight_decay: float = 0.95,  # 边权衰减（模拟动态边）
) -> None:
    """就地推进 OTALState 一个时间步 dt。"""
    if rng is None:
        rng = np.random.default_rng()

    nmap = state.node_map()

    # ── 计算每个节点的邻域加权和 ──
    new_directions = {}
    for node in state.nodes:
        nbs = state.neighbors(node.node_id)
        if nbs:
            raw_weights = [state.edge_weight(node.node_id, nb) for nb in nbs]
            w_sum = sum(raw_weights) or 1.0
            w_norm = [w / w_sum for w in raw_weights]
            nb_sum = sum(w * nmap[nb].direction for w, nb in zip(w_norm, nbs))
        else:
            nb_sum = 0 + 0j

        # 扰动项
        if sigma > 0:
            angle = rng.uniform(0, 2 * math.pi)
            eta = rng.normal(0, sigma) * cmath.exp(1j * angle)
        else:
            eta = 0 + 0j

        new_dir = (1.0 - lam) * node.direction + lam * nb_sum + eta
        new_directions[node.node_id] = new_dir

    # ── 写回 ──
    for node in state.nodes:
        node.direction = new_directions[node.node_id]
        if abs(node.direction) > 1e-12:
            node.phase = cmath.phase(node.direction)
        advance_phase(node, dt)

    # ── 可选：边权衰减（模拟动态图演化）──
    if update_edge_weights:
        for edge in state.edges:
            edge.weight *= weight_decay
            edge.weight = max(edge.weight, 1e-6)  # 防止权重归零

    state.t += dt
    state.build_adjacency()  # 刷新邻接缓存（边权已更新）
