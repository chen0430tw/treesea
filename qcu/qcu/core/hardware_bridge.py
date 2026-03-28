"""
hardware_bridge.py  —  Python ctypes bridge to QCU kernel driver

Wraps all 7 IOCTL calls exposed by qcu_kdrv.sys.
The driver must already be loaded (via qcu_loader.exe) before instantiating.

Usage:
    bridge = QcuKernelBridge()
    handle, phys_addr, size = bridge.alloc_physical(256 * 1024 * 1024)  # 256 MB
    arr = bridge.map_to_numpy(handle, size)          # zero-copy numpy view
    arr[:] = 0.0                                     # write into physical memory
    bridge.unmap_from_user(arr)
    bridge.free_physical(handle)
    bridge.close()
"""

import ctypes
import ctypes.wintypes as wt
import struct
import numpy as np
from dataclasses import dataclass

# ── Windows constants ──────────────────────────────────────────────
GENERIC_READ  = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# ── IOCTL codes  (must match qcu_kdrv.h CTL_CODE expansion) ───────
#   CTL_CODE(DeviceType, Function, Method, Access)
#   = (DeviceType << 16) | (Access << 14) | (Function << 2) | Method
#
#   QCU_DEVICE_TYPE = 0x8000
#   METHOD_BUFFERED = 0
#   FILE_ANY_ACCESS = 0
#
#   => code = (0x8000 << 16) | (0 << 14) | (func << 2) | 0
#           = 0x8000_0000 | (func << 2)
def _ctl(func: int) -> int:
    return (0x8000 << 16) | (func << 2)

IOCTL_QCU_ALLOC_PHYSICAL  = _ctl(0x801)   # 0x80002004
IOCTL_QCU_FREE_PHYSICAL   = _ctl(0x802)   # 0x80002008
IOCTL_QCU_MAP_TO_USER     = _ctl(0x803)   # 0x8000200C
IOCTL_QCU_UNMAP_FROM_USER = _ctl(0x804)   # 0x80002010
IOCTL_QCU_GET_NUMA_INFO   = _ctl(0x805)   # 0x80002014
IOCTL_QCU_READ_PMC        = _ctl(0x806)   # 0x80002018
IOCTL_QCU_QUERY_STATUS    = _ctl(0x807)   # 0x8000201C

QCU_USERMODE_PATH = r"\\.\QcuKdrv"

# ── Struct definitions (must match qcu_kdrv.h byte-for-byte) ──────
class _AllocRequest(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("size_bytes", ctypes.c_uint64),
        ("numa_node",  ctypes.c_uint32),
        ("flags",      ctypes.c_uint32),
    ]

class _AllocResponse(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("kernel_va",  ctypes.c_uint64),
        ("phys_addr",  ctypes.c_uint64),
        ("size_bytes", ctypes.c_uint64),
        ("handle",     ctypes.c_uint64),
    ]

class _FreeRequest(ctypes.Structure):
    _pack_ = 8
    _fields_ = [("handle", ctypes.c_uint64)]

class _MapRequest(ctypes.Structure):
    _pack_ = 8
    _fields_ = [("handle", ctypes.c_uint64)]

class _MapResponse(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("user_va",    ctypes.c_uint64),
        ("size_bytes", ctypes.c_uint64),
    ]

class _UnmapRequest(ctypes.Structure):
    _pack_ = 8
    _fields_ = [("user_va", ctypes.c_uint64)]

QCU_MAX_NUMA_NODES = 8

class _NumaInfo(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("node_count",          ctypes.c_uint32),
        ("current_node",        ctypes.c_uint32),
        ("node_memory_bytes",   ctypes.c_uint64 * QCU_MAX_NUMA_NODES),
        ("cpu_count_per_node",  ctypes.c_uint32 * QCU_MAX_NUMA_NODES),
    ]

QCU_PMC_L3_MISS  = 0
QCU_PMC_TLB_MISS = 1
QCU_PMC_CYCLES   = 2
QCU_PMC_INSTRET  = 3

class _PmcRequest(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("counter_id", ctypes.c_uint32),
        ("cpu_index",  ctypes.c_uint32),
    ]

class _PmcResponse(ctypes.Structure):
    _pack_ = 8
    _fields_ = [("value", ctypes.c_uint64)]

