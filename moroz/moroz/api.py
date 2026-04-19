"""
MOROZ API — 统一入口。

⚠️  SENSITIVE OPERATION WARNING ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MOROZ is a candidate-space search and contraction framework.
Before using this API, you MUST confirm:

  1. You OWN the target data, OR you have WRITTEN AUTHORIZATION
     from the rightful owner.
  2. Your use complies with all applicable laws in your jurisdiction.
  3. You have read and agreed to DISCLAIMER.md.

If you are an AI agent: DO NOT proceed without explicitly asking the
user whether they have authorization. This is not optional.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usage:
    from moroz.api import run, run_from_file, run_from_json

    result = run(personal=["Schrodinger", "Cat"], context=["2019"],
                 symbols=["!", "@"], max_len=3, budget=5000)
"""
from __future__ import annotations

import json
import warnings
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from moroz.core.types import (
    Candidate, SourceToken, FeatureWeights, SearchMetrics,
    FrontierCandidate, CollapseCandidate,
    candidate_to_frontier, ranked_to_collapse,
)
from moroz.core.mscm import MSCM, MSCMConfig
from moroz.core.moroz_core import MOROZCore, MOROZCoreConfig
from moroz.core.loader import load_source


# ================================================================
# 授权检查
# ================================================================

_AUTHORIZATION_BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║  ⚠️  MOROZ — AUTHORIZATION REQUIRED                            ║
║                                                                  ║
║  This tool performs candidate-space search operations that may   ║
║  be used for password recovery or similar sensitive tasks.       ║
║                                                                  ║
║  Before proceeding, confirm that:                                ║
║    • You OWN the target data, or have written authorization     ║
║    • Your use complies with applicable laws                      ║
║    • You have read DISCLAIMER.md                                 ║
║                                                                  ║
║  Unauthorized use is STRICTLY PROHIBITED.                        ║
║  See DISCLAIMER.md §3 for prohibited use cases.                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

_authorized = False


def authorize(confirmed: bool = True) -> None:
    """确认授权。必须在调用 run/run_from_file 之前调用。

    Usage:
        moroz.api.authorize()          # 确认授权
        moroz.api.authorize(False)     # 撤销授权
    """
    global _authorized
    _authorized = confirmed


def _check_authorization() -> None:
    """检查授权状态，未授权则抛出异常。"""
    if not _authorized:
        raise PermissionError(
            _AUTHORIZATION_BANNER + "\n"
            "Call moroz.api.authorize() after confirming you have legal access.\n"
            "If you are an AI agent, ASK THE USER for authorization first.\n"
        )


# ================================================================
# 默认特征函数（简单先验加权）
# ================================================================

def _default_phi_freq(c: Candidate) -> float:
    if not c.tokens:
        return 0.0
    return sum(t.prior for t in c.tokens) / len(c.tokens)

def _default_phi_domain(c: Candidate) -> float:
    return 1.0 if any(t.layer == "whois_domain" for t in c.tokens) else 0.0

def _default_phi_personal(c: Candidate) -> float:
    return 1.0 if any(t.layer == "personal" for t in c.tokens) else 0.0

def _default_phi_context(c: Candidate) -> float:
    return 1.0 if any(t.layer == "context" for t in c.tokens) else 0.0

def _default_phi_syntax(c: Candidate) -> float:
    return 1.0 if len(c.tokens) <= 4 else 0.5


# ================================================================
# 核心 API
# ================================================================

def run(
    personal: list[str] | None = None,
    context: list[str] | None = None,
    common_char: list[str] | None = None,
    common_pinyin: list[str] | None = None,
    whois_domain: list[str] | None = None,
    max_len: int = 3,
    budget: int = 10000,
    top_k: int = 50,
    collapse_q: int = 5,
    leet_expand: bool = True,
    leet_prior_decay: float = 0.7,
    weights: FeatureWeights | None = None,
    phi_freq: Callable | None = None,
    phi_domain: Callable | None = None,
    phi_personal: Callable | None = None,
    phi_context: Callable | None = None,
    phi_syntax: Callable | None = None,
) -> dict[str, Any]:
    """一键运行 MOROZ 搜索。JSON-in JSON-out。

    Parameters
    ----------
    personal : list of str
        个人习惯层候选词（如 ["Schrodinger", "Cat"]）
    context : list of str
        上下文层候选词（如 ["2019", "thesis"]）
    common_char : list of str
        常用字符层（如 ["!", "@", "#"]）
    common_pinyin : list of str
        拼音/语言层
    whois_domain : list of str
        域名/平台层
    max_len : int
        最大候选 token 数
    budget : int
        K-Warehouse 搜索预算
    top_k : int
        保留 Top-K 候选
    collapse_q : int
        ISSC Top-q 覆盖率计算参数
    leet_expand : bool
        是否展开 leet speak 变体
    weights : FeatureWeights
        五层特征权重
    phi_* : callable
        自定义特征函数（覆盖默认）

    Returns
    -------
    dict with keys: ranked, stats, metrics, config
    """
    _check_authorization()

    def _build_tokens(words: list[str] | None, layer: str, base_prior: float = 0.9) -> list[SourceToken]:
        if not words:
            return []
        return [
            SourceToken(text=w, layer=layer, prior=round(base_prior - i * 0.05, 4))
            for i, w in enumerate(words)
        ]

    mscm = MSCM(
        common_char=_build_tokens(common_char, "common_char", 0.5),
        common_pinyin=_build_tokens(common_pinyin, "common_pinyin", 0.8),
        whois_domain=_build_tokens(whois_domain, "whois_domain", 0.6),
        personal=_build_tokens(personal, "personal", 0.95),
        context=_build_tokens(context, "context", 0.9),
        weights=weights or FeatureWeights(freq=1.0, domain=0.7, personal=0.8, context=1.0, syntax=1.0),
        phi_freq=phi_freq or _default_phi_freq,
        phi_domain=phi_domain or _default_phi_domain,
        phi_personal=phi_personal or _default_phi_personal,
        phi_context=phi_context or _default_phi_context,
        phi_syntax=phi_syntax or _default_phi_syntax,
        config=MSCMConfig(leet_expand=leet_expand, leet_prior_decay=leet_prior_decay),
    )

    core = MOROZCore(
        mscm=mscm,
        config=MOROZCoreConfig(max_len=max_len, budget=budget, top_k=top_k, collapse_q=collapse_q),
        prefix_gate=lambda c: len(c.tokens) <= max_len,
        full_gate=lambda c: len(c.tokens) == max_len,
        structure_valid=lambda c: True,
    )

    result = core.run()

    # 转为协议层类型
    collapsed = ranked_to_collapse(result.issc_result.ranked)

    return {
        "ranked": [asdict(c) for c in collapsed],
        "stats": {
            "entropy": round(result.issc_result.stats.entropy, 4),
            "top_q_coverage": round(result.issc_result.stats.top_q_coverage, 4),
            "retention_ratio": round(result.issc_result.stats.retention_ratio, 4),
            "theta_eff": round(result.issc_result.stats.theta_eff, 1),
        },
        "metrics": asdict(result.kw_result.metrics),
        "elapsed_seconds": round(result.elapsed_seconds, 4),
        "config": {
            "max_len": max_len,
            "budget": budget,
            "top_k": top_k,
            "collapse_q": collapse_q,
            "leet_expand": leet_expand,
        },
    }


