# writeback.py
"""
QCU 结果序列化层。

包含：
- result_to_dict()：IQPURunResult → dict
- write_result()：写入 JSON 文件
- load_result()：从 JSON 文件读取并还原为 IQPURunResult
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

import numpy as np

from .state_repr import IQPURunResult


def result_to_dict(result: IQPURunResult) -> dict:
    """将 IQPURunResult 序列化为 JSON 兼容 dict。

    Parameters
    ----------
    result : IQPURunResult

    Returns
    -------
    dict
        所有 ndarray 转为 list，Optional 字段为 None 时保留 null。
    """
    def _arr(a):
        return a.tolist() if a is not None else None

    return {
        "label": result.label,
        "DIM": result.DIM,
        "elapsed_sec": result.elapsed_sec,
        "ts": _arr(result.ts),
        "rel_phase": _arr(result.rel_phase),
        "C_log": _arr(result.C_log),
        "neg_log": _arr(result.neg_log),
        "final_sz": result.final_sz,
        "final_n": result.final_n,
        "final_rel_phase": result.final_rel_phase,
        "C_end": result.C_end,
        "dtheta_end": result.dtheta_end,
        "N_end": result.N_end,
    }


def write_result(
    result: IQPURunResult,
    path: Union[str, Path],
    *,
    indent: int = 2,
    exist_ok: bool = True,
) -> Path:
    """将 IQPURunResult 写入 JSON 文件。

    Parameters
    ----------
    result : IQPURunResult
        运行结果
    path : str or Path
        目标文件路径（自动创建父目录）
    indent : int
        JSON 缩进空格数，默认 2
    exist_ok : bool
        True 时覆盖已有文件，False 时已有文件则抛出 FileExistsError

    Returns
    -------
    Path
        写入的文件路径
    """
    p = Path(path)
    if not exist_ok and p.exists():
        raise FileExistsError(f"文件已存在：{p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    data = result_to_dict(result)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    return p


def load_result(path: Union[str, Path]) -> IQPURunResult:
    """从 JSON 文件读取并还原为 IQPURunResult。

    Parameters
    ----------
    path : str or Path
        JSON 文件路径

    Returns
    -------
    IQPURunResult
    """
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)

    def _ndarray(v, dtype=np.float64):
        return np.array(v, dtype=dtype) if v is not None else None

    return IQPURunResult(
        label=d["label"],
        DIM=d["DIM"],
        elapsed_sec=d["elapsed_sec"],
        ts=_ndarray(d["ts"]),
        rel_phase=_ndarray(d["rel_phase"]),
        C_log=_ndarray(d["C_log"]),
        neg_log=_ndarray(d["neg_log"]),
        final_sz=d["final_sz"],
        final_n=d["final_n"],
        final_rel_phase=d["final_rel_phase"],
        C_end=d["C_end"],
        dtheta_end=d["dtheta_end"],
        N_end=d["N_end"],
    )
