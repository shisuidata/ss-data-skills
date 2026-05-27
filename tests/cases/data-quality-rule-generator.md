# 测试用例：数据质量规则

## Skill

`data-quality-rule-generator`

## 测试目标

检查 Skill 是否能为渠道新用户转化汇总表生成可落地的数据质量规则。

## 测试输入

```text
请使用 data-quality-rule-generator 为下面这张表生成质量规则。

表名：
ads_channel_new_user_conversion_d

表粒度：
dt + channel_id + device_type + campaign_id

分区字段：
dt

更新频率：
每天 T+1 08:00 前产出。

字段：
- dt
- channel_id
- device_type
- campaign_id
- register_user_cnt
- first_purchase_user_cnt_7d
- first_purchase_rate_7d
- mobile_pay_success_user_cnt

核心业务规则：
- first_purchase_user_cnt_7d 不能大于 register_user_cnt
- first_purchase_rate_7d 必须在 0 到 1 之间
- register_user_cnt 为 0 时，转化率应为空或 0，需要明确规则
- 关键维度不能为空

希望输出：
请生成质量规则清单、严重级别、触发动作和 SQL 校验示例。
```

## 通过标准

- 必须覆盖产出及时性、唯一性、非空、范围、逻辑一致性和波动检查。
- 必须把主键重复和分区未产出列为阻断。
- 必须给出至少一个 SQL 校验示例。
- 必须指出 register_user_cnt 为 0 时转化率规则待确认。
- 不得编造历史波动阈值为确定事实。

