"""
CFPAI LLM Sentiment — 新闻情绪分析。

白皮书 n_t：新闻、事件与情绪特征。
LLM 读财经新闻 → 情绪分数 → 喂给评分公式。
"""
from __future__ import annotations

import json
from typing import Any

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]


SENTIMENT_SYSTEM_PROMPT = """\
You are a financial sentiment analyzer for the CFPAI system.

Your job is to analyze financial news headlines/articles and produce a sentiment score for each mentioned asset.

Rules:
1. Score range: -1.0 (extremely bearish) to +1.0 (extremely bullish)
2. 0.0 = neutral / no clear direction
3. Consider: earnings, guidance, macro trends, sector rotation, geopolitical risk
4. Be conservative: most news is noise. Only strong signals move past ±0.3
5. If an asset is not mentioned, omit it from the output

Output format (JSON only, no explanation):
{
  "sentiments": {"SYMBOL": score, ...},
  "confidence": 0.0-1.0,
  "summary": "one-line summary of market mood"
}
"""


def analyze_sentiment(
    news_text: str,
    symbols: list[str],
    api_key: str | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> dict[str, Any]:
    """用 Claude API 分析新闻情绪。

    Parameters
    ----------
    news_text : str
        新闻文本（标题、摘要或全文）
    symbols : list of str
        关注的资产代码
    api_key : str, optional
        Anthropic API key，不传则从环境变量读取
    model : str
        Claude 模型 ID

    Returns
    -------
    dict with keys: sentiments, confidence, summary
    """
    if anthropic is None:
        raise ImportError("pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    user_msg = f"""Analyze the following financial news for sentiment on these assets: {', '.join(symbols)}

News:
{news_text}

Respond with JSON only."""

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SENTIMENT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = response.content[0].text.strip()
    # 提取 JSON
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    result = json.loads(text)
    return {
        "sentiments": result.get("sentiments", {}),
        "confidence": result.get("confidence", 0.5),
        "summary": result.get("summary", ""),
        "model": model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


def batch_sentiment(
    news_items: list[str],
    symbols: list[str],
    api_key: str | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> dict[str, float]:
    """批量分析多条新闻，合并情绪分数。

    最终情绪 = 加权平均（confidence 作权重）。
    """
    if not news_items:
        return {s: 0.0 for s in symbols}

    all_sentiments: dict[str, list[tuple[float, float]]] = {s: [] for s in symbols}

    for news in news_items:
        try:
            result = analyze_sentiment(news, symbols, api_key, model)
            conf = result.get("confidence", 0.5)
            for sym, score in result.get("sentiments", {}).items():
                if sym in all_sentiments:
                    all_sentiments[sym].append((float(score), float(conf)))
        except Exception:
            continue

    merged = {}
    for sym, pairs in all_sentiments.items():
        if not pairs:
            merged[sym] = 0.0
            continue
        total_weight = sum(c for _, c in pairs)
        if total_weight < 1e-8:
            merged[sym] = 0.0
        else:
            merged[sym] = round(sum(s * c for s, c in pairs) / total_weight, 4)

    return merged


def sentiment_to_scoring_adjustment(
    sentiments: dict[str, float],
    alpha: float = 0.15,
) -> dict[str, float]:
    """将情绪分数转换为评分调制系数。

    输出 {symbol: gain}，其中 gain ∈ [1-alpha, 1+alpha]。
    用于乘到 Maxwell Demon 评分上。
    """
    adjustments = {}
    for sym, score in sentiments.items():
        gain = 1.0 + alpha * max(-1.0, min(1.0, score))
        adjustments[sym] = round(gain, 4)
    return adjustments
