---
name: funnel-analysis
description: Use when analyzing conversion funnels across ordered business steps, such as registration, activation, payment, signup, onboarding, or checkout. Rebuilds strict ordered funnels from event data with a bundled zero-dependency script, decomposes period-over-period change into steps and into segment mix vs rate effects, detects tracking and truncation issues, and renders an HTML funnel report. 中文触发词：漏斗分析、转化漏斗、哪一步流失、转化率下降拆解。
metadata:
  category: 数据分析
  aliases: 转化漏斗、转化分析、漏斗拆解、步骤流失
---

# Funnel Analysis

## 目标

分析一个有明确步骤顺序的转化漏斗，回答三个问题：

1. 用户在哪一步流失最多？
2. 和对比期相比，整体转化的变化**来自哪一步、来自用户结构还是转化本身**？
3. 这个变化是真的，还是口径、埋点、观察期或样本量造成的假象？

核心原则：**数字由脚本算，判断由人做**。漏斗人数、贡献拆解、结构拆解和质量检查用 `scripts/funnel.py` 计算；模型负责定义漏斗、解释原因、提出验证动作。

## 使用场景

- 注册、激活、首购、下单支付、会员开通、线索转化、新手引导等有序流程
- “转化率下降了，哪一步出了问题”
- “是渠道变差了，还是产品变差了”
- 对比改版前后、两个时期、两个渠道的漏斗
- 审查别人算的漏斗口径是否正确

典型输入：

```text
帮我分析注册到首购的转化漏斗，5 月比 4 月下降了，看看是哪一步、哪类用户的问题。
```

## 不适用场景

- 数据集整体摸底：使用 `exploratory-data-analysis`
- 留存、复购或用户流失：使用 `retention-cohort-analysis`
- 指标整体异常，还没有明确的转化路径：使用 `business-root-cause-analysis`
- 有随机分组的实验：使用 `ab-test-analysis`（漏斗对比只能发现相关，实验才能确认因果）
- 指标口径本身有争议：先用 `metric-definition-reviewer`

步骤没有先后顺序（例如“用过功能 A、B、C 中的几个”）时，这不是漏斗，先帮助用户重新定义问题。

## 输入信息

最少输入：

- 漏斗步骤及每一步对应的事件或状态
- 每一步的人数（汇总数据），或事件明细

推荐输入：

- 事件明细 CSV：用户 ID、事件名、事件时间
- 用户属性 CSV：渠道、设备、新老客等分群字段
- 对比期（上期、去年同期、改版前）
- 转化窗口：入口后多少天内完成才算转化
- 最近的产品改版、投放变化、埋点变更

输入字段详见 [输入格式](references/input-schema.md)。

## 上下文建议

推荐使用 [漏斗分析上下文模板](../../context/templates/funnel-context.md) 准备结构化输入，也可以参考 [电商增长分析示例上下文](../../context/packs/ecommerce-growth-demo.md)。

通用分析背景请参考 [数据分析上下文模板](../../context/templates/analysis-context.md)。

最有价值的上下文是：步骤定义、统计对象、时间窗口、对比期和分群维度。步骤或事件定义不清楚时，先定义漏斗，不要直接解释流失。

## 工作流程

1. **定义漏斗**：步骤顺序、事件映射、统计对象（用户 / 企业 / 订单）、转化窗口、按入口时间划分时期。写成表格请用户确认。
2. **运行脚本**（能执行代码时必须运行）：

   ```bash
   python3 scripts/funnel.py analyze --events events.csv \
     --user-col user_id --event-col event_name --time-col event_time \
     --step 注册=register_success --step 浏览商品=product_view --step 加购=add_to_cart \
     --step 提交订单=order_submit --step 支付成功=pay_success \
     --users users.csv --segment channel_id --segment device_type \
     --period 本期=2026-05-01..2026-05-14 --period 上期=2026-04-17..2026-04-30 --baseline 上期 \
     --window-days 7 --html funnel_report.html
   ```

   数据量很大（千万级事件）时，先用 [漏斗 SQL 模板](references/funnel-sql.md) 在仓库里算出有序漏斗人数，再用 `--summary` 输入汇总 JSON。

   文件可以是 UTF-8 或 GBK。带时区的时间按 `--tz`（默认 +08:00）换算，不带时区的按业务时区处理。全部参数见 [命令行参数](references/cli.md)。
