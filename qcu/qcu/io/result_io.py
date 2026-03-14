# result_io.py
"""
QCU 结果 Bundle I/O。

提供 SeaOutputBundle 的 JSON 序列化 / 反序列化：
  write_bundle()  — SeaOutputBundle → JSON 文件
  load_bundle()   — JSON 文件 → SeaOutputBundle
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from .readout_schema import SeaOutputBundle


def write_bundle(
    bundle: SeaOutputBundle,
    path: Union[str, Path],
    *,
    indent: int = 2,
    exist_ok: bool = True,
) -> Path:
    """将 SeaOutputBundle 序列化并写入 JSON 文件。

    Parameters
    ----------
    bundle : SeaOutputBundle
    path : str or Path
        目标文件路径（自动创建父目录）
    indent : int
        JSON 缩进，默认 2
    exist_ok : bool
        False 时文件已存在则抛 FileExistsError

    Returns
    -------
    Path
        写入的文件路径
    """
    p = Path(path)
    if not exist_ok and p.exists():
        raise FileExistsError(f"文件已存在：{p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(bundle.to_dict(), f, indent=indent, ensure_ascii=False)
    return p


def load_bundle(path: Union[str, Path]) -> SeaOutputBundle:
    """从 JSON 文件读取并还原为 SeaOutputBundle。

    Parameters
    ----------
    path : str or Path

    Returns
    -------
    SeaOutputBundle
    """
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    return SeaOutputBundle.from_dict(d)
