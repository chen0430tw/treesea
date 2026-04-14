# Claude CFPAI 工作指南

## 文档目的

本文档用于向 Claude 说明 CFPAI 的系统定位、模块边界、推荐文件结构与后续协作方式。  
目标不是让 Claude 自由重写一个“很像的金融 AI”，而是让它在既定定义下推进工程实现。

一句话：

> **Claude 在 CFPAI 项目中的职责，是在既定架构和理论边界下推进实现，而不是重新发明系统定义。**

---

## 一、先理解 CFPAI 是什么

CFPAI 的正式全称是：

**Computational Finance Planning AI**  
**计算金融规划人工智能**

它不是：

- 普通选股器
- 单头价格预测模型
- 自动交易神谕
- 简单量化脚本集合

它是一个完整规划系统，主链是：

```text
状态表示 Φ
→ 反向 MOROZ 动态展开 R
→ 链式搜索 C
→ Tree Diagram 网格求值 T
→ 规划输出 Ψ
```

并由：

```text
UTM
```

作为正式调参与结构校准层贯穿全系统。

---

## 二、必须接受的系统定位

Claude 在动手之前，必须接受以下事实：

1. CFPAI 的核心是“状态—路径—行动”规划，而不是单点预测  
2. MOROZ 在这里是反向使用的动态展开与重锚定机制  
3. Tree Diagram 在这里不是背景设定，而是网格求值层  
4. UTM 不是附加优化器，而是正式调参与结构校准层  
5. CFPAI 的最终输出不是“一个价格”，而是：
   - 市场状态
   - 路径优先级
   - 风险预算
   - 资产权重
   - 动作建议

---

## 三、模块边界

### 1. state/
负责状态表示，不做路径搜索。

### 2. reverse_moroz/
负责动态锚定与展开，不做网格求值。

### 3. chain_search/
负责路径构造与评分，不直接生成资产权重。

### 4. tree_diagram/
负责网格构造、节点效用和传播求值。

### 5. planner/
负责把路径与网格价值变成：
- 风险预算
- 权重
- 动作

### 6. utm/
负责参数搜索、收缩、稳定化与调参记录。  
不得把主系统逻辑塞进 utm。

---

## 四、工作顺序

### 第一步：先读文档
必须先读：

- `CFPAI_技术白皮书.md`
- `CFPAI_API.md`
- `CFPAI_repo_structure.md`

### 第二步：先对现有原型做映射
现有原型包括：

- 单资产 toy
- 多资产 Stooq ready
- 多资产 Stooq + UTM ready

Claude 的任务是把这些原型拆回推荐目录结构，而不是继续堆成单脚本。

### 第三步：先拆模块，再做增强
优先把已有脚本拆成：

- data loader
- feature builder
- state encoder
- reverse moroz
- chain search
- tree diagram
- planner
- utm tuner
- backtest

### 第四步：保留原型可运行性
拆模块时，必须保证：
- baseline 能继续跑
- 输出路径不丢
- 结果文件格式尽量稳定

---

## 五、Claude 的修改纪律

### 1. 不要重命名系统
不要擅自把：
- CFPAI 改成别的总名
- MOROZ 改成普通 signal generator
- Tree Diagram 改成普通 scheduler
- UTM 改成 generic optimizer

### 2. 不要制造 all-in-one 巨文件
禁止继续生成：
- `final_ready_really.py`
- `ultimate_fixed.py`
- `cfpai_all_in_one_v7.py`

### 3. 优先给路径清楚的新增文件
推荐输出：
- 新文件路径
- 文件内容
- 放这里的理由

### 4. 文档与代码保持对应
如果新增：
- 状态对象
- API
- 配置结构
- 输出字段

需要同步更新文档。

---

## 六、推荐优先级

### Priority A
1. 拆 `stooq_loader`
2. 拆 `feature_pipeline`
3. 拆 `state encoder`
4. 拆 `reverse_moroz anchors`
5. 拆 `chain_search`
6. 拆 `tree_diagram grid`
7. 拆 `planner`

### Priority B
8. 拆 `utm tuner`
9. 拆 `backtest engine`
10. 补测试

### Priority C
11. 更高阶资本流矩阵
12. regime/path 可视化
13. 更高性能 Tree Diagram 求值后端

---

## 七、最短工作指令

如果只给 Claude 留一句话：

> **请以 CFPAI 白皮书、API 文档与仓库结构说明为准，把现有单脚本原型拆分为状态表示、反向 MOROZ、链式搜索、Tree Diagram、规划输出与 UTM 调参等独立模块，先保住边界，再做增强。**
