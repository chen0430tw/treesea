"""MOROZ Contracts 类型定义 — 从 core.types 统一导入。

历史：原先 contracts 和 core 各自定义了一套 LayerName / FrontierCandidate / CollapseCandidate，
导致两套类型不互通。现在统一为 core.types 作为唯一类型源，contracts 重导出。
"""
from moroz.core.types import (  # noqa: F401 — re-export
    LayerName,
    FrontierCandidate,
    CollapseCandidate,
)
