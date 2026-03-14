# HCE 完整统一包说明

这是当前的**真正整合版**。

从现在开始，这个包只保留三份核心规范文件：

1. `HCE_整合版总规范.md`
2. `HCE_技术栈选型文档.md`
3. `Claude_执行规范.md`

其余前面讨论过程中生成的碎片化 md，不再作为主规范保留在包内。

## 本包包含

- 修正后的 HCE_ROOT 完整目录结构
- 四系统并列工程骨架：
  - tree_diagram
  - qcu
  - honkai_core
  - hce
- docs / shared / environment / experiments / runs / checkpoints / logs / results / legacy
- 已归档原型源码
- 白皮书
- 三份核心规范文件

## Tree Diagram 口径

Tree Diagram 当前的参考源码基线由以下两个原型文件共同组成：

- tree_diagram_complete_mini_colab_v3_active.py
- tree_diagram_weather_oracle_v5_tuned.py

它们属于**同一个 Tree Diagram 系统**，不是两个并列模式。
