# runner.py
"""
Honkai Core 运行时。

接收 ScenarioConfig → 执行崩坏能估计 + 阈值分析 + 耦合建模 + 改写评估 → 返回 HCReportBundle。

入口：HonkaiCoreRunner.run(config) → HCReportBundle
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from ..io.scenario_loader import ScenarioConfig
from ..io.risk_schema import (
    EnergyEstimate,
    HCReportBundle,
    Recommendation,
    RewriteAssessment,
    RiskEntry,
    RiskSurface,
    ThresholdAssessment,
)
from ..models.energy_model import EnergyModel, EnergyModelConfig
from ..models.threshold_model import ThresholdModel, ThresholdModelConfig
from ..models.coupling_model import CouplingModel, CouplingModelConfig
from ..models.rewrite_model import RewriteModel, RewriteModelConfig


class HonkaiCoreRunner:
    """Honkai Core 本地运行时。

    Parameters
    ----------
    config : ScenarioConfig
        场景配置
    """

    def __init__(self, config: ScenarioConfig) -> None:
        self.config = config

        self.energy_model = EnergyModel(
            EnergyModelConfig.from_dict(config.energy_params)
        )
        self.threshold_model = ThresholdModel(
            ThresholdModelConfig.from_dict(config.threshold_params)
        )
        self.coupling_model = CouplingModel(
            CouplingModelConfig.from_dict(config.coupling_params)
        )
        self.rewrite_model = RewriteModel(
            RewriteModelConfig.from_dict(config.rewrite_params)
        )

    def run(self) -> HCReportBundle:
        """执行完整的 Honkai Core 分析流水线。

        流程
        ----
        1. 崩坏能估计
        2. 耦合分析
        3. 逐候选阈值评估 + 风险分级
        4. 改写评估
        5. 生成综合建议
        6. 组装 HCReportBundle

        Returns
        -------
        HCReportBundle
        """
        t0 = time.time()
        hc_run_id = f"hc_{uuid.uuid4().hex[:8]}"

        candidates = self._prepare_candidates()

        # 1. 崩坏能估计
        energy = self.energy_model.estimate(candidates)

        # 2. 耦合分析
        tree_scores = [c.get("tree_score", 0.5) for c in candidates]
        sea_scores = [c.get("collapse_score", 0.5) for c in candidates]
        stabilities = [c.get("stability", 0.5) for c in candidates]
        coupling = self.coupling_model.analyze(tree_scores, sea_scores, stabilities)

        # 3. 逐候选阈值评估 + 风险分级
        risk_entries: List[RiskEntry] = []
        all_assessments: List[ThresholdAssessment] = []

        for c in candidates:
            cid = c.get("candidate_id", "unknown")
            assessment = self.threshold_model.assess(
                peak=c.get("tree_score", 0.5),
                coherence=c.get("collapse_score", 0.5),
                stability=c.get("stability", 0.5),
                noise=c.get("noise", 0.1),
                honkai_density=energy.density,
                herrscherization_risk=c.get("herrscherization_risk", 0.0),
            )
            all_assessments.append(assessment)

            risk_score = self._compute_risk_score(assessment, energy, coupling.coupling_strength)
            risk_level = _score_to_level(risk_score)

            risk_entries.append(RiskEntry(
                candidate_id=cid,
                risk_level=risk_level,
                risk_score=risk_score,
                honkai_density=energy.density,
                threshold_margin=assessment.margin_collapse,
                herrscherization_risk=c.get("herrscherization_risk", 0.0),
                rewrite_risk=0.0,  # 填充后更新
                detail={"tree_score": c.get("tree_score", 0.0)},
            ))

        # 取最严格的阈值评估作为全局评估
        global_assessment = self._merge_assessments(all_assessments)

        # 4. 改写评估
        rewrite = self.rewrite_model.assess(
            energy=energy,
            threshold=global_assessment,
            coupling_strength=coupling.coupling_strength,
        )

        # 更新 risk_entries 的 rewrite_risk
        for r in risk_entries:
            r.rewrite_risk = rewrite.rewrite_risk

        # 5. 综合建议
        recommendation = self._generate_recommendation(
            energy, global_assessment, rewrite, coupling.coupling_strength
        )

        return HCReportBundle(
            request_id=self.config.request_id or self.config.scenario_id,
            hc_run_id=hc_run_id,
            energy_estimate=energy,
            threshold_assessment=global_assessment,
            risk_entries=risk_entries,
            risk_surface=None,
            rewrite_assessment=rewrite,
            recommendation=recommendation,
            elapsed_sec=time.time() - t0,
        )

    def _prepare_candidates(self) -> List[Dict[str, Any]]:
        """从配置中提取候选列表。"""
        if self.config.candidates:
            return [
                {"candidate_id": c.candidate_id, **c.payload}
                for c in self.config.candidates
            ]
        # 无候选时生成默认单候选
        return [{"candidate_id": "default", "tree_score": 0.5, "collapse_score": 0.5, "stability": 0.5}]

    def _compute_risk_score(
        self,
        assessment: ThresholdAssessment,
        energy: EnergyEstimate,
        coupling_strength: float,
    ) -> float:
        """综合风险评分。"""
        maturity_ratio = assessment.current_maturity / max(assessment.theta_collapse, 1e-12)
        energy_ratio = energy.density / max(assessment.theta_honkai, 1e-12)
        score = 0.4 * min(1.0, maturity_ratio) + 0.3 * min(1.0, energy_ratio) + 0.3 * min(1.0, coupling_strength)
        return max(0.0, min(1.0, score))

    def _merge_assessments(self, assessments: List[ThresholdAssessment]) -> ThresholdAssessment:
        """取最严格的阈值评估。"""
        if not assessments:
            return ThresholdAssessment(
                theta_collapse=self.threshold_model.cfg.theta_collapse,
                theta_tree=self.threshold_model.cfg.theta_tree,
                theta_honkai=self.threshold_model.cfg.theta_honkai,
                current_maturity=0.0,
                margin_collapse=self.threshold_model.cfg.theta_collapse,
                margin_honkai=self.threshold_model.cfg.theta_honkai,
                breach=False,
            )
        worst = max(assessments, key=lambda a: a.current_maturity)
        return worst

    def _generate_recommendation(
        self,
        energy: EnergyEstimate,
        threshold: ThresholdAssessment,
        rewrite: RewriteAssessment,
        coupling_strength: float,
    ) -> Recommendation:
        """生成综合建议。"""
        if threshold.breach:
            if threshold.breach_type == "herrscher":
                return Recommendation(
                    action="abort",
                    confidence=0.95,
                    writeback_allowed=False,
                    reason=f"Herrscher threshold breached (maturity={threshold.current_maturity:.3f})",
                )
            return Recommendation(
                action="contain",
                confidence=0.9,
                energy_limit=threshold.theta_honkai * 0.8,
                writeback_allowed=False,
                reason=f"Threshold breached: {threshold.breach_type}",
            )

        if energy.state == "gain" and energy.gain_factor > 2.0:
            return Recommendation(
                action="limit",
                confidence=0.8,
                energy_limit=threshold.theta_honkai * 0.6,
                writeback_allowed=True,
                reason=f"High energy gain (Gamma_H={energy.gain_factor:.2f})",
            )

        if rewrite.recommended_action == "defer":
            return Recommendation(
                action="limit",
                confidence=0.7,
                writeback_allowed=True,
                reason="Stabilization cost approaching budget limit",
            )

        return Recommendation(
            action="proceed",
            confidence=0.85,
            writeback_allowed=True,
            reason="All metrics within safe bounds",
        )


def main():
    """CLI 入口：演示本地运行。"""
    import json
    from ..io.scenario_loader import ScenarioConfig, CandidateSpec

    config = ScenarioConfig(
        scenario_id="demo",
        request_id="req_demo_001",
        candidates=[
            CandidateSpec("cand_01", {"tree_score": 0.8, "collapse_score": 0.6, "stability": 0.7}),
            CandidateSpec("cand_02", {"tree_score": 0.5, "collapse_score": 0.9, "stability": 0.4}),
            CandidateSpec("cand_03", {"tree_score": 0.3, "collapse_score": 0.2, "stability": 0.9}),
        ],
    )

    runner = HonkaiCoreRunner(config)
    bundle = runner.run()
    print(json.dumps(bundle.to_dict(), indent=2, ensure_ascii=False))


def _score_to_level(score: float) -> str:
    if score < 0.3:
        return "safe"
    elif score < 0.6:
        return "warning"
    elif score < 0.85:
        return "critical"
    else:
        return "terminal"


if __name__ == "__main__":
    main()
