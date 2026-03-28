# QCU 内核驱动设计文档

## 1. 目标

让 QCU（IQPU Lindblad 模拟器）通过内核驱动直接耦合物理硬件，绕过 Windows 用户态内存管理的开销，获得：

- 物理连续内存（density matrix 不被换页/碎片化）
- NUMA 感知缓冲区分配（RK4 缓冲区绑到正确 socket）
- 硬件 PMU 计数器（追踪 cache miss / TLB miss / IPC）
- GPU DMA 直通（density matrix 直接 DMA 到 GPU，省 bounce buffer）

加载方式：**kdmapper**（开发阶段，无需 test signing / WHQL）

---

## 2. 加载流程

```
[qcu_loader.exe]
    │  读取 qcu_kdrv.sys 到内存
    │  调用 kdmapper::MapDriver(raw_image)
    ▼
[iqvw64e.sys]  ← Intel 漏洞驱动（kdmapper 自带）
    │  任意内核读写原语
    │  将 qcu_kdrv.sys PE 手动映射到内核池
    │  调用 CustomDriverEntry()
    ▼
[qcu_kdrv.sys 运行于 Ring 0]
    │  IoCreateDevice → \Device\QcuKdrv
    │  IoCreateSymbolicLink → \DosDevices\QcuKdrv
    │  注册 IRP_MJ_DEVICE_CONTROL 处理器
    ▼
[用户态 qcu_kbridge.py]
    │  CreateFile("\\.\QcuKdrv")
    │  DeviceIoControl(IOCTL_*)
    ▼
[Python IQPU]
    │  ctypes 调用 bridge
    │  numpy 数组直接指向内核映射的物理内存
```

---

## 3. 驱动文件结构

```
qcu/kdriver/
├── kdmapper/               ← TheCruZ/kdmapper 原版（已 clone）
├── qcu_kdrv/
│   ├── qcu_kdrv.h          ← 共享头（IOCTL 定义，用户态+内核态都 include）
│   ├── qcu_kdrv.c          ← 驱动主体
│   └── qcu_kdrv.vcxproj    ← VS2022 内核驱动项目
├── qcu_loader/
│   ├── loader.cpp          ← 调用 kdmapper::MapDriver 的加载器
│   └── qcu_loader.vcxproj
└── qcu_kdriver.sln         ← 整体解决方案
```

Python 侧：
```
qcu/qcu/core/
├── hardware_bridge.py      ← ctypes 桥，封装所有 IOCTL
└── iqpu_hw.py              ← 硬件加速 IQPU 变体（继承 IQPU）
```

---

## 4. IOCTL 接口定义

设备名：`\\.\QcuKdrv`

```c
// FILE: qcu_kdrv.h（用户态和内核态共用）

#define QCU_DEVICE_TYPE  0x8000

#define IOCTL_QCU_ALLOC_PHYSICAL   CTL_CODE(QCU_DEVICE_TYPE, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_QCU_FREE_PHYSICAL    CTL_CODE(QCU_DEVICE_TYPE, 0x802, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_QCU_MAP_TO_USER      CTL_CODE(QCU_DEVICE_TYPE, 0x803, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_QCU_UNMAP_FROM_USER  CTL_CODE(QCU_DEVICE_TYPE, 0x804, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_QCU_GET_NUMA_INFO    CTL_CODE(QCU_DEVICE_TYPE, 0x805, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_QCU_READ_PMC         CTL_CODE(QCU_DEVICE_TYPE, 0x806, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_QCU_QUERY_STATUS     CTL_CODE(QCU_DEVICE_TYPE, 0x807, METHOD_BUFFERED, FILE_ANY_ACCESS)

// IOCTL_QCU_ALLOC_PHYSICAL
typedef struct _QCU_ALLOC_REQUEST {
    ULONG64 size_bytes;     // 请求分配大小（建议 2MB 对齐）
    ULONG   numa_node;      // 0xFFFFFFFF = 任意节点
    ULONG   flags;          // 0 = 默认，1 = 要求 2MB 大页
} QCU_ALLOC_REQUEST;

typedef struct _QCU_ALLOC_RESPONSE {
    ULONG64 kernel_va;      // 内核虚拟地址
    ULONG64 physical_addr;  // 物理地址（用于 GPU DMA）
    ULONG64 size_bytes;     // 实际分配大小
    ULONG64 handle;         // 释放时需要传回的句柄
} QCU_ALLOC_RESPONSE;

// IOCTL_QCU_MAP_TO_USER
typedef struct _QCU_MAP_REQUEST {
    ULONG64 handle;         // 来自 ALLOC_RESPONSE
} QCU_MAP_REQUEST;

typedef struct _QCU_MAP_RESPONSE {
    ULONG64 user_va;        // 用户态可访问的虚拟地址
} QCU_MAP_RESPONSE;

// IOCTL_QCU_GET_NUMA_INFO
typedef struct _QCU_NUMA_INFO {
    ULONG   node_count;
    ULONG   current_node;
    ULONG64 node_memory_bytes[8];   // 最多 8 个 NUMA 节点
    ULONG   cpu_count_per_node[8];
} QCU_NUMA_INFO;

// IOCTL_QCU_READ_PMC
typedef struct _QCU_PMC_REQUEST {
    ULONG   counter_id;     // 0=L3_CACHE_MISS, 1=TLB_MISS, 2=IPC_CYCLES, 3=IPC_INSTR
} QCU_PMC_REQUEST;

typedef struct _QCU_PMC_RESPONSE {
    ULONG64 value;
} QCU_PMC_RESPONSE;
```

