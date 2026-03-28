# qsharp_hash_search.py
"""
Q# → QCU SHA-256 Prefix-Zero 搜索
===================================
用 Q# 写量子层，驱动 QCU 执行 SHA-256 前导零搜索。

难度递增：
  Level 1  目标前导零 1 hex char   候选池 ~500
  Level 2  目标前导零 2 hex chars  候选池 ~2000
  Level 3  目标前导零 3 hex chars  候选池 ~5000
"""

from __future__ import annotations

import hashlib
import sys
import time

sys.path.insert(0, "D:/treesea/qcu")

from qcu_lang import QCircuit, QGate, EmergeOp, QCUExecutor
from qcu_lang.frontend.qsharp import from_qsharp_str
from qcu.workloads.hash_search.qcs_hm import (
    QCSHMChipRuntime,
    build_prefix_zero_program,
    generate_numeric_strings,
)

SEP = "─" * 56

# ── Q# 电路：相位编码 + 候选空间初始化 ─────────────────────────
#
# 这段 Q# 描述的不是经典算法——它在描述量子层的相位初始化。
# H 门建立叠加，RZ 注入相位偏置，CNOT 形成纠缠。
# QCU 编译器把它翻译为 boost_phase_trim / qim_evolve 序列，
# 驱动 IQPU 到一个特定相位态，C 值决定后续搜索的筛选强度。

QSHARP_HASH_CIRCUIT = """
operation HashSearchInit() : Unit {
    use (q0, q1, q2, q3, q4) = (Qubit(), Qubit(), Qubit(), Qubit(), Qubit());
    H(q0);
    H(q1);
    H(q2);
    H(q3);
    H(q4);
    Rz(0.628, q0);
    Rz(1.257, q1);
    Rz(1.885, q2);
    CNOT(q0, q2);
    CNOT(q1, q3);
    CNOT(q2, q4);
    Rz(0.314, q3);
    Rz(0.942, q4);
    let r0 = M(q0);
    let r1 = M(q1);
    let r2 = M(q2);
    let r3 = M(q3);
    let r4 = M(q4);
}
"""


def run_level(level: int, target_zeros: int, pool_size: int) -> dict:
    print(f"\n{SEP}")
    print(f"  Level {level}  —  目标前导零：{target_zeros} hex char(s)")
    print(f"  候选池：{pool_size} 个数字字符串")
    print(SEP)

    # 1. 解析 Q# 电路
    circ = from_qsharp_str(QSHARP_HASH_CIRCUIT, name=f"hash_l{level}")
    circ.gates.append(QGate(EmergeOp.QCL_BOOST, (), params=(4.0, 0.9, 0.01, 2.0)))

    # 2. 运行 IQPU 得到 C 值
    ex = QCUExecutor(verbose=False)
    r_iqpu = ex.run(circ)
    C = r_iqpu.final_C or 0.0
    mode = "sharpened" if C < 0.05 else "noisy"
    print(f"  IQPU C = {C:.4f}  →  mode = {mode}")

    # 3. 构造候选集
    candidates = list(generate_numeric_strings(1, 5))[:pool_size]

    # 4. HMPL prefix-zero 搜索
    chip = QCSHMChipRuntime()
    prog = build_prefix_zero_program(
        hash_name="sha256",
        target_zero_hex_chars=target_zeros,
        candidates=candidates,
        mode=mode,
    )

    t0 = time.time()
    result = chip.execute(prog)
    elapsed = time.time() - t0
    meta = result.state_meta

    if meta["found"]:
        inp = meta["input_text"]
        digest = meta["digest_hex"]
        z = meta["true_zero_hex_chars"]
        print(f"  ✅ 找到：'{inp}'")
        print(f"     SHA-256 = {digest}")
        print(f"     前导零  = {z} hex chars  (目标 {target_zeros})")
        print(f"     扫描了  {meta['tries']} 个候选，耗时 {elapsed:.2f}s")
    else:
        bz = meta["best_true_zero_hex_chars_seen"]
        bc = meta["best_candidate_seen"]
        bd = meta["best_digest_seen"]
        print(f"  ➖ 未达目标（候选池不够大）")
        print(f"     最佳：'{bc}' → {bd[:20]}…  前导零 {bz}")
        print(f"     扫描了 {meta['tries']} 个，耗时 {elapsed:.2f}s")

    meta["elapsed_sec"] = elapsed
    meta["C_end"] = C
    meta["mode"] = mode
    return meta


if __name__ == "__main__":
    print()
    print("=" * 56)
    print("  Q# → QCU  SHA-256 Prefix-Zero 搜索")
    print("=" * 56)
    print()
    print("Q# 电路（5 qubit，相位编码候选空间）：")
    for line in QSHARP_HASH_CIRCUIT.strip().splitlines():
        print(f"  {line}")

    results = []
    levels = [
        (1, 1,  500),
        (2, 2, 2000),
        (3, 3, 5000),
    ]

    for level, target_zeros, pool_size in levels:
        r = run_level(level, target_zeros, pool_size)
        results.append(r)

    print(f"\n{'=' * 56}")
    print("  汇总")
    print(f"{'=' * 56}")
    for i, (r, (level, tz, _)) in enumerate(zip(results, levels)):
        found = r.get("found", False)
        digest_preview = (r.get("digest_hex") or r.get("best_digest_seen") or "")[:16]
        status = "✅" if found else "➖"
        print(f"  Level {level}  ({tz} zeros)  {status}  {digest_preview}…")
    print(f"{'=' * 56}")
