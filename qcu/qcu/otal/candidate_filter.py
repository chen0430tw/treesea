# qcu/otal/candidate_filter.py
"""
候选筛选：从 OTALState 提取坍缩候选，分发到两条队列。

输出：
    CandidateResult.collapse_queue     — 直接推入 QCU 局部坍缩层
    CandidateResult.full_physics_queue — 推入高保真 Lindblad/RK4 验证层

判据（Section 7）：
    M(U,t) >= Θ_c → collapse_candidate = True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .graph_state import OTALState
from .maturity_score import score_all_nodes, maturity_score


@dataclass
class CandidateResult:
    """OTAL 筛选结果，供下游 collapse / full_physics 层消费。"""

    collapse_queue:     List[dict] = field(default_factory=list)
    full_physics_queue: List[dict] = field(default_factory=list)

    # 统计
    n_total:   int = 0
    n_collapse: int = 0
    n_full_physics: int = 0
    otal_time_s: float = 0.0


def filter_candidates(
    state:              OTALState,
    theta_c:            float = 1.2,    # 坍缩阈值 Θ_c
    top_k:              int   = 5,      # 最多送入 full_physics 的数量
    full_physics_ratio: float = 0.2,    # 取 top 20% 送 full_physics
    **score_kwargs,
) -> CandidateResult:
    """对当前 OTALState 执行候选筛选。

    流程
    ----
    1. score_all_nodes → 每个节点获得 local_score
    2. 按 local_score 降序排列
    3. score >= theta_c → collapse_queue
    4. top-k 或 top-ratio 中未入 collapse_queue 的 → full_physics_queue
    """
    import time
    t0 = time.perf_counter()

    score_all_nodes(state, **score_kwargs)

    sorted_nodes = sorted(state.nodes, key=lambda n: n.local_score, reverse=True)
    n_total = len(sorted_nodes)

    result = CandidateResult(n_total=n_total)

    n_fp = max(1, min(top_k, int(n_total * full_physics_ratio)))
    collapse_ids = set()

    for rank, node in enumerate(sorted_nodes):
        entry = {
            "node_id":      node.node_id,
            "candidate_id": node.candidate_id,
            "local_score":  node.local_score,
            "direction":    node.direction,
            "phase":        node.phase,
            "rank":         rank,
        }

        if node.local_score >= theta_c:
            entry["reason"] = "maturity_threshold"
            result.collapse_queue.append(entry)
            collapse_ids.add(node.node_id)
            result.n_collapse += 1
        elif rank < n_fp and node.node_id not in collapse_ids:
            entry["reason"] = "top_k"
            result.full_physics_queue.append(entry)
            result.n_full_physics += 1

    result.otal_time_s = time.perf_counter() - t0
    return result


def build_otal_state_from_candidates(
    candidate_labels: List[str],
    n_edges:          int   = 3,
    default_period:   float = 1.0,
    seed:             Optional[int] = None,
) -> OTALState:
    """从候选态标签列表快速构建 OTALState（随机拓扑）。

    用于将 QCU 候选态池接入 OTAL 的标准入口。

    Parameters
    ----------
    candidate_labels : 候选态 ID 列表（如 hash 字符串或索引）
    n_edges          : 每个节点的随机边数
    default_period   : 初始振荡周期
    seed             : 随机种子
    """
    import random
    import math
    import cmath
    from .graph_state import OTALNode, OTALEdge, OTALState
    from .oscillatory_direction import init_directions

    rng_np = __import__("numpy").random.default_rng(seed)
    rng_py = random.Random(seed)

    nodes = [
        OTALNode(
            node_id=i,
            direction=1.0 + 0j,
            phase=0.0,
            period=default_period,
            candidate_id=label,
        )
        for i, label in enumerate(candidate_labels)
    ]

    N = len(nodes)
    edges = []
    seen  = set()
    for i in range(N):
        targets = rng_py.sample(
            [j for j in range(N) if j != i],
            k=min(n_edges, N - 1)
        )
        for j in targets:
            key = (min(i, j), max(i, j))
            if key not in seen:
                edges.append(OTALEdge(src=key[0], dst=key[1], weight=1.0))
                seen.add(key)

    state = OTALState(nodes=nodes, edges=edges)
    state.build_adjacency()
    init_directions(state, rng=rng_np)
    return state
