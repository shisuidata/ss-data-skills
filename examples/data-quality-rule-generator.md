# data-quality-rule-generator 示例

## 适用场景

数据任务上线前，需要补齐质量规则和校验 SQL。

## 示例输入

```text
请用 data-quality-rule-generator 为下面这张表生成质量规则：

表：ads_channel_new_user_conversion_d
粒度：dt + channel_id + device_type
分区：dt
字段：dt, channel_id, device_type, register_user_cnt, first_purchase_user_cnt_7d, first_purchase_rate_7d
更新：每天 T+1 08:00 前产出
```

## 预期输出

```markdown
## 数据质量规则设计

### 规则清单

| 规则类型 | 检查对象 | 规则描述 | 严重级别 |
| --- | --- | --- | --- |
| 产出及时性 | dt 分区 | 每天 08:00 前必须产出当日分区 | 阻断 |
| 唯一性 | dt + channel_id + device_type | 分区内不能重复 | 阻断 |
| 非空 | channel_id, device_type | 关键维度不能为空 | 阻断 |
| 数值范围 | first_purchase_rate_7d | 必须在 0 到 1 之间 | 阻断 |
| 逻辑一致性 | pay <= register | 首购用户数不能大于注册用户数 | 阻断 |
| 波动检查 | register_user_cnt | 日环比异常波动需要告警 | 告警 |

### SQL 校验示例

检查转化率范围和分子分母关系。
```

## 使用说明

质量规则不要只做非空检查。核心指标表至少要覆盖产出、唯一、范围、逻辑一致性和波动。