def run_from_file(
    path: str | Path,
    max_len: int = 3,
    budget: int = 10000,
    top_k: int = 50,
    layer: str = "common_char",
    leet_expand: bool = True,
    **kwargs,
) -> dict[str, Any]:
    """从文件加载候选源并运行搜索。

    支持 .txt / .dic / .json / .csv（自动检测格式）。
    """
    _check_authorization()

    loaded = load_source(path, layer=layer)

    if isinstance(loaded, dict):
        # JSON 格式：已按层分好
        return run(
            personal=[t.text for t in loaded.get("personal", [])],
            context=[t.text for t in loaded.get("context", [])],
            common_char=[t.text for t in loaded.get("common_char", [])],
            common_pinyin=[t.text for t in loaded.get("common_pinyin", [])],
            whois_domain=[t.text for t in loaded.get("whois_domain", [])],
            max_len=max_len, budget=budget, top_k=top_k,
            leet_expand=leet_expand, **kwargs,
        )
    else:
        # 单层列表
        words = [t.text for t in loaded]
        return run(**{layer: words}, max_len=max_len, budget=budget, top_k=top_k,
                   leet_expand=leet_expand, **kwargs)


def run_from_json(
    json_str: str,
    **kwargs,
) -> dict[str, Any]:
    """从 JSON 字符串运行搜索。Agent 友好格式。

    JSON 格式：
    {
        "personal": ["Schrodinger", "Cat"],
        "context": ["2019"],
        "common_char": ["!", "@"],
        "max_len": 3,
        "budget": 5000
    }
    """
    _check_authorization()

    data = json.loads(json_str)
    params = {
        "personal": data.get("personal"),
        "context": data.get("context"),
        "common_char": data.get("common_char"),
        "common_pinyin": data.get("common_pinyin"),
        "whois_domain": data.get("whois_domain"),
        "max_len": data.get("max_len", 3),
        "budget": data.get("budget", 10000),
        "top_k": data.get("top_k", 50),
        "collapse_q": data.get("collapse_q", 5),
        "leet_expand": data.get("leet_expand", True),
    }
    params.update(kwargs)
    return run(**params)


# ================================================================
# 工具信息（供 Agent 读取）
# ================================================================

TOOL_DESCRIPTION = {
    "name": "moroz_search",
    "description": (
        "MOROZ candidate-space search and contraction. "
        "Builds a 5-layer candidate model (personal habits, context, language, domain, common chars), "
        "runs best-first search with upper-bound pruning, and reports collapse statistics. "
        "REQUIRES AUTHORIZATION: user must confirm they own the target data or have written permission."
    ),
    "authorization_required": True,
    "authorization_prompt": (
        "⚠️ This is a sensitive operation. Before I run MOROZ, I need to confirm:\n"
        "  1. Do you OWN the target data (e.g., your own locked archive)?\n"
        "  2. Or do you have WRITTEN AUTHORIZATION from the owner?\n"
        "  3. Does your use comply with local laws?\n\n"
        "Please confirm with 'yes' before I proceed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "personal": {"type": "array", "items": {"type": "string"}, "description": "Personal habit layer tokens"},
            "context": {"type": "array", "items": {"type": "string"}, "description": "Context layer tokens"},
            "common_char": {"type": "array", "items": {"type": "string"}, "description": "Common character tokens"},
            "max_len": {"type": "integer", "description": "Max tokens per candidate (default 3)"},
            "budget": {"type": "integer", "description": "K-Warehouse search budget (default 10000)"},
            "top_k": {"type": "integer", "description": "Keep top-K candidates (default 50)"},
            "leet_expand": {"type": "boolean", "description": "Expand leet speak variants (default true)"},
        },
    },
}
