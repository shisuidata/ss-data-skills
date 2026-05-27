# 测试用例：探索性数据分析

## Skill

`exploratory-data-analysis`

## 测试目标

检查 Skill 是否能根据 mock 表结构和样例目标设计 EDA 检查，而不是直接编造分布结果。

## 测试输入

```text
请使用 exploratory-data-analysis 对下面的数据做探索性分析设计。

业务背景：
某电商平台要分析新用户首购转化下降。

数据文件：
- tests/fixtures/ecommerce-growth/dwd_user_register_d.csv
- tests/fixtures/ecommerce-growth/dwd_user_event_d.csv
- tests/fixtures/ecommerce-growth/dwd_order_detail_d.csv

字段：
注册表：
- dt
- user_id
- register_time
- channel_id
- device_type
- campaign_id

事件表：
- dt
- user_id
- event_time
- event_name
- page
- session_id
- device_type

订单表：
- dt
- order_id
- user_id
- pay_time
- pay_status
- pay_amount
- refund_status

目标：
判断这些数据是否适合做转化漏斗、渠道分析和移动端流失分析。

希望输出：
请给出数据画像、质量检查项、异常检查项、可继续分析方向和待确认问题。
```

## 通过标准

- 必须说明三张表的粒度。
- 必须提出 user_id、session_id、event_time、pay_time 等关键字段质量检查。
- 必须提出事件顺序、重复事件、跨端归因、支付状态和退款状态检查。
- 必须给出后续漏斗、渠道、设备分析方向。
- 如果没有实际运行统计，不得声称已经发现具体缺失率或分布。

