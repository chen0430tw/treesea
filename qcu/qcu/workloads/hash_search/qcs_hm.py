# qcs_hm.py
"""
QCS-HM HMPL 三模态哈希搜索工作负载。

提供三种哈希任务模块：
  reverse_hash_scan  — 反向哈希查找（给定摘要，还原原像）
  prefix_zero_scan   — 前缀零摘要搜索（PoW 风格）
  toy_collision_scan — toy_hash16 碰撞枚举

三种运行模式：
  ideal     — 确定性结果
  noisy     — 模拟量子噪声（漏检率高）
  sharpened — 量子增强（漏检率低）

所有候选空间在外部生成（generate_whitelist_strings /
generate_numeric_strings），通过 QIRProgram.meta["candidates"] 传入。
"""

from __future__ import annotations

import hashlib
import itertools
import random
import string
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional


# ────────────────────────────────────────────
# IR 数据结构
# ────────────────────────────────────────────

@dataclass
class QIROp:
    """量子中间表示操作。"""
    name: str
    qubits: List[int]
    params: List[float] = field(default_factory=list)
    clbits: List[int] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QIRProgram:
    """HMPL 程序描述。

    Attributes
    ----------
    mode : str
        "ideal" / "noisy" / "sharpened"
    task : str
        目前只支持 "hmpl"
    meta : dict
        包含 module 字段（"reverse_hash_scan" / "prefix_zero_scan" /
        "toy_collision_scan"）及各模块参数
    """
    n_qubits: int
    n_clbits: int
    ops: List[QIROp]
    observables: List[Dict[str, Any]] = field(default_factory=list)
    shots: int = 1024
    mode: str = "ideal"
    task: str = "hmpl"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QCSResult:
    """运行结果容器。"""
    counts: Optional[Dict[str, int]] = None
    probabilities: Optional[Dict[str, float]] = None
    expectations: Optional[List[float]] = None
    state_meta: Dict[str, Any] = field(default_factory=dict)
    chip_meta: Dict[str, Any] = field(default_factory=dict)


# ────────────────────────────────────────────
# 哈希函数库
# ────────────────────────────────────────────

def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _sha3_256_hex(data: bytes) -> str:
    return hashlib.sha3_256(data).hexdigest()

def _blake2s_hex(data: bytes) -> str:
    return hashlib.blake2s(data).hexdigest()

HASH_FNS: Dict[str, Callable[[bytes], str]] = {
    "sha256": _sha256_hex,
    "sha3_256": _sha3_256_hex,
    "blake2s": _blake2s_hex,
}


def toy_hash16(data: bytes) -> str:
    """16-bit toy hash（用于碰撞演示）。"""
    h = 0x1234
    for i, b in enumerate(data):
        h = (h ^ ((b + i) * 257)) & 0xFFFF
        h = ((h << 5) | (h >> 11)) & 0xFFFF
        h = (h * 109 + 97) & 0xFFFF
    return f"{h:04x}"


ALL_HASH_FNS: Dict[str, Callable[[bytes], str]] = {
    "toy_hash16": toy_hash16,
    **HASH_FNS,
}


# ────────────────────────────────────────────
# 候选字符串生成器
# ────────────────────────────────────────────

def generate_whitelist_strings(
    alphabet: str,
    min_len: int,
    max_len: int,
) -> Iterable[str]:
    """枚举 alphabet 中所有长度在 [min_len, max_len] 的字符串。"""
    for n in range(min_len, max_len + 1):
        for tup in itertools.product(alphabet, repeat=n):
            yield "".join(tup)


def generate_numeric_strings(min_len: int, max_len: int) -> Iterable[str]:
    """枚举所有长度在 [min_len, max_len] 的数字字符串。"""
    yield from generate_whitelist_strings(string.digits, min_len, max_len)


# ────────────────────────────────────────────
# 芯片运行时
# ────────────────────────────────────────────

