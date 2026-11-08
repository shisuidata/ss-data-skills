# 表结构 JSON 格式

`dq_rules.py generate --schema` 读取下面的格式。完整示例见 [`assets/example_schema.json`](../assets/example_schema.json)。

```json
{
  "table": "ads_channel_new_user_conversion_d",
  "partition": "dt",
  "grain": ["dt", "channel_id"],
  "freshness": {"deadline": "08:00"},
  "row_count": {"min": 5},
  "columns": [
    {"name": "channel_id", "nullable": false, "ref": "dim_channel.channel_id"},
    {"name": "status", "enum": ["paid", "refund"]},
    {"name": "conversion_rate", "min": 0, "max": 1, "numerator": "paid_cnt", "denominator": "uv"}
  ],
  "logic": [{"name": "支付时间不早于下单时间", "expr": "pay_time >= order_time"}],
  "metrics": [{"name": "GMV", "expr": "sum(gmv)", "window_days": 7, "threshold_pct": 0.3}],
  "reconcile": [{"name": "与明细对账", "target_expr": "sum(gmv)", "source": "dwd_order", "source_expr": "sum(amount)", "source_filter": "dt = :biz_date", "tolerance_pct": 0.001}]
}
```

| 字段 | 说明 |
| --- | --- |
| `table` | 必填，表名 |
| `partition` | 分区字段，规则默认只检查当天分区 |
| `grain` | 表粒度，用于唯一性规则 |
| `freshness.deadline` | 产出时限；没填时规则标为待确认 |
| `row_count.min` | 最小行数，默认 1 |
| `columns[].nullable` | `false` 时生成非空规则 |
| `columns[].enum` | 合法取值 |
| `columns[].min` / `max` | 数值范围 |
| `columns[].numerator` / `denominator` | 生成“分子不大于分母”的规则 |
| `columns[].ref` | 外键，写成 `表.字段` |
| `logic[]` | 自定义逻辑，`expr` 写成立时的条件 |
| `metrics[]` | 波动规则。`threshold_pct` 没填时按 30% 生成，并标为待确认 |
| `reconcile[]` | 上下游对账，`tolerance_pct` 是相对容差 |

## 输出

| 参数 | 产出 | 说明 |
| --- | --- | --- |
| `--sql` | SQL 文件 | 每条返回 `invalid_count`，0 表示通过；波动规则的日期函数按 Hive/Spark 写法，其他引擎需要替换 `date_sub` |
| `--dbt` | `schema.yml` | 使用 dbt 1.10.5 起的 `arguments` 写法，旧版本加 `--dbt-legacy`。范围、波动和对账没有内置测试，写成 singular test |
| `--ge` | Great Expectations 1.x 规则集 | 只包含有内置表达的规则，其余使用 SQL |

## 从体检结果生成

`--eda` 读取 `eda.py` 的 JSON，按实际数据推断规则：

- 主键检查的列作为表粒度
- 缺失率为 0 的字段生成非空规则
- 取值不超过 8 个的类别字段生成枚举规则
- 关联检查生成外键规则

这些规则都标为 `assumption`。它们来自样本，只说明“这份数据目前满足”，上线前要和业务确认。

## 常用 SQL 写法

唯一性：

```sql
select count(*) as invalid_count
from (
  select dt, channel_id
  from ads_table
  where dt = :biz_date
  group by dt, channel_id
  having count(*) > 1
) t;
```

波动（和近 7 天均值比较）：

```sql
with today as (
  select sum(gmv) as v from ads_table where dt = :biz_date
),
history as (
  select avg(v) as v
  from (
    select dt, sum(gmv) as v
    from ads_table
    where dt >= date_sub(:biz_date, 7) and dt < :biz_date
    group by dt
  ) d
)
select case when h.v is null or h.v = 0 then 0
            when abs(t.v - h.v) / abs(h.v) > 0.3 then 1 else 0 end as invalid_count
from today t cross join history h;
```

对账：

```sql
select case when s.v is null or t.v is null then 1
            when abs(t.v - s.v) > 0.001 * greatest(abs(s.v), 1) then 1 else 0 end as invalid_count
from (select sum(gmv) as v from ads_table where dt = :biz_date) t
cross join (select sum(amount) as v from dwd_order where dt = :biz_date) s;
```
