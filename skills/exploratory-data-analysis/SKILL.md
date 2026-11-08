---
name: exploratory-data-analysis
description: Use when exploring a dataset before formal analysis, modeling, reporting, or dashboarding. Runs a bundled zero-dependency data health check on CSV files that infers field types, detects encoding, pseudo-nulls, numbers stored as text, leading-zero IDs, duplicate keys, partition-vs-event-time drift, missing dates, and orphan join keys, ranks issues P0/P1/P2, and renders an HTML report; then interprets grain, usability, and next analysis directions. 中文触发词：数据探索、EDA、数据体检、数据摸底、拿到一份新数据。
metadata:
  category: 数据分析
  aliases: EDA、数据探索、探索分析、数据体检
---

# Exploratory Data Analysis

## 目标

拿到一份新数据，先回答三个问题：

1. **一行代表什么？**（粒度、主键、时间范围）
2. **能不能直接用？**哪些问题会让结果算错，哪些需要在口径里处理？
3. **值得往哪个方向继续分析？**

核心原则：**数据长什么样由脚本说，数据意味着什么由人判断**。`scripts/eda.py` 负责体检和问题分级；模型负责推断字段含义、确认粒度、区分数据问题和真实业务现象、规划下一步。

## 使用场景

- 拿到一张新表、一份 CSV 或 Excel 导出，先摸底
- 判断数据能否支撑某个分析、看板或模型
- 接手别人的数据，快速发现坑
- 多张表要关联之前，检查键是否对得上
- 分析结果“看起来不对”，回头排查数据本身

典型输入：

```text
请帮我对这份订单数据做 EDA，看哪些字段有质量问题，能不能用来做渠道分析。
```

## 不适用场景

- 漏斗、留存、实验等专项分析：体检完成后分别使用 `funnel-analysis`、`retention-cohort-analysis`、`ab-test-analysis`
- 为一张表设计长期运行的质量监控规则：使用 `data-quality-rule-generator`（可以把体检发现的问题作为输入）
- SQL 逻辑审查：使用 `sql-reviewer`
- 写完整分析报告：使用 `data-analysis-report-writer`

只有业务问题、没有任何数据或字段时，先列出需要的数据，不要假装已经完成 EDA。

## 输入信息

最少输入：

- 数据文件（CSV、TSV 或 xlsx，UTF-8 和 GBK 都可以），或字段列表 + 样例

推荐输入：

- 分析目标：这份数据接下来要用来做什么
- 主键：一行应该由哪些字段唯一确定
- 多表时的关联关系
- 时间字段、分区字段
- 已知问题

## 上下文建议

推荐使用 [数据分析上下文模板](../../context/templates/analysis-context.md)；表结构信息可参考 [数据表上下文模板](../../context/templates/table-context.md)。

最有价值的上下文是：分析目标、预期粒度和主键、多表关联关系。没有真实数据时，只能输出检查清单，不能声称发现了具体的缺失率或分布。

## 工作流程

1. **运行体检**（有数据文件且能执行代码时必须运行）：

   ```bash
   python3 scripts/eda.py profile \
     --table orders=orders.csv --table users=users.csv \
     --key orders=order_id --key users=user_id \
     --join orders.user_id=users.user_id \
     --html eda_report.html
   ```

   - 组合主键：`--key events=user_id+event_time+event_name`
   - 指定时间字段：`--time-col orders=pay_time`（默认自动选择非分区的时间列）
   - 大文件：`--max-rows 500000` 在全表上随机抽样，报告会标注；主键和关联检查建议全量运行
   - xlsx 有多个工作表时：`--sheet orders=订单明细`
   - 业务时区不是北京时间时：`--tz -05:00`
   - 全部参数见 [命令行参数](references/cli.md)
2. **确认粒度**：根据主键检查结果和字段画像，写出“一行代表 ___”。主键重复时先弄清是重复数据还是粒度理解错了。
3. **处理问题清单**：脚本已按 P0 / P1 / P2 分级，每条带影响和建议。逐条判断是数据问题还是业务现象（例如负金额可能是退款，突增可能是大促）。检查项说明见 [检查项说明](references/checks.md)。
4. **推断字段含义**：类型是脚本推断的，含义要结合字段名和取值推测，并明确标注“推测”。
5. **规划下一步**：这份数据适合做哪些分析、需要先补什么、该用哪个 Skill。
6. **交付**：Markdown 结论 + HTML 报告路径。

## 输出格式

```markdown
## EDA 结果

### 1. 结论
<能不能用：可以使用 / 修正后可用 / 不建议直接使用，以及最关键的 1~3 个原因>

### 2. 数据概览
| 表 | 一行代表 | 行数 | 主键 | 时间范围 | 编码 |
| --- | --- | --- | --- | --- | --- |

### 3. 必须先处理的问题（P0）
| 表.字段 | 问题 | 影响 | 处理方式 |
| --- | --- | --- | --- |

### 4. 需要在口径中处理的问题（P1）

### 5. 字段画像与含义推测
| 字段 | 推断类型 | 含义（推测） | 缺失率 | 备注 |
| --- | --- | --- | --- | --- |

### 6. 值得注意的模式
<分布、趋势、关联中的发现；区分数据问题和业务现象>

### 7. 可继续分析的方向
| 方向 | 需要的前置处理 | 推荐 Skill |
| --- | --- | --- |

### 8. 待确认问题

报告文件：<eda_report.html 路径>
```

## 质量标准

输出必须：

- 先说明粒度和能否使用，再列细节
- 所有缺失率、重复数、分布数字来自脚本输出，或明确标注为“未实际运行”
- 区分数据质量问题和真实业务异常（负金额、突增、长尾都可能是真的）
- 字段含义不确定时标注为推测
- 不把相关写成因果
- 每个 P0 问题都给出具体处理方式
- 给出下一步分析方向和对应 Skill，而不是只罗列统计量

## 完成后的下一步

- 专项分析：`funnel-analysis`、`retention-cohort-analysis`、`ab-test-analysis`
- 建模：`feature-engineering-advisor`
- 把体检发现变成长期校验：`data-quality-rule-generator`
- 写报告：`data-analysis-report-writer`

## 示例 Prompt

```text
请用 exploratory-data-analysis 体检这两份导出数据，判断能不能做渠道 GMV 分析：

orders.csv：订单导出（Excel 另存，可能是 GBK 编码），主键 order_id
users.csv：用户表，主键 user_id
关联：orders.user_id = users.user_id
```

```text
请用 exploratory-data-analysis 分析下面这张 SaaS 订阅变更事件表：

粒度：一行一条订阅状态变更事件
字段：company_id, event_time, event_type, plan, amount, prev_plan, prev_amount, seats, reason
目标：判断哪些字段适合用于构建客户流失预测模型特征，是否存在数据质量问题
```
