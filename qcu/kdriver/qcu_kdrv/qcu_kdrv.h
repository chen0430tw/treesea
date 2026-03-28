/*
 * qcu_kdrv.h  —  QCU Kernel Driver shared interface
 *
 * Included by both the kernel driver (qcu_kdrv.c)
 * and the user-mode Python bridge (hardware_bridge.py via ctypes).
 *
 * Safe to include from user-mode: no kernel-only types used here.
 */

#pragma once

/* ── Device name ─────────────────────────────────────────────────── */
#define QCU_DEVICE_NAME     L"\\Device\\QcuKdrv"
#define QCU_SYMLINK_NAME    L"\\DosDevices\\QcuKdrv"
#define QCU_USERMODE_PATH   L"\\\\.\\QcuKdrv"

/* ── IOCTL codes ─────────────────────────────────────────────────── */
#define QCU_DEVICE_TYPE     0x8000u

#define IOCTL_QCU_ALLOC_PHYSICAL  \
    CTL_CODE(QCU_DEVICE_TYPE, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)

#define IOCTL_QCU_FREE_PHYSICAL   \
    CTL_CODE(QCU_DEVICE_TYPE, 0x802, METHOD_BUFFERED, FILE_ANY_ACCESS)

#define IOCTL_QCU_MAP_TO_USER     \
    CTL_CODE(QCU_DEVICE_TYPE, 0x803, METHOD_BUFFERED, FILE_ANY_ACCESS)

#define IOCTL_QCU_UNMAP_FROM_USER \
    CTL_CODE(QCU_DEVICE_TYPE, 0x804, METHOD_BUFFERED, FILE_ANY_ACCESS)

#define IOCTL_QCU_GET_NUMA_INFO   \
    CTL_CODE(QCU_DEVICE_TYPE, 0x805, METHOD_BUFFERED, FILE_ANY_ACCESS)

#define IOCTL_QCU_READ_PMC        \
    CTL_CODE(QCU_DEVICE_TYPE, 0x806, METHOD_BUFFERED, FILE_ANY_ACCESS)

#define IOCTL_QCU_QUERY_STATUS    \
    CTL_CODE(QCU_DEVICE_TYPE, 0x807, METHOD_BUFFERED, FILE_ANY_ACCESS)

/* ── IOCTL_QCU_ALLOC_PHYSICAL ────────────────────────────────────── */
typedef struct _QCU_ALLOC_REQUEST {
    unsigned __int64  size_bytes;   /* requested size (2MB alignment recommended) */
    unsigned int      numa_node;    /* 0xFFFFFFFF = any node                      */
    unsigned int      flags;        /* 0 = default, 1 = require 2MB large page    */
} QCU_ALLOC_REQUEST;

typedef struct _QCU_ALLOC_RESPONSE {
    unsigned __int64  kernel_va;    /* kernel virtual address (opaque to user)    */
    unsigned __int64  phys_addr;    /* physical address for GPU DMA registration  */
    unsigned __int64  size_bytes;   /* actual allocated size                      */
    unsigned __int64  handle;       /* opaque handle — pass to FREE / MAP_TO_USER */
} QCU_ALLOC_RESPONSE;

/* ── IOCTL_QCU_FREE_PHYSICAL ─────────────────────────────────────── */
typedef struct _QCU_FREE_REQUEST {
    unsigned __int64  handle;       /* from QCU_ALLOC_RESPONSE.handle             */
} QCU_FREE_REQUEST;

/* ── IOCTL_QCU_MAP_TO_USER ───────────────────────────────────────── */
typedef struct _QCU_MAP_REQUEST {
    unsigned __int64  handle;       /* from QCU_ALLOC_RESPONSE.handle             */
} QCU_MAP_REQUEST;

typedef struct _QCU_MAP_RESPONSE {
    unsigned __int64  user_va;      /* user-mode virtual address                  */
    unsigned __int64  size_bytes;   /* mapped size                                */
} QCU_MAP_RESPONSE;

/* ── IOCTL_QCU_UNMAP_FROM_USER ───────────────────────────────────── */
typedef struct _QCU_UNMAP_REQUEST {
    unsigned __int64  user_va;      /* from QCU_MAP_RESPONSE.user_va              */
} QCU_UNMAP_REQUEST;

/* ── IOCTL_QCU_GET_NUMA_INFO ─────────────────────────────────────── */
#define QCU_MAX_NUMA_NODES  8

typedef struct _QCU_NUMA_INFO {
    unsigned int      node_count;
    unsigned int      current_node;
    unsigned __int64  node_memory_bytes[QCU_MAX_NUMA_NODES];
    unsigned int      cpu_count_per_node[QCU_MAX_NUMA_NODES];
} QCU_NUMA_INFO;

/* ── IOCTL_QCU_READ_PMC ──────────────────────────────────────────── */
#define QCU_PMC_L3_MISS     0u  /* L3 cache misses         */
#define QCU_PMC_TLB_MISS    1u  /* TLB misses              */
#define QCU_PMC_CYCLES      2u  /* CPU clock cycles        */
#define QCU_PMC_INSTRET     3u  /* instructions retired    */

typedef struct _QCU_PMC_REQUEST {
    unsigned int      counter_id;   /* QCU_PMC_* constant                         */
    unsigned int      cpu_index;    /* logical CPU to read from (0 = current)     */
} QCU_PMC_REQUEST;

typedef struct _QCU_PMC_RESPONSE {
    unsigned __int64  value;
} QCU_PMC_RESPONSE;

/* ── IOCTL_QCU_QUERY_STATUS ──────────────────────────────────────── */
typedef struct _QCU_STATUS {
    unsigned int      version;           /* driver version: 0x00010000 = 1.0      */
    unsigned int      active_allocs;     /* number of live physical allocations    */
    unsigned __int64  total_alloc_bytes; /* total bytes currently allocated        */
    unsigned int      numa_nodes;        /* NUMA node count on this machine        */
    unsigned int      reserved;
} QCU_STATUS;
