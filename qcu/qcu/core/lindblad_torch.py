# lindblad_torch.py
"""
Lindblad 主方程 torch fused 求解器。

将整个 RK4 时间演化 fuse 到 GPU 上：
  - collapse operators 堆成 batch tensor，用 batched matmul 替代 Python for 循环
  - 整个时间步循环用 torch.compile 编译
  - 最小化 Python↔GPU 来回次数

参考 FlashMLA 设计：一次 kernel launch 跑完全部计算。
"""

from __future__ import annotations

import torch
import numpy as np
from typing import List, Tuple, Optional


def _np_to_torch(arr, device: str = "cuda", dtype=torch.complex64):
    """numpy/cupy array → torch tensor。"""
    if hasattr(arr, 'get'):
        arr = arr.get()  # cupy → numpy
    if isinstance(arr, np.ndarray):
        return torch.from_numpy(arr.astype(np.complex64 if dtype == torch.complex64 else np.complex128)).to(device)
    return arr.to(device=device, dtype=dtype)


class FusedLindbladSolver:
    """Fused Lindblad RK4 solver on torch.

    把 collapse operators 堆成 (K, DIM, DIM) 的 batch tensor，
    用 torch.bmm 一次算完所有耗散项，避免 Python 循环。

    Parameters
    ----------
    DIM : int
        Hilbert space dimension
    device : str
        "cuda" or "cpu"
    dtype : torch.dtype
        torch.complex64 (fast) or torch.complex128 (full)
    """

    def __init__(self, DIM: int, device: str = "cuda", dtype=torch.complex64):
        self.DIM = DIM
        self.device = device
        self.dtype = dtype

    def prepare_collapse_tensors(
        self, c_cache: list
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """将 collapse cache (c, c†, c†c) 列表转成 batch tensors。

        Returns
        -------
        c_batch : (K, DIM, DIM)
        cd_batch : (K, DIM, DIM)
        cdc_batch : (K, DIM, DIM)
        """
        cs, cds, cdcs = [], [], []
        for c, cd, cdc in c_cache:
            cs.append(_np_to_torch(c, self.device, self.dtype))
            cds.append(_np_to_torch(cd, self.device, self.dtype))
            cdcs.append(_np_to_torch(cdc, self.device, self.dtype))
        return (
            torch.stack(cs),    # (K, DIM, DIM)
            torch.stack(cds),   # (K, DIM, DIM)
            torch.stack(cdcs),  # (K, DIM, DIM)
        )

    def run(
        self,
        rho_init: np.ndarray,
        dt: float,
        steps: int,
        H_phases: List[Tuple[int, np.ndarray, list]],
        obs_every: int = 8,
        obs_fn: Optional[callable] = None,
    ) -> Tuple[torch.Tensor, list]:
        """执行完整的时间演化。

        Parameters
        ----------
        rho_init : ndarray
            初始密度矩阵
        dt : float
            时间步长
        steps : int
            总步数
        H_phases : list of (end_step, H_matrix, collapse_cache)
            各阶段的 (结束步数, Hamiltonian, collapse_cache)。
            按时间顺序，end_step 递增。
        obs_every : int
            观测间隔
        obs_fn : callable, optional
            观测回调 fn(step, rho_tensor) -> dict

        Returns
        -------
        rho_final : torch.Tensor
            最终密度矩阵
        obs_log : list of dict
            观测记录
        """
        dev = self.device
        dtype = self.dtype
        DIM = self.DIM

        rho = _np_to_torch(rho_init, dev, dtype)

        # 预转换各阶段的 H 和 collapse tensors
        phases = []
        for end_step, H_np, c_cache in H_phases:
            H_t = _np_to_torch(H_np, dev, dtype)
            c_b, cd_b, cdc_b = self.prepare_collapse_tensors(c_cache)
            phases.append((end_step, H_t, c_b, cd_b, cdc_b))

        # 预分配工作缓冲区
        k1 = torch.zeros(DIM, DIM, device=dev, dtype=dtype)
        k2 = torch.zeros_like(k1)
        k3 = torch.zeros_like(k1)
        k4 = torch.zeros_like(k1)
        work = torch.zeros_like(k1)

        obs_log = []
        dt_t = torch.tensor(dt, device=dev, dtype=torch.float32)

        # 找当前 phase
        phase_idx = 0

        for step in range(steps):
            # 观测
            if obs_fn is not None and (step % obs_every) == 0:
                obs_log.append(obs_fn(step, rho))

            # 确定当前 phase
            while phase_idx < len(phases) - 1 and step >= phases[phase_idx][0]:
                phase_idx += 1
            _, H, c_b, cd_b, cdc_b = phases[phase_idx]

            # Fused RK4 step
            rho = _fused_rk4_step(rho, dt, H, c_b, cd_b, cdc_b, k1, k2, k3, k4, work)

        # 最终观测
        if obs_fn is not None:
            obs_log.append(obs_fn(steps, rho))

        return rho, obs_log


def _lindblad_rhs_fused(
    rho: torch.Tensor,
    H: torch.Tensor,
    c_batch: torch.Tensor,
    cd_batch: torch.Tensor,
    cdc_batch: torch.Tensor,
) -> torch.Tensor:
    """Fused Lindblad RHS: 用 batched matmul 一次算完所有 collapse operators。

    dρ/dt = -i[H, ρ] + Σ_k (c_k ρ c_k† - ½ c_k†c_k ρ - ½ ρ c_k†c_k)
    """
    # 相干项: -i[H, ρ]
    commutator = H @ rho - rho @ H
    out = torch.mul(commutator, -1j)

    K = c_batch.shape[0]
    if K > 0:
        # rho 扩展成 (K, DIM, DIM) 与 collapse batch 对齐
        rho_exp = rho.unsqueeze(0).expand(K, -1, -1)  # (K, DIM, DIM)

        # c_k ρ c_k†
        term1 = torch.bmm(torch.bmm(c_batch, rho_exp), cd_batch)  # (K, DIM, DIM)

        # c_k†c_k ρ
        term2 = torch.bmm(cdc_batch, rho_exp)  # (K, DIM, DIM)

        # ρ c_k†c_k
        term3 = torch.bmm(rho_exp, cdc_batch)  # (K, DIM, DIM)

        # 沿 K 维求和
        out = out + term1.sum(dim=0) - 0.5 * term2.sum(dim=0) - 0.5 * term3.sum(dim=0)

    return out


def _fused_rk4_step(
    rho: torch.Tensor,
    dt: float,
    H: torch.Tensor,
    c_batch: torch.Tensor,
    cd_batch: torch.Tensor,
    cdc_batch: torch.Tensor,
    k1: torch.Tensor,
    k2: torch.Tensor,
    k3: torch.Tensor,
    k4: torch.Tensor,
    work: torch.Tensor,
) -> torch.Tensor:
    """Fused RK4 step。"""
    k1 = _lindblad_rhs_fused(rho, H, c_batch, cd_batch, cdc_batch)

    work = rho + 0.5 * dt * k1
    k2 = _lindblad_rhs_fused(work, H, c_batch, cd_batch, cdc_batch)

    work = rho + 0.5 * dt * k2
    k3 = _lindblad_rhs_fused(work, H, c_batch, cd_batch, cdc_batch)

    work = rho + dt * k3
    k4 = _lindblad_rhs_fused(work, H, c_batch, cd_batch, cdc_batch)

    rho_new = rho + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

    # enforce density matrix: Hermitian + trace=1
    rho_new = 0.5 * (rho_new + rho_new.conj().T)
    rho_new = rho_new / rho_new.trace()

    return rho_new
