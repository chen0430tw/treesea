# runner.py
"""
QCU 本地运行时。

接收 CollapseRequest → 调度 → 执行 IQPU → 返回 SeaOutputBundle。

入口：QCURunner.run(request) → SeaOutputBundle
"""

from __future__ import annotations

import time
from typing import Optional

from ..core.state_repr import IQPUConfig
from ..core.iqpu_runtime import IQPU
from ..io.readout_schema import ReadoutBundleEntry, SeaOutputBundle
from ..scheduler.models import CollapseRequest, Candidate
from ..scheduler.request_ingress import RequestIngress
from ..scheduler.cluster_scheduler import ClusterScheduler
from ..scheduler.termination_policy import TerminationPolicy


class QCURunner:
    """QCU 本地单机运行时。

    Parameters
    ----------
    cfg : IQPUConfig
        虚拟量子芯片配置（所有候选共用同一芯片实例）
    """

    def __init__(self, cfg: IQPUConfig) -> None:
        self.iqpu = IQPU(cfg)
        self._ingress = RequestIngress()
        self._cluster_sched = ClusterScheduler()
        self._term_policy = TerminationPolicy()

    def run(self, request: CollapseRequest) -> SeaOutputBundle:
        """执行 CollapseRequest 并返回 SeaOutputBundle。

        流程
        ----
        1. RequestIngress.normalize() — 填充默认值并校验
        2. ClusterScheduler.build_plan() — 生成 CollapsePlan
        3. 按 plan 顺序逐 Candidate 调用 IQPU.run_qcl_v6()
        4. 汇总为 SeaOutputBundle

        Parameters
        ----------
        request : CollapseRequest

        Returns
        -------
        SeaOutputBundle
        """
        request = self._ingress.normalize(request)
        plan = self._cluster_sched.build_plan(request)

        entries: list[ReadoutBundleEntry] = []
        t_total_start = time.time()

        for cluster_plan in plan.cluster_plans:
            cluster = _find_cluster(request, cluster_plan.cluster_id)
            if cluster is None:
                continue

            for candidate in cluster.candidates:
                params = candidate.payload
                run_id = f"{request.request_id}/{cluster_plan.cluster_id}/{candidate.candidate_id}"
                label = params.get("label", run_id)

                result = self.iqpu.run_qcl_v6(
                    label=label,
                    t1=float(params.get("t1", 3.0)),
                    t2=float(params.get("t2", 5.0)),
                    omega_x=float(params.get("omega_x", 1.0)),
                    gamma_pcm=float(params.get("gamma_pcm", 0.2)),
                    gamma_qim=float(params.get("gamma_qim", 0.03)),
                    gamma_boost=float(params.get("gamma_boost", 0.9)),
                    boost_duration=float(params.get("boost_duration", 3.0)),
                    gamma_reset=float(params.get("gamma_reset", 0.25)),
                    gamma_phi0=float(params.get("gamma_phi0", 0.6)),
                    eps_boost=float(params.get("eps_boost", 4.0)),
                    boost_phase_trim=float(params.get("boost_phase_trim", 0.012)),
                )

                entries.append(ReadoutBundleEntry(
                    run_id=run_id,
                    label=label,
                    DIM=result.DIM,
                    C_end=result.C_end,
                    dtheta_end=result.dtheta_end,
                    N_end=result.N_end,
                    final_sz=result.final_sz,
                    final_n=result.final_n,
                    final_rel_phase=result.final_rel_phase,
                    elapsed_sec=result.elapsed_sec,
                ))

        total_elapsed = time.time() - t_total_start

        summary = _compute_summary(entries)

        return SeaOutputBundle(
            request_id=request.request_id,
            qcu_session_id=request.qcu_session_id,
            entries=entries,
            total_elapsed_sec=total_elapsed,
            summary=summary,
        )


def _find_cluster(request: CollapseRequest, cluster_id: str):
    for c in request.clusters:
        if c.cluster_id == cluster_id:
            return c
    return None


def _compute_summary(entries: list[ReadoutBundleEntry]) -> dict:
    if not entries:
        return {}
    C_ends = [e.C_end for e in entries]
    return {
        "n_runs": len(entries),
        "C_end_min": min(C_ends),
        "C_end_mean": sum(C_ends) / len(C_ends),
        "C_end_max": max(C_ends),
        "best_run_id": min(entries, key=lambda e: e.C_end).run_id,
    }


def main():
    """CLI 入口：演示单次本地运行。"""
    import json
    from ..core.state_repr import IQPUConfig
    from ..scheduler.models import Candidate, CandidateCluster, CollapseRequest

    cfg = IQPUConfig(Nq=2, Nm=2, d=4)
    runner = QCURunner(cfg)

    request = CollapseRequest(
        request_id="demo-001",
        qcu_session_id="sess-001",
        clusters=[
            CandidateCluster(
                cluster_id="cl-0",
                candidates=[
                    Candidate(
                        candidate_id="c0",
                        payload={"label": "demo_run", "boost_duration": 2.0},
                    ),
                ],
            )
        ],
    )

    bundle = runner.run(request)
    print(json.dumps(bundle.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
