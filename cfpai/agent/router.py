from __future__ import annotations

def classify_intent(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["调参", "utm", "tuning", "generations", "population", "elite"]):
        return "tuning"
    if any(k in t for k in ["回测", "backtest", "历史表现", "绩效", "过去"]):
        return "backtest"
    if any(k in t for k in ["新闻", "情绪", "sentiment", "news", "舆情"]):
        return "sentiment"
    if any(k in t for k in ["解释策略", "explain", "说明决策", "为什么这样配"]):
        return "explain"
    if any(k in t for k in ["解释", "为什么", "锚点", "路径", "diagnostic", "诊断"]):
        return "diagnostics"
    if any(k in t for k in ["报告", "report", "整理", "总结"]):
        return "reporting"
    if any(k in t for k in ["异常", "anomaly", "洗钱", "循环", "杠杆检查"]):
        return "anomaly_detect"
    return "planning"
