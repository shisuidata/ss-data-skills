# retention-cohort-analysis 示例

## 适用场景

想知道用户是否持续回来、哪些批次和分群更差，以及最近批次变差是“来了不一样的用户”还是“同样的用户留得更差”。

## 示例输入

```text
请用 retention-cohort-analysis 分析新用户周留存，并生成 HTML 报告：

数据：events.csv（user_id, event_name, event_time），users.csv（user_id, channel_id）
起点：register_success；回访：app_open 或 product_view（push_receive 不算）
粒度：按周，看 W1、W2、W3、W4、W6、W8，重点看 W2
对比：3 月前 4 周 vs 后 4 周
```

## 预期输出

Agent 运行：

```bash
python3 skills/retention-cohort-analysis/scripts/retention.py analyze --events events.csv --users users.csv \
  --start-event register_success --return-event "app_open|product_view" --segment channel_id \
  --unit week --periods 1,2,3,4,6,8 --key-period 2 \
  --period 前4周=2026-03-02..2026-03-29 --period 后4周=2026-03-30..2026-04-26 --baseline 前4周 \
  --html retention_report.html
```

然后基于脚本结果输出：

```markdown
## 留存 / Cohort 分析结果

### 1. 结论

后 4 周批次的 W2 留存从 44.7% 降到 31.6%（−13.1pp，显著）。其中 −9.4pp 来自用户构成：channel_a 占比从 31% 升到 55%，而它的 W2 留存只有 17.1%。另有 2026-04-06 这一批在排除构成影响后仍显著偏低，需要单独排查。

### 2. Cohort 定义

| 项目 | 口径 |
| --- | --- |
| Cohort 起点 | 首次 register_success，按周分批（周一开始） |
| 回访行为 | app_open 或 product_view（不含 push_receive） |
| 统计对象 | user_id |
| 粒度与周期 | 周；W1–W8 |
| 留存口径 | 第 N 周当周有回访 |

### 3. 留存曲线与矩阵

基于 5 个已观察到 W4 的批次，曲线 W1 49.1% → W4 44.3%，W2 以后基本趋平：有一群稳定留下来的用户。矩阵中 2026-04-06 一行明显偏浅。

### 4. 分群差异

| 分群 | W2 留存 | 与其余用户差异 | 95% 区间 | 显著 |
| --- | --- | --- | --- | --- |
| channel_a | 17.1% | −37.3pp | [−40.2pp, −34.4pp] | 是 |
| organic | 58.6% | +34.9pp | [+31.9pp, +38.0pp] | 是 |
| channel_b | 41.8% | +3.3pp | [−1.3pp, +7.8pp] | 否 |

### 5. 异常批次

2026-04-06：W2 留存 23.7%，按渠道构成调整后的预期是 36.0%，低 12.4pp。请对照这一周的发版和故障记录。

### 6. 批次间变化拆解

结构效应 −9.4pp，留存效应 −3.7pp：主要是获客结构问题，其次才是产品留存。

### 7. 可能原因与验证动作

| 假设 | 支持证据 | 如何验证 |
| --- | --- | --- |
| channel_a 投放放量，带来低意向用户 | 结构效应占主导，channel_a 留存低 | 和投放团队核对 3 月底起的预算和定向变化 |
| 4/6 当周新手引导出过问题 | 构成调整后仍显著偏低 | 查该周发版记录、崩溃率和新手引导完成率 |

报告文件：retention_report.html
```

## 使用说明

- 未成熟的单元格是“还不知道”，不是 0。
- 最近批次变差时，先拆用户构成，再找产品原因。
- 回访事件只算主动行为，推送到达和后台唤醒会虚高留存。
- 批次按业务时区划分。UTC 数据不用手工转换，默认按 +08:00 换算，可用 `--tz` 修改。
