/*
 * qcu_kdrv.c  -  QCU Kernel Driver
 *
 * Loaded via kdmapper (unsigned, no registry entry, disappears on reboot).
 * Entry point: CustomDriverEntry (not DriverEntry).
 *
 * Exposes \Device\QcuKdrv + \DosDevices\QcuKdrv.
 * User-mode opens \\.\QcuKdrv and sends IOCTLs.
 *
 * Capabilities:
 *   - Physically contiguous memory allocation (MmAllocateContiguousMemory)
 *   - MDL-based user-mode mapping (MmMapLockedPagesSpecifyCache)
 *   - NUMA topology query
 *   - Hardware PMC read via DPC (per-CPU MSR access)
 */

#include <ntddk.h>
#include <wdm.h>
#include "qcu_kdrv.h"

/* -- Version ------------------------------------------------------- */
#define QCU_DRIVER_VERSION  0x00010000u  /* 1.0 */
#define QCU_POOL_TAG        'uqCQ'       /* 'QCqu' reversed for pool tag display */

/* -- Allocation tracking ------------------------------------------- */
typedef struct _QCU_ALLOC_ENTRY {
    LIST_ENTRY      list;
    PVOID           kernel_va;
    PHYSICAL_ADDRESS phys_addr;
    SIZE_T          size;
    PMDL            mdl;            /* non-NULL if mapped to user */
    PVOID           user_va;        /* non-NULL if mapped to user */
    ULONG64         handle;         /* == (ULONG64)kernel_va, unique per alloc */
} QCU_ALLOC_ENTRY, *PQCU_ALLOC_ENTRY;

static LIST_ENTRY   g_alloc_list;
static KSPIN_LOCK   g_alloc_lock;
static LONG         g_alloc_count = 0;
static LONG64       g_alloc_bytes = 0;

static PDEVICE_OBJECT g_device_obj = NULL;

/* -- Forward declarations ------------------------------------------ */
static NTSTATUS QcuCreate      (PDEVICE_OBJECT DevObj, PIRP Irp);
static NTSTATUS QcuClose       (PDEVICE_OBJECT DevObj, PIRP Irp);
static NTSTATUS QcuDeviceControl(PDEVICE_OBJECT DevObj, PIRP Irp);
static VOID     QcuUnload      (PDRIVER_OBJECT DriverObj);

static NTSTATUS HandleAllocPhysical (PIRP Irp, PIO_STACK_LOCATION Stack);
static NTSTATUS HandleFreePhysical  (PIRP Irp, PIO_STACK_LOCATION Stack);
static NTSTATUS HandleMapToUser     (PIRP Irp, PIO_STACK_LOCATION Stack);
static NTSTATUS HandleUnmapFromUser (PIRP Irp, PIO_STACK_LOCATION Stack);
static NTSTATUS HandleGetNumaInfo   (PIRP Irp, PIO_STACK_LOCATION Stack);
static NTSTATUS HandleReadPmc       (PIRP Irp, PIO_STACK_LOCATION Stack);
static NTSTATUS HandleQueryStatus   (PIRP Irp, PIO_STACK_LOCATION Stack);

static PQCU_ALLOC_ENTRY FindEntry(ULONG64 handle);

/* -- Helpers ------------------------------------------------------- */
static NTSTATUS CompleteIrp(PIRP Irp, NTSTATUS status, ULONG_PTR info)
{
    Irp->IoStatus.Status      = status;
    Irp->IoStatus.Information = info;
    IoCompleteRequest(Irp, IO_NO_INCREMENT);
    return status;
}

/* -- CustomDriverEntry --------------------------------------------- */
/*
 * kdmapper calls this instead of the standard DriverEntry.
 * DriverObject is a fabricated stub - we can still use it for
 * registering dispatch routines and creating device objects.
 */
