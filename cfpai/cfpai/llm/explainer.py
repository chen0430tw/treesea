"""
CFPAI LLM Explainer — 策略解释生成。

Maxwell Demon 的择时决策 → LLM 生成人话报告。
"""
from __future__ import annotations

import json
from typing import Any

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]


EXPLAINER_SYSTEM_PROMPT = """\
You are the CFPAI Strategy Explainer. You translate quantitative portfolio decisions into clear, actionable human language.

CFPAI uses a Maxwell Demon scoring model that:
- Separates upside volatility (good) from downside volatility (bad)
- Uses non-linear gating: amplifies momentum when upside vol > downside vol, suppresses when opposite
- Applies risk signals: green (low risk), yellow (moderate), red (high), purple (black swan)
- Enforces constraints: cash floor (10%), single asset cap (50%)

Your job:
1. Explain WHY the portfolio is positioned this way
2. Highlight the key drivers (momentum, vol asymmetry, risk signals)
3. Note any unusual patterns or warnings
4. Keep it professional but readable — this is for a financial planner, not a quant PhD

Output in Chinese (繁體中文) unless asked otherwise. Use markdown formatting.
"""


def explain_planning(
    snapshot: dict[str, Any],
    stats: dict[str, Any],
    latest_weights: dict[str, float],
    symbols: list[str],
    api_key: str | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """用 LLM 生成規劃解釋報告。"""
    if anthropic is None:
        raise ImportError("pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    context = json.dumps({
        "planning_snapshot": snapshot,
        "performance_stats": stats,
        "latest_weights": latest_weights,
        "symbols": symbols,
    }, indent=2, ensure_ascii=False)

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=EXPLAINER_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"請解釋以下 CFPAI 規劃結果，說明為什麼做出這樣的配置決策：\n\n```json\n{context}\n```",
        }],
    )

    return response.content[0].text


def explain_risk_signal(
    risk_signal: dict[str, Any],
    api_key: str | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """解釋風險信號的含義和建議行動。"""
    if anthropic is None:
        raise ImportError("pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    context = json.dumps(risk_signal, indent=2, ensure_ascii=False)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=EXPLAINER_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"請解釋以下風險信號，用白話文說明當前風險狀態和建議行動：\n\n```json\n{context}\n```",
        }],
    )

    return response.content[0].text


def explain_weight_change(
    old_weights: dict[str, float],
    new_weights: dict[str, float],
    api_key: str | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """解釋權重變化的原因。"""
    if anthropic is None:
        raise ImportError("pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    changes = {}
    all_syms = set(old_weights) | set(new_weights)
    for sym in all_syms:
        old = old_weights.get(sym, 0.0)
        new = new_weights.get(sym, 0.0)
        changes[sym] = {"old": old, "new": new, "delta": round(new - old, 4)}

    context = json.dumps(changes, indent=2, ensure_ascii=False)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=EXPLAINER_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"請解釋以下資產權重變化，分析調整原因和可能的市場驅動因素：\n\n```json\n{context}\n```",
        }],
    )

    return response.content[0].text