class QCSHMChipRuntime:
    """QCS-HM HMPL 三模态虚拟芯片运行时。"""

    def __init__(self, rng_seed: int = 430) -> None:
        self.supported_modes = {"ideal", "noisy", "sharpened"}
        self.supported_tasks = {"hmpl"}
        self.rng = random.Random(rng_seed)

    def execute(self, program: QIRProgram) -> QCSResult:
        if program.mode not in self.supported_modes:
            raise ValueError(f"Unsupported mode: {program.mode}")
        if program.task not in self.supported_tasks:
            raise ValueError(f"Unsupported task: {program.task}")

        module = program.meta.get("module")
        if module == "reverse_hash_scan":
            return self._execute_reverse_hash_scan(program)
        elif module == "prefix_zero_scan":
            return self._execute_prefix_zero_scan(program)
        elif module == "toy_collision_scan":
            return self._execute_toy_collision_scan(program)
        else:
            raise ValueError(f"Unsupported HMPL module: {module!r}")

    # ── mode helpers ──────────────────────────

    def _mode_reverse_accept(self, mode: str, is_true_hit: bool) -> bool:
        if mode == "ideal":
            return is_true_hit
        if mode == "noisy":
            return is_true_hit and self.rng.random() < 0.72
        if mode == "sharpened":
            return is_true_hit and self.rng.random() < 0.90
        return is_true_hit

    def _mode_prefix_accept(
        self,
        mode: str,
        true_zero_chars: int,
        target_zero_chars: int,
    ) -> bool:
        if mode == "ideal":
            return true_zero_chars >= target_zero_chars
        if mode == "noisy":
            if true_zero_chars >= target_zero_chars:
                return self.rng.random() < 0.65
            if true_zero_chars == target_zero_chars - 1:
                return self.rng.random() < 0.03
            return False
        if mode == "sharpened":
            if true_zero_chars >= target_zero_chars:
                return self.rng.random() < 0.88
            if true_zero_chars == target_zero_chars - 1:
                return self.rng.random() < 0.01
            return False
        return true_zero_chars >= target_zero_chars

    def _mode_collision_keep(self, mode: str) -> bool:
        if mode == "ideal":
            return True
        if mode == "noisy":
            return self.rng.random() < 0.62
        if mode == "sharpened":
            return self.rng.random() < 0.86
        return True

    @staticmethod
    def _leading_zero_hex_chars(digest_hex: str) -> int:
        n = 0
        for ch in digest_hex:
            if ch == "0":
                n += 1
            else:
                break
        return n

    # ── HMPL module 1: reverse hash scan ──────

    def _execute_reverse_hash_scan(self, program: QIRProgram) -> QCSResult:
        meta = program.meta
        hash_fn = ALL_HASH_FNS[meta["hash_name"]]
        target_hash = meta["target_hash"]
        mode = program.mode

        t0 = time.perf_counter()
        tries = 0
        recovered = None
        true_hit_index = None

        for idx, s in enumerate(meta["candidates"], start=1):
            tries += 1
            is_hit = hash_fn(s.encode()) == target_hash
            if is_hit and true_hit_index is None:
                true_hit_index = idx
            if self._mode_reverse_accept(mode, is_hit):
                recovered = s
                break

        return QCSResult(
            state_meta={
                "module": "reverse_hash_scan",
                "mode": mode,
                "hash_name": meta["hash_name"],
                "target_hash": target_hash,
                "found": recovered is not None,
                "recovered_input": recovered,
                "tries": tries,
                "true_hit_index": true_hit_index,
                "elapsed_sec": time.perf_counter() - t0,
                "candidate_space_desc": meta.get("candidate_space_desc", "unknown"),
            },
            chip_meta={"task": "hmpl", "engine": "QCS-HM reverse", "mode": mode},
        )

    # ── HMPL module 2: prefix zero scan ───────

    def _execute_prefix_zero_scan(self, program: QIRProgram) -> QCSResult:
        meta = program.meta
        hash_fn = ALL_HASH_FNS[meta["hash_name"]]
        target_z = int(meta["target_zero_hex_chars"])
        mode = program.mode

        t0 = time.perf_counter()
        tries = 0
        found_input = found_digest = found_z = None
        best_z, best_cand, best_digest = -1, None, None

        for s in meta["candidates"]:
            tries += 1
            d = hash_fn(s.encode())
            z = self._leading_zero_hex_chars(d)
            if z > best_z:
                best_z, best_cand, best_digest = z, s, d
            if self._mode_prefix_accept(mode, z, target_z):
                found_input, found_digest, found_z = s, d, z
                break

        return QCSResult(
            state_meta={
                "module": "prefix_zero_scan",
                "mode": mode,
                "hash_name": meta["hash_name"],
                "target_zero_hex_chars": target_z,
                "found": found_input is not None,
                "input_text": found_input,
                "digest_hex": found_digest,
                "true_zero_hex_chars": found_z,
                "tries": tries,
                "best_true_zero_hex_chars_seen": best_z,
                "best_candidate_seen": best_cand,
                "best_digest_seen": best_digest,
                "elapsed_sec": time.perf_counter() - t0,
            },
            chip_meta={"task": "hmpl", "engine": "QCS-HM prefix", "mode": mode},
        )

    # ── HMPL module 3: toy collision scan ─────

    def _execute_toy_collision_scan(self, program: QIRProgram) -> QCSResult:
        mode = program.mode
        seen: Dict[str, str] = {}
        all_cols: List[Dict[str, str]] = []
        kept_cols: List[Dict[str, str]] = []

        t0 = time.perf_counter()

        for s in program.meta["candidates"]:
            d = toy_hash16(s.encode())
            if d in seen and seen[d] != s:
                row = {"digest_hex": d, "first_input": seen[d], "second_input": s}
                all_cols.append(row)
                if self._mode_collision_keep(mode):
                    kept_cols.append(row)
            else:
                seen[d] = s

        return QCSResult(
            state_meta={
                "module": "toy_collision_scan",
                "mode": mode,
                "true_collision_count": len(all_cols),
                "reported_collision_count": len(kept_cols),
                "first_10_reported_collisions": kept_cols[:10],
                "elapsed_sec": time.perf_counter() - t0,
            },
            chip_meta={"task": "hmpl", "engine": "QCS-HM collision", "mode": mode},
        )