NTSTATUS CustomDriverEntry(
    _In_ PDRIVER_OBJECT  DriverObject,
    _In_ PUNICODE_STRING RegistryPath)
{
    UNREFERENCED_PARAMETER(RegistryPath);

    NTSTATUS         status;
    UNICODE_STRING   dev_name, symlink_name;

    /* 0. kdmapper passes DriverObject=NULL (param1=0).
     *    IoCreateDevice needs a valid DRIVER_OBJECT with DriverExtension.
     *    Allocate a minimal fake one from NonPagedPool.
     */
    if (!DriverObject) {
        DriverObject = (PDRIVER_OBJECT)ExAllocatePoolWithTag(
            NonPagedPool, sizeof(DRIVER_OBJECT), 'OvrD');
        if (!DriverObject)
            return STATUS_INSUFFICIENT_RESOURCES;
        RtlZeroMemory(DriverObject, sizeof(DRIVER_OBJECT));
        DriverObject->Type = IO_TYPE_DRIVER;
        DriverObject->Size = sizeof(DRIVER_OBJECT);

        DriverObject->DriverExtension = (PDRIVER_EXTENSION)ExAllocatePoolWithTag(
            NonPagedPool, sizeof(DRIVER_EXTENSION), 'ExtD');
        if (!DriverObject->DriverExtension) {
            ExFreePoolWithTag(DriverObject, 'OvrD');
            return STATUS_INSUFFICIENT_RESOURCES;
        }
        RtlZeroMemory(DriverObject->DriverExtension, sizeof(DRIVER_EXTENSION));
        DriverObject->DriverExtension->DriverObject = DriverObject;
    }

    /* 1. Init allocation tracking */
    InitializeListHead(&g_alloc_list);
    KeInitializeSpinLock(&g_alloc_lock);

    /* 2. Create device object */
    RtlInitUnicodeString(&dev_name, QCU_DEVICE_NAME);
    status = IoCreateDevice(
        DriverObject,
        0,                          /* no device extension needed */
        &dev_name,
        FILE_DEVICE_UNKNOWN,
        FILE_DEVICE_SECURE_OPEN,
        FALSE,
        &g_device_obj);

    if (!NT_SUCCESS(status)) {
        DbgPrintEx(DPFLTR_DEFAULT_ID, DPFLTR_ERROR_LEVEL,
            "[QCU] IoCreateDevice failed: 0x%08X\n", status);
        return status;
    }

    /* 3. Create symbolic link \\.\QcuKdrv */
    RtlInitUnicodeString(&symlink_name, QCU_SYMLINK_NAME);
    status = IoCreateSymbolicLink(&symlink_name, &dev_name);
    if (!NT_SUCCESS(status)) {
        IoDeleteDevice(g_device_obj);
        DbgPrintEx(DPFLTR_DEFAULT_ID, DPFLTR_ERROR_LEVEL,
            "[QCU] IoCreateSymbolicLink failed: 0x%08X\n", status);
        return status;
    }

    /* 4. Register dispatch routines */
    DriverObject->MajorFunction[IRP_MJ_CREATE]         = QcuCreate;
    DriverObject->MajorFunction[IRP_MJ_CLOSE]          = QcuClose;
    DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL] = QcuDeviceControl;
    DriverObject->DriverUnload                          = QcuUnload;

    /* 5. Enable direct I/O for IOCTL buffers */
    g_device_obj->Flags |= DO_BUFFERED_IO;
    g_device_obj->Flags &= ~DO_DEVICE_INITIALIZING;

    DbgPrintEx(DPFLTR_DEFAULT_ID, DPFLTR_INFO_LEVEL,
        "[QCU] Driver loaded. Device: %wZ\n", &dev_name);

    return STATUS_SUCCESS;
}

/* -- IRP_MJ_CREATE / IRP_MJ_CLOSE --------------------------------- */
static NTSTATUS QcuCreate(PDEVICE_OBJECT DevObj, PIRP Irp)
{
    UNREFERENCED_PARAMETER(DevObj);
    return CompleteIrp(Irp, STATUS_SUCCESS, 0);
}

