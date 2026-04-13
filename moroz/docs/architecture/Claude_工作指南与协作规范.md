# Claude_工作指南与协作规范.md

## 文档目的

本文档用于向 Claude 说明 MOROZ 项目的系统定位、文件结构、模块边界、协作方式与修改纪律。  
目标不是让 Claude 从零“自由发挥”，而是让它在既定架构下：

- 继续补全源码
- 整理上传包里的 QCU / HCE 真实源码
- 保持 MOROZ 的分层不被破坏
- 避免把 toy / benchmark / real 混写
- 避免把 QCU、HCE、MOROZ 混成一个 all-in-one 巨文件

一句话：

> Claude 在 MOROZ 项目中的职责，是在既有架构和边界下推进工程实现，而不是重新发明系统定义。

---

## 一、先理解 MOROZ 是什么

MOROZ 的正式全称是：

**Modular Orchestrator for Retrieval, Optimization, and Zero-copy Semantic Collapse**  
**模组化检索、优化与零拷贝语义坍缩编排器**

一句话定义：

> MOROZ 是一个面向超大候选空间的冷启动搜索与收缩框架，通过 MSCM 提供多源候选，利用 K-Warehouse 完成候选压缩与分层调度，再由 ISSC 在执行端进行原地语义坍缩，并由 HCE 负责全局编排、实验追踪、任务分片与运行时管理。

请务必先接受以下系统定位：

1. MOROZ 不是单一算法  
2. MOROZ 不是 QCU 的别名  
3. MOROZ 不是普通爆破器的壳  
4. MOROZ 是总装层系统  
5. MOROZ 的核心链路是：

```text
MSCM -> K-Warehouse -> ISSC -> HCE
```

如果后续整理中需要引入 QCU，则关系是：

```text
MOROZ -> adapters -> QCU runtime -> OPU governance
```

---

## 二、你需要理解的四个核心模块

### 1. MSCM

全称：**Multi-Source Semantic Collapse Model**

职责：
- 组织多源候选
- 建立分层来源
- 计算语义特征
- 输出统一加权候选空间

回答的问题：

> 候选从哪里来，为什么这些候选更值得先看？

### 2. K-Warehouse

职责：
- 候选压缩
- Gate 剪枝
- 上界估计
- Top-K 排序
- 分片准备
- 预算控制

回答的问题：

> 候选如何被压缩、排序、分片？

### 3. ISSC

全称：**In-Situ Semantic Collapse**

职责：
- 原地生成
- 前缀过滤
- 上界评估
- 本地评分
- 局部丢弃
- 收缩监测

回答的问题：

> 候选如何在执行端被筛选并发生原地语义坍缩？

### 4. HCE

职责：
- 调度
- 分片
- checkpoint
- runs / logs / results
- recovery
- 全局编排

回答的问题：

> 整个系统如何被编排、观测、恢复与扩展？

---

## 三、必须遵守的分层原则

### 原则 1：MOROZ 和 QCU 分层

- `moroz/` 负责总系统、前端压缩、链路组织、接口与 HCE 调度
- `qcu/` 负责真实坍缩设施、runtime 与 OPU 治理
- `moroz/adapters/` 负责把 frontier 映射进 QCU

禁止：
- 让 MOROZ 吞掉 QCU
- 让 QCU 直接重写 MOROZ 前端语义
- 让 HCE 直接挤进 QCU runtime 内核

### 原则 2：HCE 只做运行层

HCE 只负责：

- 调度
- 分片
- checkpoint
- recovery
- run registry
- 聚合

HCE 不负责：

- MSCM 本体
- K-Warehouse 本体
- ISSC 本体
- QCU runtime 本体

### 原则 3：contracts 是边界层

`moroz/contracts/` 必须单独存在，用来统一定义：

- `FrontierCandidate`
- `CollapseRequest`
- `CollapseResult`
- `RuntimeStats`
- 序列化语义

任何 CLI / TUI / Agent / benchmark / backend 都应该走这层，不要私自绕过。

### 原则 4：toy / benchmark / real 严格隔离

必须维持三种模式：

- `toy`
- `benchmark`
- `real`

禁止：

- 用 toy 结果冒充真实系统能力
- 把 benchmark 快速适配代码写回 real 版本
- 把临时调试逻辑偷偷留在正式实现里

---

## 四、当前推荐文件结构

请默认按以下结构工作：

```text
MOROZ/
├─ docs/
├─ configs/
├─ runs/
├─ outputs/
├─ scripts/
├─ tests/
├─ moroz/
│  ├─ contracts/
│  ├─ core/
│  ├─ backends/
│  ├─ adapters/
│  ├─ hce/
│  ├─ interfaces/
│  └─ utils/
├─ qcu/
│  ├─ runtime/
│  ├─ opu/
│  ├─ profiles/
│  └─ legacy/
└─ archive/
   ├─ uploads/
   └─ extracted_reference/
```

### `moroz/core/`
放：
- `mscm.py`
- `k_warehouse.py`
- `issc.py`
- `metrics.py`
- `frontier.py`
- `moroz_core.py`

### `moroz/contracts/`
放：
- `types.py`
- `request.py`
- `result.py`
- `serialization.py`

### `moroz/adapters/`
放：
- `request_mapper.py`
- `result_adapter.py`
- `qcu_mapping_rules.py`

### `moroz/backends/`
放：
- `base.py`
- `toy_backend.py`
- `benchmark_backend.py`
- `qcu_backend.py`

