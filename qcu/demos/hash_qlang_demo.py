# hash_qlang_demo.py
"""
用量子编程语言驱动 QCU Hash 坍缩搜索
=====================================

展示 IBM / 本源量子无法做到的事：
  - 他们的 ISA 里没有 COLLAPSE_SCAN
  - 他们的编译器无法将相位动力学映射到 hash 候选筛选
  - 他们的芯片读出的是测量比特，不是相位相干度 C

这里用四种量子编程语言分别写量子层（门电路），
统一接入 QCU 的 COLLAPSE_SCAN 指令，运行三类 hash 任务：
  1. 逆向 Hash（给定 SHA-256 摘要，找原像）
  2. Prefix-zero 搜索（找开头有 N 个零的哈希，比特币 PoW 同原理）
  3. Toy 碰撞扫描（找两个不同输入产生相同 toy_hash16）

电路结构
--------
  量子门层（QASM / Q# / Qiskit / Cirq）
      ↓  phase_shift / qim_evolve  （相位态初始化）
  QCL_BOOST emerge 指令
      ↓  C 值决定模式：C 低 → sharpened（精准筛选），C 高 → noisy（宽松筛选）
  COLLAPSE_SCAN
      ↓  HMPL 三模态 hash 候选过滤
  结果回写
"""

from __future__ import annotations

import hashlib
import sys
import time

sys.path.insert(0, "D:/treesea/qcu")

from qcu_lang import QCircuit, QGate, GateType, EmergeOp, QCUExecutor
from qcu_lang import from_qasm_str, compile_circuit, optimize
from qcu_lang.frontend.qsharp import from_qsharp_str
from qcu_lang.frontend.qiskit_frontend import from_qiskit
from qcu_lang.frontend.cirq_frontend import from_cirq

from qcu.workloads.hash_search.qcs_hm import (
    QCSHMChipRuntime,
    build_reverse_hash_program,
    build_prefix_zero_program,
    build_toy_collision_program,
    generate_whitelist_strings,
    generate_numeric_strings,
    toy_hash16,
)

SEP = "=" * 64


# ── 工具：在任意 QCircuit 末尾追加 COLLAPSE_SCAN ──────────────────

def append_collapse_scan(circ: QCircuit, candidates: list, target_hash: str = "",
                          task_meta: dict = None) -> QCircuit:
    """向电路末尾追加 QCL_BOOST + COLLAPSE_SCAN。

    这两条指令在 IBM / 本源的 ISA 里不存在。
    QCL_BOOST 驱动相位坍缩，COLLAPSE_SCAN 用 C 值决定筛选模式。
    """
    meta = task_meta or {}
    meta["candidates"] = candidates
    meta["target_hash"] = target_hash
    # Layer 2: 相位坍缩驱动
    circ.gates.append(QGate(EmergeOp.QCL_BOOST,  (), params=(4.0, 0.9, 0.01, 2.0)))
    circ.gates.append(QGate(EmergeOp.COLLAPSE_SCAN, (), meta=meta))
    return circ


# ── 准备候选集 ────────────────────────────────────────────────────

def make_candidates_reverse(secret: str, pool_size: int = 500) -> tuple[list, str]:
    """构造逆向 hash 候选集：secret 混入数字候选池中。"""
    import random, string
    rng = random.Random(42)
    pool = list(generate_numeric_strings(1, 3))[:pool_size]
    if secret not in pool:
        insert_at = rng.randint(0, len(pool))
        pool.insert(insert_at, secret)
    target = hashlib.sha256(secret.encode()).hexdigest()
    return pool, target


def make_candidates_prefix(pool_size: int = 2000) -> list:
    """构造 prefix-zero 候选集：枚举数字字符串，找前导零最多的。"""
    return list(generate_numeric_strings(1, 4))[:pool_size]


def make_candidates_collision() -> list:
    """构造碰撞候选集：全字母数字 2-char 组合（1296 个）。
    toy_hash16 输出 16-bit，1296 个候选的生日碰撞概率 ~99.99%。
    """
    import string as _s
    alpha = _s.ascii_lowercase + _s.digits
    return [a + b for a in alpha for b in alpha]