static NTSTATUS QcuClose(PDEVICE_OBJECT DevObj, PIRP Irp)
{
    UNREFERENCED_PARAMETER(DevObj);
    return CompleteIrp(Irp, STATUS_SUCCESS, 0);
}

/* -- DriverUnload -------------------------------------------------- */
static VOID QcuUnload(PDRIVER_OBJECT DriverObj)
{
    UNREFERENCED_PARAMETER(DriverObj);
    KIRQL    irql;
    PLIST_ENTRY entry;

    DbgPrintEx(DPFLTR_DEFAULT_ID, DPFLTR_INFO_LEVEL, "[QCU] Unloading...\n");

    /* Free all outstanding allocations */
    KeAcquireSpinLock(&g_alloc_lock, &irql);
    while (!IsListEmpty(&g_alloc_list)) {
        entry = RemoveHeadList(&g_alloc_list);
        PQCU_ALLOC_ENTRY e = CONTAINING_RECORD(entry, QCU_ALLOC_ENTRY, list);

        if (e->user_va && e->mdl) {
            MmUnmapLockedPages(e->user_va, e->mdl);
        }
        if (e->mdl) {
            IoFreeMdl(e->mdl);
        }
        if (e->kernel_va) {
            MmFreeContiguousMemory(e->kernel_va);
        }
        ExFreePoolWithTag(e, QCU_POOL_TAG);
    }
    KeReleaseSpinLock(&g_alloc_lock, irql);

    /* Remove symbolic link and device */
    UNICODE_STRING symlink_name;
    RtlInitUnicodeString(&symlink_name, QCU_SYMLINK_NAME);
    IoDeleteSymbolicLink(&symlink_name);
    if (g_device_obj) IoDeleteDevice(g_device_obj);

    DbgPrintEx(DPFLTR_DEFAULT_ID, DPFLTR_INFO_LEVEL, "[QCU] Unloaded.\n");
}

/* -- IRP_MJ_DEVICE_CONTROL dispatcher ----------------------------- */
static NTSTATUS QcuDeviceControl(PDEVICE_OBJECT DevObj, PIRP Irp)
{
    UNREFERENCED_PARAMETER(DevObj);
    PIO_STACK_LOCATION stack = IoGetCurrentIrpStackLocation(Irp);
    ULONG code = stack->Parameters.DeviceIoControl.IoControlCode;

    switch (code) {
    case IOCTL_QCU_ALLOC_PHYSICAL:   return HandleAllocPhysical (Irp, stack);
    case IOCTL_QCU_FREE_PHYSICAL:    return HandleFreePhysical  (Irp, stack);
    case IOCTL_QCU_MAP_TO_USER:      return HandleMapToUser     (Irp, stack);
    case IOCTL_QCU_UNMAP_FROM_USER:  return HandleUnmapFromUser (Irp, stack);
    case IOCTL_QCU_GET_NUMA_INFO:    return HandleGetNumaInfo   (Irp, stack);
    case IOCTL_QCU_READ_PMC:         return HandleReadPmc       (Irp, stack);
    case IOCTL_QCU_QUERY_STATUS:     return HandleQueryStatus   (Irp, stack);
    default:
        return CompleteIrp(Irp, STATUS_INVALID_DEVICE_REQUEST, 0);
    }
}

