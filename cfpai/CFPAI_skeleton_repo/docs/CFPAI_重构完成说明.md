# CFPAI 重构完成说明

本版本已一次性完成以下主链重构：

- Stooq 多资产逻辑拆回 `cfpai/` 包内部
- 数据、特征、状态、反向 MOROZ、链式搜索、Tree Diagram、规划、回测、UTM 分层就位
- service 层调用内部包，不再依赖外部 ready script subprocess
- agent/tools 对接 service 层
- diagnostics/reporting 读取内部统一输出产物
- tests 补入最小 smoke / router / service imports

当前状态可定义为：

> 内部模块化可运行骨架 + agent/service/tool 联通版 + 多资产/UTM 主链内聚版