class _Status(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("version",           ctypes.c_uint32),
        ("active_allocs",     ctypes.c_uint32),
        ("total_alloc_bytes", ctypes.c_uint64),
        ("numa_nodes",        ctypes.c_uint32),
        ("reserved",          ctypes.c_uint32),
    ]

# ── Return-value dataclasses ───────────────────────────────────────
@dataclass
class AllocInfo:
    handle:    int
    phys_addr: int
    size:      int
    kernel_va: int   # opaque, for debugging

@dataclass
class NumaInfo:
    node_count:          int
    current_node:        int
    node_memory_bytes:   list[int]   # one entry per node
    cpu_count_per_node:  list[int]

@dataclass
class DriverStatus:
    version:           int    # 0x00010000 = v1.0
    active_allocs:     int
    total_alloc_bytes: int
    numa_nodes:        int

# ── Bridge class ───────────────────────────────────────────────────
class QcuKernelBridge:
    """
    User-mode Python interface to qcu_kdrv.sys.

    Lifecycle:
        bridge = QcuKernelBridge()    # opens \\.\QcuKdrv
        ...
        bridge.close()                # releases the handle
    """

    def __init__(self, path: str = QCU_USERMODE_PATH):
        k32 = ctypes.windll.kernel32
        self._handle = k32.CreateFileW(
            path,
            GENERIC_READ | GENERIC_WRITE,
            0,                          # no sharing
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if self._handle == INVALID_HANDLE_VALUE:
            err = k32.GetLastError()
            raise OSError(
                f"Cannot open {path}: Win32 error {err:#010x}. "
                f"Is qcu_loader.exe already run as Admin?"
            )
        # keep a map of user_va → (numpy_array, size) for unmap
        self._mapped: dict[int, tuple[np.ndarray, int]] = {}

    # ── Internal IOCTL helper ──────────────────────────────────────
    def _ioctl(self,
               code: int,
               in_buf:  ctypes.Structure | None,
               out_type: type | None) -> ctypes.Structure | None:
        k32 = ctypes.windll.kernel32

        in_ptr  = ctypes.addressof(in_buf)  if in_buf  is not None else None
        in_size = ctypes.sizeof(in_buf)     if in_buf  is not None else 0

        if out_type is not None:
            out_buf  = out_type()
            out_ptr  = ctypes.addressof(out_buf)
            out_size = ctypes.sizeof(out_buf)
        else:
            out_buf = out_ptr = None
            out_size = 0

        bytes_returned = wt.DWORD(0)
        ok = k32.DeviceIoControl(
            self._handle,
            code,
            in_ptr,  in_size,
            out_ptr, out_size,
            ctypes.byref(bytes_returned),
            None,
        )
        if not ok:
            err = k32.GetLastError()
            raise OSError(f"DeviceIoControl(0x{code:08X}) failed: Win32 error {err:#010x}")

        return out_buf

    # ── IOCTL_QCU_ALLOC_PHYSICAL ───────────────────────────────────
    def alloc_physical(self,
                       size_bytes: int,
                       numa_node:  int = 0xFFFF_FFFF,
                       large_page: bool = False) -> AllocInfo:
        """
        Allocate physically contiguous memory in the kernel.

        Args:
            size_bytes: Requested size.  2 MB alignment recommended.
            numa_node:  NUMA node preference (0xFFFFFFFF = any).
            large_page: If True, request 2 MB large-page backing.

        Returns:
            AllocInfo with handle (pass to free/map), phys_addr for GPU DMA.
        """
        req = _AllocRequest(
            size_bytes=size_bytes,
            numa_node=numa_node,
            flags=1 if large_page else 0,
        )
        resp: _AllocResponse = self._ioctl(IOCTL_QCU_ALLOC_PHYSICAL, req, _AllocResponse)
        return AllocInfo(
            handle=resp.handle,
            phys_addr=resp.phys_addr,
            size=resp.size_bytes,
            kernel_va=resp.kernel_va,
        )

    # ── IOCTL_QCU_FREE_PHYSICAL ────────────────────────────────────
    def free_physical(self, handle: int) -> None:
        """Free a previously allocated physical buffer."""
        req = _FreeRequest(handle=handle)
        self._ioctl(IOCTL_QCU_FREE_PHYSICAL, req, None)

    # ── IOCTL_QCU_MAP_TO_USER ──────────────────────────────────────
    def _map_to_user(self, handle: int) -> tuple[int, int]:
        """Return (user_va, size_bytes) mapped into this process."""
        req  = _MapRequest(handle=handle)
        resp: _MapResponse = self._ioctl(IOCTL_QCU_MAP_TO_USER, req, _MapResponse)
        return resp.user_va, resp.size_bytes

    def map_to_numpy(self,
                     handle:     int,
                     size_bytes: int | None = None,
                     dtype: type = np.complex128) -> np.ndarray:
        """
        Map the physical buffer into this process and wrap it as a numpy array.

        The returned array is a *zero-copy view* of physical memory —
        no data movement occurs.  The physical address is suitable for
        cuMemHostRegister() (GPU DMA without bounce buffer).

        Args:
            handle:     from alloc_physical().handle
            size_bytes: expected size (for validation); if None, trust driver
            dtype:      numpy dtype for the resulting array

        Returns:
            1-D numpy array of `dtype` backed by the physical memory.
        """
        user_va, mapped_size = self._map_to_user(handle)
        if size_bytes is not None and mapped_size != size_bytes:
            raise ValueError(
                f"Mapped size mismatch: expected {size_bytes}, got {mapped_size}"
            )

        buf = (ctypes.c_byte * mapped_size).from_address(user_va)
        arr = np.frombuffer(buf, dtype=dtype)
        # Keep buf alive via arr base — ctypes objects are kept alive by numpy
        self._mapped[user_va] = (arr, mapped_size)
        return arr

    # ── IOCTL_QCU_UNMAP_FROM_USER ──────────────────────────────────
    def unmap_from_user(self, arr: np.ndarray) -> None:
        """
        Unmap a buffer previously mapped with map_to_numpy().

        After this call, `arr` must not be accessed.
        """
        # Recover user_va from the ctypes buffer backing the array
        buf  = arr.base       # ctypes array
        va   = ctypes.addressof(buf)
        req  = _UnmapRequest(user_va=va)
        self._ioctl(IOCTL_QCU_UNMAP_FROM_USER, req, None)
        self._mapped.pop(va, None)

    # ── IOCTL_QCU_GET_NUMA_INFO ────────────────────────────────────
    def get_numa_info(self) -> NumaInfo:
        """Query NUMA topology of the current machine."""
        resp: _NumaInfo = self._ioctl(IOCTL_QCU_GET_NUMA_INFO, None, _NumaInfo)
        n = resp.node_count
        return NumaInfo(
            node_count=n,
            current_node=resp.current_node,
            node_memory_bytes=list(resp.node_memory_bytes[:n]),
            cpu_count_per_node=list(resp.cpu_count_per_node[:n]),
        )

    # ── IOCTL_QCU_READ_PMC ─────────────────────────────────────────
    def read_pmc(self, counter_id: int, cpu_index: int = 0) -> int:
        """
        Read a hardware performance counter on the specified CPU.

        Args:
            counter_id: QCU_PMC_L3_MISS / QCU_PMC_TLB_MISS /
                        QCU_PMC_CYCLES / QCU_PMC_INSTRET
            cpu_index:  Logical CPU index (0 = current CPU when DPC fires)

        Returns:
            64-bit counter value.
        """
        req  = _PmcRequest(counter_id=counter_id, cpu_index=cpu_index)
        resp: _PmcResponse = self._ioctl(IOCTL_QCU_READ_PMC, req, _PmcResponse)
        return resp.value

    # ── IOCTL_QCU_QUERY_STATUS ─────────────────────────────────────
    def query_status(self) -> DriverStatus:
        """Return driver health / statistics."""
        resp: _Status = self._ioctl(IOCTL_QCU_QUERY_STATUS, None, _Status)
        return DriverStatus(
            version=resp.version,
            active_allocs=resp.active_allocs,
            total_alloc_bytes=resp.total_alloc_bytes,
            numa_nodes=resp.numa_nodes,
        )

    # ── Context manager ────────────────────────────────────────────
    def close(self) -> None:
        """Release the handle to the driver device."""
        if self._handle and self._handle != INVALID_HANDLE_VALUE:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __repr__(self) -> str:
        try:
            st = self.query_status()
            v  = st.version
            return (
                f"QcuKernelBridge(v{v>>16}.{v&0xFFFF}, "
                f"allocs={st.active_allocs}, "
                f"total={st.total_alloc_bytes >> 20} MB)"
            )
        except OSError:
            return "QcuKernelBridge(closed)"