/* -- IOCTL: ALLOC_PHYSICAL ----------------------------------------- */
static NTSTATUS HandleAllocPhysical(PIRP Irp, PIO_STACK_LOCATION Stack)
{
    ULONG in_len  = Stack->Parameters.DeviceIoControl.InputBufferLength;
    ULONG out_len = Stack->Parameters.DeviceIoControl.OutputBufferLength;

    if (in_len  < sizeof(QCU_ALLOC_REQUEST) ||
        out_len < sizeof(QCU_ALLOC_RESPONSE))
        return CompleteIrp(Irp, STATUS_BUFFER_TOO_SMALL, 0);

    QCU_ALLOC_REQUEST  *req  = (QCU_ALLOC_REQUEST*)Irp->AssociatedIrp.SystemBuffer;
    QCU_ALLOC_RESPONSE *resp = (QCU_ALLOC_RESPONSE*)Irp->AssociatedIrp.SystemBuffer;

    if (req->size_bytes == 0 || req->size_bytes > (SIZE_T)1 * 1024 * 1024 * 1024)
        return CompleteIrp(Irp, STATUS_INVALID_PARAMETER, 0);

    /* Align to 2MB */
    SIZE_T alloc_size = (req->size_bytes + (2*1024*1024 - 1)) & ~(SIZE_T)(2*1024*1024 - 1);

    PHYSICAL_ADDRESS lo = {0}, hi = {.QuadPart = MAXLONGLONG}, skip = {0};
    PVOID kernel_va = MmAllocateContiguousMemorySpecifyCache(
        alloc_size, lo, hi, skip, MmCached);

    if (!kernel_va)
        return CompleteIrp(Irp, STATUS_INSUFFICIENT_RESOURCES, 0);

    RtlZeroMemory(kernel_va, alloc_size);

    PHYSICAL_ADDRESS phys = MmGetPhysicalAddress(kernel_va);

    /* Track this allocation */
    PQCU_ALLOC_ENTRY entry = (PQCU_ALLOC_ENTRY)ExAllocatePoolWithTag(
        NonPagedPool, sizeof(QCU_ALLOC_ENTRY), QCU_POOL_TAG);
    if (!entry) {
        MmFreeContiguousMemory(kernel_va);
        return CompleteIrp(Irp, STATUS_INSUFFICIENT_RESOURCES, 0);
    }

    entry->kernel_va = kernel_va;
    entry->phys_addr = phys;
    entry->size      = alloc_size;
    entry->mdl       = NULL;
    entry->user_va   = NULL;
    entry->handle    = (ULONG64)kernel_va;

    KIRQL irql;
    KeAcquireSpinLock(&g_alloc_lock, &irql);
    InsertTailList(&g_alloc_list, &entry->list);
    KeReleaseSpinLock(&g_alloc_lock, irql);

    InterlockedIncrement(&g_alloc_count);
    InterlockedAdd64(&g_alloc_bytes, (LONG64)alloc_size);

    resp->kernel_va  = (ULONG64)kernel_va;
    resp->phys_addr  = (ULONG64)phys.QuadPart;
    resp->size_bytes = alloc_size;
    resp->handle     = entry->handle;

    DbgPrintEx(DPFLTR_DEFAULT_ID, DPFLTR_INFO_LEVEL,
        "[QCU] Alloc %llu MB @ phys=0x%llX handle=0x%llX\n",
        alloc_size >> 20, phys.QuadPart, entry->handle);

    return CompleteIrp(Irp, STATUS_SUCCESS, sizeof(QCU_ALLOC_RESPONSE));
}

/* -- IOCTL: FREE_PHYSICAL ------------------------------------------ */
static NTSTATUS HandleFreePhysical(PIRP Irp, PIO_STACK_LOCATION Stack)
{
    if (Stack->Parameters.DeviceIoControl.InputBufferLength < sizeof(QCU_FREE_REQUEST))
        return CompleteIrp(Irp, STATUS_BUFFER_TOO_SMALL, 0);

    QCU_FREE_REQUEST *req = (QCU_FREE_REQUEST*)Irp->AssociatedIrp.SystemBuffer;
    PQCU_ALLOC_ENTRY  e   = FindEntry(req->handle);
    if (!e) return CompleteIrp(Irp, STATUS_NOT_FOUND, 0);

    if (e->user_va && e->mdl) {
        MmUnmapLockedPages(e->user_va, e->mdl);
        e->user_va = NULL;
    }
    if (e->mdl) {
        IoFreeMdl(e->mdl);
        e->mdl = NULL;
    }

    InterlockedDecrement(&g_alloc_count);
    InterlockedAdd64(&g_alloc_bytes, -(LONG64)e->size);

    KIRQL irql;
    KeAcquireSpinLock(&g_alloc_lock, &irql);
    RemoveEntryList(&e->list);
    KeReleaseSpinLock(&g_alloc_lock, irql);

    MmFreeContiguousMemory(e->kernel_va);
    ExFreePoolWithTag(e, QCU_POOL_TAG);

    return CompleteIrp(Irp, STATUS_SUCCESS, 0);
}