# ────────────────────────────────────────────
# Program builders
# ────────────────────────────────────────────

def build_reverse_hash_program(
    *,
    hash_name: str,
    target_hash: str,
    candidates: List[str],
    candidate_space_desc: str,
    mode: str,
) -> QIRProgram:
    return QIRProgram(
        n_qubits=8, n_clbits=8, ops=[],
        mode=mode, task="hmpl",
        meta={
            "module": "reverse_hash_scan",
            "hash_name": hash_name,
            "target_hash": target_hash,
            "candidates": candidates,
            "candidate_space_desc": candidate_space_desc,
        },
    )


def build_prefix_zero_program(
    *,
    hash_name: str,
    target_zero_hex_chars: int,
    candidates: List[str],
    mode: str,
) -> QIRProgram:
    return QIRProgram(
        n_qubits=8, n_clbits=8, ops=[],
        mode=mode, task="hmpl",
        meta={
            "module": "prefix_zero_scan",
            "hash_name": hash_name,
            "target_zero_hex_chars": target_zero_hex_chars,
            "candidates": candidates,
        },
    )


def build_toy_collision_program(
    *,
    candidates: List[str],
    mode: str,
) -> QIRProgram:
    return QIRProgram(
        n_qubits=8, n_clbits=8, ops=[],
        mode=mode, task="hmpl",
        meta={
            "module": "toy_collision_scan",
            "candidates": candidates,
        },
    )
