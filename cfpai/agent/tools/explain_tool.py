"""Agent tool: 策略解釋生成。"""
from __future__ import annotations

from typing import Any


def explain_portfolio(
    snapshot: dict[str, Any],
    stats: dict[str, Any],
    latest_weights: dict[str, float],
    symbols: list[str],
    api_key: str | None = None,
) -> str:
    """生成規劃解釋報告。"""
    from cfpai.llm.explainer import explain_planning
    return explain_planning(snapshot, stats, latest_weights, symbols, api_key=api_key)


def explain_risk(
    risk_signal: dict[str, Any],
    api_key: str | None = None,
) -> str:
    """解釋風險信號。"""
    from cfpai.llm.explainer import explain_risk_signal
    return explain_risk_signal(risk_signal, api_key=api_key)
