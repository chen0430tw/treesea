# qcu/otal/graph_state.py
"""
OTALState：振荡拓扑近似层的图状态表示。

节点：OTALNode  — 携带振荡指向数 (complex)、相位、周期、局部评分
边：  OTALEdge  — 携带动态边权
图：  OTALState — 节点表 + 边表 + 时刻 + 稀疏邻接缓存
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class OTALNode:
    node_id:     int
    direction:   complex   # 振荡指向数 D_i(t)
    phase:       float     # 当前相位 θ_i(t)
    period:      float     # 局部振荡周期 T_i
    local_score: float = 0.0   # 累计成熟度分
    candidate_id: Optional[str] = None  # 对应的候选态标签


@dataclass
class OTALEdge:
    src:    int
    dst:    int
    weight: float   # 动态边权 w_ij(t)


@dataclass
class OTALState:
    nodes: List[OTALNode]
    edges: List[OTALEdge]
    t:     float = 0.0

    # ── 邻接缓存（由 build_adjacency 填充）──
    _adj: Dict[int, List[int]] = field(default_factory=dict, repr=False, compare=False)
    _w:   Dict[tuple, float]   = field(default_factory=dict, repr=False, compare=False)

    def build_adjacency(self) -> None:
        """从 edges 构建邻接表与边权字典（无向图）。"""
        self._adj = {}
        self._w   = {}
        for node in self.nodes:
            self._adj[node.node_id] = []
        for e in self.edges:
            self._adj[e.src].append(e.dst)
            self._adj[e.dst].append(e.src)
            self._w[(e.src, e.dst)] = e.weight
            self._w[(e.dst, e.src)] = e.weight

    def neighbors(self, node_id: int) -> List[int]:
        return self._adj.get(node_id, [])

    def edge_weight(self, src: int, dst: int) -> float:
        return self._w.get((src, dst), 0.0)

    def node_map(self) -> Dict[int, OTALNode]:
        return {n.node_id: n for n in self.nodes}