3. **先看质量检查**：`checks` 里有 fail 时（例如后一步人数多于前一步），先修口径，不要解读转化率。
4. **读拆解结果**：
   - `comparison.steps[].share_of_change`：整体变化中每一步的占比，各步相加为 100%
   - `comparison.steps[].counterfactual_overall`：这一步恢复到对比期水平时，整体转化能回到多少
   - `comparison.segments[dim].mix_effect / rate_effect`：结构效应（分群占比变化）与转化效应（分群自身变化），两项相加等于整体变化
5. **解释与建议**：结合 [解读要点](references/pitfalls.md) 把数字翻译成业务原因和可验证的下一步。
6. **交付**：Markdown 结论 + HTML 报告路径。

不能执行代码时：按同样的结构人工计算，并在结论中写明“未经脚本计算”。

## 输出格式

```markdown
## 漏斗分析结果

### 1. 结论
<一句话：整体变化多少、是否可信、主要来自哪一步、是获客问题还是产品问题>

### 2. 漏斗定义
| 步骤 | 事件/状态 | 统计对象 | 转化窗口 |
| --- | --- | --- | --- |

### 3. 漏斗表现
| 步骤 | 本期人数 | 单步转化 | 累计转化 | 对比期单步转化 | 变化 |
| --- | --- | --- | --- | --- | --- |

### 4. 变化来自哪一步
<各步贡献占比；最大贡献步骤恢复后整体能回到多少>

### 5. 变化来自哪类用户
<每个分群维度：结构效应 vs 转化效应，以及具体是哪个分群>

### 6. 数据质量与口径
<样本量、跳步、乱序、缺入口、观察期/截断，以及时间按哪个时区处理>

### 7. 可能原因与验证动作
| 假设 | 支持证据 | 如何验证 | 负责人建议 |
| --- | --- | --- | --- |

### 8. 待确认问题

报告文件：<funnel_report.html 路径>
```

## 质量标准

输出必须：

- 明确步骤顺序、统计对象、转化窗口，并按入口时间划分时期
- 同时看单步转化和累计转化，用比例对比而不是人数对比
- 区分“结构变化”（来了不一样的用户）和“转化变化”（同样的用户转化变差）
- 先排除口径、埋点、观察期截断，再做业务解释
- 样本量不足或变化不显著时明确说明，不过度归因
- 不把分群差异直接写成因果；需要因果时建议做实验
- 数据里混有多种时间写法时，确认时区后再解读按天和按期的结果
- 每个可能原因都对应一个可执行的验证动作

## 完成后的下一步

- 写成报告：`data-analysis-report-writer`，把 `--json` 的结果作为来源
- 验证改版效果：`ab-test-analysis`
- 继续看留存：`retention-cohort-analysis`

## 示例 Prompt

```text
请用 funnel-analysis 分析新用户首购漏斗，并生成 HTML 报告：

数据：events.csv（user_id, event_name, event_time），users.csv（user_id, channel_id, device_type）
步骤：注册 register_success -> 浏览商品 product_view -> 加购 add_to_cart -> 提交订单 order_submit -> 支付成功 pay_success
本期：2026-05-01 到 2026-05-14；对比期：2026-04-17 到 2026-04-30
转化窗口：注册后 7 天
分群：渠道、设备
```

```text
请用 funnel-analysis 分析 SaaS 产品 Trial 到付费的转化漏斗（汇总数据）：

步骤：注册试用 -> 完成 onboarding -> 邀请团队成员 -> 创建首个核心工作流 -> 升级付费
3 月：4200 / 1890 / 1020 / 760 / 290
4 月：5100 / 2091 / 1004 / 742 / 281
另附各注册渠道的分步人数。想知道 4 月转化下降是渠道结构变了，还是产品哪一步出了问题。
```
