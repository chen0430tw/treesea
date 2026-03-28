# qcu/gates/__init__.py
"""
QCU 基础量子 benchmark 门层。

第一层：量子 sanity check
  deutsch      — Deutsch 算法（单比特 oracle 判别）
"""

from .deutsch import (
    DeutschConfig,
    build_constant_oracle,
    build_balanced_oracle,
    run_deutsch,
    benchmark_deutsch,
)

__all__ = [
    "DeutschConfig",
    "build_constant_oracle",
    "build_balanced_oracle",
    "run_deutsch",
    "benchmark_deutsch",
]
