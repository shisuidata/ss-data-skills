---
name: stream-pipeline-designer
description: Use when designing or reviewing a real-time data pipeline with Flink, Spark Structured Streaming, Kafka, or CDC. Advises on time semantics, watermarks, state management, exactly-once guarantees, throughput, backpressure, and real-time to batch alignment. 中文触发词：实时数仓、Flink、Kafka、实时管道、背压、Watermark、CDC。
metadata:
  category: 基础 Infra
  aliases: 流处理设计、Flink 方案、实时管道设计
---

# Stream Pipeline Designer

## 目标

帮助用户设计或审查基于 Flink、Spark Structured Streaming、Kafka、CDC 的实时数据管道，重点关注数据一致性、状态管理、延迟保证和实时/批次对齐。

这个 Skill 覆盖实时管道设计决策，不负责替代具体代码审查（使用 `sql-reviewer` 处理 Flink SQL 逻辑）。

## 使用场景

使用这个 Skill，当用户需要：

- 设计 Kafka + Flink 实时数仓管道
- 选择时间语义：Event Time、Processing Time 还是 Ingestion Time
- 评估 State 大小和 RocksDB 配置
- 设计 Watermark 策略和乱序容忍窗口
- 判断是否需要 Exactly-once 保证以及实现成本
- 设计 ODS 实时层 Kafka Topic 结构
- 评估实时和离线数仓数据对齐方案
- 分析背压问题的定位和缓解策略
- 选择计算引擎，设计 CDC 入湖或入仓链路

典型输入：

```text
我们要用 Flink 实时消费订单支付事件，计算渠道实时 GMV，请帮我设计管道方案。
```

## 不适用场景

不要用这个 Skill 直接完成：

- Flink SQL / Spark SQL 逻辑审查，应使用 `sql-reviewer`
- 批处理数仓表设计，应使用 `table-design-advisor`
- 实时数据质量规则设计，应使用 `data-quality-rule-generator`
- 工具接入配置，应使用 `data-tool-integration-planner`

如果用户没有描述数据量级、延迟要求和一致性需求，先列出待确认问题，不要直接给出配置参数。

## 输入信息

最少输入：

- 数据来源（Kafka Topic 或上游系统）
- 计算目标（实时指标或流处理结果）
- 使用框架

可选输入：

- 消息量级（QPS 或条/天）
- 延迟要求（端到端 P99）
- 一致性要求：At-least-once 或 Exactly-once
- 时间字段：Event Time、Kafka 时间还是系统时间
- 乱序容忍范围
- 下游系统：Kafka、ClickHouse、Redis、API
- Checkpoint 周期和状态后端
- 是否需要与离线数仓对齐

## 上下文建议

推荐使用 [实时管道上下文模板](../../context/templates/stream-context.md)。需要接入新数据源时，补充 [工具集成上下文模板](../../context/templates/tool-integration-context.md)。

最有价值的上下文是：消息量级、延迟要求、Key 基数、一致性需求和下游系统写入能力。

## 设计框架

1. 明确计算目标和输出要求。
2. 确认时间语义：Event Time 还是 Processing Time，对应业务场景是什么。
3. 设计 Watermark 策略：乱序窗口大小、迟到数据处理方式。
4. 评估 State 规模：窗口大小、Key 基数、保存时间、State 后端选择。
5. 设计 Exactly-once 方案（如需要）：两阶段提交、幂等写入或 At-least-once + 下游去重。
6. 设计 Kafka Topic：分区数、Key 设计、Retention 策略。
7. 评估背压风险：瓶颈环节、Buffer 配置、反压传导路径。
8. 设计实时/离线对齐：时间边界对齐、补数机制、异常修复。
9. 设计监控：Checkpoint 成功率、延迟 P99、消费 Lag、数据量异常告警。

不同引擎的差异和 CDC 注意事项见 [引擎与接入方式](references/engine-notes.md)。

## 可用脚本

State、分区和 Checkpoint 的数字用脚本估算，不要心算：

```bash
python3 scripts/estimate.py state --keys 5000000 --value-bytes 200 --parallelism 20
python3 scripts/estimate.py kafka --peak-qps 5000 --message-bytes 800 --retention-days 3 --consumer-parallelism 12
python3 scripts/estimate.py checkpoint --state-gb 40 --interval-s 300 --changed-ratio 0.2 --upload-mbps 200
```

全部参数见 [命令行参数](references/cli.md)。

`--keys` 是 TTL 内出现过的不同 Key 数，不是日活。结果是数量级估算，用来发现明显不合理的配置，上线前必须压测。

## 输出格式

````markdown
## 实时管道设计方案

### 1. 设计结论

### 2. 管道架构

```text
数据来源 → Kafka Topic → Flink 作业 → 下游系统
```

### 3. 关键设计决策

| 决策点 | 建议方案 | 原因 |
| --- | --- | --- |
| 时间语义 |  |  |
| Watermark 策略 |  |  |
| State 后端 |  |  |
| 一致性保证 |  |  |
| Checkpoint 周期 |  |  |

### 4. Kafka Topic 设计

### 5. State 大小估算

### 6. 背压风险与缓解

### 7. 实时/离线对齐方案

### 8. 监控告警清单

| 监控项 | 告警阈值 | 告警动作 |
| --- | --- | --- |

### 9. 待确认问题
````

## 质量标准

输出必须：

- 明确时间语义和业务含义，不能混用 Event Time 和 Processing Time
- State 大小估算要结合 Key 基数和窗口大小
- Exactly-once 方案必须说明下游是否支持两阶段提交或幂等写入
- 给出实时/离线数仓对齐方案和数据修复机制
- 监控清单要覆盖 Checkpoint、延迟和消费 Lag
- 没有量级和延迟要求时不给配置参数，容量数字来自估算脚本

## 完成后的下一步

- 审查 Flink SQL：`sql-reviewer`
- 设计实时质量和对账规则：`data-quality-rule-generator`
- 写作业文档：`data-doc-writer`

## 示例 Prompt

```text
请用 stream-pipeline-designer 设计一个实时 GMV 统计管道。

数据来源：Kafka Topic `order-paid-events`，消息格式 JSON，包含 order_id, channel_id, amount, pay_time
计算目标：按渠道实时统计 GMV，每分钟写入 ClickHouse
消息量级：峰值 5000 条/秒
延迟要求：P99 < 30 秒
一致性：允许 At-least-once + ClickHouse 幂等写入
乱序：支付事件最多乱序 60 秒
下游：ClickHouse gmv_realtime 表，按 channel_id + minute 分区
```

```text
请用 stream-pipeline-designer 评估下面这个 Flink 作业的 State 和 Checkpoint 配置是否合理。

作业：实时计算每个用户最近 7 天的行为频次
Key：user_id（日活约 500 万）
State：每个 Key 保存一个大小约 200 字节的计数器，保留 7 天
Checkpoint：每 5 分钟一次，State 后端：RocksDB
背压现象：高峰期 Checkpoint 超时频繁，Lag 持续攀升
请评估 State 规模和背压原因，给出调整建议。
```
