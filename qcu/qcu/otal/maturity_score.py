# qcu/otal/maturity_score.py
"""
成熟度评分：按 Section 7 计算局部子图 U 的成熟度 M(U,t)。

M(U,t) = α1·A(U,t) + α2·P(U,t) + α3·S(U,t) - α4·R(U,t)

各项定义：
    A(U,t)  振荡一致性：子图内所有节点对的平均方向对齐度
    P(U,t)  相位集中度：Kuramoto 同步序参量 R = |Σ e^{iθ}|/N
    S(U,t)  邻域支持强度：子图与外部节点之间边权的均值
    R(U,t)  扰动/发散度：子图内振荡指向数模长的标准差
"""

from __future__ import annotations

import math
import cmath
import statistics
from typing import List, Optional, Sequence

from .graph_state import OTALNode, OTALState
from .oscillatory_direction import direction_alignment, local_phase_concentration


def oscillation_consistency(nodes: Sequence[OTALNode]) -> float:
    """A(U,t)：所有节点对方向对齐度的均值。"""
    if len(nodes) < 2:
        return 1.0
    pairs = 0
    total = 0.0
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            total += direction_alignment(nodes[i].direction, nodes[j].direction)
            pairs += 1
    return total / pairs


def phase_concentration(nodes: Sequence[OTALNode]) -> float:
    """P(U,t)：Kuramoto 序参量。"""
    return local_phase_concentration([n.direction for n in nodes])


def neighbor_support(
    state:    OTALState,
    node_ids: Sequence[int],
) -> float:
    """S(U,t)：子图节点与子图外节点之间边权的均值。

    衡量子图被外部支持的程度。
    """
    uid_set = set(node_ids)
    cross_weights = []
    for nid in node_ids:
        for nb in state.neighbors(nid):
            if nb not in uid_set:
                cross_weights.append(state.edge_weight(nid, nb))
    if not cross_weights:
        return 0.0
    return sum(cross_weights) / len(cross_weights)


def dispersion(nodes: Sequence[OTALNode]) -> float:
    """R(U,t)：振荡指向数模长的标准差（度量发散性）。"""
    if len(nodes) < 2:
        return 0.0
    mags = [abs(n.direction) for n in nodes]
    return statistics.stdev(mags)


def maturity_score(
    state:    OTALState,
    node_ids: Sequence[int],
    alpha1:   float = 1.0,   # A 权重
    alpha2:   float = 1.0,   # P 权重
    alpha3:   float = 0.5,   # S 权重
    alpha4:   float = 0.5,   # R 惩罚
) -> float:
    """计算子图 node_ids 的总成熟度 M(U,t)。"""
    nmap  = state.node_map()
    nodes = [nmap[nid] for nid in node_ids if nid in nmap]
    if not nodes:
        return 0.0

    A = oscillation_consistency(nodes)
    P = phase_concentration(nodes)
    S = neighbor_support(state, node_ids)
    R = dispersion(nodes)

    return alpha1 * A + alpha2 * P + alpha3 * S - alpha4 * R


def score_all_nodes(
    state:    OTALState,
    **kwargs,
) -> None:
    """为每个节点单独计算成熟度并写入 node.local_score。

    以节点自身 + 其邻域作为子图 U（单节点邻域成熟度）。
    """
    for node in state.nodes:
        subgraph = [node.node_id] + state.neighbors(node.node_id)
        node.local_score = maturity_score(state, subgraph, **kwargs)
