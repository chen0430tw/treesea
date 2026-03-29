# qcu/otal/runner.py
"""
OTAL 快搜流水线 —— QCU 的前置筛选层入口。

架构：
    候选态池
       ↓
    OTAL 快搜层   ← 本模块
       ↓
    ┌────────────────────┐
    │ collapse_queue     │ → QCU 局部坍缩层
    │ full_physics_queue │ → Lindblad/RK4 高保真验证层
    └────────────────────┘

OTAL 不是 RK4 的等价替换，而是：
    - 前置近似层
    - 候选成熟度预筛
    - 方向判断层

用法（接入现有 hash_search 流水线）
-------------------------------------
    from qcu.qcu.otal.runner import OTALRunner

    runner = OTALRunner(n_steps=20, theta_c=1.2, top_k=5)
    result = runner.prefilter(candidate_labels)   # OTAL 快搜

    # 只对 full_physics_queue 中的候选运行 IQPU
    for cand in result.full_physics_queue:
        iqpu_result = iqpu.run_qcl_v6(label=cand["candidate_id"], ...)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .graph_state import OTALState
from .oscillatory_direction import init_directions
from .topology_update import topology_step
from .maturity_score import score_all_nodes
from .candidate_filter import CandidateResult, build_otal_state_from_candidates, filter_candidates


@dataclass
class OTALConfig:
    n_steps:            int   = 20     # 拓扑传播步数
    dt:                 float = 0.05   # 时间步长
    lam:                float = 0.3    # 邻域耦合系数 λ
    sigma:              float = 0.01   # 扰动项标准差
    n_edges:            int   = 3      # 初始随机边数
    theta_c:            float = 1.2    # 坍缩阈值 Θ_c
    top_k:              int   = 5      # full_physics 候选上限
    full_physics_ratio: float = 0.2    # full_physics 候选比例
    seed:               Optional[int] = None


@dataclass
class OTALRunResult:
    """OTAL 一次预筛的完整结果。"""
    otal_result:        CandidateResult
    state:              OTALState
    n_candidates_in:    int
    n_collapse:         int
    n_full_physics:     int
    prefilter_time_s:   float
    # 下游 IQPU 结果（若调用了 run_with_iqpu）
    iqpu_results:       List[Any] = field(default_factory=list)
    iqpu_time_s:        float = 0.0


class OTALRunner:
    """振荡拓扑近似层的运行控制器。

    Parameters
    ----------
    cfg : OTALConfig 或关键字参数（透传给 OTALConfig）
    """

    def __init__(self, cfg: Optional[OTALConfig] = None, **kwargs):
        self.cfg = cfg or OTALConfig(**kwargs)

    def prefilter(self, candidate_labels: List[str]) -> OTALRunResult:
        """对候选态列表执行 OTAL 预筛。

        Parameters
        ----------
        candidate_labels : 候选态 ID 列表

        Returns
        -------
        OTALRunResult
        """
        cfg = self.cfg
        t0  = time.perf_counter()

        # ── 1. 构建图状态 ──
        state = build_otal_state_from_candidates(
            candidate_labels,
            n_edges=cfg.n_edges,
            seed=cfg.seed,
        )

        # ── 2. 拓扑传播 n_steps 步 ──
        for _ in range(cfg.n_steps):
            topology_step(
                state,
                dt=cfg.dt,
                lam=cfg.lam,
                sigma=cfg.sigma,
            )

        # ── 3. 候选筛选 ──
        otal_result = filter_candidates(
            state,
            theta_c=cfg.theta_c,
            top_k=cfg.top_k,
            full_physics_ratio=cfg.full_physics_ratio,
        )

        prefilter_time_s = time.perf_counter() - t0

        return OTALRunResult(
            otal_result      = otal_result,
            state            = state,
            n_candidates_in  = len(candidate_labels),
            n_collapse       = otal_result.n_collapse,
            n_full_physics   = otal_result.n_full_physics,
            prefilter_time_s = prefilter_time_s,
        )

    def run_with_iqpu(
        self,
        candidate_labels: List[str],
        iqpu_fn:          Callable[[str], Any],
    ) -> OTALRunResult:
        """OTAL 预筛 + 对 full_physics 候选调用 iqpu_fn。

        Parameters
        ----------
        candidate_labels : 候选态 ID 列表
        iqpu_fn          : 接收 candidate_id (str) 并返回 IQPU 结果的回调

        示例
        ----
        >>> runner.run_with_iqpu(
        ...     labels,
        ...     iqpu_fn=lambda cid: iqpu.run_qcl_v6(label=cid, ...),
        ... )
        """
        run = self.prefilter(candidate_labels)

        t_iqpu = time.perf_counter()
        for cand in run.otal_result.full_physics_queue:
            cid = cand.get("candidate_id") or str(cand["node_id"])
            res = iqpu_fn(cid)
            run.iqpu_results.append({"candidate_id": cid, "result": res})
        run.iqpu_time_s = time.perf_counter() - t_iqpu

        return run

    def summary(self, run: OTALRunResult) -> str:
        """返回本次运行的摘要字符串。"""
        lines = [
            f"OTAL 预筛完成：",
            f"  候选数       : {run.n_candidates_in}",
            f"  → 坍缩队列   : {run.n_collapse}",
            f"  → 高保真验证 : {run.n_full_physics}",
            f"  OTAL 耗时    : {run.prefilter_time_s*1000:.1f} ms",
        ]
        if run.iqpu_time_s > 0:
            lines.append(f"  IQPU 耗时    : {run.iqpu_time_s:.3f} s")
        return "\n".join(lines)