/* -- IOCTL: MAP_TO_USER -------------------------------------------- */
static NTSTATUS HandleMapToUser(PIRP Irp, PIO_STACK_LOCATION Stack)
{
    ULONG in_len  = Stack->Parameters.DeviceIoControl.InputBufferLength;
    ULONG out_len = Stack->Parameters.DeviceIoControl.OutputBufferLength;

    if (in_len  < sizeof(QCU_MAP_REQUEST) ||
        out_len < sizeof(QCU_MAP_RESPONSE))
        return CompleteIrp(Irp, STATUS_BUFFER_TOO_SMALL, 0);

    QCU_MAP_REQUEST  *req  = (QCU_MAP_REQUEST*)Irp->AssociatedIrp.SystemBuffer;
    QCU_MAP_RESPONSE *resp = (QCU_MAP_RESPONSE*)Irp->AssociatedIrp.SystemBuffer;

    PQCU_ALLOC_ENTRY e = FindEntry(req->handle);
    if (!e) return CompleteIrp(Irp, STATUS_NOT_FOUND, 0);
    if (e->user_va) return CompleteIrp(Irp, STATUS_ALREADY_COMMITTED, 0);

    /* Build MDL over the kernel VA */
    PMDL mdl = IoAllocateMdl(e->kernel_va, (ULONG)e->size, FALSE, FALSE, NULL);
    if (!mdl) return CompleteIrp(Irp, STATUS_INSUFFICIENT_RESOURCES, 0);

    MmBuildMdlForNonPagedPool(mdl);

    __try {
        PVOID user_va = MmMapLockedPagesSpecifyCache(
            mdl,
            UserMode,
            MmCached,
            NULL,
            FALSE,
            NormalPagePriority | MdlMappingNoExecute);

        if (!user_va) {
            IoFreeMdl(mdl);
            return CompleteIrp(Irp, STATUS_INSUFFICIENT_RESOURCES, 0);
        }

        e->mdl     = mdl;
        e->user_va = user_va;

        resp->user_va    = (ULONG64)user_va;
        resp->size_bytes = e->size;

        DbgPrintEx(DPFLTR_DEFAULT_ID, DPFLTR_INFO_LEVEL,
            "[QCU] Mapped handle=0x%llX -> user_va=0x%llX\n",
            req->handle, (ULONG64)user_va);
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        IoFreeMdl(mdl);
        return CompleteIrp(Irp, GetExceptionCode(), 0);
    }

    return CompleteIrp(Irp, STATUS_SUCCESS, sizeof(QCU_MAP_RESPONSE));
}

/* -- IOCTL: UNMAP_FROM_USER ---------------------------------------- */
static NTSTATUS HandleUnmapFromUser(PIRP Irp, PIO_STACK_LOCATION Stack)
{
    if (Stack->Parameters.DeviceIoControl.InputBufferLength < sizeof(QCU_UNMAP_REQUEST))
        return CompleteIrp(Irp, STATUS_BUFFER_TOO_SMALL, 0);

    QCU_UNMAP_REQUEST *req = (QCU_UNMAP_REQUEST*)Irp->AssociatedIrp.SystemBuffer;

    /* Find entry by user_va */
    KIRQL irql;
    PQCU_ALLOC_ENTRY found = NULL;
    KeAcquireSpinLock(&g_alloc_lock, &irql);
    for (PLIST_ENTRY p = g_alloc_list.Flink; p != &g_alloc_list; p = p->Flink) {
        PQCU_ALLOC_ENTRY e = CONTAINING_RECORD(p, QCU_ALLOC_ENTRY, list);
        if ((ULONG64)e->user_va == req->user_va) { found = e; break; }
    }
    KeReleaseSpinLock(&g_alloc_lock, irql);

    if (!found || !found->mdl)
        return CompleteIrp(Irp, STATUS_NOT_FOUND, 0);

    MmUnmapLockedPages(found->user_va, found->mdl);
    IoFreeMdl(found->mdl);
    found->user_va = NULL;
    found->mdl     = NULL;

    return CompleteIrp(Irp, STATUS_SUCCESS, 0);
}

