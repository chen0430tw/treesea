from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from .router import classify_intent
from .memory import AgentMemory
from .tools.planning_tool import run_planning
from .tools.backtest_tool import run_backtest
from .tools.tuning_tool import run_tuning
from .tools.diagnostics_tool import explain_latest_run
from .tools.reporting_tool import build_report

@dataclass
class AgentResponse:
    intent: str
    result: dict[str, Any]

class CFPAIAgent:
    def __init__(self) -> None:
        self.memory = AgentMemory()

    def handle(self, text: str, **kwargs) -> AgentResponse:
        intent = classify_intent(text)

        if intent == "planning":
            result = run_planning(**kwargs)
            self.memory.update(
                last_symbols=result.get("symbols", []),
                last_start=result.get("start"),
                last_end=result.get("end"),
                last_run_dir=result.get("run_dir"),
            )
            return AgentResponse(intent=intent, result=result)

        if intent == "backtest":
            result = run_backtest(**kwargs)
            self.memory.update(
                last_symbols=result.get("symbols", []),
                last_start=result.get("start"),
                last_end=result.get("end"),
                last_run_dir=result.get("run_dir"),
            )
            return AgentResponse(intent=intent, result=result)

        if intent == "tuning":
            result = run_tuning(**kwargs)
            self.memory.update(
                last_symbols=result.get("symbols", []),
                last_start=result.get("start"),
                last_end=result.get("end"),
                last_run_dir=result.get("run_dir"),
                last_best_params=result.get("best_params", {}),
            )
            return AgentResponse(intent=intent, result=result)

        if intent == "diagnostics":
            run_dir = kwargs.get("run_dir") or self.memory.last_run_dir or "runs/latest"
            return AgentResponse(intent=intent, result=explain_latest_run(run_dir))

        run_dir = kwargs.get("run_dir") or self.memory.last_run_dir or "runs/latest"
        return AgentResponse(intent=intent, result={"report": build_report(run_dir)})
