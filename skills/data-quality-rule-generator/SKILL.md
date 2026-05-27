---
name: data-quality-rule-generator
description: Use when generating data quality rules from a table schema, SQL, metric definition, or data pipeline description. Produces validation rules for freshness, row count, uniqueness, nulls, enums, ranges, referential integrity, metric fluctuation, reconciliation, and SQL checks.
---

# Data Quality Rule Generator

## 目标

根据表结构、SQL、指标定义或任务说明，生成可落地的数据质量规则。

这个 Skill 关注质量规则设计，不负责替代调度平台、质量平台或监控系统。默认输出通用 SQL 校验规则；如果用户指定 dbt、Great Expectations、DataWorks、DolphinScheduler 等平台，可以按对应形式改写。

## 使用场景

使用这个 Skill，当用户需要：

- 给一张新表配置质量校验
- 给核心指标增加监控规则
- 给数据任务上线前补充验收标准
- 为补数、重刷、口径变更设计校验 SQL
- 为 ODS、DWD、DWS、ADS 层表设计不同强度的质量规则
- 从 SQL 或表结构中推导非空、唯一、枚举、范围、波动等规则

典型输入：

```text
请根据这张订单汇总表设计数据质量规则。
```

```text
这段 SQL 每天产出渠道转化率，请帮我生成上线前校验项。
```

## 不适用场景

不要用这个 Skill 直接完成：

- 模糊需求澄清，请使用 `data-requirement-clarifier`
- 指标口径审查，请使用 `metric-definition-reviewer`
- 表结构设计，请使用 `table-design-advisor`
- SQL 逻辑审查，请使用 `sql-reviewer`

如果表粒度、主键或指标口径不明确，必须先列为待确认问题，再给出基于假设的规则。

## 输入信息

最少输入之一：

- 表结构
- SQL
- 指标定义
- 数据任务说明

可选输入：

- 表粒度
- 主键或唯一键
- 分区字段
- 更新频率
- 数据延迟要求
- 上游表
- 下游指标
- 历史波动范围
- 质量平台类型
- 告警接收人或处理机制

## 规则类型

优先从这些维度生成规则：

1. 产出及时性：分区是否按时产出，数据延迟是否可接受。
2. 数据量：行数是否为 0，日环比或周同比是否异常。
3. 唯一性：主键、业务键、分区内唯一键是否重复。
4. 非空：关键维度、主键、金额、状态、时间字段是否为空。
5. 枚举值：状态、渠道、类型字段是否在合法集合内。
6. 数值范围：金额、次数、比例、时长是否落在合理范围内。
7. 逻辑一致性：开始时间小于结束时间，支付金额不小于 0，分子不大于分母。
8. 关联完整性：事实表外键是否能关联到维表。
9. 指标波动：核心指标是否出现异常升降。
10. 上下游对账：汇总表与明细表、源表与目标表是否一致。
11. 新鲜度：最新分区、最新事件时间是否满足 SLA。

## 输出格式

````markdown
## 数据质量规则设计

### 1. 规则设计结论

### 2. 设计假设

### 3. 规则清单

| 规则编号 | 规则类型 | 检查对象 | 规则描述 | 严重级别 | 触发动作 |
| --- | --- | --- | --- | --- | --- |

### 4. SQL 校验示例

```sql
-- rule_xxx
```

### 5. 分层处理建议

| 严重级别 | 处理方式 |
| --- | --- |
| 阻断 | 任务失败或禁止发布 |
| 告警 | 通知负责人处理 |
| 观察 | 记录趋势，暂不拦截 |

### 6. 待确认问题

### 7. 上线前验收清单
````

## 严重级别

- 阻断：会导致核心指标错误、主键重复、关键分区缺失或下游不可用
- 告警：数据可能异常，需要人工确认
- 观察：短期不阻断，但建议持续追踪

## SQL 规则写法

默认用返回异常行数的方式表达：

```sql
select count(*) as invalid_count
from target_table
where dt = '${bizdate}'
  and critical_field is null;
```

如果规则需要判断波动，默认用近 7 天或近 30 天作为参考窗口，但必须标记为可调整假设。

## 质量标准

输出必须：

- 先确认表粒度和关键字段
- 按阻断、告警、观察区分规则强度
- 给出能落地的 SQL 示例
- 不虚构历史阈值，把阈值假设写清楚
- 覆盖产出、唯一、非空、枚举、范围、波动和对账中的关键项

## 示例 Prompt

```text
请用 data-quality-rule-generator 为下面这张表生成质量规则：

表：ads_channel_new_user_conversion_d
粒度：dt + channel_id
分区：dt
字段：dt, channel_id, register_user_cnt, first_purchase_user_cnt, conversion_rate
更新：每天 T+1 08:00 前产出
```
