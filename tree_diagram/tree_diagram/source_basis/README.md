# Tree Diagram 原型基线说明

Tree Diagram 当前的参考源码基线由以下两个原型脚本共同组成：

- `tree_diagram_complete_mini_colab_v3_active.py`
- `tree_diagram_weather_oracle_v5_tuned.py`

它们共同构成 **同一个 Tree Diagram 系统** 的原型集合。
不应将第二个文件视为独立系统、附属模式或外部壳层。

当前正式模块的建立方式应为：
- 从两个原型共同抽取抽象层、数值层与排序/Oracle 流程
- 保留二者在 `legacy/` 中作为行为基线
- 新模块一律按“共同取材”方式迁移
