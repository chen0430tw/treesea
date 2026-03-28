# QCU 内核驱动编译指南

> 记录从零到 `qcu_kdrv.sys` 的完整踩坑过程

---

## 环境要求

| 工具 | 版本 | 说明 |
|------|------|------|
| Visual Studio | 2022 (v143) | 标准 C++ 工具集 |
| Windows SDK | 10.0.26100.0 | 必须指定完整版本号 |
| WDK | 10.0.26100.0 | 提供 km/ 内核头文件和 ntoskrnl.lib |
| kdmapper | latest | 免签名加载，开发期使用 |

WDK VS 扩展安装路径：
```
C:\Program Files (x86)\Windows Kits\10\Vsix\VS2022\10.0.26100.0\amd64\WDK.vsix
```

---

## 项目配置要点

### 关键 .vcxproj 设置

```xml
<!-- 用 DynamicLibrary 而不是 WDK 的 Driver 类型 -->
<ConfigurationType>DynamicLibrary</ConfigurationType>
<PlatformToolset>v143</PlatformToolset>

<!-- 必须写完整版本号，写 10.0 会找不到 km/ 头文件 -->
<WindowsTargetPlatformVersion>10.0.26100.0</WindowsTargetPlatformVersion>

<!-- 输出 .sys 而不是 .dll -->
<TargetExt>.sys</TargetExt>
```

### 头文件路径

```xml
<IncludePath>
  $(WindowsSdkDir)Include\$(WindowsTargetPlatformVersion)\km;
  $(WindowsSdkDir)Include\$(WindowsTargetPlatformVersion)\shared;
  $(IncludePath)
</IncludePath>
<LibraryPath>
  $(WindowsSdkDir)Lib\$(WindowsTargetPlatformVersion)\km\x64;
  $(LibraryPath)
</LibraryPath>
```

### 编译器设置

```xml
<RuntimeLibrary>MultiThreaded</RuntimeLibrary>   <!-- MT，不能用 DLL 版 -->
<BufferSecurityCheck>false</BufferSecurityCheck> <!-- 内核不支持 /GS cookie -->
<BasicRuntimeChecks>Default</BasicRuntimeChecks> <!-- 禁用 RTC，否则拉入 LIBCMT -->
<SupportJustMyCode>false</SupportJustMyCode>     <!-- 禁用 JMC，否则导入 KERNEL32.dll -->
<AdditionalOptions>/kernel %(AdditionalOptions)</AdditionalOptions>
```

### 链接器设置

```xml
<EntryPointSymbol>CustomDriverEntry</EntryPointSymbol>
<SubSystem>Native</SubSystem>
<NoDefaultLib>true</NoDefaultLib>
<AdditionalDependencies>ntoskrnl.lib;%(AdditionalDependencies)</AdditionalDependencies>
<AdditionalOptions>/DRIVER:WDM /ALIGN:0x1000 /SECTION:.pdata,D /MANIFEST:NO %(AdditionalOptions)</AdditionalOptions>
```

### Manifest 禁用（必须在 PropertyGroup 里）

```xml
<!-- 必须放在 PropertyGroup，放在 Link/ItemDefinitionGroup 里无效 -->
<PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
  <GenerateManifest>false</GenerateManifest>
  <EmbedManifest>false</EmbedManifest>
</PropertyGroup>
```

### Spectre 缓解

```xml
<!-- 两个都要加，只加一个不够 -->
<PropertyGroup Label="Configuration">
  <SpectreMitigation>false</SpectreMitigation>
  <Driver_SpectreMitigation>false</Driver_SpectreMitigation>
</PropertyGroup>
```

---

## 踩过的坑（按出现顺序）

### 1. WindowsKernelModeDriver10.0 找不到

**错误**：
```
无法找到 WindowsKernelModeDriver10.0 的生成工具
```

**原因**：WDK VS 扩展没装。

**修复**：安装 WDK.vsix（路径见上）。但实际上我们最终放弃了 WDK 的 Driver 项目类型，改用 `DynamicLibrary` + 手工设置链接器标志，避免依赖 WDK MSBuild 工具集。

---

### 2. 代码页 936 不能表示的字符

**错误**：
```
该文件包含不能在当前代码页(936)中表示的字符
```

**原因**：.vcxproj / .sln / .c / .h 里有 Unicode 符号（`—`、`──`、`→` 等）。GBK 环境下 VS 拒绝处理。

