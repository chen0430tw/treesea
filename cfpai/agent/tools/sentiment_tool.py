"""Agent tool: 新聞情緒分析。"""
from __future__ import annotations

from typing import Any


def analyze_news_sentiment(
    news_text: str,
    symbols: list[str] | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """分析新聞文本的市場情緒。"""
    from cfpai.llm.sentiment import analyze_sentiment
    symbols = symbols or []
    return analyze_sentiment(news_text, symbols, api_key=api_key)


def batch_news_sentiment(
    news_items: list[str],
    symbols: list[str] | None = None,
    api_key: str | None = None,
) -> dict[str, float]:
    """批量新聞情緒合併。"""
    from cfpai.llm.sentiment import batch_sentiment
    symbols = symbols or []
    return batch_sentiment(news_items, symbols, api_key=api_key)
