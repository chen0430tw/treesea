"""Phase 2 smoke tests — API layer, UTM diagnostics, plots, LLM stubs, LASA bridge."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


# ================================================================
# UTM Dimension Matrix
# ================================================================

def test_dimension_matrix_basic():
    from cfpai.utm.dimension_matrix import compute_dimension_matrix, PARAM_NAMES
    vecs = np.random.randn(4, len(PARAM_NAMES))
    dm = compute_dimension_matrix(vecs)
    assert "means" in dm
    assert "eigenvalues" in dm
    assert len(dm["eigenvalues"]) == len(PARAM_NAMES)


def test_sensitivity_ranking():
    from cfpai.utm.dimension_matrix import compute_dimension_matrix, sensitivity_ranking, PARAM_NAMES
    vecs = np.random.randn(6, len(PARAM_NAMES))
    dm = compute_dimension_matrix(vecs)
    ranking = sensitivity_ranking(dm)
    assert len(ranking) == len(PARAM_NAMES)
    assert all(0 <= score <= 1.0 for _, score in ranking)


def test_track_contraction():
    from cfpai.utm.dimension_matrix import track_contraction, PARAM_NAMES
    history = []
    for g in range(3):
        vecs = np.random.randn(4, len(PARAM_NAMES)) * (1.0 / (g + 1))
        history.append({"generation": g, "elite_vecs": vecs})
    snapshots = track_contraction(history)
    assert len(snapshots) == 3
    assert snapshots[0].contraction_ratio == 1.0  # 第一代无对比


# ================================================================
# UTM Diagnostics
# ================================================================

def test_diagnose_convergence():
    from cfpai.utm.diagnostics import diagnose_convergence
    df = pd.DataFrame({
        "generation": [0, 1, 2],
        "score": [0.5, 0.8, 0.82],
        "train_sharpe": [1.0, 1.5, 1.6],
        "val_sharpe": [0.8, 1.2, 1.3],
    })
    result = diagnose_convergence(df)
    assert "converged" in result
    assert "overfit_warning" in result
    assert result["generations"] == 3


def test_diagnose_param_stability():
    from cfpai.utm.diagnostics import diagnose_param_stability
    df = pd.DataFrame({
        "w_mom": [0.8, 0.82, 0.81],
        "w_vol": [0.3, 0.9, 0.1],  # 不稳定
    })
    result = diagnose_param_stability(df)
    assert "w_vol" in result["unstable_params"]


# ================================================================
# LASA Bridge
# ================================================================

def test_lasa_to_cfpai_budget():
    from cfpai.lasa_bridge import LASAPortfolioInput, lasa_to_cfpai_budget
    inp = LASAPortfolioInput(
        disposable_cash=100000,
        realized_income=5000,
        free_net_assets=150000,
        restricted_amount=20000,
        risk_reserve=10000,
        pending_amount=3000,
    )
    budget = lasa_to_cfpai_budget(inp)
    assert budget["investable"] == 105000
    assert budget["cash_reserve"] == 30000


def test_cfpai_to_lasa_tags():
    from cfpai.lasa_bridge import cfpai_to_lasa_tags
    weights = {"NVDA": 0.4, "QQQ": 0.3, "TLT": 0.2}
    events = cfpai_to_lasa_tags(weights, total_investment=100000, leverage_ratio=1.0)
    assert len(events) == 3
    assert all(e["accountClass"] == "ASSET" for e in events)


def test_cfpai_to_lasa_tags_with_leverage():
    from cfpai.lasa_bridge import cfpai_to_lasa_tags
    weights = {"NVDA": 0.5, "QQQ": 0.4}
    events = cfpai_to_lasa_tags(weights, total_investment=100000, leverage_ratio=1.5)
    # 有借入部分
    liability_events = [e for e in events if e["accountClass"] == "LIABILITY"]
    assert len(liability_events) > 0


def test_leverage_safety_check():
    from cfpai.lasa_bridge import LASAPortfolioInput, check_leverage_safety
    inp = LASAPortfolioInput(
        disposable_cash=100000,
        realized_income=5000,
        free_net_assets=150000,
        restricted_amount=20000,
        risk_reserve=10000,
        pending_amount=3000,
    )
    result = check_leverage_safety(inp, requested_leverage=1.5, max_leverage=2.0)
    assert result["approved"]
    assert result["actual_leverage"] <= 2.0


def test_leverage_safety_blocked():
    from cfpai.lasa_bridge import LASAPortfolioInput, check_leverage_safety
    inp = LASAPortfolioInput(
        disposable_cash=0,
        realized_income=0,
        free_net_assets=-1000,
        restricted_amount=50000,
        risk_reserve=10000,
        pending_amount=0,
    )
    result = check_leverage_safety(inp, requested_leverage=2.0)
    assert not result["approved"]


# ================================================================
# Anomaly Detection (rule-based, no LLM)
# ================================================================

def test_check_leverage_loop():
    from cfpai.llm.detector import check_leverage_loop
    records = [
        {"accountClass": "ASSET", "riskTags": ["NORMAL"]} for _ in range(5)
    ] + [
        {"accountClass": "LIABILITY", "riskTags": ["HIGH_RISK"]} for _ in range(5)
    ]
    result = check_leverage_loop(records, threshold=0.3)
    assert result["loop_detected"]


def test_check_leverage_loop_safe():
    from cfpai.llm.detector import check_leverage_loop
    records = [
        {"accountClass": "ASSET", "riskTags": ["NORMAL"]} for _ in range(9)
    ] + [
        {"accountClass": "LIABILITY", "riskTags": ["NORMAL"]} for _ in range(1)
    ]
    result = check_leverage_loop(records, threshold=0.3)
    assert not result["loop_detected"]


# ================================================================
# Sentiment scoring adjustment (no LLM)
# ================================================================

def test_sentiment_to_scoring_adjustment():
    from cfpai.llm.sentiment import sentiment_to_scoring_adjustment
    sentiments = {"NVDA": 0.8, "AMD": -0.5, "QQQ": 0.0}
    adj = sentiment_to_scoring_adjustment(sentiments, alpha=0.15)
    assert adj["NVDA"] > 1.0
    assert adj["AMD"] < 1.0
    assert adj["QQQ"] == 1.0


# ================================================================
# Params update
# ================================================================

def test_params_new_fields():
    from cfpai.contracts.params import CFPAIParams
    p = CFPAIParams()
    assert p.allow_short is False
    assert p.max_leverage == 1.0
    assert p.sentiment_alpha == 0.15


# ================================================================
# Router new intents
# ================================================================

def test_router_sentiment():
    from agent.router import classify_intent
    assert classify_intent("分析最新新闻的情绪") == "sentiment"
    assert classify_intent("analyze news sentiment") == "sentiment"


def test_router_explain():
    from agent.router import classify_intent
    assert classify_intent("explain this decision") == "explain"
    assert classify_intent("解释策略配置") == "explain"


def test_router_anomaly():
    from agent.router import classify_intent
    assert classify_intent("检查异常资金") == "anomaly_detect"