**修复**：用 Python 扫描并删除所有非 ASCII 字节：
```python
with open(path, 'rb') as f:
    data = f.read()
cleaned = bytes(b for b in data if b < 128)
with open(path, 'wb') as f:
    f.write(cleaned)
```

---

### 3. MSB8040 Spectre 缓解错误

**错误**：
```
此项目需要缓解了 Spectre 漏洞的库
```

**修复**：在 `PropertyGroup Label="Configuration"` 里同时设置：
```xml
<SpectreMitigation>false</SpectreMitigation>
<Driver_SpectreMitigation>false</Driver_SpectreMitigation>
```

注意：在 ClCompile 里设置 `<SpectreMitigation>Disabled</SpectreMitigation>` 会报另一个错（无效值），不能这样写。

---

### 4. ntddk.h 找不到（第一次）

**原因**：源文件里有非 ASCII 字符，编译器在处理 include 前就报错退出。

**修复**：同上，清理非 ASCII 字符。

---

### 5. ntddk.h 找不到（第二次）

**原因**：`WindowsTargetPlatformVersion=10.0` 不能解析为实际路径，头文件在 `10.0.26100.0` 子目录下。

**修复**：改为完整版本号：
```xml
<WindowsTargetPlatformVersion>10.0.26100.0</WindowsTargetPlatformVersion>
```

---

### 6. KeQueryHighestNodeNumber 参数错误

**错误**：
```
'USHORT KeQueryHighestNodeNumber(void)': 用于调用的参数太多
```

**原因**：WDK 10.0.26100.0 中此函数无参数，返回 `ULONG`（不是 `USHORT`）。

**修复**：
```c
// 错误
USHORT highest;
KeQueryHighestNodeNumber(&highest);

// 正确
ULONG highest = KeQueryHighestNodeNumber();
```

---

### 7. ULONG 转 USHORT 警告

**错误**：
```
C4244: "函数": 从"ULONG"转换到"USHORT"，可能丢失数据
```

**原因**：`KeQueryNodeActiveAffinity2` 第一个参数是 `USHORT`，但循环变量 `node` 是 `ULONG`。

**修复**：
```c
KeQueryNodeActiveAffinity2((USHORT)node, ...);
```

---

### 8. /MANIFEST 与 /DRIVER 不兼容（LNK1295）

**错误**：
```
LINK : fatal error LNK1295: "/MANIFEST"与"/DRIVER"规范不兼容
```

**原因**：DynamicLibrary 项目默认生成 manifest，而 `/DRIVER:WDM` 不允许有 manifest。

**误区**：把 `<GenerateManifest>false</GenerateManifest>` 放在 `<Link>` 的 `ItemDefinitionGroup` 里无效，放在 `<EmbedManifest>` 里只控制 mt.exe 嵌入步骤，不控制链接器的 `/MANIFEST` 标志。

**正确修复**：放在对应配置的 `PropertyGroup` 里：
```xml
<PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
  <GenerateManifest>false</GenerateManifest>
  <EmbedManifest>false</EmbedManifest>
</PropertyGroup>
```

---

### 9. LIBCMT 符号无法解析（LNK2019）

**错误**：
```
LIBCMT.lib(error.obj): error LNK2019: 无法解析的外部符号 __stdio_common_vsprintf_s
```

**原因**：Debug 配置默认开启 RTC（Runtime Checks），拉入了 LIBCMT.lib，而内核环境缺少 LIBCMT 的部分依赖。

**修复**：在 ClCompile 里禁用 RTC：
```xml
<BasicRuntimeChecks>Default</BasicRuntimeChecks>
```

---

### 10. KERNEL32.dll 被导入（kdmapper 报错）

**kdmapper 输出**：
```
[-] Dependency KERNEL32.dll wasn't found
[-] Failed to resolve imports
```

**排查过程**：用链接器 MAP 文件定位：
```
0001:00001730  __CheckForDebuggerJustMyCode  LIBCMT:debugger_jmc.obj
0001:0000176c  GetCurrentThreadId            kernel32:KERNEL32.dll
```

**原因**：Debug 模式默认开启 Just My Code（JMC），会在每个函数里插入 `__CheckForDebuggerJustMyCode` 调用，而这个函数的实现（debugger_jmc.obj）引用了 `GetCurrentThreadId`（KERNEL32.dll）。内核没有 KERNEL32.dll，导致 kdmapper 映射失败。

**修复**：
```xml
<SupportJustMyCode>false</SupportJustMyCode>
```

---

## 成功构建输出

