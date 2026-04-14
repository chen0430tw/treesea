from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class AgentMemory:
    last_symbols: list[str] = field(default_factory=list)
    last_start: str | None = None
    last_end: str | None = None
    last_run_dir: str | None = None
    last_best_params: dict[str, Any] = field(default_factory=dict)

    def update(self, **kwargs) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)
