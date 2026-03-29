# qcu_executor.py
"""
QCU 执行后端：将 PhaseStep 序列在 IQPU 上执行。

执行流程
--------
1. 初始化 IQPU（使用传入的 IQPUConfig 或默认配置）
2. 逐步执行 PhaseStep：
   - phase_shift   → 累积到 boost_phase_trim，在 FREE_EVOLVE 时刷新
   - qim_evolve    → 短时 QIM 阶段（临时构建 H + sigma_x 驱动）
   - dispersive    → 在 H_base 下自由演化（色散耦合积累相位）
   - free_evolve   → 在当前 H 下自由演化
   - readout       → compute_final_observables
   - emerge        → 调用 IQPU.run_qcl_v6()
   - collapse_scan → QCSHMChipRuntime
3. 返回 QCUExecResult（包含各步读出值和末态）
"""

from __future__ import annotations

import sys
sys.path.insert(0, 'D:/treesea/qcu')

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..compiler.phase_map import PhaseStep, compile_circuit
from ..ir.circuit import QCircuit
from ..ir.ops import EmergeOp


@dataclass
class StepResult:
    """单步执行结果。"""
    step_index: int
    kind: str
    readout: Optional[Dict[str, Any]] = None


@dataclass
class QCUExecResult:
    """电路执行结果。"""
    circuit_name: str
    n_steps: int
    step_results: List[StepResult] = field(default_factory=list)
    final_C: Optional[float] = None
    final_dtheta: Optional[float] = None
    final_sz: Optional[List[float]] = None
    final_n: Optional[List[float]] = None
    final_rel_phase: Optional[List[float]] = None
    bit_results: Optional[List[int]] = None   # sz > 0 → 0, sz ≤ 0 → 1
    elapsed_sec: float = 0.0
    iqpu_results: List[Any] = field(default_factory=list)

    def __repr__(self) -> str:
        c = f"{self.final_C:.4f}" if self.final_C is not None else "N/A"
        d = f"{self.final_dtheta:.4f}" if self.final_dtheta is not None else "N/A"
        b = self.bit_results if self.bit_results is not None else "N/A"
        return (
            f"QCUExecResult({self.circuit_name!r}, "
            f"steps={self.n_steps}, C_end={c}, dtheta={d}, bits={b})"
        )


