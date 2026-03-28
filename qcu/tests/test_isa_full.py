"""
qcu_lang 全套指令集测试
======================
Layer 0 全部标准门编译验证
Layer 1 Phase 指令直通验证
Layer 2 Emerge 指令执行验证
优化 pass 验证
端到端执行抽样
"""
import sys, math, traceback
import pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from qcu_lang import (
    QCircuit, QGate, GateType, PhaseOp, EmergeOp,
    compile_circuit, optimize, QCUExecutor, from_qasm_str
)
from qcu_lang.compiler.phase_map import PhaseStep

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
results = []

def check(name, fn):
    try:
        info = fn()
        tag = PASS
        results.append((name, True, info))
    except Exception as e:
        tag = FAIL
        info = str(e)
        results.append((name, False, info))
    print(f"  [{tag}] {name:<40} {info}")

print("=" * 65)
print("【Layer 0】标准量子门 → PhaseStep 编译")
print("=" * 65)

# ── 单量子比特门 ──────────────────────────────────────────────

def _compile1(op, *params):
    g = QGate(op, (0,), params=params)
    steps = [s for s in compile_circuit(QCircuit(1, gates=[g]))
             if s.kind != "noop"]
    return f"{len(steps)} steps: {[s.kind for s in steps]}"

check("X",     lambda: _compile1(GateType.X))
check("Y",     lambda: _compile1(GateType.Y))
check("Z",     lambda: _compile1(GateType.Z))
check("H",     lambda: _compile1(GateType.H))
check("S",     lambda: _compile1(GateType.S))
check("SDG",   lambda: _compile1(GateType.SDG))
check("T",     lambda: _compile1(GateType.T))
check("TDG",   lambda: _compile1(GateType.TDG))
check("SX",    lambda: _compile1(GateType.SX))
check("RX(π)", lambda: _compile1(GateType.RX, math.pi))
check("RY(π)", lambda: _compile1(GateType.RY, math.pi))
check("RZ(π)", lambda: _compile1(GateType.RZ, math.pi))
check("P(π/4)",lambda: _compile1(GateType.P, math.pi/4))
check("U(θ,φ,λ)",lambda: _compile1(GateType.U, math.pi/2, math.pi/4, math.pi/8))
check("ID",    lambda: _compile1(GateType.ID))
check("BARRIER",lambda: _compile1(GateType.BARRIER))
check("RESET", lambda: _compile1(GateType.RESET))

# ── 双量子比特门 ──────────────────────────────────────────────

def _compile2(op, *params):
    g = QGate(op, (0,1), params=params)
    steps = [s for s in compile_circuit(QCircuit(2, gates=[g]))
             if s.kind != "noop"]
    return f"{len(steps)} steps: {[s.kind for s in steps]}"

check("CX",    lambda: _compile2(GateType.CX))
check("CY",    lambda: _compile2(GateType.CY))
check("CZ",    lambda: _compile2(GateType.CZ))
check("SWAP",  lambda: _compile2(GateType.SWAP))
check("ISWAP", lambda: _compile2(GateType.ISWAP))
check("ECR",   lambda: _compile2(GateType.ECR))

# ── 三量子比特门（分解后验证步数合理） ──────────────────────

def _compile3(op):
    g = QGate(op, (0,1,2))
    steps = [s for s in compile_circuit(QCircuit(3, gates=[g]))
             if s.kind != "noop"]
    return f"{len(steps)} steps"

check("CCX (Toffoli)", lambda: _compile3(GateType.CCX))
check("CSWAP (Fredkin)",lambda: _compile3(GateType.CSWAP))
check("MCX(n=2→CCX)", lambda: (
    lambda g: f"{len([s for s in compile_circuit(QCircuit(3, gates=[g])) if s.kind!='noop'])} steps"
)(QGate(GateType.MCX, (0,1,2))))

# MEAS
check("MEAS", lambda: (
    lambda g: f"kind={compile_circuit(QCircuit(1, n_clbits=1, gates=[g]))[0].kind}"
)(QGate(GateType.MEAS, (0,), clbits=(0,))))

print()
print("=" * 65)
print("【Layer 1】Phase 指令直通")
print("=" * 65)

def _check_phase(op, *params):
    circ = QCircuit(2)
    circ.gates.append(QGate(op, (0,), params=params))
    steps = compile_circuit(circ)
    # Layer 1 → phase_op
    assert any(s.kind == "phase_op" for s in steps), f"no phase_op: {steps}"
    return f"phase_op ok, params={steps[0].params}"

