# 测试用例：SQL 审查

## Skill

`sql-reviewer`

## 测试目标

检查 Skill 是否能识别典型数据 SQL 逻辑错误，尤其是 left join 后在 where 中过滤右表字段。

## 测试输入

```text
请使用 sql-reviewer 审查下面的 Spark SQL。

上下文：
- 目标：计算 2026-05-01 到 2026-05-14 每天每个渠道的新用户首购转化率
- 结果粒度：dt + channel_id
- 注册表分区字段：dt
- 订单表分区字段：dt
- 新用户口径：统计周期内注册成功的 user_id
- 支付口径：注册后 7 个自然日内至少一次 pay_status = success

SQL：

select
  r.dt,
  r.channel_id,
  count(distinct r.user_id) as register_user_cnt,
  count(distinct o.user_id) as pay_user_cnt,
  count(distinct o.user_id) / count(distinct r.user_id) as pay_rate
from dwd_user_register_d r
left join dwd_order_detail_d o
  on r.user_id = o.user_id
where r.dt between '2026-05-01' and '2026-05-14'
  and o.pay_status = 'success'
group by r.dt, r.channel_id;
```

## 通过标准

- 必须识别 `where o.pay_status = 'success'` 会破坏 left join 语义。
- 必须说明注册用户数会被低估。
- 必须指出缺少注册后 7 日支付窗口限制。
- 应指出订单表缺少分区过滤或支付时间范围过滤。
- 应指出除法精度或整数除法风险。
- 应给出更安全的改写方向。

