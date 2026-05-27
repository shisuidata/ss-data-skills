# table-design-advisor 示例

## 适用场景

需要把临时分析逻辑沉淀成一张可长期维护的数据表。

## 示例输入

```text
请用 table-design-advisor 设计一张表：

场景：渠道投放看板需要每天看新用户注册、首购、7 日转化。
查询维度：日期、渠道、设备。
更新频率：T+1。
执行引擎：Hive/Spark。
```

## 预期输出

```markdown
## 表设计建议

### 表定位

| 项目 | 建议 |
| --- | --- |
| 数仓层级 | ADS |
| 表类型 | 日粒度汇总表 |
| 表粒度 | dt + channel_id + device_type |
| 分区字段 | dt |
| 更新策略 | T+1 覆盖分区 |

### 字段设计

| 字段名 | 类型建议 | 含义 |
| --- | --- | --- |
| dt | string | 统计日期 |
| channel_id | string | 渠道 ID |
| device_type | string | 设备类型 |
| register_user_cnt | bigint | 注册用户数 |
| first_purchase_user_cnt_7d | bigint | 注册后 7 日内首购用户数 |
| first_purchase_rate_7d | decimal | 7 日首购转化率 |

### 风险点

- 7 日转化需要延迟回看，不能只在注册次日一次性固化。
- 渠道归因口径需要先确认首触、末触还是注册来源。
```

## 使用说明

表设计最重要的是粒度。这个 Skill 会优先逼你说清楚“一行代表什么”。