```
1>  qcu_kdrv.c
1>LINK : warning LNK4075: 忽略"/INCREMENTAL"(由于"/RELEASE"规范)
1>qcu_kdrv.obj : warning LNK4075: 忽略"/EDITANDCONTINUE"(由于"/DRIVER"规范)
1>  qcu_kdrv.vcxproj -> D:\treesea\qcu\kdriver\x64\Debug\qcu_kdrv.sys
========== 全部重新生成: 1 成功，0 失败，0 已跳过 ==========
```

两个 LNK4075 是正常的，不影响结果。

---

## 加载驱动

```
# 以管理员身份运行
qcu_loader.exe qcu_kdrv.sys
```

kdmapper 成功输出包含：
```
[+] Image base has been allocated at 0xFFFF...
[+] Driver mapped successfully
```

加载后设备节点 `\\.\QcuKdrv` 可用。

---

## 蓝屏排查速查

蓝屏后重启，按以下顺序找信息，30 秒内能定位问题。

### 第一步：看事件日志（最快，不需要 sudo）

```powershell
Get-WinEvent -LogName Application -MaxEvents 100 |
  Where-Object { $_.Id -eq 1001 } |
  Select-Object -First 3 |
  Format-List TimeCreated, Message
```

输出里找 `OcaBucket` — 这是崩溃模块名，例如：
- `AV_nt!IoCreateDevice` = ntoskrnl 的 IoCreateDevice 崩溃
- `AV_qcu_kdrv!xxx` = 我们自己的驱动崩溃

### 第二步：确认 Minidump 文件存在

```powershell
# 需要 sudo（Minidump 目录权限受保护）
sudo powershell.exe -Command "ls C:\Windows\Minidump\ | Sort-Object LastWriteTime -Descending | Select-Object -First 3 | Format-Table Name, LastWriteTime -AutoSize"
```

文件名格式：`MMDDYY-XXXXX-01.dmp`，按时间倒序，第一个就是最近一次。

### 第三步：从事件日志读 Stop Code 和参数

```powershell
Get-WinEvent -LogName Application -MaxEvents 100 |
  Where-Object { $_.Id -eq 1001 -and $_.ProviderName -like '*Error*' } |
  Select-Object -First 1 |
  Format-List Message
```

关键字段：
| 字段 | 含义 |
|------|------|
| P1 | 故障地址（发生 fault 的内存地址） |
| P2 | 操作类型（0=读, 1=写, 2=执行） |
| P3 | RIP（崩溃时 CPU 正在执行的地址） |
| P4 | 模式（2=内核模式） |
| OcaBucket | 崩溃模块 + 函数名 |

### 常见 Stop Code

| Code | 名称 | 驱动开发常见原因 |
|------|------|----------------|
| 0x50 | PAGE_FAULT_IN_NONPAGED_AREA | 解引用 NULL 或野指针 |
| 0xBE | ATTEMPTED_WRITE_TO_READONLY_MEMORY | 写了只读页（如写代码段） |
| 0x3B | SYSTEM_SERVICE_EXCEPTION | 内核系统调用时的访问违规 |
| 0x1E | KMODE_EXCEPTION_NOT_HANDLED | 内核未处理异常（通常是除零或非法指令） |
| 0x7E | SYSTEM_THREAD_EXCEPTION_NOT_HANDLED | 内核线程异常 |

### P1 地址的判断规律

| P1 值范围 | 说明 |
|-----------|------|
| `0x0` ~ `0xFFFF` | NULL 指针加小偏移，经典空指针解引用 |
| `0xFFFFFFFFFFFFxxxx` | 负数偏移，通常是 NULL - offset |
| `0xDEAD????` / `0xBAD????` | 内存已被释放（use-after-free）或未初始化 |
| 正常内核地址但不可访问 | 页面未映射，分页内存在 IRQL > DISPATCH_LEVEL 被访问 |

---

### 11. 蓝屏 STOP 0x50 PAGE_FAULT_IN_NONPAGED_AREA（kdmapper DriverObject=NULL）

**现象**：驱动被 kdmapper 成功映射并执行，但立即蓝屏。

**事件日志（Event ID 1001）**：
```
检测错误: 0x00000050
P1: ffffffffffffffd0  (故障地址)
P2: 0000000000000002
P3: fffff8031c74b254  (RIP，位于 ntoskrnl)
P4: 0000000000000002  (内核模式)
OcaBucket: AV_nt!IoCreateDevice
```

**根因**：kdmapper 调用驱动入口时 `param1=0, param2=0`，即 `CustomDriverEntry(NULL, NULL)`。`IoCreateDevice` 内部访问 `DriverObject->DriverExtension`（偏移约 +0x28~+0x30），NULL 指针加偏移 = 非法地址，触发 PAGE_FAULT。

