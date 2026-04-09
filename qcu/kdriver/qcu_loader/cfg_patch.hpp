/*
 * cfg_patch.hpp — Kernel CFG bitmap registration for kdmapper-loaded drivers
 *
 * Uses iqvw64e.sys (intel_driver) read/write primitives to locate
 * nt!MiCfgBitMap and mark a pool allocation as CFG-valid, so that
 * IofCallDriver can call dispatch routines in anonymous pool without
 * triggering BSOD 0x139 LEGACY_GS_VIOLATION (guard_icall_bugcheck).
 *
 * Must be called while intel_driver is still loaded (before Unload).
 */
#pragma once
#include <cstdint>

namespace cfg_patch {

/*
 * Register all 16-byte granules in [alloc_va, alloc_va + alloc_size) as
 * valid CFG indirect-call targets in the kernel CFG bitmap.
 *
 * Returns true  if at least one bitmap QWORD was successfully updated.
 * Returns false if MiCfgBitMap could not be located (pattern not found)
 *               or if no bitmap pages were committed for the given range.
 *               In the latter case CFG may be disabled for that range
 *               anyway (uncommitted bitmap page = architecture default).
 */
bool RegisterRange(uint64_t alloc_va, uint64_t alloc_size);

} // namespace cfg_patch
