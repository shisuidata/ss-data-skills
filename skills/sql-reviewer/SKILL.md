---
name: sql-reviewer
description: Use when reviewing SQL for data development. Checks logic correctness, metric consistency, joins, aggregations, deduplication, null handling, date boundaries, partition filters, performance risks, engine-specific issues, and safer rewrite suggestions.
---

# SQL Reviewer

## 目标

审查数据开发 SQL 的逻辑正确性、口径一致性和性能风险。

这个 Skill 不只是格式化 SQL，而是站在数据开发代码审查的角度，判断这段 SQL 会不会算错、跑慢、影响下游或难以维护。

## 使用场景

使用这个 Skill，当用户需要审查：

- Hive SQL
- Spark SQL
- Flink SQL
- ClickHouse SQL
- MySQL 或 PostgreSQL 分析 SQL
- dbt model SQL
- 临时取数 SQL
- 看板或报表 SQL
- 指标计算 SQL

重点适合检查：

- Join 是否放大数据
- 聚合粒度是否正确
- 去重逻辑是否可靠
- 日期边界是否准确
- 分区过滤是否缺失
- NULL 是否影响结果
- 窗口函数是否符合预期
- 指标口径是否被 SQL 改写
- 大表扫描、数据倾斜、重复计算等性能风险

## 不适用场景

不要用这个 Skill 直接完成：

- 从零澄清需求，请使用 `data-requirement-clarifier`
- 指标定义专项审查，请使用 `metric-definition-reviewer`
- 表结构设计，请使用 `table-design-advisor`
- 数据质量规则生成，请使用 `data-quality-rule-generator`

如果缺少表结构或业务口径，可以继续审查 SQL 结构，但必须标记结论的不确定性。

## 输入信息

最少输入：

- SQL

可选输入：

- 执行引擎
- 表结构
- 表数据量级
- 分区字段
- 指标口径
- 期望结果粒度
- 报错日志
- 运行耗时
- 下游使用场景

## 审查流程

1. 判断 SQL 目标：这段 SQL 想产出什么结果。
2. 识别结果粒度：最终一行代表什么。
3. 检查输入表：主表、维表、事实表、临时表和过滤条件。
4. 检查 Join：关联键、关联类型、是否可能一对多放大。
5. 检查聚合：GROUP BY 字段是否匹配指标粒度。
6. 检查去重：ROW_NUMBER、COUNT DISTINCT、主键去重是否符合业务。
7. 检查时间条件：自然日、分区日、事件时间、支付时间、跨天边界。
8. 检查 NULL 和默认值：是否影响加总、比较、Join 和分组。
9. 检查窗口函数：PARTITION BY、ORDER BY、排序稳定性。
10. 检查性能：分区裁剪、重复扫描、大表 Join、数据倾斜、无谓排序。
11. 检查可维护性：命名、CTE 拆分、注释、硬编码。
12. 给出修复建议：优先修正会导致结果错误的问题。

## 输出格式

````markdown
## SQL 审查结果

### 1. 总体结论

### 2. SQL 目标与结果粒度

### 3. 高风险问题

| 风险等级 | 位置 | 问题 | 影响 | 建议 |
| --- | --- | --- | --- | --- |

### 4. 逻辑正确性检查

### 5. 性能检查

### 6. 可维护性检查

### 7. 待确认问题

### 8. 建议改写

```sql
-- 如有必要，给出更安全的 SQL 版本
```
````

## 风险等级

- P0：会导致结果明显错误、重复计算、漏算或重大口径偏差
- P1：在特定数据分布或业务边界下会出错
- P2：性能、可维护性或稳定性问题

## 引擎注意事项

如果用户指定执行引擎，要补充对应检查：

- Hive/Spark：分区裁剪、Shuffle、数据倾斜、Broadcast Join、动态分区
- Flink：状态大小、时间语义、Watermark、乱序、去重状态、Upsert 语义
- ClickHouse：分区键、排序键、FINAL、去重表引擎、分布式表
- MySQL/PostgreSQL：索引、执行计划、隐式类型转换、锁和临时表

## 质量标准

输出必须：

- 先给结论，再列问题
- 说明问题为什么会影响结果或性能
- 区分确定问题和基于缺失信息的风险
- 能改写时给出可运行方向的 SQL
- 不因为缺少表结构就假装知道字段唯一性或数据分布

## 示例 Prompt

```text
请用 sql-reviewer 审查下面这段 Spark SQL。

背景：计算每天每个渠道的新用户首购转化率。
结果粒度：dt + channel_id。
分区字段：dt。

[粘贴 SQL]
```