# ── 执行器：电路 → IQPU → COLLAPSE_SCAN ──────────────────────────

def run_hash_circuit(circ: QCircuit, candidates: list,
                     task: str, target_hash: str = "",
                     target_zeros: int = 2) -> dict:
    """执行量子电路 + hash 坍缩扫描，返回结果字典。"""
    chip = QCSHMChipRuntime()

    # 先跑 IQPU 得到 C 值（决定 sharpened / noisy 模式）
    ex = QCUExecutor(verbose=False)

    # 把 COLLAPSE_SCAN 以外的门先跑一遍，得到 C
    phase_circ = QCircuit(circ.n_qubits, n_clbits=circ.n_clbits,
                          gates=[g for g in circ.gates
                                 if not isinstance(g.op, type(EmergeOp.COLLAPSE_SCAN))
                                 and g.op != EmergeOp.COLLAPSE_SCAN
                                 and g.op != EmergeOp.QCL_BOOST])
    phase_circ.gates.append(QGate(EmergeOp.QCL_BOOST, (), params=(4.0, 0.9, 0.01, 2.0)))
    r = ex.run(phase_circ)
    C = r.final_C if r.final_C is not None else 1.0
    mode = "sharpened" if C < 0.05 else "noisy"

    # 根据任务类型构造 HMPL 程序
    if task == "reverse":
        prog = build_reverse_hash_program(
            hash_name="sha256",
            target_hash=target_hash,
            candidates=candidates,
            candidate_space_desc="numeric_1to3",
            mode=mode,
        )
    elif task == "prefix":
        prog = build_prefix_zero_program(
            hash_name="sha256",
            target_zero_hex_chars=target_zeros,
            candidates=candidates,
            mode=mode,
        )
    elif task == "collision":
        prog = build_toy_collision_program(candidates=candidates, mode=mode)
    else:
        raise ValueError(task)

    result = chip.execute(prog)
    result.state_meta["C_end"] = C
    result.state_meta["mode_selected"] = mode
    return result.state_meta


# ════════════════════════════════════════════════════════════════
# 任务一：QASM 写门电路 → 逆向 SHA-256
# ════════════════════════════════════════════════════════════════

def demo_qasm_reverse():
    print(SEP)
    print("【QASM → 逆向 SHA-256】")
    print("  给定 SHA-256 摘要，从候选池中找回原像")
    print(SEP)

    secret = "42"
    candidates, target_hash = make_candidates_reverse(secret, pool_size=500)
    print(f"  目标原像：'{secret}'  SHA-256：{target_hash[:16]}…")
    print(f"  候选池大小：{len(candidates)}")

    # QASM 量子层：超位叠加 + 相位偏置
    # 在 IBM/Origin 上这部分是合法的，但 COLLAPSE_SCAN 不是
    qasm_src = """
OPENQASM 2.0;
include "qelib1.inc";
qreg q[4];
creg c[4];
h q[0]; h q[1]; h q[2]; h q[3];
rz(0.785) q[0];
rz(1.571) q[1];
cx q[0], q[1];
cx q[2], q[3];
"""
    circ = from_qasm_str(qasm_src)
    # 追加 QCU 原生指令（IBM/Origin 无法表达）
    circ.gates.append(QGate(EmergeOp.QCL_BOOST, (), params=(4.0, 0.9, 0.01, 2.0)))

    t0 = time.time()
    result = run_hash_circuit(circ, candidates, "reverse", target_hash=target_hash)
    elapsed = time.time() - t0

    print(f"  C 值 = {result['C_end']:.4f}  →  模式：{result['mode_selected']}")
    print(f"  found = {result['found']}")
    if result["found"]:
        print(f"  ✅ 找到原像：'{result['recovered_input']}'")
        print(f"     验证：SHA-256('{result['recovered_input']}') = "
              f"{hashlib.sha256(result['recovered_input'].encode()).hexdigest()[:16]}…")
    else:
        print(f"  扫描了 {result['tries']} 个候选，真实命中位置：{result['true_hit_index']}")
    print(f"  耗时：{elapsed:.2f}s\n")
    return result


