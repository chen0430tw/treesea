"""
iqpu_hw.py  —  硬件加速 IQPU 变体

在标准 IQPU 的基础上，将 density matrix（rho）的存储从普通
numpy 内存换成内核驱动分配的**物理连续内存**：

    * rho 不会被 Windows 换页或碎片化
    * 物理地址可直接注册给 CUDA（cuMemHostRegister），
      GPU DMA 传输时无需 bounce buffer
    * 绑定到指定 NUMA 节点，减少跨 socket 内存访问

使用前提
--------
1. 以管理员权限运行 qcu_loader.exe qcu_kdrv.sys
2. \\.\QcuKdrv 设备节点可用

Usage
-----
    from qcu.qcu.core.state_repr import IQPUConfig
    from qcu.qcu.core.hardware_bridge import QcuKernelBridge
    from qcu.qcu.core.iqpu_hw import IQPUHardware

    bridge = QcuKernelBridge()
    cfg    = IQPUConfig(Nq=2, Nm=2, d=6)
    iqpu   = IQPUHardware(cfg, bridge, numa_node=0)

    result = iqpu.run_qcl_v6(
        label="hw_test",
        t1=3.0, t2=5.0, omega_x=1.0,
        gamma_pcm=0.2, gamma_qim=0.03,
        gamma_boost=0.9, boost_duration=3.0,
        gamma_reset=0.25, gamma_phi0=0.6,
        eps_boost=4.0, boost_phase_trim=0.012,
    )
    print(result)
    bridge.close()
"""

from __future__ import annotations

import numpy as np

from .hardware_bridge import QcuKernelBridge, AllocInfo, QCU_PMC_L3_MISS, QCU_PMC_CYCLES, QCU_PMC_INSTRET
from .iqpu_runtime import IQPU
from .state_repr import IQPUConfig, IQPURunResult