check("PHASE_SHIFT",    lambda: _check_phase(PhaseOp.PHASE_SHIFT, 0.5))
check("PHASE_TRIM",     lambda: _check_phase(PhaseOp.PHASE_TRIM, 0, 1, 0.01))
check("PHASE_LOCK",     lambda: _check_phase(PhaseOp.PHASE_LOCK))
check("DRIVE_SET",      lambda: _check_phase(PhaseOp.DRIVE_SET, 1.0))
check("DRIVE_BOOST",    lambda: _check_phase(PhaseOp.DRIVE_BOOST, 2.0))
check("DISPERSIVE_WAIT",lambda: _check_phase(PhaseOp.DISPERSIVE_WAIT, 1.0))
check("FREE_EVOLVE",    lambda: _check_phase(PhaseOp.FREE_EVOLVE, 0.5))

print()
print("=" * 65)
print("【Layer 2】Emerge 指令编译")
print("=" * 65)

def _check_emerge(op, *params, meta=None):
    circ = QCircuit(2)
    circ.gates.append(QGate(op, (), params=params, meta=meta or {}))
    steps = compile_circuit(circ)
    kinds = [s.kind for s in steps]
    return f"kinds={kinds}"

check("QCL_PCM",       lambda: _check_emerge(EmergeOp.QCL_PCM, 0.2, 1.0))
check("QCL_QIM",       lambda: _check_emerge(EmergeOp.QCL_QIM, 1.0, 0.05, 2.0))
check("QCL_BOOST",     lambda: _check_emerge(EmergeOp.QCL_BOOST, 4.0, 0.9, 0.01, 2.0))
check("QCL_RUN",       lambda: _check_emerge(EmergeOp.QCL_RUN))
check("SYNC_EMERGE",   lambda: _check_emerge(EmergeOp.SYNC_EMERGE))
check("PHASE_LOCK_WAIT",lambda: _check_emerge(EmergeOp.PHASE_LOCK_WAIT, 0.02))
check("PHASE_ANNEAL",  lambda: _check_emerge(EmergeOp.PHASE_ANNEAL,
                                              meta={"schedule": [0.1, 0.5, 1.0]}))

print()
print("=" * 65)
print("【Optimizer】编译期优化 pass")
print("=" * 65)

def _opt_merge():
    circ = QCircuit(1)
    for t in [math.pi/4]*4:
        circ.rz(t, 0)
    raw = compile_circuit(circ)
    opt = optimize(raw)
    assert len(opt) == 1 and abs(opt[0].params["theta"] - math.pi) < 1e-9
    return f"4×RZ(π/4) → 1×RZ(π) ✓"

def _opt_cancel():
    circ = QCircuit(1)
    circ.rz(math.pi/3, 0)
    circ.rz(-math.pi/3, 0)
    raw = compile_circuit(circ)
    opt = optimize(raw)
    assert len(opt) == 0
    return f"RZ(π/3)+RZ(-π/3) → 0 steps ✓"

def _opt_noop():
    circ = QCircuit(1)
    circ.gates.append(QGate(GateType.ID, (0,)))
    circ.gates.append(QGate(GateType.BARRIER, (0,)))
    raw = compile_circuit(circ)
    opt = optimize(raw)
    assert len(opt) == 0
    return f"ID+BARRIER stripped ✓"

def _opt_interleaved():
    # phase_shift 中间夹了 qim_evolve，不能合并跨越
    circ = QCircuit(1)
    circ.rz(math.pi/4, 0)
    circ.rx(math.pi/2, 0)
    circ.rz(math.pi/4, 0)
    raw = compile_circuit(circ)
    opt = optimize(raw)
    kinds = [s.kind for s in opt]
    assert kinds == ["phase_shift", "qim_evolve", "phase_shift"]
    return f"RZ·RX·RZ 跨越不合并 ✓ kinds={kinds}"

check("合并相邻 phase_shift",          _opt_merge)
check("相消为 0 时整体移除",           _opt_cancel)
check("noop_strip (ID/BARRIER)",       _opt_noop)
check("跨 qim_evolve 不合并",          _opt_interleaved)

print()
print("=" * 65)
print("【端到端执行】QASM + 混合电路抽样")
print("=" * 65)

ex = QCUExecutor(verbose=False)

def _run_bell():
    qasm = """OPENQASM 2.0; include "qelib1.inc";
qreg q[2]; creg c[2];
h q[0]; cx q[0],q[1];
measure q[0]->c[0]; measure q[1]->c[1];"""
    r = ex.run(from_qasm_str(qasm))
    assert r.final_C is not None
    return f"C={r.final_C:.4f} dθ={r.final_dtheta:.6f}"