class QCUExecutor:
    """QCU 执行后端。

    Parameters
    ----------
    cfg : IQPUConfig, optional
        IQPU 配置；若不传则使用默认值（Nq=2, Nm=2, d=6）
    device : str
        'cpu' 或 'cuda'
    verbose : bool
        是否打印每步执行信息
    """

    def __init__(self, cfg=None, device: str = "cpu",
                 profile: str = "full_physics", verbose: bool = True):
        self._user_cfg = cfg   # None → auto-detect Nq from circuit at run()
        self.device = device
        self.profile = profile
        self.verbose = verbose
        self.cfg = cfg         # may be overwritten per-run when auto-detecting
        self._iqpu = None

    def _make_cfg(self, circ: QCircuit, Nq: int):
        """从电路推导 IQPUConfig（含噪声模型推导）。

        segment 级操作固定 Nq=2（局部相位交互，DIM=144）；
        emerge 级才用真实 n_qubits。噪声参数来自 circ.set_noise() 注解，
        未注解时按电路双比特门数自动校正。
        """
        from ..compiler.noise_infer import infer_iqpu_config
        from qcu.core.profiles import IQPUFastProfile, IQPUFullProfile, apply_profile
        cfg = infer_iqpu_config(circ, Nq=Nq, device=self.device)
        if self.profile == "fast_search":
            apply_profile(cfg, IQPUFastProfile(backend=self.device))
        else:
            apply_profile(cfg, IQPUFullProfile(backend=self.device))
        return cfg

    def run(self, circ: QCircuit) -> QCUExecResult:
        """执行量子电路，返回结果。"""
        import time
        from qcu.core.iqpu_runtime import IQPU
        from ..compiler.noise_infer import noise_summary
        # segment 级固定 Nq=2（局部相位交互），emerge 级才用 circ.n_qubits
        seg_cfg    = self._user_cfg or self._make_cfg(circ, Nq=2)
        emerge_cfg = self._user_cfg or self._make_cfg(circ, Nq=circ.n_qubits)
        self.cfg   = seg_cfg          # 暴露给外部检查（代表 segment 级配置）
        self._iqpu = IQPU(seg_cfg)
        if self.verbose:
            print(f"  noise: {noise_summary(circ)}")
        steps = compile_circuit(circ)
        result = QCUExecResult(circuit_name=circ.name, n_steps=len(steps))

        # 累积相位偏移（在 flush 时统一应用）
        phase_accumulator: float = 0.0
        t0 = time.time()

        for i, step in enumerate(steps):
            if self.verbose:
                print(f"  [{i:>3}] {step.kind:<16} {step.params}", flush=True)

            sr = StepResult(step_index=i, kind=step.kind)

            if step.kind == "noop":
                pass

            elif step.kind == "phase_shift":
                phase_accumulator += step.params.get("theta", 0.0)

            elif step.kind in ("qim_evolve", "dispersive", "free_evolve"):
                # 刷新累积相位 → 跑一段 QCL v6（只用 PCM 阶段）
                trim = phase_accumulator
                phase_accumulator = 0.0
                duration = step.params.get("duration", 0.5)
                omega_x = step.params.get("omega_x", 1.0) if step.kind == "qim_evolve" else 0.0

                r = self._run_segment(
                    t1=duration,                     # QIM 开始
                    t2=duration + 0.1,               # BOOST 开始（短）
                    omega_x=omega_x,
                    gamma_pcm=0.1, gamma_qim=0.05,
                    gamma_boost=0.5, boost_duration=0.1,
                    gamma_reset=0.0, gamma_phi0=0.0,
                    eps_boost=1.0,
                    boost_phase_trim=trim,
                )
                sr.readout = {
                    "C_end": r.C_end,
                    "dtheta": r.dtheta_end,
                    "rel_phase": r.final_rel_phase,
                }
                result.iqpu_results.append(r)

            elif step.kind == "discriminate":
                # 诱导判决：C > threshold → bit=0，否则 bit=1
                threshold = step.params.get("threshold", 0.01)
                last_C = result.iqpu_results[-1].C_end if result.iqpu_results else 0.0
                bit = 0 if last_C > threshold else 1
                qubit = step.params.get("qubit", 0)
                if result.bit_results is None:
                    result.bit_results = []
                # 确保列表够长
                while len(result.bit_results) <= qubit:
                    result.bit_results.append(0)
                result.bit_results[qubit] = bit
                sr.readout = {"C": last_C, "threshold": threshold, "bit": bit}

            elif step.kind == "readout":
                # 读出当前（最后一次 IQPU 运行的末态）
                if result.iqpu_results:
                    last = result.iqpu_results[-1]
                    sr.readout = {
                        "C_end": last.C_end,
                        "sz": last.final_sz,
                        "n": last.final_n,
                        "rel_phase": last.final_rel_phase,
                    }

            elif step.kind == "proj_readout":
                # 投影测量：高强度辨别协议（eps_boost=8.0）→ sz 推向 ±1
                trim = phase_accumulator
                phase_accumulator = 0.0
                r = self._run_segment(
                    t1=0.1, t2=0.3,
                    omega_x=0.0,
                    gamma_pcm=0.3, gamma_qim=0.0,
                    gamma_boost=0.9, boost_duration=0.2,
                    gamma_reset=0.0, gamma_phi0=0.0,
                    eps_boost=8.0,
                    boost_phase_trim=trim,
                )
                sr.readout = {
                    "C_end": r.C_end,
                    "sz": r.final_sz,
                    "n": r.final_n,
                    "rel_phase": r.final_rel_phase,
                }
                result.iqpu_results.append(r)

            elif step.kind == "qcl_phase":
                phase = step.params.get("phase", "pcm")
                duration = step.params.get("duration", 1.0)
                gamma = step.params.get("gamma", 0.2)
                trim = phase_accumulator
                phase_accumulator = 0.0

                if phase == "pcm":
                    r = self._run_segment(t1=duration, t2=duration+0.01,
                        omega_x=0.0, gamma_pcm=gamma, gamma_qim=0.0,
                        gamma_boost=0.1, boost_duration=0.01,
                        gamma_reset=0.0, gamma_phi0=0.0,
                        eps_boost=1.0, boost_phase_trim=trim)
                elif phase == "qim":
                    r = self._run_segment(t1=0.1, t2=0.1+duration,
                        omega_x=step.params.get("omega_x", 1.0),
                        gamma_pcm=0.05, gamma_qim=gamma,
                        gamma_boost=0.1, boost_duration=0.01,
                        gamma_reset=0.0, gamma_phi0=0.0,
                        eps_boost=1.0, boost_phase_trim=trim)
                else:  # boost
                    r = self._run_segment(t1=0.1, t2=0.2,
                        omega_x=0.0, gamma_pcm=0.1, gamma_qim=0.05,
                        gamma_boost=gamma, boost_duration=duration,
                        gamma_reset=step.params.get("gamma_reset", 0.0),
                        gamma_phi0=step.params.get("gamma_phi0", 0.0),
                        eps_boost=step.params.get("eps_boost", 4.0),
                        boost_phase_trim=step.params.get("trim", 0.0))

                sr.readout = {"C_end": r.C_end, "dtheta": r.dtheta_end}
                result.iqpu_results.append(r)

            elif step.kind == "emerge":
                # 完整 QCL v6 协议 — 用 emerge_cfg（包含真实 n_qubits）
                trim = phase_accumulator
                phase_accumulator = 0.0
                r = self._run_segment(
                    t1=3.0, t2=5.0, omega_x=1.0,
                    gamma_pcm=0.2, gamma_qim=0.03,
                    gamma_boost=0.9, boost_duration=3.0,
                    gamma_reset=0.25, gamma_phi0=0.6,
                    eps_boost=4.0, boost_phase_trim=trim,
                    _cfg=emerge_cfg,
                )
                sr.readout = {
                    "C_end": r.C_end,
                    "dtheta": r.dtheta_end,
                    "sz": r.final_sz,
                    "n": r.final_n,
                    "rel_phase": r.final_rel_phase,
                }
                result.iqpu_results.append(r)

            elif step.kind == "collapse_scan":
                from qcu.workloads.hash_search.qcs_hm import (
                    QCSHMChipRuntime, build_reverse_hash_program,
                )
                candidates = step.params.get("candidates", [])
                C_threshold = step.params.get("C_threshold", 0.01)
                # 根据末态 C 值选择模式
                last_C = result.iqpu_results[-1].C_end if result.iqpu_results else 1.0
                mode = "sharpened" if last_C < C_threshold else "noisy"
                chip = QCSHMChipRuntime()
                prog = build_reverse_hash_program(
                    hash_name="sha256",
                    target_hash=step.params.get("target_hash", ""),
                    candidates=list(candidates),
                    candidate_space_desc="from_qcu_circuit",
                    mode=mode,
                )
                scan_r = chip.execute(prog)
                sr.readout = {"collapse_result": scan_r.state_meta, "mode": mode}

            result.step_results.append(sr)

        # 填充最终结果
        if result.iqpu_results:
            last = result.iqpu_results[-1]
            result.final_C = last.C_end
            result.final_dtheta = last.dtheta_end
            result.final_sz = last.final_sz
            result.final_n = last.final_n
            result.final_rel_phase = last.final_rel_phase
            # 经典 bit 读出：⟨σz⟩ > 0 → |0⟩ → bit=0；≤ 0 → |1⟩ → bit=1
            if last.final_sz is not None:
                result.bit_results = [0 if sz > 0 else 1 for sz in last.final_sz]

        result.elapsed_sec = time.time() - t0
        return result

    def _run_segment(self, *, _cfg=None, _init_rho=None, **kw) -> Any:
        """运行一段 QCL v6 协议。

        _cfg      : 可选，传入则覆盖 self.cfg（emerge 步骤用 emerge_cfg）。
        _init_rho : 可选初态密度矩阵；传入则从上一 gate 末态继续演化，
                    实现 gate 间量子态连续传递。None → 从 |0⟩ 初始化。
        """
        from qcu.core.iqpu_runtime import IQPU
        iqpu = IQPU(_cfg if _cfg is not None else self.cfg)
        return iqpu.run_qcl_v6(label="seg", init_rho=_init_rho, **kw)
