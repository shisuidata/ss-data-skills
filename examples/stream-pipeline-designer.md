# stream-pipeline-designer 示例

## 适用场景

要设计或审查 Kafka、Flink 等实时数据管道，需要明确时间语义、一致性、State、Checkpoint、背压和监控方案。

## 示例输入

```text
请用 stream-pipeline-designer 设计一个实时 GMV 统计管道。

数据来源：Kafka Topic `order-paid-events`，消息格式 JSON，包含 order_id, channel_id, amount, pay_time。
计算目标：按渠道实时统计 GMV，每分钟写入 ClickHouse。
消息量级：峰值 5000 条/秒。
延迟要求：P99 < 30 秒。
一致性：允许 At-least-once + ClickHouse 幂等写入。
乱序：支付事件最多乱序 60 秒。
下游：ClickHouse gmv_realtime 表，按 channel_id + minute 分区。
```

## 预期输出

```markdown
## 实时管道设计方案

### 设计结论

建议使用 Kafka -> Flink Event Time 窗口聚合 -> ClickHouse 幂等写入。由于业务允许 At-least-once，应优先保证 order_id + channel_id + minute 的幂等更新，而不是强行追求端到端 Exactly-once。

### 关键设计决策

| 决策点 | 建议方案 | 原因 |
| --- | --- | --- |
| 时间语义 | Event Time，使用 pay_time | GMV 应按真实支付时间归属 |
| Watermark | 60-90 秒乱序容忍 | 覆盖已知最大乱序并留安全边界 |
| 一致性 | At-least-once + 下游幂等 | 符合业务要求且成本较低 |
| Checkpoint | 30-60 秒起步压测 | 兼顾恢复点和吞吐 |

### 监控告警清单

- Kafka 消费 Lag
- Flink 端到端延迟 P99
- Checkpoint 成功率和耗时
- ClickHouse 写入失败率
- 实时 GMV 与离线 T+1 GMV 差异
```

## 使用说明

实时管道设计必须先确认延迟和一致性目标。没有量级、乱序和下游写入能力时，不要直接给固定参数。
- State、分区和 Checkpoint 用 `skills/stream-pipeline-designer/scripts/estimate.py` 估算。`--keys` 是 TTL 内的不同 Key 数，不是日活。