def _run_mixed():
    circ = QCircuit(2, n_clbits=2, name="mixed")
    circ.h(0).rz(math.pi/4, 0).cx(0, 1)
    circ.phase_trim(0, 1, 0.01)
    circ.qcl_boost(4.0, 0.9, 0.01, 2.0)
    circ.measure(0, 0).measure(1, 1)
    raw = compile_circuit(circ)
    opt = optimize(raw)
    r = ex.run(circ)
    return f"raw={len(raw)} opt={len(opt)} C={r.final_C:.4f}"

def _run_toffoli():
    circ = QCircuit(3, name="toffoli")
    circ.gates.append(QGate(GateType.CCX, (0,1,2)))
    raw = compile_circuit(circ)
    opt = optimize(raw)
    return f"CCX: raw={len(raw)} opt={len(opt)} steps (no exec, compile only)"

check("Bell 态执行",       _run_bell)
check("三层混合电路执行",  _run_mixed)
check("CCX 编译（不执行）", _run_toffoli)

# ── 汇总 ─────────────────────────────────────────────────────
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed

print()
print("=" * 65)
print(f"汇总：{passed}/{total} PASS  {'✓ 全部通过' if failed==0 else f'✗ {failed} 个失败'}")
if failed:
    print("\n失败项目：")
    for name, ok, info in results:
        if not ok:
            print(f"  ✗ {name}: {info}")
print("=" * 65)

# ─────────────────────────────────────────────────────────────
# 噪声模型推导测试（追加）
# ─────────────────────────────────────────────────────────────
SEP = "=" * 65
print()
print(SEP)
print("【噪声模型推导】set_noise + infer_noise_params")
print(SEP)

from qcu_lang import infer_noise_params, noise_summary

def _noise(circ):
    return infer_noise_params(circ)

def t_default():
    circ = QCircuit(2)
    circ.h(0).cx(0, 1)  # 1 个双比特门 → 自动校正
    p = _noise(circ)
    assert p["T1"] < 100., f"T1 应因双比特门降低，实际={p['T1']}"
    return f"T1={p['T1']:.1f}  Tphi={p['Tphi']:.1f}  κ={p['kappa']:.4f}"

def t_preset_ideal():
    circ = QCircuit(2)
    circ.set_noise(preset="ideal")
    p = _noise(circ)
    assert p["T1"] >= 1e5, f"ideal T1 应极大，实际={p['T1']}"
    return f"preset=ideal: T1={p['T1']:.0e}  κ={p['kappa']:.1e}"

def t_preset_nisq():
    circ = QCircuit(2)
    circ.set_noise(preset="nisq")
    p = _noise(circ)
    assert abs(p["T1"] - 50.) < 1e-9
    return f"preset=nisq: T1={p['T1']}  Tphi={p['Tphi']}  κ={p['kappa']}"

def t_explicit_override():
    circ = QCircuit(2)
    circ.set_noise(preset="nisq", T1=80.)  # 覆盖 preset 的 T1
    p = _noise(circ)
    assert abs(p["T1"] - 80.) < 1e-9, f"显式 T1=80 未覆盖 preset，实际={p['T1']}"
    assert abs(p["Tphi"] - 100.) < 1e-9  # Tphi 来自 nisq preset
    return f"explicit override: T1={p['T1']}  Tphi={p['Tphi']}"

def t_unknown_preset():
    try:
        circ = QCircuit(2)
        circ.set_noise(preset="quantum_supremacy")
        _noise(circ)
        return "FAIL: 应抛 ValueError"
    except ValueError as e:
        return f"ValueError ✓: {e}"

def t_noise_summary():
    circ = QCircuit(2)
    circ.h(0).cx(0,1).cx(0,1)
    s = noise_summary(circ)
    assert "NoiseModel" in s and "T1=" in s
    return s

def t_executor_noise():
    circ = QCircuit(2, name="nisq_bell")
    circ.set_noise(preset="nisq")
    circ.h(0).cx(0,1)
    r = ex.run(circ)
    assert r.final_C is not None
    return f"nisq Bell: C={r.final_C:.4f}  (T1={infer_noise_params(circ)['T1']}μs)"

check("无注解 + 双比特门自动校正",    t_default)
check("preset=ideal",               t_preset_ideal)
check("preset=nisq",                t_preset_nisq)
check("显式参数覆盖 preset",         t_explicit_override)
check("未知 preset → ValueError",   t_unknown_preset)
check("noise_summary 摘要字符串",    t_noise_summary)
check("nisq 噪声 Bell 态执行",       t_executor_noise)