---

## 5. 内核驱动实现要点（qcu_kdrv.c）

### 5.1 入口（kdmapper 专用）

```c
// 不是 DriverEntry，是 CustomDriverEntry
NTSTATUS CustomDriverEntry(
    PDRIVER_OBJECT  DriverObject,   // kdmapper 传入的伪造对象，可用
    PUNICODE_STRING RegistryPath    // 伪造，忽略
) {
    // 1. 创建设备对象
    IoCreateDevice(..., L"\\Device\\QcuKdrv", ...);
    IoCreateSymbolicLink(L"\\DosDevices\\QcuKdrv", L"\\Device\\QcuKdrv");

    // 2. 注册 IRP 处理器
    DriverObject->MajorFunction[IRP_MJ_CREATE]         = QcuCreate;
    DriverObject->MajorFunction[IRP_MJ_CLOSE]          = QcuClose;
    DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL] = QcuDeviceControl;
    DriverObject->DriverUnload = QcuUnload;

    // 3. 初始化分配表（链表，管理所有已分配的物理内存块）
    InitializeListHead(&g_alloc_list);
    KeInitializeSpinLock(&g_alloc_lock);
}
```

### 5.2 物理内存分配

```c
// IOCTL_QCU_ALLOC_PHYSICAL 处理
PHYSICAL_ADDRESS max_addr = { .QuadPart = MAXLONGLONG };
PVOID kernel_va = MmAllocateContiguousMemorySpecifyCache(
    req->size_bytes,
    zero_addr,          // lowest acceptable physical address
    max_addr,           // highest acceptable
    zero_addr,          // boundary (0 = no boundary)
    MmCached            // cache type
);
// MmGetPhysicalAddress(kernel_va) → 返回物理地址给用户态
```

### 5.3 映射到用户态

```c
// IOCTL_QCU_MAP_TO_USER 处理
// 方式：MDL（Memory Descriptor List）
PMDL mdl = IoAllocateMdl(kernel_va, size, FALSE, FALSE, NULL);
MmBuildMdlForNonPagedPool(mdl);
PVOID user_va = MmMapLockedPagesSpecifyCache(
    mdl,
    UserMode,
    MmCached,
    NULL, FALSE,
    NormalPagePriority | MdlMappingNoExecute
);
// 返回 user_va 给 Python
```

### 5.4 NUMA 信息

```c
// IOCTL_QCU_GET_NUMA_INFO
ULONG highest_node;
KeQueryHighestNodeNumber(&highest_node);
for (ULONG node = 0; node <= highest_node; node++) {
    ULONGLONG avail;
    KeQueryNodeActiveAffinity(node, NULL, NULL);
    MmQuerySystemSize();  // 配合 KeQueryLogicalProcessorRelationship
}
```

### 5.5 PMU 计数器