# ════════════════════════════════════════════════════════════════
# 任务二：Q# 写门电路 → Prefix-Zero 搜索（比特币 PoW 同原理）
# ════════════════════════════════════════════════════════════════

def demo_qsharp_prefix():
    print(SEP)
    print("【Q# → Prefix-Zero SHA-256 搜索】")
    print("  找一个输入，使其 SHA-256 哈希以 2 个零字符开头")
    print("  （比特币挖矿同原理，只是难度更低）")
    print(SEP)

    candidates = make_candidates_prefix(pool_size=2000)
    target_zeros = 2
    print(f"  目标前导零：{target_zeros} hex chars  候选池：{len(candidates)}")

    # Q# 量子层：Hadamard + CNOT 纠缠 + 旋转
    qs_src = """
operation HashSearch() : Unit {
    use (q0, q1, q2, q3) = (Qubit(), Qubit(), Qubit(), Qubit());
    H(q0);
    H(q1);
    H(q2);
    H(q3);
    Rz(1.047, q0);
    Rz(2.094, q1);
    CNOT(q0, q2);
    CNOT(q1, q3);
    let r0 = M(q0);
    let r1 = M(q1);
    let r2 = M(q2);
    let r3 = M(q3);
}
"""
    circ = from_qsharp_str(qs_src, name="prefix_search")
    circ.gates.append(QGate(EmergeOp.QCL_BOOST, (), params=(4.0, 0.9, 0.01, 2.0)))

    t0 = time.time()
    result = run_hash_circuit(circ, candidates, "prefix", target_zeros=target_zeros)
    elapsed = time.time() - t0

    print(f"  C 值 = {result['C_end']:.4f}  →  模式：{result['mode_selected']}")
    print(f"  found = {result['found']}")
    if result["found"]:
        print(f"  ✅ 找到输入：'{result['input_text']}'")
        print(f"     SHA-256：{result['digest_hex'][:24]}…")
        print(f"     前导零：{result['true_zero_hex_chars']} hex chars")
    else:
        print(f"  最佳前导零：{result['best_true_zero_hex_chars_seen']} "
              f"（来自 '{result['best_candidate_seen']}'）")
    print(f"  耗时：{elapsed:.2f}s\n")
    return result


# ════════════════════════════════════════════════════════════════
# 任务三：Qiskit 写门电路 → Toy Hash 碰撞扫描
# ════════════════════════════════════════════════════════════════

def demo_qiskit_collision():
    print(SEP)
    print("【Qiskit → Toy Hash 碰撞扫描】")
    print("  在候选池中找两个不同输入，使 toy_hash16 相同")
    print(SEP)

    candidates = make_candidates_collision()
    print(f"  候选池大小：{len(candidates)}")

    try:
        from qiskit import QuantumCircuit as QkCircuit
        qk = QkCircuit(3, 3)
        qk.h(0); qk.h(1); qk.h(2)
        qk.rz(0.524, 0); qk.rz(1.047, 1)
        qk.cx(0, 1); qk.cx(1, 2)
        qk.measure([0, 1, 2], [0, 1, 2])
        circ = from_qiskit(qk)
        circ.name = "collision_search"
        print("  量子层：Qiskit QuantumCircuit（直接对象转换）")
    except ImportError:
        # Qiskit 未安装，回退到 QASM
        qasm_src = """
OPENQASM 2.0;
qreg q[3]; creg c[3];
h q[0]; h q[1]; h q[2];
rz(0.524) q[0]; rz(1.047) q[1];
cx q[0],q[1]; cx q[1],q[2];
measure q -> c;
"""
        circ = from_qasm_str(qasm_src)
        print("  量子层：QASM（Qiskit 未安装，自动回退）")

    circ.gates.append(QGate(EmergeOp.QCL_BOOST, (), params=(4.0, 0.9, 0.01, 2.0)))

    t0 = time.time()
    result = run_hash_circuit(circ, candidates, "collision")
    elapsed = time.time() - t0

    print(f"  C 值 = {result['C_end']:.4f}  →  模式：{result['mode_selected']}")
    n_col = result.get("reported_collision_count", 0)
    print(f"  找到碰撞对：{n_col} 组（真实总数：{result.get('true_collision_count', 0)}）")
    if n_col > 0:
        row = result["first_10_reported_collisions"][0]
        a, b, d = row["first_input"], row["second_input"], row["digest_hex"]
        print(f"  ✅ 碰撞对：'{a}' 和 '{b}'")
        print(f"     toy_hash16 = {d}")
        print(f"     验证：{toy_hash16(a.encode()) == toy_hash16(b.encode())}")
    print(f"  耗时：{elapsed:.2f}s\n")
    return result