/* -- IOCTL: GET_NUMA_INFO ------------------------------------------ */
static NTSTATUS HandleGetNumaInfo(PIRP Irp, PIO_STACK_LOCATION Stack)
{
    if (Stack->Parameters.DeviceIoControl.OutputBufferLength < sizeof(QCU_NUMA_INFO))
        return CompleteIrp(Irp, STATUS_BUFFER_TOO_SMALL, 0);

    QCU_NUMA_INFO *info = (QCU_NUMA_INFO*)Irp->AssociatedIrp.SystemBuffer;
    RtlZeroMemory(info, sizeof(QCU_NUMA_INFO));

    ULONG highest = KeQueryHighestNodeNumber();
    info->node_count = (ULONG)highest + 1;
    if (info->node_count > QCU_MAX_NUMA_NODES)
        info->node_count = QCU_MAX_NUMA_NODES;

    /* Current node of calling thread */
    info->current_node = KeGetCurrentNodeNumber();

    for (ULONG node = 0; node < info->node_count; node++) {
        /* Available memory on this node */
        ULONGLONG avail = 0;
        KeQueryNodeActiveAffinity2((USHORT)node, NULL, 0, NULL);
        /* Use MmAvailablePages as a rough proxy (node-level API limited) */
        info->node_memory_bytes[node] = (ULONG64)MmGetPhysicalMemoryRanges() != 0
            ? 0  /* placeholder - filled below */
            : 0;

        /* CPU count per node via affinity mask popcount */
        GROUP_AFFINITY aff = {0};
        USHORT         aff_count = 1;
        NTSTATUS s = KeQueryNodeActiveAffinity2((USHORT)node, &aff, 1, &aff_count);
        if (NT_SUCCESS(s)) {
            ULONG cnt = 0;
            ULONG_PTR mask = aff.Mask;
            while (mask) { cnt += (ULONG)(mask & 1); mask >>= 1; }
            info->cpu_count_per_node[node] = cnt;
        }
    }

    return CompleteIrp(Irp, STATUS_SUCCESS, sizeof(QCU_NUMA_INFO));
}

/* -- PMC DPC context ----------------------------------------------- */
typedef struct _QCU_PMC_DPC_CTX {
    KDPC        dpc;
    ULONG       counter_id;
    ULONG64     result;
    KEVENT      done;
} QCU_PMC_DPC_CTX;

static VOID PmcDpcRoutine(PKDPC Dpc, PVOID Ctx, PVOID S1, PVOID S2)
{
    UNREFERENCED_PARAMETER(Dpc); UNREFERENCED_PARAMETER(S1); UNREFERENCED_PARAMETER(S2);
    QCU_PMC_DPC_CTX *ctx = (QCU_PMC_DPC_CTX*)Ctx;

    switch (ctx->counter_id) {
    case QCU_PMC_L3_MISS:   ctx->result = __readpmc(0x2E | (0x41 << 8)); break;
    case QCU_PMC_TLB_MISS:  ctx->result = __readpmc(0x08 | (0x20 << 8)); break;
    case QCU_PMC_CYCLES:    ctx->result = __rdtsc();                       break;
    case QCU_PMC_INSTRET:   ctx->result = __readmsr(0xC0000096);           break;
    default:                ctx->result = 0;                               break;
    }
    KeSetEvent(&ctx->done, 0, FALSE);
}

