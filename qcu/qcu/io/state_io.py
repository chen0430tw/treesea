# state_io.py
"""
QCU 密度矩阵状态 I/O（本地调试用）。

save_density_matrix()  — ndarray → .npy 文件
load_density_matrix()  — .npy 文件 → ndarray

注意：密度矩阵不进入 Bundle 契约，仅用于本地存档和调试。
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np


def save_density_matrix(
    rho: np.ndarray,
    path: Union[str, Path],
    *,
    exist_ok: bool = True,
) -> Path:
    """将密度矩阵保存为 .npy 文件。"""
    p = Path(path)
    if not exist_ok and p.exists():
        raise FileExistsError(f"文件已存在：{p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(p), rho)
    return p


def load_density_matrix(path: Union[str, Path]) -> np.ndarray:
    """从 .npy 文件加载密度矩阵。"""
    return np.load(str(path))
