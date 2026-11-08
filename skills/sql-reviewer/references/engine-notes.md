# 引擎注意事项

审查时只看用户实际使用的引擎。不确定版本特性时，先向用户确认版本，不要假设。

## Hive / Spark SQL

- 分区裁剪：分区字段不要包函数，不要用隐式类型转换。
- 数据倾斜：大 Key 关联看 `explain` 和任务耗时分布，必要时加盐或先过滤大 Key。
- Join 策略：小表 Broadcast，大表 SortMerge；确认统计信息是否过期。
- 动态分区：确认 `INSERT OVERWRITE` 的分区范围，避免误覆盖历史分区。
- 除法：`/` 返回小数，除零得到 NULL，分母为 0 时不会报错，数据会悄悄变空。

## Flink SQL

- 时间语义：事件时间需要 Watermark 定义，处理时间结果不可重放。
- 状态：无界 Join 和 `GROUP BY` 的状态会无限增长，必须设置 State TTL。
- 去重：`ROW_NUMBER` 去重要 `ORDER BY` 时间字段，并确认下游接受回撤流。
- Upsert：下游主键必须和聚合键一致。

## ClickHouse

- 分区键和排序键决定查询性能，过滤条件尽量命中排序键前缀。
- `ReplacingMergeTree` 去重是异步的，要求精确结果时用 `FINAL` 或显式聚合。
- 分布式表 `JOIN` 和 `IN` 注意 `GLOBAL` 语义，否则可能得到错误结果或放大查询。
- `/` 返回浮点数，除零得到 `inf` 或 `nan`，下游聚合会被污染。

## MySQL

- 看执行计划，确认走了哪个索引。
- 隐式类型转换和对索引列用函数都会让索引失效。
- 大事务和长查询会造成锁等待和主从延迟。
- `NOT IN` 遇到 NULL 的语义和其他引擎一致，都会筛空。

## PostgreSQL

- 整数相除结果被截断，`count(a) / count(b)` 几乎总是 0，分子要乘 `1.0` 或转换类型。
- 除零直接报错，分母用 `NULLIF`。
- 用 `EXPLAIN (ANALYZE, BUFFERS)` 看真实执行计划。

## Trino / Presto

- 整数相除结果被截断，和 PostgreSQL 一样要转换类型。
- 分区谓词要写在能下推的位置，分布式 Join 注意构建侧大小。

## Doris / StarRocks

- 表模型决定语义：明细、聚合、主键（Unique）模型的查询结果和更新方式不同。
- 分区和分桶键决定裁剪效果，分桶键倾斜会造成单节点瓶颈。
- 物化视图命中与否要看执行计划，不要假设一定被改写。
- Colocate 和 Bucket Shuffle 能改善 Join，需要建表时规划。

## dbt

- 模型里用 `ref()` 和 `source()`，不要写死表名，否则血缘断开。
- 增量模型检查 `is_incremental()` 的过滤条件和 `unique_key`，迟到数据是否会漏。
- `unique` 和 `not_null` 测试放在模型的 YAML 里，关联键尤其要测。
- 审查编译后的 SQL（`target/compiled`）更准确，Jinja 里的条件分支静态检查看不到。