/* -- IOCTL: READ_PMC ----------------------------------------------- */
static NTSTATUS HandleReadPmc(PIRP Irp, PIO_STACK_LOCATION Stack)
{
    ULONG in_len  = Stack->Parameters.DeviceIoControl.InputBufferLength;
    ULONG out_len = Stack->Parameters.DeviceIoControl.OutputBufferLength;

    if (in_len  < sizeof(QCU_PMC_REQUEST) ||
        out_len < sizeof(QCU_PMC_RESPONSE))
        return CompleteIrp(Irp, STATUS_BUFFER_TOO_SMALL, 0);

    QCU_PMC_REQUEST  *req  = (QCU_PMC_REQUEST*)Irp->AssociatedIrp.SystemBuffer;
    QCU_PMC_RESPONSE *resp = (QCU_PMC_RESPONSE*)Irp->AssociatedIrp.SystemBuffer;

    QCU_PMC_DPC_CTX ctx = {0};
    ctx.counter_id = req->counter_id;
    KeInitializeEvent(&ctx.done, NotificationEvent, FALSE);

    CCHAR target_cpu = (CCHAR)(UCHAR)((req->cpu_index == 0)
        ? KeGetCurrentProcessorNumberEx(NULL)
        : req->cpu_index);

    KeInitializeDpc(&ctx.dpc, PmcDpcRoutine, &ctx);
    KeSetTargetProcessorDpc(&ctx.dpc, target_cpu);
    KeSetImportanceDpc(&ctx.dpc, HighImportance);
    KeInsertQueueDpc(&ctx.dpc, NULL, NULL);

    LARGE_INTEGER timeout = { .QuadPart = -10 * 1000 * 1000 }; /* 1 second */
    NTSTATUS s = KeWaitForSingleObject(&ctx.done, Executive, KernelMode, FALSE, &timeout);
    if (s != STATUS_SUCCESS)
        return CompleteIrp(Irp, STATUS_TIMEOUT, 0);

    resp->value = ctx.result;
    return CompleteIrp(Irp, STATUS_SUCCESS, sizeof(QCU_PMC_RESPONSE));
}

/* -- IOCTL: QUERY_STATUS ------------------------------------------- */
static NTSTATUS HandleQueryStatus(PIRP Irp, PIO_STACK_LOCATION Stack)
{
    if (Stack->Parameters.DeviceIoControl.OutputBufferLength < sizeof(QCU_STATUS))
        return CompleteIrp(Irp, STATUS_BUFFER_TOO_SMALL, 0);

    QCU_STATUS *s = (QCU_STATUS*)Irp->AssociatedIrp.SystemBuffer;
    ULONG highest = KeQueryHighestNodeNumber();

    s->version           = QCU_DRIVER_VERSION;
    s->active_allocs     = (ULONG)g_alloc_count;
    s->total_alloc_bytes = (ULONG64)g_alloc_bytes;
    s->numa_nodes        = (ULONG)highest + 1;
    s->reserved          = 0;

    return CompleteIrp(Irp, STATUS_SUCCESS, sizeof(QCU_STATUS));
}

/* -- FindEntry (spinlock held externally if needed) ---------------- */
static PQCU_ALLOC_ENTRY FindEntry(ULONG64 handle)
{
    KIRQL irql;
    PQCU_ALLOC_ENTRY found = NULL;

    KeAcquireSpinLock(&g_alloc_lock, &irql);
    for (PLIST_ENTRY p = g_alloc_list.Flink; p != &g_alloc_list; p = p->Flink) {
        PQCU_ALLOC_ENTRY e = CONTAINING_RECORD(p, QCU_ALLOC_ENTRY, list);
        if (e->handle == handle) { found = e; break; }
    }
    KeReleaseSpinLock(&g_alloc_lock, irql);
    return found;
}