class IQPUHardware(IQPU):
    """
    IQPU 变体：density matrix 存活在内核分配的物理连续内存中。

    Parameters
    ----------
    cfg       : IQPUConfig
    bridge    : QcuKernelBridge（调用者负责其生命周期）
    numa_node : NUMA 节点编号（0xFFFFFFFF = 任意）
    """

    def __init__(
        self,
        cfg:       IQPUConfig,
        bridge:    QcuKernelBridge,
        numa_node: int = 0xFFFF_FFFF,
    ) -> None:
        self.bridge    = bridge
        self.numa_node = numa_node

        # 物理内存分配信息（run 期间填充）
        self._alloc:   AllocInfo | None = None
        self._rho_phys: np.ndarray | None = None

        # 调用父类 __init__（构建算符库、RK4 缓冲区等）
        super().__init__(cfg)

    # ── 物理内存管理 ──────────────────────────────────────────────

    def _alloc_rho_physical(self) -> np.ndarray:
        """
        在内核分配 DIM×DIM complex128 矩阵所需的物理连续内存，
        映射到用户态并返回零初始化的 numpy 数组。

        complex128 = 16 字节；建议 2 MB 对齐。
        """
        size = self.DIM * self.DIM * 16   # complex128 per element
        # 向上对齐到 2 MB
        align = 2 * 1024 * 1024
        size  = (size + align - 1) & ~(align - 1)

        alloc = self.bridge.alloc_physical(size, numa_node=self.numa_node)
        arr   = self.bridge.map_to_numpy(alloc.handle, alloc.size, dtype=np.complex128)
        arr   = arr.reshape(self.DIM, self.DIM)
        arr[:] = 0.0

        self._alloc      = alloc
        self._rho_phys   = arr
        return arr

    def _free_rho_physical(self) -> None:
        """释放物理内存（unmap + free）。"""
        if self._rho_phys is not None:
            self.bridge.unmap_from_user(self._rho_phys.ravel())
            self._rho_phys = None
        if self._alloc is not None:
            self.bridge.free_physical(self._alloc.handle)
            self._alloc = None

    @property
    def phys_addr(self) -> int | None:
        """
        density matrix 的物理起始地址（GPU DMA 注册用）。

        在 run_qcl_v6_hw() 期间有效；调用 free_rho_physical() 后失效。
        """
        return self._alloc.phys_addr if self._alloc else None

    # ── 硬件加速运行接口 ──────────────────────────────────────────

    def run_qcl_v6_hw(
        self,
        label:            str,
        t1:               float,
        t2:               float,
        omega_x:          float,
        gamma_pcm:        float,
        gamma_qim:        float,
        gamma_boost:      float,
        boost_duration:   float,
        gamma_reset:      float,
        gamma_phi0:       float,
        eps_boost:        float,
        boost_phase_trim: float,
        keep_rho:         bool = False,
    ) -> IQPURunResult:
        """
        与 IQPU.run_qcl_v6() 完全相同的协议，
        但 density matrix 存储在物理连续内存中。

        Parameters
        ----------
        keep_rho : bool
            True → 运行结束后保留物理内存映射（便于 GPU DMA）；
                     调用者负责稍后调用 free_rho_physical()。
            False → 自动释放（默认）。
        """
        # 分配物理 rho
        rho = self._alloc_rho_physical()

        # 读取运行前 PMC 基准值
        pmc_cycles_before = self.bridge.read_pmc(QCU_PMC_CYCLES, cpu_index=0)
        pmc_l3_before     = self.bridge.read_pmc(QCU_PMC_L3_MISS, cpu_index=0)

        # 执行 QCL v6 — 复用父类逻辑，但把 rho_initial 注入
        # 父类 run_qcl_v6 每次都会在内部 build_initial_state 重新分配 rho；
        # 这里我们 patch 使其直接使用我们提供的物理内存。
        result = self._run_with_preallocated_rho(
            rho_buf=rho,
            label=label,
            t1=t1, t2=t2, omega_x=omega_x,
            gamma_pcm=gamma_pcm, gamma_qim=gamma_qim,
            gamma_boost=gamma_boost, boost_duration=boost_duration,
            gamma_reset=gamma_reset, gamma_phi0=gamma_phi0,
            eps_boost=eps_boost, boost_phase_trim=boost_phase_trim,
        )

        # PMC 差值
        pmc_cycles_after = self.bridge.read_pmc(QCU_PMC_CYCLES, cpu_index=0)
        pmc_l3_after     = self.bridge.read_pmc(QCU_PMC_L3_MISS, cpu_index=0)

        result.extra["hw_cycles"]   = pmc_cycles_after - pmc_cycles_before
        result.extra["hw_l3_miss"]  = pmc_l3_after - pmc_l3_before
        result.extra["phys_addr"]   = f"0x{self.phys_addr:016X}" if self.phys_addr else None
        result.extra["numa_node"]   = self.numa_node

        if not keep_rho:
            self._free_rho_physical()

        return result

    def _run_with_preallocated_rho(
        self,
        rho_buf: np.ndarray,
        **kwargs,
    ) -> IQPURunResult:
        """
        内部：用已分配好的 rho_buf 作为初态缓冲区，
        调用父类 run_qcl_v6()。

        实现方式：暂时 monkey-patch build_initial_state，
        使其返回我们的物理内存缓冲区而不是重新分配。
        """
        import qcu.qcu.core.state_repr as _sr
        _orig = _sr.build_initial_state

        cfg = self.cfg

        def _patched_build(c, xp=None):
            # 初始化 |0⟩ 态 — qubit 0 激发，其余基态
            rho_buf[:] = 0.0
            rho_buf[0, 0] = 1.0
            return rho_buf

        _sr.build_initial_state = _patched_build
        try:
            result = self.run_qcl_v6(**kwargs)
        finally:
            _sr.build_initial_state = _orig

        return result

    # ── 清理 ─────────────────────────────────────────────────────

    def __del__(self) -> None:
        self._free_rho_physical()
