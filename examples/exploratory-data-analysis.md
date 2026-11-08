# exploratory-data-analysis 示例

## 适用场景

刚拿到一份数据，不确定能不能用、有哪些坑、接下来该分析什么。

## 示例输入

```text
请用 exploratory-data-analysis 体检这两份导出数据，判断能不能做渠道 GMV 分析：

orders_gbk.csv：订单导出（Excel 另存），主键 order_id
users.csv：用户表，主键 user_id
关联：orders.user_id = users.user_id
```

## 预期输出

Agent 运行：

```bash
python3 skills/exploratory-data-analysis/scripts/eda.py profile \
  --table orders=orders_gbk.csv --table users=users.csv \
  --key orders=order_id --key users=user_id \
  --join orders.user_id=users.user_id --html eda_report.html
```

然后基于脚本结果输出：

```markdown
## EDA 结果

### 1. 结论

不建议直接使用：有 3 个 P0 问题会让渠道 GMV 算错（列错位、订单号重复、5.7% 的订单关联不到用户）。另外金额是“￥1,234.50”格式的文本，必须先清洗才能求和。

### 2. 数据概览

| 表 | 一行代表 | 行数 | 主键 | 时间范围 | 编码 |
| --- | --- | --- | --- | --- | --- |
| orders | 一笔订单（推测） | 421 | order_id（有 2 个重复） | 2026-05-01 ~ 2026-05-14 | GBK |
| users | 一个用户 | 300 | user_id | — | UTF-8 |

### 3. 必须先处理的问题（P0）

| 表.字段 | 问题 | 影响 | 处理方式 |
| --- | --- | --- | --- |
| orders | 1 行列数与表头不一致 | 该行字段错位 | 备注字段含逗号未转义，重新导出时加引号 |
| orders.order_id | 2 个订单号重复 | GMV 重复计算 | 确认是重复导出还是拆单，按业务规则去重 |
| orders.user_id → users | 5.7% 找不到用户 | 按用户维度分析时丢数据 | 确认用户表是否完整、是否有注销用户 |

### 4. 需要在口径中处理的问题（P1）

- pay_amount 是文本型数字，去掉 ￥ 和千分位后转数值；10 个负值可能是退款，需要和 status 对照
- dt 与 pay_time 有 9.6% 不一致（40 行晚到一天）：按 pay_time 取日期，分区范围放宽 1 天
- 2026-05-07 整天没有订单：确认是任务失败还是业务真空
- channel 有 21 个 \N；另有 22 个“未知”，需要确认是否等同于缺失
- user_id 带前导零，必须按字符串读取

### 7. 可继续分析的方向

| 方向 | 需要的前置处理 | 推荐 Skill |
| --- | --- | --- |
| 渠道 GMV 对比 | 处理 P0；金额清洗；channel 缺失单列 | data-analysis-report-writer |
| 长期质量监控 | 把上述问题转成规则 | data-quality-rule-generator |

报告文件：eda_report.html
```

## 使用说明

- 先看 P0。P0 不处理，后面的分析都没有意义。
- 负金额、突增、长尾可能是真实业务（退款、大促、大客户），不要一律当成脏数据。
- 体检发现的问题可以直接交给 `data-quality-rule-generator`，变成上线后的监控规则。
- 可以直接读 xlsx。Excel 科学计数法 ID、序列日期和公式错误值都会被列出来。