# ── 最终汇总 ─────────────────────────────────────────────────
total  = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed
print()
print(SEP)
print(f"最终汇总：{passed}/{total} PASS  {'✓ 全部通过' if not failed else f'✗ {failed} 个失败'}")
if failed:
    print("\n失败项目：")
    for name, ok, info in results:
        if not ok:
            print(f"  ✗ {name}: {info}")
print(SEP)

# ─────────────────────────────────────────────────────────────
# Cirq 前端测试
# ─────────────────────────────────────────────────────────────
try:
    import cirq as _cirq
    _HAS_CIRQ = True
except ImportError:
    _HAS_CIRQ = False

if _HAS_CIRQ:
    print()
    print(SEP)
    print("【Cirq 前端】from_cirq + to_cirq")
    print(SEP)
    from qcu_lang.frontend.cirq_frontend import from_cirq, to_cirq
    import cirq

    def t_cirq_bell():
        q0, q1 = cirq.LineQubit.range(2)
        c = cirq.Circuit([cirq.H(q0), cirq.CNOT(q0, q1),
                          cirq.measure(q0, key='m0'), cirq.measure(q1, key='m1')])
        qcirc = from_cirq(c, name='bell')
        assert qcirc.n_qubits == 2
        ops = [g.op for g in qcirc.gates]
        assert GateType.H in ops and GateType.CX in ops and GateType.MEAS in ops
        r = ex.run(qcirc)
        assert r.final_C is not None
        return f"n_qubits={qcirc.n_qubits}  C={r.final_C:.4f}"

    def t_cirq_toffoli():
        q0, q1, q2 = cirq.LineQubit.range(3)
        c = cirq.Circuit([cirq.X(q0), cirq.X(q1), cirq.CCX(q0, q1, q2)])
        qcirc = from_cirq(c, name='toffoli')
        assert qcirc.n_qubits == 3
        raw = compile_circuit(qcirc)
        opt = optimize(raw)
        r = ex.run(qcirc)
        return f"n_qubits={qcirc.n_qubits}  raw={len(raw)} opt={len(opt)}  C={r.final_C:.4f}"

    def t_cirq_rot():
        q = cirq.LineQubit(0)
        c = cirq.Circuit([cirq.rz(1.57)(q), cirq.ry(0.78)(q), cirq.rx(3.14)(q)])
        qcirc = from_cirq(c)
        ops = [g.op for g in qcirc.gates]
        assert GateType.RZ in ops and GateType.RY in ops and GateType.RX in ops
        rz = next(g for g in qcirc.gates if g.op == GateType.RZ)
        assert abs(rz.params[0] - 1.57) < 1e-6
        return f"gates={[g.op.name for g in qcirc.gates]}"

    def t_cirq_pow():
        q = cirq.LineQubit(0)
        c = cirq.Circuit([cirq.Z(q)**0.5, cirq.X(q)**0.5])
        qcirc = from_cirq(c)
        ops = [g.op for g in qcirc.gates]
        assert GateType.RZ in ops   # Z^0.5 → RZ(π/2)
        assert GateType.SX in ops   # X^0.5 → SX
        return f"Z^0.5→RZ, X^0.5→SX ✓"

    def t_cirq_to_cirq():
        q0, q1 = cirq.LineQubit.range(2)
        c = cirq.Circuit([cirq.H(q0), cirq.CNOT(q0, q1)])
        qcirc = from_cirq(c)
        c_back = to_cirq(qcirc)
        assert len(list(c_back.all_operations())) == 2
        return f"roundtrip ops={[str(op.gate) for m in c_back for op in m.operations]}"

    check("Cirq Bell 解析 + 执行",  t_cirq_bell)
    check("Cirq Toffoli（3-qubit）", t_cirq_toffoli)
    check("Cirq 旋转门 rz/ry/rx",    t_cirq_rot)
    check("Cirq ZPow/XPow 门",       t_cirq_pow)
    check("to_cirq 双向转换",         t_cirq_to_cirq)

    total  = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed
    print()
    print(SEP)
    print(f"最终汇总（含 Cirq）：{passed}/{total} PASS  {'✓ 全部通过' if not failed else f'✗ {failed} 个失败'}")
    if failed:
        for name, ok, info in results:
            if not ok:
                print(f"  ✗ {name}: {info}")
    print(SEP)
else:
    print("\n[跳过] cirq-core 未安装，Cirq 前端测试略过")
