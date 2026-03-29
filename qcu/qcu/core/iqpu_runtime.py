# iqpu_runtime.py
"""
IQPU 主运行时类。

组装 state_repr / phase_modulation / collapse_operator /
lindblad_solver / readout / entanglement_metrics，
提供完整的虚拟量子芯片单次运行接口。

公开别名：QCU = IQPU（与原型文件保持兼容）

Profile
-------
full_physics  高保真模式：complex128，obs_every 密，完整 readout，negativity 可开
fast_search   快搜模式：complex64，obs_every 稀疏，只算 C/rel_phase，negativity 关闭
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from .state_repr import IQPUConfig, IQPURunResult, build_initial_state, get_xp
from .phase_modulation import OperatorBank, build_operator_bank, build_H_base, build_H_boost_trim
from .collapse_operator import build_collapse_cache, CollapseCache
from .lindblad_solver import alloc_rk4_buffers, rk4_step
from .readout import (
    ReadoutSnapshot,
    compute_step_snapshot_fast,
    compute_step_snapshot_full,
    compute_final_observables,
)
from .entanglement_metrics import negativity_qubit0_vs_rest

# profile 默认参数
_FAST_OBS_EVERY      = 8
_FAST_NEG_EVERY      = 0
_FAST_DTYPE          = np.complex64
_FULL_DTYPE          = np.complex128


class IQPU:
    """虚拟量子芯片（Imaginary QPU）。

    使用 Lindblad 主方程 + RK4 模拟开放量子系统演化，
    支持多阶段协议（PCM → QIM → BOOST → PCM）。

    Parameters
    ----------
    cfg : IQPUConfig
        运行参数配置（会在内部调用 finalize()）

    Examples
    --------
    >>> import numpy as np
    >>> from qcu.qcu.core.state_repr import IQPUConfig
    >>> from qcu.qcu.core.iqpu_runtime import IQPU
    >>> cfg = IQPUConfig(Nq=2, Nm=2, d=6)
    >>> iqpu = IQPU(cfg)
    >>> result = iqpu.run_qcl_v6(
    ...     label="test",
    ...     t1=3.0, t2=5.0,
    ...     omega_x=1.0,
    ...     gamma_pcm=0.2, gamma_qim=0.03,
    ...     gamma_boost=0.9, boost_duration=3.0,
    ...     gamma_reset=0.25, gamma_phi0=0.6,
    ...     eps_boost=4.0, boost_phase_trim=0.012,
    ... )
    """

    def __init__(self, cfg: IQPUConfig) -> None:
        self.cfg: IQPUConfig = cfg.finalize()

        self.Nq = self.cfg.Nq
        self.Nm = self.cfg.Nm
        self.d  = self.cfg.d

        self.dimQ: int = 2 ** self.Nq
        self.dimM: int = self.d ** self.Nm
        self.DIM:  int = self.dimQ * self.dimM

        # 计算后端（numpy / cupy），初始化时确定，不在热路径重复判断
        self.xp = get_xp(self.cfg.device)

        # profile → dtype
        self._dtype = (
            _FAST_DTYPE if self.cfg.profile == "fast_search" else _FULL_DTYPE
        )

        # obs_every：fast_search 强制稀疏
        self._obs_every = (
            max(self.cfg.obs_every, _FAST_OBS_EVERY)
            if self.cfg.profile == "fast_search"
            else self.cfg.obs_every
        )

        # negativity_every：fast_search 强制关闭
        self._neg_every = (
            0 if self.cfg.profile == "fast_search"
            else self.cfg.negativity_every
        )

        # 算符库（CPU 构建后移到目标设备）
        ops_cpu: OperatorBank = build_operator_bank(self.cfg)
        self.ops: OperatorBank = self._move_ops(ops_cpu)

        # 基础 Hamiltonian
        H_base_cpu = build_H_base(self.cfg, ops_cpu)
        self.H_base = self.xp.asarray(H_base_cpu.astype(
            np.complex64 if self._dtype == np.complex64 else np.complex128
        ))

        # RK4 缓冲区（目标设备，目标 dtype）
        self.buffers = alloc_rk4_buffers(self.DIM, self.xp, self._dtype)

    # ──────────────────────────────────────────────
    # 公开运行接口
    # ──────────────────────────────────────────────

    def run_qcl_v6(
        self,
        label: str,
        t1: float,
        t2: float,
        omega_x: float,
        gamma_pcm: float,
        gamma_qim: float,
        gamma_boost: float,
        boost_duration: float,
        gamma_reset: float,
        gamma_phi0: float,
        eps_boost: float,
        boost_phase_trim: float,
        init_rho=None,
        t_max_override: float = None,
    ) -> IQPURunResult:
        """运行 QCL v6 四阶段协议并返回结果。

        协议阶段
        --------
        [0, t1)    PCM 阶段
        [t1, t2)   QIM 阶段
        [t2, t3)   BOOST 阶段
        [t3, t_max] PCM 阶段

        Parameters
        ----------
        t_max_override : float, optional
            覆盖 cfg.t_max 的实际运行时长。用于 segment 级别的快速执行：
            t3（物理结束点）之后只需短暂 PCM 尾，无需跑满 cfg.t_max=10。
            传入时需保证 t_max_override >= t3（t2 + boost_duration）。
        """
        cfg  = self.cfg
        ops  = self.ops
        xp   = self.xp
        dt   = np.float32(cfg.dt) if self._dtype == np.complex64 else cfg.dt

        # ── 初始化密度矩阵 ──
        if init_rho is not None:
            rho = xp.asarray(init_rho.astype(
                np.complex64 if self._dtype == np.complex64 else np.complex128
            ))
        else:
            rho = xp.asarray(
                build_initial_state(cfg, self.dimQ, self.dimM).astype(
                    np.complex64 if self._dtype == np.complex64 else np.complex128
                )
            )

        # ── 构建各阶段 Hamiltonian ──
        H_pulse = 0.5 * float(omega_x) * ops.sxJ[0]
        H_boost = self.xp.asarray(
            build_H_boost_trim(cfg, self._ops_cpu_ref, self._H_base_cpu_ref,
                               eps_boost, boost_phase_trim).astype(
                np.complex64 if self._dtype == np.complex64 else np.complex128
            )
        )

        # ── 有效 t_max（支持 segment 级收紧）──
        eff_t_max = t_max_override if t_max_override is not None else cfg.t_max
        t3 = min(eff_t_max, t2 + boost_duration)

        # ── 跳跃算符缓存 ──
        c_pcm   = self._make_cache(gamma_pcm,   0.0,          0.0)
        c_qim   = self._make_cache(gamma_qim,   0.0,          0.0)
        c_boost = self._make_cache(gamma_boost, gamma_reset,  gamma_phi0)

        # ── 时间轴 ──
        steps   = int(np.ceil(eff_t_max / cfg.dt))
        ts_full = np.linspace(0.0, steps * cfg.dt, steps + 1)

        t_log, C_log, rel_phase_log, neg_log = [], [], [], []
        obs_idx = 0   # 用于 negativity_every 计数

        t_start = time.time()
        for i, t in enumerate(ts_full):
            # 过程观测（稀疏）
            if (i % self._obs_every) == 0:
                if cfg.profile == "fast_search":
                    C, rp = compute_step_snapshot_fast(xp, t, rho, ops.aJ, cfg.phi_ref)
                    t_log.append(float(t))
                    C_log.append(C)
                    rel_phase_log.append(rp)
                else:
                    track_neg = (
                        cfg.track_entanglement
                        and self._neg_every > 0
                        and (obs_idx % self._neg_every) == 0
                    )
                    snap = compute_step_snapshot_full(xp, t, rho, ops, cfg.phi_ref, track_neg)
                    t_log.append(snap.t)
                    C_log.append(snap.C)
                    rel_phase_log.append(snap.rel_phase)
                    if snap.negativity is not None:
                        neg_log.append(snap.negativity)
                obs_idx += 1

            # RK4 推进
            if i < len(ts_full) - 1:
                if t < t1:
                    Ht, cache = self.H_base, c_pcm
                elif t < t2:
                    Ht, cache = self.H_base + H_pulse, c_qim
                elif t < t3:
                    Ht, cache = H_boost, c_boost
                else:
                    Ht, cache = self.H_base, c_pcm

                rho_next = rk4_step(xp, rho, dt, Ht, cache, self.buffers)
                rho[:] = rho_next

        elapsed = time.time() - t_start

        # ── 末态统计量（一次性完整读出）──
        final_sz, final_n, final_rel_phase, C_end, dtheta_end = \
            compute_final_observables(rho, ops, cfg.phi_ref)

        N_end = float(neg_log[-1]) if (neg_log and cfg.track_entanglement) else None

        rho_cpu = rho.get() if hasattr(rho, 'get') else np.array(rho)

        return IQPURunResult(
            label=label,
            DIM=self.DIM,
            elapsed_sec=elapsed,
            ts=np.array(t_log, dtype=np.float64),
            rel_phase=np.array(rel_phase_log, dtype=object if rel_phase_log and isinstance(rel_phase_log[0], list) else np.float64),
            C_log=np.array(C_log, dtype=np.float64),
            neg_log=np.array(neg_log, dtype=np.float64) if neg_log else None,
            final_sz=final_sz,
            final_n=final_n,
            final_rel_phase=final_rel_phase,
            C_end=C_end,
            dtheta_end=dtheta_end,
            N_end=N_end,
            final_rho=rho_cpu,
        )

    # ──────────────────────────────────────────────
    # 内部辅助
    # ──────────────────────────────────────────────

    def _move_ops(self, ops_cpu: OperatorBank) -> OperatorBank:
        """将 numpy 算符库移到目标设备，并保留 CPU 引用供 H_boost 构建。"""
        xp = self.xp
        dtype = self._dtype
        self._ops_cpu_ref   = ops_cpu   # 保留 CPU 引用
        self._H_base_cpu_ref = build_H_base(self.cfg, ops_cpu)  # CPU H_base 引用
        cast = lambda a: xp.asarray(a.astype(
            np.complex64 if dtype == np.complex64 else np.complex128
        ))
        return OperatorBank(
            DIM=ops_cpu.DIM,
            szJ=[cast(o) for o in ops_cpu.szJ],
            sxJ=[cast(o) for o in ops_cpu.sxJ],
            smJ=[cast(o) for o in ops_cpu.smJ],
            aJ= [cast(o) for o in ops_cpu.aJ],
            adJ=[cast(o) for o in ops_cpu.adJ],
            nJ= [cast(o) for o in ops_cpu.nJ],
        )

    def _make_cache(
        self,
        gamma_sync: float,
        gamma_reset_q0: float,
        gamma_phi0: float,
    ) -> CollapseCache:
        """组装指定参数的跳跃算符缓存。"""
        return build_collapse_cache(
            Nq=self.Nq,
            Nm=self.Nm,
            kappa=self.cfg.kappa,
            T1=self.cfg.T1,
            Tphi=self.cfg.Tphi,
            smJ=self.ops.smJ,
            szJ=self.ops.szJ,
            aJ=self.ops.aJ,
            gamma_sync=gamma_sync,
            gamma_reset_q0=gamma_reset_q0,
            gamma_phi0=gamma_phi0,
        )


# 公开别名
QCU = IQPU
