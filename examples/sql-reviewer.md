# sql-reviewer 示例

## 适用场景

SQL 已经写完，需要上线前检查逻辑风险和性能风险。

## 示例输入

```text
请用 sql-reviewer 审查下面这段 Spark SQL。

背景：计算每天每个渠道的新用户首购转化率。
结果粒度：dt + channel_id。
分区字段：dt。

select
  r.dt,
  r.channel_id,
  count(distinct r.user_id) as register_user_cnt,
  count(distinct o.user_id) as pay_user_cnt
from dwd_user_register_d r
left join dwd_order_detail_d o
  on r.user_id = o.user_id
where r.dt = '${bizdate}'
  and o.pay_status = 'success'
group by r.dt, r.channel_id;
```

## 预期输出

```markdown
## SQL 审查结果

### 总体结论

存在 P0 逻辑问题：`where o.pay_status = 'success'` 会把 left join 变成事实上的 inner join，导致未支付用户被过滤，注册用户数被低估。

### 高风险问题

| 风险等级 | 问题 | 影响 | 建议 |
| --- | --- | --- | --- |
| P0 | 右表条件写在 where | 未支付用户丢失 | 移到 join 条件或子查询 |
| P1 | 未限制订单时间窗口 | 可能把历史任意支付都算入首购 | 明确注册后 7 日或当日窗口 |

### 建议改写方向

先按用户粒度计算注册与支付标记，再按 dt + channel_id 聚合。
```

## 使用说明

这个示例展示了数据 SQL 中非常常见的坑：left join 后在 where 里过滤右表字段。

