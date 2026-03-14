# iqpu_runtime.py
"""
IQPU 主运行时类。

组装 state_repr / phase_modulation / collapse_operator /
lindblad_solver / readout / entanglement_metrics，
提供完整的虚拟量子芯片单次运行接口。

公开别名：QCU = IQPU（与原型文件保持兼容）
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from .state_repr import IQPUConfig, IQPURunResult, build_initial_state
from .phase_modulation import OperatorBank, build_operator_bank, build_H_base, build_H_boost_trim
from .collapse_operator import build_collapse_cache, CollapseCache
from .lindblad_solver import alloc_rk4_buffers, rk4_step
from .readout import (
    ReadoutSnapshot,
    compute_step_snapshot,
    compute_final_observables,
)
from .entanglement_metrics import negativity_qubit0_vs_rest


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
        self.d = self.cfg.d

        self.dimQ: int = 2 ** self.Nq
        self.dimM: int = self.d ** self.Nm
        self.DIM: int = self.dimQ * self.dimM

        # 算符库
        self.ops: OperatorBank = build_operator_bank(self.cfg)

        # 基础 Hamiltonian
        self.H_base: np.ndarray = build_H_base(self.cfg, self.ops)

        # RK4 缓冲区（预分配，避免运行时 GC 压力）
        self.buffers = alloc_rk4_buffers(self.DIM)

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
    ) -> IQPURunResult:
        """运行 QCL v6 四阶段协议并返回结果。

        协议阶段
        --------
        [0, t1)    PCM 阶段：基础 H + PCM 耗散
        [t1, t2)   QIM 阶段：H_base + Ω_x σ_x,0 + QIM 耗散
        [t2, t3)   BOOST 阶段：H_boost + BOOST 耗散（含强制复位与相位噪声）
        [t3, t_max] PCM 阶段：回到基础 H + PCM 耗散

        Parameters
        ----------
        label : str
            运行标签，写入结果
        t1 : float
            QIM 阶段开始时刻
        t2 : float
            BOOST 阶段开始时刻
        omega_x : float
            QIM 阶段 qubit 0 的 σ_x 驱动频率
        gamma_pcm : float
            PCM 阶段 mode 间同步耗散率
        gamma_qim : float
            QIM 阶段 mode 间同步耗散率
        gamma_boost : float
            BOOST 阶段 mode 间同步耗散率
        boost_duration : float
            BOOST 阶段持续时间（超出 t_max 则截断）
        gamma_reset : float
            BOOST 阶段 qubit 0 强制复位率
        gamma_phi0 : float
            BOOST 阶段 qubit 0 相位噪声率
        eps_boost : float
            BOOST 驱动增强倍数
        boost_phase_trim : float
            BOOST 阶段两 mode 相位修正量（rad）

        Returns
        -------
        IQPURunResult
        """
        cfg = self.cfg
        ops = self.ops

        # ── 初始化密度矩阵 ──
        rho = build_initial_state(cfg, self.dimQ, self.dimM)

        # ── 构建各阶段 Hamiltonian ──
        H_pulse = 0.5 * float(omega_x) * ops.sxJ[0]
        H_boost = build_H_boost_trim(cfg, ops, self.H_base, eps_boost, boost_phase_trim)
        t3 = min(cfg.t_max, t2 + boost_duration)

        # ── 构建各阶段跳跃算符缓存 ──
        c_pcm = self._make_cache(gamma_pcm, 0.0, 0.0)
        c_qim = self._make_cache(gamma_qim, 0.0, 0.0)
        c_boost = self._make_cache(gamma_boost, gamma_reset, gamma_phi0)

        # ── 时间轴 ──
        steps = int(np.ceil(cfg.t_max / cfg.dt))
        ts_full = np.linspace(0.0, steps * cfg.dt, steps + 1)

        t_log, C_log, rel_phase_log, neg_log = [], [], [], []

        t_start = time.time()
        for i, t in enumerate(ts_full):
            # 每 obs_every 步记录一次
            if (i % cfg.obs_every) == 0:
                snap = compute_step_snapshot(
                    float(t), rho, ops, cfg.phi_ref, cfg.track_entanglement
                )
                t_log.append(snap.t)
                C_log.append(snap.C)
                rel_phase_log.append(snap.rel_phase)
                if cfg.track_entanglement:
                    neg_log.append(snap.negativity)

            # 推进一步（最后一步不需要推进）
            if i < len(ts_full) - 1:
                if t < t1:
                    Ht, cache = self.H_base, c_pcm
                elif t < t2:
                    Ht, cache = self.H_base + H_pulse, c_qim
                elif t < t3:
                    Ht, cache = H_boost, c_boost
                else:
                    Ht, cache = self.H_base, c_pcm

                rho_next = rk4_step(rho, cfg.dt, Ht, cache, self.buffers)
                rho[:] = rho_next

        elapsed = time.time() - t_start

        # ── 提取末态统计量 ──
        final_sz, final_n, final_rel_phase, C_end, dtheta_end = \
            compute_final_observables(rho, ops, cfg.phi_ref)

        N_end = float(neg_log[-1]) if (neg_log and cfg.track_entanglement) else None

        return IQPURunResult(
            label=label,
            DIM=self.DIM,
            elapsed_sec=elapsed,
            ts=np.array(t_log, dtype=np.float64),
            rel_phase=np.array(rel_phase_log, dtype=np.float64),
            C_log=np.array(C_log, dtype=np.float64),
            neg_log=np.array(neg_log, dtype=np.float64) if neg_log else None,
            final_sz=final_sz,
            final_n=final_n,
            final_rel_phase=final_rel_phase,
            C_end=C_end,
            dtheta_end=dtheta_end,
            N_end=N_end,
        )

    # ──────────────────────────────────────────────
    # 内部辅助
    # ──────────────────────────────────────────────

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


# 公开别名（与原型文件保持兼容）
QCU = IQPU
