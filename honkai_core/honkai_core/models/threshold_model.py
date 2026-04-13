# threshold_model.py
"""
阈值分析模型。

实现白皮书 §8.1/§8.2 的阈值判据：
  树端：gamma_i in T_infty iff P + L - D >= theta_T
  海端：M(U_i) = a1*P + a2*C + a3*S - a4*N >= Theta_c

核心职责：
  - 计算局部成熟度 M(U_i)
  - 判定是否越限（collapse / honkai / herrscher）
  - 阈值扫描（沿参数轴扫描临界点）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..io.risk_schema import ThresholdAssessment
from ..io.threshold_schema import ThresholdScanPoint, ThresholdScanResult


@dataclass
class ThresholdModelConfig:
    """阈值模型配置。"""
    theta_collapse: float = 0.8    # 坍缩阈值 Theta_c
    theta_tree: float = 0.6       # 树端阈值 theta_T
    theta_honkai: float = 10.0    # 崩坏能密度上限
    theta_herrscher: float = 0.9  # 律者化阈值
    # 成熟度权重 alpha_1..4
    alpha_peak: float = 0.4       # 峰值权重
    alpha_coherence: float = 0.3  # 相干性权重
    alpha_stability: float = 0.2  # 稳定性权重
    alpha_noise: float = 0.1      # 噪声惩罚权重

    @classmethod
    def from_dict(cls, d: dict) -> "ThresholdModelConfig":
        return cls(
            theta_collapse=d.get("theta_collapse", 0.8),
            theta_tree=d.get("theta_tree", 0.6),
            theta_honkai=d.get("theta_honkai", 10.0),
            theta_herrscher=d.get("theta_herrscher", 0.9),
            alpha_peak=d.get("alpha_peak", 0.4),
            alpha_coherence=d.get("alpha_coherence", 0.3),
            alpha_stability=d.get("alpha_stability", 0.2),
            alpha_noise=d.get("alpha_noise", 0.1),
        )


class ThresholdModel:
    """阈值分析器。

    Parameters
    ----------
    cfg : ThresholdModelConfig
    """

    def __init__(self, cfg: Optional[ThresholdModelConfig] = None) -> None:
        self.cfg = cfg or ThresholdModelConfig()

    def compute_maturity(
        self,
        peak: float,
        coherence: float,
        stability: float,
        noise: float,
    ) -> float:
        """计算局部成熟度 M(U_i)。

        M = alpha1*P + alpha2*C + alpha3*S - alpha4*N
        """
        return (
            self.cfg.alpha_peak * peak
            + self.cfg.alpha_coherence * coherence
            + self.cfg.alpha_stability * stability
            - self.cfg.alpha_noise * noise
        )

    def assess(
        self,
        peak: float,
        coherence: float,
        stability: float,
        noise: float,
        honkai_density: float,
        herrscherization_risk: float = 0.0,
    ) -> ThresholdAssessment:
        """执行阈值评估。

        Parameters
        ----------
        peak, coherence, stability, noise : float
            用于计算成熟度的四维指标
        honkai_density : float
            当前崩坏能密度 rho_H
        herrscherization_risk : float
            律者化风险 0~1

        Returns
        -------
        ThresholdAssessment
        """
        maturity = self.compute_maturity(peak, coherence, stability, noise)
        margin_collapse = self.cfg.theta_collapse - maturity
        margin_honkai = self.cfg.theta_honkai - honkai_density

        breach = False
        breach_type: Optional[str] = None

        if maturity >= self.cfg.theta_collapse:
            breach = True
            breach_type = "collapse"
        if honkai_density >= self.cfg.theta_honkai:
            breach = True
            breach_type = "honkai"
        if herrscherization_risk >= self.cfg.theta_herrscher:
            breach = True
            breach_type = "herrscher"

        return ThresholdAssessment(
            theta_collapse=self.cfg.theta_collapse,
            theta_tree=self.cfg.theta_tree,
            theta_honkai=self.cfg.theta_honkai,
            current_maturity=maturity,
            margin_collapse=margin_collapse,
            margin_honkai=margin_honkai,
            breach=breach,
            breach_type=breach_type,
        )

    def scan(
        self,
        scan_id: str,
        param_name: str,
        param_range: List[float],
        base_values: Dict[str, float],
    ) -> ThresholdScanResult:
        """沿参数轴扫描阈值。

        Parameters
        ----------
        scan_id : str
        param_name : str
            要扫描的参数名（peak/coherence/stability/noise/honkai_density）
        param_range : list
            [start, end, step]
        base_values : dict
            其他参数的基础值

        Returns
        -------
        ThresholdScanResult
        """
        import time
        t0 = time.time()

        start, end, step = param_range
        points: List[ThresholdScanPoint] = []
        critical_value: Optional[float] = None
        prev_breach = False

        val = start
        while val <= end + 1e-12:
            values = dict(base_values)
            values[param_name] = val

            assessment = self.assess(
                peak=values.get("peak", 0.5),
                coherence=values.get("coherence", 0.5),
                stability=values.get("stability", 0.5),
                noise=values.get("noise", 0.1),
                honkai_density=values.get("honkai_density", 1.0),
                herrscherization_risk=values.get("herrscherization_risk", 0.0),
            )

            risk_level = _maturity_to_risk_level(
                assessment.current_maturity, self.cfg.theta_collapse
            )

            point = ThresholdScanPoint(
                param_name=param_name,
                param_value=val,
                maturity=assessment.current_maturity,
                honkai_density=values.get("honkai_density", 1.0),
                gain_factor=0.0,
                breach=assessment.breach,
                risk_level=risk_level,
            )
            points.append(point)

            if assessment.breach and not prev_breach:
                critical_value = val
            prev_breach = assessment.breach

            val += step

        # 安全区间
        safe_range: Optional[List[float]] = None
        if critical_value is not None:
            safe_range = [start, critical_value]

        return ThresholdScanResult(
            scan_id=scan_id,
            param_name=param_name,
            param_range=param_range,
            points=points,
            critical_value=critical_value,
            safe_range=safe_range,
            elapsed_sec=time.time() - t0,
        )


def _maturity_to_risk_level(maturity: float, theta: float) -> str:
    ratio = maturity / max(theta, 1e-12)
    if ratio < 0.5:
        return "safe"
    elif ratio < 0.8:
        return "warning"
    elif ratio < 1.0:
        return "critical"
    else:
        return "terminal"
