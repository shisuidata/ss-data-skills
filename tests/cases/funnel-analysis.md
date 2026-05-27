# 测试用例：漏斗分析

## Skill

`funnel-analysis`

## 测试目标

检查 Skill 是否能基于 mock 漏斗数据识别关键流失环节和分群风险。

## 测试输入

```text
请使用 funnel-analysis 分析下面的新用户首购漏斗。

业务背景：
某电商平台 2026 年 5 月新用户首购转化下降，需要定位主要流失环节。

数据来源：
- tests/fixtures/ecommerce-growth/dwd_user_register_d.csv
- tests/fixtures/ecommerce-growth/dwd_user_event_d.csv
- tests/fixtures/ecommerce-growth/dwd_order_detail_d.csv

漏斗步骤：
注册成功 -> 浏览商品 -> 加购 -> 提交订单 -> 支付成功

事件映射：
- 注册成功：register_success
- 浏览商品：product_view
- 加购：add_to_cart
- 提交订单：order_submit
- 支付成功：pay_status = success

统计对象：
user_id 去重

对比周期：
2026-04-17 到 2026-04-30

分析周期：
2026-05-01 到 2026-05-14

希望输出：
请给出漏斗表现、关键流失点、渠道和设备风险，以及下一步建议。
```

## 通过标准

- 应识别分析周期首购转化率低于对比周期。
- 应识别分析周期“浏览商品 -> 加购”是关键流失点。
- 应注意渠道 A 占比提升。
- 应注意移动端支付表现弱。
- 应明确样本量小，只能作为 mock 测试，不能过度归因。

