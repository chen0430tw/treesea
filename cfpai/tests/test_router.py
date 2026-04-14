from agent.router import classify_intent

def test_router_labels():
    assert classify_intent("现在跑一次 planning") == "planning"
    assert classify_intent("帮我回测过去十年") == "backtest"
    assert classify_intent("再用UTM调参") == "tuning"
