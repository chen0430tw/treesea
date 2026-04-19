"""MSCM Source Loader — 从文件加载候选源。

支持格式：
  - .txt   纯文本字典（一行一词，兼容 hashcat/john wordlist）
  - .dic   字典档（密码学风格：一行一词 / hunspell 风格：首行计数 + affix flags）
  - .json  结构化候选源（带层标签和 prior 权重）
  - .csv   批量候选（columns: text, layer, prior）
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Sequence

from .types import SourceToken, LayerName


# ================================================================
# TXT — 一行一词，prior 按行号递减
# ================================================================

def load_txt(
    path: str | Path,
    layer: LayerName = "common_char",
    base_prior: float = 1.0,
    decay: float = 0.999,
    encoding: str = "utf-8",
) -> list[SourceToken]:
    """加载纯文本字典。

    prior = base_prior * decay^line_index
    第 1 行 prior 最高，越往后越低（假设字典已按频率排序）。
    """
    path = Path(path)
    tokens: list[SourceToken] = []
    with open(path, "r", encoding=encoding, errors="replace") as f:
        for i, line in enumerate(f):
            word = line.strip()
            if not word or word.startswith("#"):
                continue
            prior = base_prior * (decay ** i)
            tokens.append(SourceToken(
                text=word,
                layer=layer,
                prior=round(prior, 6),
                meta={"source_file": path.name, "line": i},
            ))
    return tokens


# ================================================================
# DIC — 密码学字典 + hunspell 兼容
# ================================================================

def load_dic(
    path: str | Path,
    layer: LayerName = "common_char",
    base_prior: float = 1.0,
    decay: float = 0.999,
    encoding: str = "utf-8",
    expand_affixes: bool = True,
) -> list[SourceToken]:
    """加载 .dic 字典档。

    自动检测格式：
    - 首行是纯数字 → hunspell 格式（跳过计数行，解析 affix flags）
    - 否则 → 密码学格式（等同 txt，一行一词）

    hunspell affix flags（/S, /ED 等）：
    - expand_affixes=True 时，把 flags 记入 meta 供后续展开
    - 词本身去掉 /FLAGS 部分
    """
    path = Path(path)
    lines: list[str] = []
    with open(path, "r", encoding=encoding, errors="replace") as f:
        lines = f.readlines()

    if not lines:
        return []

    # 检测 hunspell 格式：首行是纯数字
    first = lines[0].strip()
    is_hunspell = first.isdigit()
    start_line = 1 if is_hunspell else 0

    tokens: list[SourceToken] = []
    word_index = 0
    for i in range(start_line, len(lines)):
        raw = lines[i].strip()
        if not raw or raw.startswith("#"):
            continue

        # hunspell: word/FLAGS
        affix_flags = ""
        if is_hunspell and "/" in raw:
            parts = raw.split("/", 1)
            word = parts[0]
            affix_flags = parts[1] if len(parts) > 1 else ""
        else:
            word = raw

        if not word:
            continue

        prior = base_prior * (decay ** word_index)
        meta = {"source_file": path.name, "line": i, "format": "hunspell" if is_hunspell else "cracking"}
        if affix_flags:
            meta["affix_flags"] = affix_flags

        tokens.append(SourceToken(
            text=word,
            layer=layer,
            prior=round(prior, 6),
            meta=meta,
        ))
        word_index += 1

    return tokens


# ================================================================
# JSON — 结构化候选源
# ================================================================

def load_json(
    path: str | Path,
    encoding: str = "utf-8",
) -> dict[LayerName, list[SourceToken]]:
    """加载 JSON 结构化候选源。

    格式：
    {
      "personal": [
        {"text": "Schrodinger", "prior": 0.9},
        {"text": "Cat", "prior": 0.7, "meta": {"note": "pet name"}}
      ],
      "context": [
        {"text": "2019", "prior": 0.95}
      ],
      "common_char": [...],
      "common_pinyin": [...],
      "whois_domain": [...]
    }
    """
    path = Path(path)
    with open(path, "r", encoding=encoding) as f:
        data = json.load(f)

    result: dict[LayerName, list[SourceToken]] = {}
    for layer_name, entries in data.items():
        if layer_name not in ("common_char", "common_pinyin", "whois_domain", "personal", "context"):
            continue
        tokens: list[SourceToken] = []
        for entry in entries:
            if isinstance(entry, str):
                tokens.append(SourceToken(text=entry, layer=layer_name, prior=1.0))
            elif isinstance(entry, dict):
                tokens.append(SourceToken(
                    text=entry["text"],
                    layer=layer_name,
                    prior=entry.get("prior", 1.0),
                    meta={**entry.get("meta", {}), "source_file": path.name},
                ))
        result[layer_name] = tokens

    return result


# ================================================================
# CSV — 批量导入
# ================================================================

def load_csv(
    path: str | Path,
    encoding: str = "utf-8",
) -> list[SourceToken]:
    """加载 CSV 候选源。

    格式（含表头）：
    text,layer,prior
    Schrodinger,personal,0.9
    Cat,personal,0.7
    2019,context,0.95

    或无表头（自动检测）：
    Schrodinger,personal,0.9
    """
    path = Path(path)
    tokens: list[SourceToken] = []

    with open(path, "r", encoding=encoding, errors="replace", newline="") as f:
        # 检测是否有表头
        sample = f.read(1024)
        f.seek(0)
        has_header = sample.startswith("text,") or sample.startswith("text\t")

        reader = csv.reader(f)
        if has_header:
            next(reader)  # skip header

        for row in reader:
            if len(row) < 1:
                continue
            text = row[0].strip()
            if not text:
                continue
            layer: LayerName = row[1].strip() if len(row) > 1 and row[1].strip() in (
                "common_char", "common_pinyin", "whois_domain", "personal", "context"
            ) else "common_char"
            prior = float(row[2]) if len(row) > 2 else 1.0

            tokens.append(SourceToken(
                text=text,
                layer=layer,
                prior=round(prior, 6),
                meta={"source_file": path.name},
            ))

    return tokens


# ================================================================
# 统一入口：自动检测格式
# ================================================================

def load_source(
    path: str | Path,
    layer: LayerName = "common_char",
    encoding: str = "utf-8",
    **kwargs,
) -> list[SourceToken] | dict[LayerName, list[SourceToken]]:
    """根据扩展名自动选择加载器。

    .txt → load_txt
    .dic → load_dic
    .json → load_json（返回 dict[layer, tokens]）
    .csv → load_csv
    """
    path = Path(path)
    ext = path.suffix.lower()

    if ext == ".json":
        return load_json(path, encoding=encoding)
    elif ext == ".csv":
        return load_csv(path, encoding=encoding)
    elif ext == ".dic":
        return load_dic(path, layer=layer, encoding=encoding, **kwargs)
    else:
        # .txt 和其他所有格式都当 txt 处理
        return load_txt(path, layer=layer, encoding=encoding, **kwargs)
