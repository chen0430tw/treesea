"""
CFPAI LLM Detector — 異常資金檢測。

LASA 標記的異常資金流 → LLM 語義分析。
"""
from __future__ import annotations

import json
from typing import Any

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]


DETECTOR_SYSTEM_PROMPT = """\
You are the CFPAI Anomaly Detector. You analyze fund flow patterns flagged by LASA (Layered Accounting for Semantic Assets) for potential risks.

LASA risk tags you may encounter:
- NORMAL: no risk
- RESTRICTED_USE: funds with usage constraints
- LEGALLY_SENSITIVE: potential legal/regulatory concerns
- VALUATION_RISK: uncertain valuation
- LIQUIDITY_RISK: hard to liquidate
- HIGH_RISK: elevated risk profile
- ABNORMAL_SOURCE: unusual fund origin
- PENDING_REVIEW: awaiting review

Your job:
1. Identify patterns that could indicate: wash trading, circular leverage, unreported liabilities, concentration risk
2. Assess severity: LOW / MEDIUM / HIGH / CRITICAL
3. Suggest concrete actions
4. Be conservative — flag potential issues without false alarms

Output in Chinese (繁體中文). Use structured format with clear sections.
"""


def detect_anomalies(
    lasa_records: list[dict[str, Any]],
    portfolio_weights: dict[str, float] | None = None,
    api_key: str | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> dict[str, Any]:
    """分析 LASA 記錄中的異常模式。

    Parameters
    ----------
    lasa_records : list of dict
        LASA metaLog 記錄，含 eventId, accountClass, riskTags, totalLnVar
    portfolio_weights : dict, optional
        當前投資組合權重，用於交叉比對
    """
    if anthropic is None:
        raise ImportError("pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    context = {
        "lasa_records": lasa_records[-50:],  # 最近 50 筆
        "portfolio_weights": portfolio_weights,
        "total_records": len(lasa_records),
    }

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=DETECTOR_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                "請分析以下 LASA 資金記錄，檢測是否存在異常模式：\n\n"
                f"```json\n{json.dumps(context, indent=2, ensure_ascii=False)}\n```\n\n"
                "請輸出 JSON 格式的分析結果，包含：\n"
                '{"severity": "LOW/MEDIUM/HIGH/CRITICAL", "findings": [...], "actions": [...], "summary": "..."}'
            ),
        }],
    )

    text = response.content[0].text.strip()
    # 嘗試提取 JSON
    try:
        if "```" in text:
            lines = text.split("```")
            for block in lines:
                block = block.strip()
                if block.startswith("json"):
                    block = block[4:].strip()
                try:
                    return json.loads(block)
                except json.JSONDecodeError:
                    continue
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "severity": "UNKNOWN",
            "findings": [],
            "actions": [],
            "summary": text,
            "raw_response": True,
        }


def check_leverage_loop(
    lasa_records: list[dict[str, Any]],
    threshold: float = 0.3,
) -> dict[str, Any]:
    """檢測循環加槓桿：同一資金反復在 ASSET↔LIABILITY 間流轉。

    不需要 LLM，純規則檢測。
    """
    # 追蹤每個 eventId 的 accountClass 歷史
    class_counts: dict[str, int] = {}
    for rec in lasa_records:
        cls = rec.get("accountClass", "")
        class_counts[cls] = class_counts.get(cls, 0) + 1

    total = len(lasa_records)
    if total == 0:
        return {"loop_detected": False, "risk": "NONE"}

    asset_ratio = class_counts.get("ASSET", 0) / total
    liability_ratio = class_counts.get("LIABILITY", 0) / total

    # 如果 ASSET 和 LIABILITY 都佔比超過 threshold，可能存在循環
    loop_detected = asset_ratio > threshold and liability_ratio > threshold

    # 檢查高風險標記
    high_risk_count = sum(
        1 for rec in lasa_records
        if any(t in rec.get("riskTags", []) for t in ["HIGH_RISK", "ABNORMAL_SOURCE"])
    )

    return {
        "loop_detected": loop_detected,
        "risk": "HIGH" if loop_detected and high_risk_count > 3 else "MEDIUM" if loop_detected else "LOW",
        "asset_ratio": round(asset_ratio, 3),
        "liability_ratio": round(liability_ratio, 3),
        "high_risk_events": high_risk_count,
        "total_events": total,
    }
