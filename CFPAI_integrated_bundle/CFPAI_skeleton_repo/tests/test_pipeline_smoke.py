"""CFPAI pipeline smoke tests."""
import pytest


def test_smoke_params():
    from cfpai.contracts.params import CFPAIParams
    p = CFPAIParams()
    assert p.max_assets >= 1
    assert 0.0 <= p.cash_floor <= 1.0
    assert p.lambda_risk > 0


def test_smoke_state_types():
    from cfpai.contracts.state_types import MarketState
    s = MarketState(timestamp="2026-01-01")
    assert s.timestamp == "2026-01-01"
    d = s.to_dict()
    assert "flow_state" in d


def test_smoke_universe():
    from cfpai.data.universe_builder import build_default_universe, build_universe
    u = build_default_universe()
    assert len(u) >= 4
    assert "SPY.US" in u
    macro = build_universe("global_macro")
    assert "EFA.US" in macro


def test_smoke_scoring():
    from cfpai.chain_search.scoring import persistence_adjusted_score
    s = persistence_adjusted_score(0.5, "SPY", "SPY", 0.1)
    assert s == pytest.approx(0.6)
    s2 = persistence_adjusted_score(0.5, "SPY", "QQQ", 0.1)
    assert s2 == pytest.approx(0.5)


def test_smoke_risk_budget():
    from cfpai.planner.risk_budget import compute_budget_from_weights, compute_hhi
    b = compute_budget_from_weights({"SPY": 0.6, "QQQ": 0.3})
    assert b == pytest.approx(0.4)
    hhi = compute_hhi({"SPY": 0.6, "QQQ": 0.4})
    assert 0 < hhi < 1


def test_smoke_allocator():
    from cfpai.contracts.params import CFPAIParams
    from cfpai.planner.allocator import allocate_from_scores
    p = CFPAIParams(max_assets=2, cash_floor=0.1)
    w = allocate_from_scores({"SPY": 0.8, "QQQ": 0.6, "TLT": 0.3}, p)
    assert len(w) == 2
    assert sum(w.values()) <= 1.0


def test_smoke_node_utility():
    from cfpai.tree_diagram.node_utility import compute_node_utility, compute_grid_entropy
    u = compute_node_utility(0.8, 0.3, lambda_risk=0.5)
    assert u == pytest.approx(0.65)
    e = compute_grid_entropy({"SPY": 0.5, "QQQ": 0.5})
    assert e > 0


def test_smoke_propagation():
    import pandas as pd
    from cfpai.tree_diagram.propagation import apply_identity_like_propagation
    df = pd.DataFrame({"Date": ["2026-01-01"], "SPY": [0.6], "QQQ": [0.4]})
    result = apply_identity_like_propagation(df)
    assert len(result) == 1
    assert result.at[0, "SPY"] == 0.6


def test_smoke_router():
    from agent.router import classify_intent
    assert classify_intent("帮我回测") == "backtest"
    assert classify_intent("用UTM调参") == "tuning"
    assert classify_intent("现在跑一次planning") == "planning"
