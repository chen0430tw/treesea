from __future__ import annotations

# 默认多资产宇宙：美股 ETF 覆盖股票/债券/黄金/行业
DEFAULT_UNIVERSE = ["SPY.US", "QQQ.US", "TLT.US", "GLD.US", "XLF.US", "XLK.US", "XLE.US"]

# 扩展宇宙模板
UNIVERSE_TEMPLATES: dict[str, list[str]] = {
    "us_core": ["SPY.US", "QQQ.US", "TLT.US", "GLD.US"],
    "us_sector": ["XLF.US", "XLK.US", "XLE.US", "XLV.US", "XLI.US", "XLY.US"],
    "us_full": DEFAULT_UNIVERSE,
    "global_macro": ["SPY.US", "EFA.US", "EEM.US", "TLT.US", "GLD.US", "DBC.US"],
    "crypto": ["BTC.V", "ETH.V"],
}


def build_default_universe() -> list[str]:
    """返回默认多资产宇宙。"""
    return DEFAULT_UNIVERSE.copy()


def build_universe(template: str = "us_full") -> list[str]:
    """根据模板名构建资产宇宙。"""
    return UNIVERSE_TEMPLATES.get(template, DEFAULT_UNIVERSE).copy()


def build_custom_universe(symbols: list[str]) -> list[str]:
    """验证并返回自定义资产列表。"""
    if not symbols:
        return build_default_universe()
    return [s.upper() for s in symbols]
