from __future__ import annotations

"""runtime/single_node_runner.py

Single-node entry point for Tree Diagram.

Architecture position:
  runtime layer — wraps CandidatePipeline for single-node (non-distributed)
  execution.  Provides a clean CLI-compatible interface and returns a
  TreeOutputBundle.

This is the standard runner for local development and single-GPU deployment.
For multi-node MPI execution, use multi_node_runner.py.
"""

import time
from dataclasses import dataclass
from typing import Optional

from ..core.problem_seed import ProblemSeed, default_seed
from ..numerics.forcing import GridConfig
from ..pipeline.candidate_pipeline import CandidatePipeline
from ..io.oracle_schema import TreeOutputBundle
from ..oracle.report_builder import ReportBuilder, OracleReport
from ..oracle.oracle_output import OracleEnvelope, wrap_abstract


@dataclass
class SingleNodeConfig:
    """Configuration for single-node runs."""
    top_k:     int   = 12
    NX:        int   = 28
    NY:        int   = 21
    steps:     int   = 20
    dt:        float = 45.0
    n_workers: int   = 1


class SingleNodeRunner:
    """Run Tree Diagram on a single node.

    Usage::

        runner = SingleNodeRunner()
        bundle = runner.run()
        report = runner.build_report(bundle)
    """

    def __init__(
        self,
        cfg:  Optional[SingleNodeConfig] = None,
        seed: Optional[ProblemSeed] = None,
    ) -> None:
        self.cfg  = cfg  if cfg  is not None else SingleNodeConfig()
        self.seed = seed if seed is not None else default_seed()

    def run(self) -> TreeOutputBundle:
        """Execute the pipeline and return a TreeOutputBundle."""
        t0 = time.time()
        c  = self.cfg

        pipeline = CandidatePipeline(
            seed=self.seed,
            top_k=c.top_k,
            n_workers=c.n_workers,
            NX=c.NX,
            NY=c.NY,
            steps=c.steps,
            dt=c.dt,
        )
        top_results, hydro, abstract_oracle = pipeline.run()
        elapsed = time.time() - t0

        best_worldline = abstract_oracle.get("best_worldline", {})

        return TreeOutputBundle(
            seed_title=self.seed.title,
            mode="integrated",
            best_worldline=best_worldline,
            hydro_control=hydro,
            branch_histogram=abstract_oracle.get("branch_histogram", {}),
            oracle_details=abstract_oracle,
            elapsed_sec=elapsed,
        )

    def run_with_report(self) -> tuple:
        """Run and return (TreeOutputBundle, OracleReport)."""
        bundle = self.run()
        envelope = wrap_abstract(
            bundle.oracle_details,
            elapsed_ms=bundle.elapsed_sec * 1000,
        )
        report = ReportBuilder().build(envelope)
        return bundle, report

    @classmethod
    def from_grid_config(
        cls,
        grid_cfg: GridConfig,
        seed: Optional[ProblemSeed] = None,
        top_k: int = 12,
    ) -> "SingleNodeRunner":
        """Construct from a GridConfig."""
        cfg = SingleNodeConfig(
            top_k=top_k,
            NX=max(28, grid_cfg.NX // 4),
            NY=max(21, grid_cfg.NY // 4),
            steps=max(20, grid_cfg.STEPS // 6),
            dt=float(grid_cfg.DT),
        )
        return cls(cfg=cfg, seed=seed)

    def build_report(self, bundle: TreeOutputBundle) -> OracleReport:
        envelope = wrap_abstract(
            bundle.oracle_details,
            elapsed_ms=bundle.elapsed_sec * 1000,
        )
        return ReportBuilder().build(envelope)