# ════════════════════════════════════════════════════════════════
# 任务四：Cirq 写门电路 → 三模态对比实验
# ════════════════════════════════════════════════════════════════

def demo_cirq_mode_compare():
    print(SEP)
    print("【Cirq → 三模态 C 值对比】")
    print("  用不同相位偏置观察 QCU 模式选择行为")
    print(SEP)

    try:
        import cirq
        q0, q1 = cirq.LineQubit.range(2)
        _has_cirq = True
    except ImportError:
        _has_cirq = False
        print("  [跳过] cirq-core 未安装\n")
        return None

    from qcu.core.iqpu_runtime import IQPU
    from qcu.core.state_repr import IQPUConfig
    from qcu_lang.frontend.cirq_frontend import from_cirq
    import math

    # eps_drive 必须非零才能让相位偏置影响 C 值（Deutsch 同原理）
    iqpu_cfg = IQPUConfig(Nq=2, Nm=2, d=6, eps_drive=[1.0+0j, 1.0+0j])
    iqpu = IQPU(iqpu_cfg)

    results = []

    # boost_phase_trim 编码相位偏置：不同 Cirq 电路对应不同积累相位
    configs = [
        ("无偏置（均匀叠加）",    0.0),
        ("RZ π/4 偏置",          math.pi / 4),
        ("RZ π/2 偏置",          math.pi / 2),
        ("RZ π 偏置（平衡）",    math.pi),
    ]

    for label, trim in configs:
        r = iqpu.run_qcl_v6(
            label="mode_test",
            t1=3.0, t2=5.0, omega_x=1.0,
            gamma_pcm=0.2, gamma_qim=0.03,
            gamma_boost=0.9, boost_duration=3.0,
            gamma_reset=0.25, gamma_phi0=0.6,
            eps_boost=4.0, boost_phase_trim=trim,
        )
        C = r.C_end
        mode = "sharpened" if C < 1.0 else "noisy"
        print(f"  {label:<28}  C={C:>10.4f}  →  {mode}")
        results.append((label, C, mode))

    print()
    return results


# ════════════════════════════════════════════════════════════════
# 主程序
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print(SEP)
    print("  QCU Hash 坍缩搜索 × 量子编程语言")
    print("  IBM / 本源量子无法运行此程序：")
    print("    · COLLAPSE_SCAN 不在其 ISA 中")
    print("    · 无法将相位动力学 C 值映射到 hash 筛选模式")
    print(SEP)
    print()

    r1 = demo_qasm_reverse()
    r2 = demo_qsharp_prefix()
    r3 = demo_qiskit_collision()
    r4 = demo_cirq_mode_compare()

    print(SEP)
    print("  汇总")
    print(SEP)
    ok1 = r1 and r1.get("found")
    ok2 = r2 and r2.get("found")
    ok3 = r3 and r3.get("reported_collision_count", 0) > 0
    print(f"  逆向 SHA-256  （QASM）  : {'✅ 找到' if ok1 else '➖'}")
    print(f"  Prefix-Zero  （Q#）    : {'✅ 找到' if ok2 else '➖'}")
    print(f"  Toy 碰撞扫描 （Qiskit）: {'✅ 找到' if ok3 else '➖'}")
    if r4:
        print(f"  模式对比     （Cirq）  : ✅ {len(r4)} 组")
    print(SEP)
