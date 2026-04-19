"""
CFPAI Agent Orchestrator v2 — 接 Claude API 的自然語言交互。

升級點：
1. router 從關鍵字匹配升級為 LLM 意圖分類
2. 新增 sentiment 工具（新聞情緒分析）
3. 新增 explain 工具（策略解釋生成）
4. orchestrator 使用 Claude API 做多步推理
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]

from agent.router import classify_intent
from agent.memory import AgentMemory
from agent.tools.planning_tool import run_planning
from agent.tools.backtest_tool import run_backtest
from agent.tools.tuning_tool import run_tuning
from agent.tools.diagnostics_tool import explain_latest_run
from agent.tools.reporting_tool import build_report


AGENT_SYSTEM_PROMPT = """\
You are the CFPAI Agent — a financial planning assistant powered by the CFPAI system.

You can:
1. **plan** — Run portfolio planning (asset weights, risk signals, paths)
2. **backtest** — Run historical backtests with performance stats
3. **tune** — Run UTM parameter optimization
4. **diagnose** — Explain why the portfolio is positioned this way
5. **report** — Generate formatted reports
6. **sentiment** — Analyze news for market sentiment
7. **explain** — Generate natural language explanations of decisions

When the user asks a question, determine which tool(s) to use and extract parameters.

Output JSON:
{
  "intent": "plan|backtest|tune|diagnose|report|sentiment|explain",
  "params": {extracted parameters},
  "explanation": "brief plan of what you'll do"
}
"""


# Claude API tool definitions for function calling
CFPAI_TOOLS = [
    {
        "name": "run_planning",
        "description": "Run CFPAI portfolio planning. Returns asset weights, risk signals, and paths.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {"type": "array", "items": {"type": "string"}, "description": "Asset symbols (e.g. ['NVDA', 'AMD', 'QQQ'])"},
                "start": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "end": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            },
        },
    },
    {
        "name": "run_backtest",
        "description": "Run historical backtest with performance metrics (Sharpe, MaxDD, returns).",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {"type": "array", "items": {"type": "string"}},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "use_utm": {"type": "boolean", "description": "Use UTM-optimized params"},
            },
        },
    },
    {
        "name": "run_tuning",
        "description": "Run UTM parameter optimization (evolutionary search).",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {"type": "array", "items": {"type": "string"}},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "generations": {"type": "integer", "description": "Search generations (default 6)"},
                "population": {"type": "integer", "description": "Population size (default 12)"},
            },
        },
    },
    {
        "name": "analyze_sentiment",
        "description": "Analyze financial news text for sentiment scores per asset.",
        "input_schema": {
            "type": "object",
            "properties": {
                "news_text": {"type": "string", "description": "Financial news text to analyze"},
                "symbols": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["news_text", "symbols"],
        },
    },
    {
        "name": "explain_decision",
        "description": "Generate natural language explanation of CFPAI planning decisions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "run_dir": {"type": "string", "description": "Path to run results directory"},
            },
        },
    },
]


@dataclass
class AgentResponse:
    intent: str
    result: dict[str, Any]
    explanation: str = ""


class CFPAIAgentV2:
    """v2 Agent: 支持 LLM 意圖分類和策略解釋。"""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514") -> None:
        self.memory = AgentMemory()
        self.api_key = api_key
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if anthropic is None:
                raise ImportError("pip install anthropic")
            self._client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else anthropic.Anthropic()
        return self._client

    def handle(self, text: str, **kwargs) -> AgentResponse:
        """處理用戶自然語言請求。

        優先使用 LLM 分類，fallback 到關鍵字匹配。
        """
        try:
            intent, params, explanation = self._llm_classify(text)
        except Exception:
            intent = classify_intent(text)
            params = {}
            explanation = ""

        # 合併 kwargs 和 LLM 提取的參數
        merged = {**params, **kwargs}

        if intent == "planning" or intent == "plan":
            result = run_planning(**{k: v for k, v in merged.items() if k in ("symbols", "start", "end", "mode", "config")})
            self._update_memory(result)
            return AgentResponse(intent="planning", result=result, explanation=explanation)

        if intent == "backtest":
            result = run_backtest(**{k: v for k, v in merged.items() if k in ("symbols", "start", "end", "use_utm", "config")})
            self._update_memory(result)
            return AgentResponse(intent="backtest", result=result, explanation=explanation)

        if intent == "tuning" or intent == "tune":
            result = run_tuning(**{k: v for k, v in merged.items() if k in ("symbols", "start", "end", "generations", "population", "elite_k", "seed")})
            self._update_memory(result)
            return AgentResponse(intent="tuning", result=result, explanation=explanation)

        if intent == "sentiment":
            from cfpai.llm.sentiment import analyze_sentiment
            news = merged.get("news_text", text)
            syms = merged.get("symbols") or self.memory.last_symbols or []
            result = analyze_sentiment(news, syms, api_key=self.api_key)
            return AgentResponse(intent="sentiment", result=result, explanation=explanation)

        if intent == "explain":
            from cfpai.llm.explainer import explain_planning
            run_dir = merged.get("run_dir") or self.memory.last_run_dir or "runs/latest"
            diag = explain_latest_run(run_dir)
            explanation_text = explain_planning(
                diag.get("planning", {}),
                diag.get("stats", {}),
                diag.get("weights", {}),
                diag.get("anchors", []),
                api_key=self.api_key,
            )
            return AgentResponse(intent="explain", result={"explanation": explanation_text}, explanation=explanation)

        if intent == "diagnostics" or intent == "diagnose":
            run_dir = merged.get("run_dir") or self.memory.last_run_dir or "runs/latest"
            return AgentResponse(intent="diagnostics", result=explain_latest_run(run_dir), explanation=explanation)

        # reporting fallback
        run_dir = merged.get("run_dir") or self.memory.last_run_dir or "runs/latest"
        return AgentResponse(intent="reporting", result={"report": build_report(run_dir)}, explanation=explanation)

    def chat(self, text: str, **kwargs) -> str:
        """對話模式：返回人話回覆而非結構化結果。"""
        resp = self.handle(text, **kwargs)
        try:
            summary = json.dumps(resp.result, indent=2, ensure_ascii=False, default=str)
            reply = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system="You are the CFPAI financial planning assistant. Summarize results concisely in Chinese (繁體中文). Use markdown.",
                messages=[{
                    "role": "user",
                    "content": f"用戶問：{text}\n\n系統返回：\n```json\n{summary[:3000]}\n```\n\n請用白話文回覆用戶。",
                }],
            )
            return reply.content[0].text
        except Exception:
            return json.dumps(resp.result, indent=2, ensure_ascii=False, default=str)

    def _llm_classify(self, text: str) -> tuple[str, dict, str]:
        """用 Claude API 分類意圖並提取參數。"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            system=AGENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )

        raw = response.content[0].text.strip()
        if "```" in raw:
            lines = raw.split("```")
            for block in lines:
                block = block.strip()
                if block.startswith("json"):
                    block = block[4:].strip()
                try:
                    parsed = json.loads(block)
                    return parsed["intent"], parsed.get("params", {}), parsed.get("explanation", "")
                except (json.JSONDecodeError, KeyError):
                    continue

        parsed = json.loads(raw)
        return parsed["intent"], parsed.get("params", {}), parsed.get("explanation", "")

    def _update_memory(self, result: dict) -> None:
        self.memory.update(
            last_symbols=result.get("symbols", []),
            last_start=result.get("start"),
            last_end=result.get("end"),
            last_run_dir=result.get("run_dir"),
        )
        if "best_params" in result:
            self.memory.update(last_best_params=result["best_params"])
