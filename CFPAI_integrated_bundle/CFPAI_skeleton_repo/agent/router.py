from __future__ import annotations

def classify_intent(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["调参", "utm", "tuning", "generations", "population", "elite"]):
        return "tuning"
    if any(k in t for k in ["回测", "backtest", "历史表现", "绩效", "过去"]):
        return "backtest"
    if any(k in t for k in ["解释", "为什么", "锚点", "路径", "diagnostic", "诊断"]):
        return "diagnostics"
    if any(k in t for k in ["报告", "report", "整理", "总结"]):
        return "reporting"
    return "planning"
