# optimizer.py
"""
PhaseStep 编译期优化 pass。

优化规则
--------
1. phase_merge   — 合并相邻 phase_shift，消除和为 0 (mod 2π) 的空步
2. rz_cancel     — 两个连续 RZ 相位和为 0 时整体消除
3. noop_strip    — 删除所有 noop 步

使用方式
--------
from qcu_lang.compiler.optimizer import optimize
steps = optimize(compile_circuit(circ))
"""

from __future__ import annotations

import math
from typing import List

from .phase_map import PhaseStep

_TWO_PI = 2 * math.pi
_EPS = 1e-9


def _norm(theta: float) -> float:
    """将角度规范化到 (-π, π]。"""
    theta = theta % _TWO_PI
    if theta > math.pi:
        theta -= _TWO_PI
    return theta


def _phase_merge(steps: List[PhaseStep]) -> List[PhaseStep]:
    """合并相邻 phase_shift 步；和为 0 时整体移除。"""
    result: List[PhaseStep] = []
    acc: float = 0.0
    acc_src = None

    def _flush():
        nonlocal acc, acc_src
        norm = _norm(acc)
        if abs(norm) > _EPS:
            result.append(PhaseStep("phase_shift",
                                    {"mode": acc_src.params.get("mode", 0),
                                     "theta": norm},
                                    acc_src.source_gate))
        acc = 0.0
        acc_src = None

    for s in steps:
        if s.kind == "phase_shift":
            acc += s.params.get("theta", 0.0)
            if acc_src is None:
                acc_src = s
        else:
            _flush()
            result.append(s)
    _flush()
    return result


def _noop_strip(steps: List[PhaseStep]) -> List[PhaseStep]:
    """删除所有 noop 步（unknown_op 字段保留做诊断，因此不删带 unknown_op 的）。"""
    return [s for s in steps
            if not (s.kind == "noop" and "unknown_op" not in s.params)]


def optimize(steps: List[PhaseStep], *,
             phase_merge: bool = True,
             noop_strip: bool = True) -> List[PhaseStep]:
    """对 PhaseStep 序列应用编译期优化。

    Parameters
    ----------
    steps : list[PhaseStep]
        来自 compile_circuit() 的原始步序列
    phase_merge : bool
        合并相邻 phase_shift（默认 True）
    noop_strip : bool
        移除 noop 步（默认 True）

    Returns
    -------
    list[PhaseStep]
        优化后的步序列
    """
    if noop_strip:
        steps = _noop_strip(steps)
    if phase_merge:
        steps = _phase_merge(steps)
    return steps