**初始错误修复（会引发后续蓝屏）**：从 NonPagedPool 分配假的 DRIVER_OBJECT。这能解决 0x50，但会导致 0x139（见坑 12）。

**注意**：用 kdmapper 加载的驱动都会遇到这个问题，因为 kdmapper 不走正常的 `IopLoadDriver` 流程，不会自动分配 DRIVER_OBJECT。这是 kdmapper 驱动开发的必走坑之一。

---

### 12. 蓝屏 STOP 0x139 KERNEL_SECURITY_CHECK_FAILURE（假 DRIVER_OBJECT 破坏栈 cookie）

**现象**：驱动加载、设备创建成功，但第一次打开设备（DeviceIoControl）时立即蓝屏。

**事件日志（Event ID 1001）**：
```
检测错误: 0x00000139
P1: 0000000000000003  (LEGACY_GS_VIOLATION)
P2: ...（内核栈地址）
P3: ...
OcaBucket: GSOD_nt!IofCallDriver
```

**根因**：`LEGACY_GS_VIOLATION` = 栈 cookie 被破坏。

IofCallDriver 进入驱动的分发函数前，会读 `DriverObject->OBJECT_HEADER`（位于 DriverObject 指针前的固定负偏移）来做类型验证和引用计数。从 NonPagedPool 分配的假 DRIVER_OBJECT，其前面是 pool 块头（`POOL_HEADER`），内容完全是垃圾。内核把这些垃圾当作 OBJECT_HEADER 读取，写入了不正确的值，破坏了相邻的栈 cookie，触发 GS cookie 检查失败。

**结论**：NonPagedPool 分配的对象**永远不能**当作 Object Manager 对象使用。只有通过 `ObCreateObject` 等 API 创建的对象才有合法的 OBJECT_HEADER 前缀。

**正确修复**：借用 `\Driver\Null` 的 DRIVER_OBJECT（这是一个真正的 OB 对象），保存其原有分发例程，hook 进我们自己的，对不属于我们设备的 IRP 转发回原例程：

```c
// 声明未导出的 API
NTKERNELAPI NTSTATUS ObReferenceObjectByName(
    PUNICODE_STRING ObjectName, ULONG Attributes,
    PACCESS_STATE AccessState, ACCESS_MASK DesiredAccess,
    POBJECT_TYPE ObjectType, KPROCESSOR_MODE AccessMode,
    PVOID ParseContext, PVOID *Object);
extern POBJECT_TYPE *IoDriverObjectType;

// 保存原始例程
static PDRIVER_DISPATCH g_orig_create, g_orig_close, g_orig_ioctl;

// 在 CustomDriverEntry 里
PDRIVER_OBJECT real_drv = NULL;
if (!DriverObject) {
    UNICODE_STRING null_name;
    RtlInitUnicodeString(&null_name, L"\\Driver\\Null");
    ObReferenceObjectByName(&null_name, OBJ_CASE_INSENSITIVE,
        NULL, 0, *IoDriverObjectType, KernelMode, NULL, (PVOID*)&real_drv);
    DriverObject = real_drv;
}

// Hook（不设置 DriverUnload，\Driver\Null 必须保持存活）
g_orig_create = DriverObject->MajorFunction[IRP_MJ_CREATE];
g_orig_close  = DriverObject->MajorFunction[IRP_MJ_CLOSE];
g_orig_ioctl  = DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL];
DriverObject->MajorFunction[IRP_MJ_CREATE]         = QcuCreate;
DriverObject->MajorFunction[IRP_MJ_CLOSE]          = QcuClose;
DriverObject->MajorFunction[IRP_MJ_DEVICE_CONTROL] = QcuDeviceControl;
if (real_drv) ObDereferenceObject(real_drv);

// 分发函数里转发非 QCU 设备的 IRP
static NTSTATUS QcuCreate(PDEVICE_OBJECT DevObj, PIRP Irp) {
    if (DevObj != g_device_obj) {
        if (g_orig_create) return g_orig_create(DevObj, Irp);
        return CompleteIrp(Irp, STATUS_SUCCESS, 0);
    }
    return CompleteIrp(Irp, STATUS_SUCCESS, 0);
}
```

**注意**：不能设置 `DriverObject->DriverUnload`，因为这是 `\Driver\Null` 的卸载回调，设置后系统卸载 Null 驱动时会调用我们的卸载函数（或更糟糕的问题）。
