# fault_tolerance.py
"""
HCE 容错机制。

提供流水线阶段级别的重试、降级和错误隔离。
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class StageError:
    """阶段错误记录。"""
    stage_name: str
    error_type: str
    error_message: str
    timestamp: float
    attempt: int
    traceback: str = ""

    def to_dict(self) -> dict:
        return {
            "stage_name": self.stage_name,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
            "attempt": self.attempt,
            "traceback": self.traceback,
        }


@dataclass
class FaultToleranceConfig:
    """容错配置。"""
    max_retries: int = 3
    retry_delay_sec: float = 1.0
    allow_partial_results: bool = True   # 允许部分阶段失败时仍产出结果
    skip_failed_stages: bool = False     # 跳过失败的阶段继续后续

    @classmethod
    def from_dict(cls, d: dict) -> "FaultToleranceConfig":
        return cls(
            max_retries=d.get("max_retries", 3),
            retry_delay_sec=d.get("retry_delay_sec", 1.0),
            allow_partial_results=d.get("allow_partial_results", True),
            skip_failed_stages=d.get("skip_failed_stages", False),
        )


class FaultToleranceHandler:
    """容错处理器。

    Parameters
    ----------
    config : FaultToleranceConfig
    """

    def __init__(self, config: Optional[FaultToleranceConfig] = None) -> None:
        self.config = config or FaultToleranceConfig()
        self.errors: List[StageError] = []

    def execute_with_retry(
        self,
        stage_name: str,
        func: Callable[[], Any],
        fallback: Optional[Callable[[], Any]] = None,
    ) -> Any:
        """带重试地执行阶段。

        Parameters
        ----------
        stage_name : str
        func : callable
            要执行的函数
        fallback : callable, optional
            所有重试失败后的降级回调

        Returns
        -------
        Any
            执行结果

        Raises
        ------
        RuntimeError
            当所有重试和降级都失败时
        """
        last_error = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                return func()
            except Exception as e:
                error = StageError(
                    stage_name=stage_name,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    timestamp=time.time(),
                    attempt=attempt,
                    traceback=traceback.format_exc(),
                )
                self.errors.append(error)
                last_error = e

                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay_sec)

        # 所有重试失败
        if fallback is not None:
            try:
                return fallback()
            except Exception as e:
                self.errors.append(StageError(
                    stage_name=f"{stage_name}_fallback",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    timestamp=time.time(),
                    attempt=0,
                ))

        if self.config.skip_failed_stages:
            return None

        raise RuntimeError(
            f"Stage {stage_name} failed after {self.config.max_retries} retries: {last_error}"
        )

    def get_error_summary(self) -> dict:
        """返回错误摘要。"""
        return {
            "total_errors": len(self.errors),
            "errors": [e.to_dict() for e in self.errors],
            "failed_stages": list(set(e.stage_name for e in self.errors)),
        }
