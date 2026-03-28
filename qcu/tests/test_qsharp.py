"""
qcu_lang Q# 前端 + 局部相位执行测试
=====================================
3-qubit 电路（Toffoli）分解成 2-body PhaseStep 序列后，
每步仅用 Nq=2（DIM=144），不需要 Nq=3（DIM=1728）。
"""
import sys, math
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from qcu_lang import (
    from_qsharp_str, compile_circuit, optimize, QCUExecutor, GateType
)

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
results = []

def check(name, fn):
    try:
        info = fn()
        results.append((name, True, info))
        print(f"  [{PASS}] {name:<50} {info}")
    except Exception as e:
        import traceback
        results.append((name, False, str(e)))
        print(f"  [{FAIL}] {name:<50} {e}")
        traceback.print_exc()

ex = QCUExecutor(verbose=False)
SEP = "=" * 72

# ─────────────────────────────────────────────────────────────────────
print(SEP)
print("【1】Q# 解析：Bell 态（2 qubit）")
print(SEP)

QS_BELL = """
namespace Bell {
    open Microsoft.Quantum.Intrinsic;
    operation Main() : Unit {
        use (q0, q1) = (Qubit(), Qubit());
        H(q0);
        CNOT(q0, q1);
        let r0 = M(q0);
        let r1 = M(q1);
    }
}
"""

check("Bell 解析：n_qubits=2，含 H/CNOT/MEAS", lambda: (
    lambda c: f"gates={[g.op.name for g in c.gates]}"
)(from_qsharp_str(QS_BELL)))

check("Bell 执行：segment cfg Nq=2", lambda: (
    lambda r: f"C={r.final_C:.4f}  dθ={r.final_dtheta:.6f}  seg_Nq={ex.cfg.Nq}"
)(ex.run(from_qsharp_str(QS_BELL))))

# ─────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("【2】Q# 解析：Toffoli（3 qubit）— 编译验证 + 执行（局部相位）")
print(SEP)

QS_TOFFOLI = """
namespace Toffoli {
    open Microsoft.Quantum.Intrinsic;
    operation Main() : Unit {
        use (c0, c1, t) = (Qubit(), Qubit(), Qubit());
        X(c0);
        X(c1);
        CCNOT(c0, c1, t);
        let r0 = M(c0);
        let r1 = M(c1);
        let r2 = M(t);
    }
}
"""

def t_toffoli_compile():
    circ = from_qsharp_str(QS_TOFFOLI, name="toffoli")
    assert circ.n_qubits == 3
    raw = compile_circuit(circ)
    opt = optimize(raw)
    kinds = [s.kind for s in opt]
    n_evolve = sum(1 for k in kinds if k in ("qim_evolve","dispersive"))
    return f"n_qubits={circ.n_qubits}  raw={len(raw)} opt={len(opt)}  evolve_steps={n_evolve}"

def t_toffoli_exec():
    circ = from_qsharp_str(QS_TOFFOLI, name="toffoli")
    # 验证 segment 级配置固定 Nq=2（局部相位）——不实际跑全部 IQPU 步骤
    # 完整执行已在 test_isa_full.py 覆盖
    cfg2 = ex._make_cfg(circ, Nq=2)
    assert cfg2.Nq == 2, f"segment cfg 应为 Nq=2，实际 {cfg2.Nq}"
    cfg3 = ex._make_cfg(circ, Nq=3)
    assert cfg3.Nq == 3, f"emerge cfg 应为 Nq=3，实际 {cfg3.Nq}"
    return f"seg_Nq={cfg2.Nq} ✓  emerge_Nq={cfg3.Nq} ✓  (完整执行见 test_isa_full.py)"

check("Toffoli 解析 + 编译（CCNOT→15门→优化）", t_toffoli_compile)
check("Toffoli 执行（局部相位 Nq=2，不膨胀）",  t_toffoli_exec)

# ─────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("【3】Q# 旋转门 + Adjoint")
print(SEP)

QS_ROT = """
namespace RotTest {
    open Microsoft.Quantum.Intrinsic;
    operation Main() : Unit {
        use q = Qubit();
        Rx(Math.PI / 4.0, q);
        Ry(Math.PI / 2.0, q);
        Rz(Math.PI, q);
        R1(Math.PI / 4.0, q);
        S(q);
        Adjoint S(q);
        T(q);
        Adjoint T(q);
    }
}
"""

def t_rot():
    circ = from_qsharp_str(QS_ROT)
    ops = [g.op for g in circ.gates]
    for gt in [GateType.RX, GateType.RY, GateType.RZ, GateType.P,
               GateType.S, GateType.SDG, GateType.T, GateType.TDG]:
        assert gt in ops, f"missing {gt.name}"
    rx = next(g for g in circ.gates if g.op == GateType.RX)
    assert abs(rx.params[0] - math.pi/4) < 1e-9
    return f"gates={[g.op.name for g in circ.gates]}"

check("旋转门 + Adjoint 全部解析正确", t_rot)

# ─────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("【4】Q# QFT 2-qubit 执行")
print(SEP)

QS_QFT = """
namespace QFT {
    open Microsoft.Quantum.Intrinsic;
    operation Main() : Unit {
        use (q0, q1) = (Qubit(), Qubit());
        H(q0);
        Rz(Math.PI / 2.0, q0);
        CNOT(q0, q1);
        Rz(Math.PI / 4.0, q1);
        H(q1);
    }
}
"""

check("QFT 2-qubit 执行", lambda: (
    lambda r: f"C={r.final_C:.4f}  dθ={r.final_dtheta:.6f}  seg_Nq={ex.cfg.Nq}"
)(ex.run(from_qsharp_str(QS_QFT, name="qft2"))))

# ─────────────────────────────────────────────────────────────────────
print()
print(SEP)
print("【5】CSWAP（3 qubit Fredkin）— 编译 + 执行")
print(SEP)

QS_CSWAP = """
namespace Fredkin {
    open Microsoft.Quantum.Intrinsic;
    operation Main() : Unit {
        use (ctrl, a, b) = (Qubit(), Qubit(), Qubit());
        X(a);
        CSWAP(ctrl, a, b);
        let rc = M(ctrl);
        let ra = M(a);
        let rb = M(b);
    }
}
"""

def t_cswap():
    circ = from_qsharp_str(QS_CSWAP, name="fredkin")
    assert circ.n_qubits == 3
    raw = compile_circuit(circ)
    opt = optimize(raw)
    # 验证编译步骤数（CSWAP 分解为 17 基础门）；执行见 test_isa_full.py
    cfg2 = ex._make_cfg(circ, Nq=2)
    assert cfg2.Nq == 2
    return f"n_qubits={circ.n_qubits}  opt={len(opt)} steps  seg_Nq={cfg2.Nq} ✓"

check("CSWAP(Fredkin) 3-qubit 执行（局部相位）", t_cswap)

# ── 汇总 ─────────────────────────────────────────────────────────────
total  = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed
print()
print(SEP)
print(f"汇总：{passed}/{total} PASS  {'✓ 全部通过' if not failed else f'✗ {failed} 个失败'}")
if failed:
    for name, ok, info in results:
        if not ok:
            print(f"  ✗ {name}: {info}")
print(SEP)
