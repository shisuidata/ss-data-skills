# 电商增长分析示例上下文

这是一个完全虚构、可公开使用的上下文包，用于演示转化、留存、实验、报告和 PPT 类 Skill。

## 业务背景

某电商平台在 2026 年 5 月发现新用户首购转化率下降。业务团队希望判断下降是否真实存在，并定位主要原因。

## 业务目标

提升新用户注册后 7 日内的首购转化率。

## 时间范围

分析周期：

```text
2026-05-01 到 2026-05-14
```

对比周期：

```text
2026-04-17 到 2026-04-30
```

## 核心指标

| 指标 | 口径 |
| --- | --- |
| 新注册用户数 | 统计周期内注册成功的 user_id 去重数 |
| 7 日首购用户数 | 注册后 7 个自然日内至少一次支付成功的 user_id 去重数 |
| 7 日首购转化率 | 7 日首购用户数 / 新注册用户数 |
| 支付页加载耗时 | 用户进入支付页到页面可交互的耗时中位数 |

## 关键表

### dwd_user_register_d

| 字段 | 含义 |
| --- | --- |
| dt | 分区日期 |
| user_id | 用户 ID |
| register_time | 注册时间 |
| channel_id | 注册渠道 |
| device_type | 设备类型 |
| campaign_id | 投放活动 ID |

### dwd_user_event_d

| 字段 | 含义 |
| --- | --- |
| dt | 分区日期 |
| user_id | 用户 ID |
| event_time | 事件时间 |
| event_name | 事件名称 |
| page | 页面 |
| session_id | 会话 ID |
| device_type | 设备类型 |

### dwd_order_detail_d

| 字段 | 含义 |
| --- | --- |
| dt | 分区日期 |
| order_id | 订单 ID |
| user_id | 用户 ID |
| pay_time | 支付时间 |
| pay_status | 支付状态 |
| pay_amount | 支付金额 |
| refund_status | 退款状态 |

## 漏斗步骤

```text
注册成功 -> 浏览商品 -> 加购 -> 提交订单 -> 支付成功
```

事件映射：

| 步骤 | event_name / 状态 |
| --- | --- |
| 注册成功 | register_success |
| 浏览商品 | product_view |
| 加购 | add_to_cart |
| 提交订单 | order_submit |
| 支付成功 | pay_status = success |

## 已知现象

- 新用户 7 日首购转化率从 8.2% 下降到 6.9%。
- 下降主要集中在移动端。
- 渠道 A 的新用户占比提升，但渠道 A 的转化率低于平均。
- 支付页加载耗时中位数从 1.8 秒上升到 3.4 秒。

## 待确认问题

- 7 日窗口按自然日还是滚动 168 小时计算。
- 全额退款订单是否仍算首购。
- 渠道归因使用注册来源、首触来源还是末触来源。
- 支付页加载耗时是否有埋点变更。

## 可配合使用的 Skill

- `data-requirement-clarifier`
- `metric-definition-reviewer`
- `exploratory-data-analysis`
- `funnel-analysis`
- `retention-cohort-analysis`
- `ab-test-analysis`
- `data-analysis-report-writer`
- `data-presentation-architect`

