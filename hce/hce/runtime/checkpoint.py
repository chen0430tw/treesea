# checkpoint.py
"""
HCE 检查点管理。

在流水线各阶段之间保存和恢复中间产物，
支持故障恢复和断点续跑。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class CheckpointManager:
    """检查点管理器。

    Parameters
    ----------
    checkpoint_dir : str
        检查点文件保存目录
    """

    def __init__(self, checkpoint_dir: str = "checkpoints/hce") -> None:
        self.checkpoint_dir = Path(checkpoint_dir)

    def save(self, request_id: str, data: dict) -> Path:
        """保存检查点。

        Parameters
        ----------
        request_id : str
        data : dict
            要保存的中间产物

        Returns
        -------
        Path
            检查点文件路径
        """
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.checkpoint_dir / f"ckpt_{request_id}.json"

        # 过滤掉 None 值
        clean_data = {k: v for k, v in data.items() if v is not None}

        filepath.write_text(
            json.dumps(clean_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return filepath

    def try_restore(self, request_id: str) -> Optional[dict]:
        """尝试从检查点恢复。

        Parameters
        ----------
        request_id : str

        Returns
        -------
        dict or None
            恢复的数据，如果没有检查点则返回 None
        """
        filepath = self.checkpoint_dir / f"ckpt_{request_id}.json"
        if not filepath.exists():
            return None

        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def delete(self, request_id: str) -> bool:
        """删除检查点。"""
        filepath = self.checkpoint_dir / f"ckpt_{request_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def list_checkpoints(self) -> list[str]:
        """列出所有检查点的 request_id。"""
        if not self.checkpoint_dir.exists():
            return []
        return [
            p.stem.replace("ckpt_", "")
            for p in self.checkpoint_dir.glob("ckpt_*.json")
        ]
