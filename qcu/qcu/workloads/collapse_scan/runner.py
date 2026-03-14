# runner.py
"""
QCU collapse_scan workload。

提供 QCL v6 协议参数扫描功能：
- sweep_boost_duration()：单轴扫描 boost_duration
- sweep_grid()：多维网格扫描，返回 CollapseRow 列表
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

from ...core.state_repr import IQPUConfig
from ...core.iqpu_runtime import IQPU


@dataclass
class CollapseParam:
    """单次扫描点的协议参数。

    所有字段与 IQPU.run_qcl_v6() 参数一一对应；
    label 可选，默认由参数值自动生成。
    """
    t1: float = 3.0
    t2: float = 5.0
    omega_x: float = 1.0
    gamma_pcm: float = 0.2
    gamma_qim: float = 0.03
    gamma_boost: float = 0.9
    boost_duration: float = 3.0
    gamma_reset: float = 0.25
    gamma_phi0: float = 0.6
    eps_boost: float = 4.0
    boost_phase_trim: float = 0.012
    label: Optional[str] = None

    def auto_label(self) -> str:
        return (
            f"bd={self.boost_duration:.2f}"
            f"_eps={self.eps_boost:.1f}"
            f"_gpcm={self.gamma_pcm:.2f}"
        )


@dataclass
class CollapseRow:
    """单次扫描点的结果。"""
    param: CollapseParam
    C_end: float
    dtheta_end: float
    N_end: Optional[float]
    elapsed_sec: float
    extra: Dict[str, Any] = field(default_factory=dict)


def sweep_boost_duration(
    iqpu: IQPU,
    base_param: CollapseParam,
    durations: Iterable[float],
) -> List[CollapseRow]:
    """扫描 boost_duration，其余参数固定。

    Parameters
    ----------
    iqpu : IQPU
        已初始化的虚拟量子芯片
    base_param : CollapseParam
        基础参数（boost_duration 字段会被逐步替换）
    durations : iterable of float
        待扫描的 boost_duration 值序列

    Returns
    -------
    list of CollapseRow
    """
    rows: List[CollapseRow] = []
    for bd in durations:
        p = CollapseParam(
            t1=base_param.t1,
            t2=base_param.t2,
            omega_x=base_param.omega_x,
            gamma_pcm=base_param.gamma_pcm,
            gamma_qim=base_param.gamma_qim,
            gamma_boost=base_param.gamma_boost,
            boost_duration=bd,
            gamma_reset=base_param.gamma_reset,
            gamma_phi0=base_param.gamma_phi0,
            eps_boost=base_param.eps_boost,
            boost_phase_trim=base_param.boost_phase_trim,
        )
        label = p.label or f"sweep_bd={bd:.3f}"
        res = iqpu.run_qcl_v6(
            label=label,
            t1=p.t1, t2=p.t2,
            omega_x=p.omega_x,
            gamma_pcm=p.gamma_pcm,
            gamma_qim=p.gamma_qim,
            gamma_boost=p.gamma_boost,
            boost_duration=p.boost_duration,
            gamma_reset=p.gamma_reset,
            gamma_phi0=p.gamma_phi0,
            eps_boost=p.eps_boost,
            boost_phase_trim=p.boost_phase_trim,
        )
        rows.append(CollapseRow(
            param=p,
            C_end=res.C_end,
            dtheta_end=res.dtheta_end,
            N_end=res.N_end,
            elapsed_sec=res.elapsed_sec,
        ))
    return rows


def sweep_grid(
    iqpu: IQPU,
    grid: Iterable[CollapseParam],
) -> List[CollapseRow]:
    """任意网格扫描：逐一运行 grid 中每个 CollapseParam。

    Parameters
    ----------
    iqpu : IQPU
        已初始化的虚拟量子芯片
    grid : iterable of CollapseParam
        扫描点列表（可由外部 itertools.product 生成）

    Returns
    -------
    list of CollapseRow
    """
    rows: List[CollapseRow] = []
    for p in grid:
        label = p.label or p.auto_label()
        res = iqpu.run_qcl_v6(
            label=label,
            t1=p.t1, t2=p.t2,
            omega_x=p.omega_x,
            gamma_pcm=p.gamma_pcm,
            gamma_qim=p.gamma_qim,
            gamma_boost=p.gamma_boost,
            boost_duration=p.boost_duration,
            gamma_reset=p.gamma_reset,
            gamma_phi0=p.gamma_phi0,
            eps_boost=p.eps_boost,
            boost_phase_trim=p.boost_phase_trim,
        )
        rows.append(CollapseRow(
            param=p,
            C_end=res.C_end,
            dtheta_end=res.dtheta_end,
            N_end=res.N_end,
            elapsed_sec=res.elapsed_sec,
        ))
    return rows