```c
// IOCTL_QCU_READ_PMC
// 在目标 CPU 上用 DPC 读取 MSR
KDPC dpc;
KeInitializeDpc(&dpc, QcuReadPmcDpc, context);
KeSetTargetProcessorDpc(&dpc, (CCHAR)target_cpu);
KeInsertQueueDpc(&dpc, NULL, NULL);
// DPC 内部：__readmsr(0xC1 + counter_id)  或 __readpmc(counter_id)
```

---

## 6. Python 桥（hardware_bridge.py）

```python
import ctypes
import numpy as np

IOCTL_QCU_ALLOC_PHYSICAL = 0x8000_2004  # CTL_CODE 展开值
IOCTL_QCU_MAP_TO_USER    = 0x8000_200C

class QcuKernelBridge:
    def __init__(self):
        self.handle = ctypes.windll.kernel32.CreateFileW(
            r"\\.\QcuKdrv",
            0xC0000000,  # GENERIC_READ | GENERIC_WRITE
            0, None, 3, 0, None
        )

    def alloc_physical(self, size_bytes, numa_node=0xFFFFFFFF):
        # DeviceIoControl → 返回 (kernel_va, phys_addr, handle)
        ...

    def map_to_numpy(self, handle, size_bytes, dtype=np.complex128):
        # map_to_user → 用 ctypes.from_address 包成 numpy array
        user_va = self._map_to_user(handle)
        arr = np.frombuffer(
            (ctypes.c_byte * size_bytes).from_address(user_va),
            dtype=dtype
        )
        return arr
```

---

## 7. IQPU 集成（iqpu_hw.py）

```python
class IQPUHardware(IQPU):
    """IQPU 变体：density matrix 分配在内核物理连续内存上。"""

    def __init__(self, cfg, bridge: QcuKernelBridge):
        self.bridge = bridge
        super().__init__(cfg)

    def _alloc_rho(self):
        size = self.DIM ** 2 * 16  # complex128 = 16 bytes
        handle, phys = self.bridge.alloc_physical(size, numa_node=0)
        rho_np = self.bridge.map_to_numpy(handle, size)
        rho_np[:] = 0.0
        return rho_np, handle, phys

    def run_qcl_v6_hw(self, ...):
        rho, handle, phys_addr = self._alloc_rho()
        # phys_addr 可直接传给 CUDA cuMemHostRegister 做 GPU DMA
        # 其余逻辑与 IQPU.run_qcl_v6 相同
        ...
```

---

## 8. 构建环境

| 工具 | 版本 |
|------|------|
| Visual Studio | 2022 |
| WDK | Windows 11 SDK + WDK 10.0.26100 |
| 目标平台 | x64, Windows 10 19041+ |
| 运行时库 | 无 CRT（内核驱动不链接 ucrt） |
| 优化 | /O2 /kernel |

编译顺序：
1. 编译 `qcu_kdrv.vcxproj` → 生成 `qcu_kdrv.sys`
2. 编译 `qcu_loader.vcxproj` → 生成 `qcu_loader.exe`（内嵌 kdmapper 逻辑）
3. 运行 `qcu_loader.exe qcu_kdrv.sys` → 驱动加载完成
4. Python 侧 `QcuKernelBridge()` 打开 `\\.\QcuKdrv`

---

## 9. 关键风险与限制

| 风险 | 说明 |
|------|------|
| iqvw64e.sys blocklist | 微软持续更新阻止列表，部分 Win11 23H2+ 可能拦截 |
| BSOD | 内核 bug 直接蓝屏，调试用 WinDbg + VMware |
| 驱动卸载 | kdmapper 加载的驱动没有注册表项，重启自动消失（正好） |
| 内存泄漏 | DriverUnload 必须 MmFreeContiguousMemory 所有分配块 |
| 多进程 | 当前设计单进程独占，需要加引用计数才能多进程共享 |

---

## 10. 开发顺序

1. `qcu_kdrv.h` — IOCTL 定义（用户态/内核态共用）
2. `qcu_kdrv.c` — 驱动骨架（CustomDriverEntry + 设备创建）
3. `qcu_kdrv.c` — ALLOC_PHYSICAL + MAP_TO_USER 实现
4. `qcu_kdrv.c` — NUMA_INFO + READ_PMC 实现
5. `hardware_bridge.py` — Python ctypes 桥
6. `iqpu_hw.py` — 硬件加速 IQPU 变体
7. 端到端测试：分配 1GB 物理内存 → numpy 读写 → 验证物理地址连续性