### `moroz/hce/`
放：
- `scheduler.py`
- `sharding.py`
- `checkpoint.py`
- `recovery.py`
- `run_registry.py`
- `aggregator.py`

### `qcu/runtime/`
放：
- `iqpu_core.py`
- `qcu_runner.py`
- `readout.py`
- `state.py`
- `traces.py`

### `qcu/opu/`
放：
- `controller.py`
- `policies.py`
- `signals.py`
- `governance.py`

### `qcu/legacy/imported_from_hce/`
保留上传包里的原始 QCU 参考版本，不要一开始就直接改烂。

---

## 五、当前已有参考物

Claude 在接手前，应优先阅读这些文件：

### 文档
- `docs/api/MOROZ_API.md`
- `docs/whitepaper/MOROZ_技术白皮书.md`
- `docs/whitepaper/MOROZ_技术白皮书_扩展版.md`
- `docs/architecture/repo_structure.md`
- `docs/narrative/MOROZ_传说叙事抽象文档.md`
- `docs/narrative/MOROZ_神秘感与传说叙事整合文档.md`

### 参考上传包
- `archive/uploads/MOROZ代码.txt`
- `archive/uploads/HCE_complete_integrated_with_agent_ssh.zip`
- `archive/uploads/QCU_调度工程完整版压缩包.zip`

### 当前骨架
- `moroz/`
- `qcu/`

---

## 六、你应该如何工作

### 第一步：先读，不要先改

先通读：

1. 白皮书
2. repo_structure
3. MOROZ代码.txt
4. 当前骨架目录

确认以下几点再动手：

- 当前实现覆盖到哪一层
- 哪些是骨架
- 哪些是上传包里的真实参考
- 哪些地方只是临时 stub
- 哪些地方以后要对位替换

### 第二步：先做“对位迁移”，不是“自由重写”

优先任务应是：

1. 从 `QCU_调度工程完整版压缩包.zip` 里提取真实 QCU runtime / OPU 结构
2. 对位迁移到：
   - `qcu/runtime/`
   - `qcu/opu/`
   - `qcu/profiles/`
3. 从 `HCE_complete_integrated_with_agent_ssh.zip` 里提取：
   - 调度
   - 分片
   - checkpoint
   - recovery
   - run registry
4. 对位迁移到：
   - `moroz/hce/`

### 第三步：只在必要时补 adapter / contract

如果上传包里的真实代码与当前骨架接口不匹配，则：

- 优先通过 `request_mapper.py`
- `result_adapter.py`
- `contracts/*.py`

做适配，而不是到处硬改。

### 第四步：保留原始参考层

任何从上传包里拆出来的代码，都应该优先先放到：

- `qcu/legacy/imported_from_hce/`
- 或 `archive/extracted_reference/`

再慢慢抽取成正式版本。

不要一上来就“复制粘贴进 runtime 然后随手改”。

---

## 七、代码修改纪律

### 1. 不要写巨型 all-in-one 文件
禁止继续制造：

- `allinone_final_real_v2.py`
- `use_this_final_really_ok.py`
- `new_final_fixed_ultimate.py`

### 2. 文件名必须写职责，不写情绪
推荐：
- `request_mapper.py`
- `qcu_runner.py`
- `controller.py`
- `aggregator.py`

不要：
- `last_try.py`
- `fixed2.py`
- `really_final.py`

### 3. 每次改动后优先保留三样东西
- 旧文件位置
- 新文件位置
- 迁移说明

### 4. 不要悄悄改系统定义
不能私自把：

- MOROZ 改成单算法
- HCE 改成算法内核
- QCU 改成全系统总名
- ISSC 改成随便一个评分器

---

## 八、推荐优先级

Claude 接手后的最优先级任务顺序：

### Priority A
1. 对位整理 QCU runtime / OPU
2. 对位整理 HCE 调度层
3. 校准 `qcu_backend.py` 与真实 runtime 的接口

### Priority B
4. 补 `tests/`
5. 补 CLI 最小入口
6. 补 config 结构
7. 补 run 目录与 checkpoint 读写

### Priority C
8. 补 TUI / dashboard
9. 补更多 benchmark
10. 补文档中的图与示例

---

## 九、Claude 输出格式要求

如果 Claude 继续协作，请优先输出以下形式之一：

### 形式 A：目录级变更说明
- 改了哪些文件
- 新增哪些文件
- 为什么放在这里

### 形式 B：模块级迁移说明
- 原代码来自哪里
- 对位迁移到哪里
- 还缺什么

### 形式 C：直接给 patch / 新文件
- 文件路径
- 完整内容
- 简短说明

不建议：
- 长篇空谈
- 重新命名整个系统
- 不落盘只讨论

---

## 十、最终协作原则

Claude 在 MOROZ 项目中的任务，不是“重新发明一套很像的系统”，而是：

> 在已有定义、边界、文件结构与上传源码参考的前提下，把 MOROZ 从讨论态推进到真正的工程态。

最重要的四句话：

1. **先保住边界，再补功能**
2. **先对位迁移，再自由重构**
3. **先保留原始参考，再抽取正式模块**
4. **先让系统能持续长，再追求一次写完**

---

## 附：给 Claude 的最短工作指令

如果只保留一句话给 Claude：

> 请以当前 `repo_structure.md`、白皮书、`MOROZ代码.txt` 以及上传的 QCU / HCE 压缩包为准，优先完成对位迁移与模块拆分，不要重写系统定义，不要混淆 MOROZ、QCU、HCE 的职责边界。
