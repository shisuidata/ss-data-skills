---
name: retention-cohort-analysis
description: Use when analyzing retention, cohort behavior, repeat purchase, active user return, subscription renewal, or user stickiness over time. Builds cohort retention matrices from event data with a bundled zero-dependency script that masks immature cells, keeps curves on a fixed cohort set, compares segments, flags mix-adjusted anomaly cohorts, decomposes cohort-over-cohort change into mix vs retention effects, and renders an HTML report. 中文触发词：留存分析、Cohort、复购、续费、用户流失、次日留存。
metadata:
  category: 数据分析
  aliases: 留存分析、Cohort 分析、复购分析、续费分析
---

# Retention Cohort Analysis

## 目标

分析用户、客户或业务对象在进入之后是否持续回来，并回答：

1. 留存曲线长什么样？后段有没有趋平（有没有稳定留下来的用户）？
2. 哪些分群留存更差？哪些批次异常？
3. 最近批次留存变差，是**来了不一样的用户**，还是**同样的用户留得更差**？

核心原则：**数字由脚本算，判断由人做**。留存矩阵、曲线、分群对比、异常批次和结构拆解用 `scripts/retention.py` 计算；模型负责定义口径、解释原因、提出验证动作。

## 使用场景

- 新用户次日、7 日、30 日留存
- 周留存、月留存、会员续费、订阅续约
- 首购后复购
- 不同渠道、版本、首日行为的用户质量对比
- “最近几批用户留存变差了，为什么”
- B 端客户活跃与流失

典型输入：

```text
帮我看不同渠道新用户的 7 日和 30 日留存，最近几周是不是变差了。
```

## 不适用场景

- 有序步骤的转化：使用 `funnel-analysis`
- 有随机分组的实验：使用 `ab-test-analysis`
- 指标口径本身有争议：先用 `metric-definition-reviewer`
- 预测某个用户会不会流失：这是建模问题，使用 `feature-engineering-advisor` 和 `model-evaluation-reviewer`

没有明确“起点行为”和“回访行为”时，先定义 Cohort 口径。

## 输入信息

最少输入：

- 起点：注册、首购、首次签约等事件或时间
- 回访行为：主动打开、核心行为、再次购买、续费
- 用户或对象 ID、时间字段

推荐输入：

- 事件明细 CSV + 用户属性 CSV（渠道、设备、套餐等）
- Cohort 粒度：日 / 周 / 月
- 留存口径：第 N 期当期回访，还是 N 期内有过回访
- 按日时：自然日还是滚动 24 小时
- 想对比的两组批次（例如改版前后）

输入字段详见 [输入格式](references/input-schema.md)。

## 上下文建议

推荐使用 [留存 Cohort 分析上下文模板](../../context/templates/cohort-context.md) 准备结构化输入。

通用分析背景请参考 [数据分析上下文模板](../../context/templates/analysis-context.md)。

最有价值的上下文是：起点行为、回访行为、时间口径（自然日 / 滚动 24 小时）、Cohort 粒度和分群维度。时间口径不明确时，必须先确认，不能混用。

## 工作流程

1. **定义口径**：起点、回访行为（只算主动行为，排除推送到达、后台唤醒）、粒度、留存口径、时间边界。写成表格请用户确认。
2. **运行脚本**（能执行代码时必须运行）：

   ```bash
   python3 scripts/retention.py analyze --events events.csv \
     --start-event register_success --return-event "app_open|product_view" \
     --users users.csv --segment channel_id \
     --unit week --periods 1,2,3,4,6,8 --key-period 2 \
     --period 前4周=2026-03-02..2026-03-29 --period 后4周=2026-03-30..2026-04-26 --baseline 前4周 \
     --html retention_report.html
   ```

   数据量很大时，先用 [留存 SQL 模板](references/retention-sql.md) 在仓库里汇总，再用 `--summary` 输入。

   列名不同时用 `--user-col`、`--event-col`、`--time-col` 指定。文件可以是 UTF-8 或 GBK。批次按业务时区划分：带时区的时间按 `--tz`（默认 +08:00）换算，UTC 数据不用手工转换。全部参数见 [命令行参数](references/cli.md)。
3. **先看质量检查**：成熟度、样本量、自然日与滚动口径的差距、回访事件是否被动。
4. **读结果**：
   - `curve`：固定批次集合上的留存曲线，后段是否趋平
   - `segment_tests`：每个分群与其余用户的差异和置信区间
   - `anomalies`：按分群构成调整后仍然异常的批次
   - `comparison.segments[dim]`：两组批次之间的结构效应与留存效应
5. **解释与建议**：结合 [解读要点](references/pitfalls.md) 给出原因假设和验证动作。
6. **交付**：Markdown 结论 + HTML 报告路径。

不能执行代码时：按同样的结构人工计算，并在结论中写明“未经脚本计算”。

## 输出格式

```markdown
## 留存 / Cohort 分析结果

### 1. 结论
<一句话：关键周期留存多少、有没有变差、主要原因是用户构成还是产品>

### 2. Cohort 定义
| 项目 | 口径 |
| --- | --- |
| Cohort 起点 |  |
| 回访行为 |  |
| 统计对象 |  |
| 粒度与周期 |  |
| 留存口径 | 第 N 期当期 / N 期内 |
| 时间边界 | 自然日 / 滚动 24 小时 |

### 3. 留存曲线与矩阵
<曲线形状、是否趋平；矩阵里哪些批次偏深偏浅>

### 4. 分群差异
| 分群 | 关键周期留存 | 与其余用户差异 | 95% 区间 | 显著 |
| --- | --- | --- | --- | --- |

### 5. 异常批次
<批次、偏离多少、对应时间点发生了什么>

### 6. 批次间变化拆解
<结构效应 vs 留存效应，具体是哪个分群>

### 7. 可能原因与验证动作
| 假设 | 支持证据 | 如何验证 |
| --- | --- | --- |

### 8. 口径风险与待确认问题

报告文件：<retention_report.html 路径>
```

## 质量标准

输出必须：

- 先定义起点、回访行为、时间边界，再看数字
- 未成熟的单元格留空，不能当作 0，也不能拿来和成熟批次比较
- 曲线基于固定的批次集合，不能每个周期各用各的批次
- 区分“用户构成变化”和“同类用户留存变化”
- 异常批次要先排除构成变化的影响
- 不把短期活动拉高的留存写成长期改善
- 标记样本量过小的批次和分群
- 说明批次按哪个时区划分

## 完成后的下一步

- 写成报告：`data-analysis-report-writer`，把 `--json` 的结果作为来源
- 验证改善动作：`ab-test-analysis`
- 做流失预测：`feature-engineering-advisor`

## 示例 Prompt

```text
请用 retention-cohort-analysis 分析新用户周留存，并生成 HTML 报告：

数据：events.csv（user_id, event_name, event_time），users.csv（user_id, channel_id）
起点：register_success；回访：app_open 或 product_view（push_receive 不算）
粒度：按周，看 W1、W2、W3、W4、W6、W8
对比：3 月前 4 周 vs 后 4 周，最近几批留存好像变差了
```

```text
请用 retention-cohort-analysis 分析 SaaS 企业客户的订阅续费留存（汇总数据）：

起点：首次签约月；留存：当月订阅仍为 active
窗口：M1、M3、M6
分群：套餐类型（starter / pro）
已知：最近两个签约批次的 M3 明显低于历史，想知道是套餐结构变了还是同套餐续费变差了
```
