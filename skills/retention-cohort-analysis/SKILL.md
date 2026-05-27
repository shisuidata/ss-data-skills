---
name: retention-cohort-analysis
description: Use when analyzing retention, cohort behavior, repeat purchase, active user return, lifecycle changes, or user stickiness over time. Builds cohort definitions, retention matrices, segment comparisons, and business interpretations.
---

# Retention Cohort Analysis

## 目标

分析用户、客户或业务对象在一段时间后的回访、复购、活跃或留存情况，并通过 Cohort 找出不同批次之间的差异。

这个 Skill 关注留存和 Cohort 分析，不负责完整增长策略，也不直接替代指标口径审查。

## 使用场景

使用这个 Skill，当用户需要分析：

- 新用户次日、7 日、30 日留存
- 会员续费或复购
- 客户生命周期变化
- 不同渠道用户质量
- 新功能上线后用户是否持续使用
- 首购后复购间隔
- B 端客户活跃和流失

典型输入：

```text
帮我看不同渠道新用户的 7 日和 30 日留存表现。
```

## 不适用场景

不要用这个 Skill 直接完成：

- 漏斗转化分析，请使用 `funnel-analysis`
- A/B 实验分析，请使用 `ab-test-analysis`
- 指标口径专项审查，请使用 `metric-definition-reviewer`
- 完整报告撰写，请使用 `data-analysis-report-writer`

如果没有明确“首日行为”和“回访行为”，先定义 Cohort 口径。

## 输入信息

最少输入：

- Cohort 起点事件
- 留存或回访事件
- 用户或对象 ID
- 时间字段

可选输入：

- 留存窗口
- 分群维度
- 用户来源
- 业务线
- 历史对比周期
- 是否按自然日、滚动 24 小时或自然周统计
- 复购、续费、活跃等具体行为定义

## 分析框架

1. 定义 Cohort：用户按什么时间和什么行为进入同一批次。
2. 定义回访行为：什么算留存、复购、活跃或继续使用。
3. 定义时间窗口：D1、D7、D30，自然日还是滚动窗口。
4. 构建留存矩阵：横轴为观察窗口，纵轴为 Cohort 批次。
5. 分析整体趋势：留存是否稳定、下降、改善或周期性波动。
6. 分群比较：渠道、版本、地区、用户类型、首单品类等。
7. 识别异常批次：某些 Cohort 是否明显高于或低于历史。
8. 解释原因：结合渠道质量、产品变化、活动、节假日、埋点变更。
9. 给出建议：优化入口、召回、产品体验、会员机制或数据口径。

## 输出格式

```markdown
## 留存 / Cohort 分析结果

### 1. 结论摘要

### 2. Cohort 定义

| 项目 | 口径 |
| --- | --- |
| Cohort 起点 |  |
| 回访/留存行为 |  |
| 统计对象 |  |
| 时间窗口 |  |
| 分群维度 |  |

### 3. 留存矩阵

| Cohort | D1 | D7 | D14 | D30 |
| --- | --- | --- | --- | --- |

### 4. 关键发现

### 5. 分群差异

### 6. 异常批次

### 7. 可能原因

### 8. 建议动作

### 9. 口径风险与待确认问题
```

## 质量标准

输出必须：

- 先定义 Cohort 起点和回访行为
- 说明自然日和滚动窗口差异
- 区分留存率下降和 Cohort 质量变化
- 避免把短期活动效果误读为长期留存改善
- 标记样本量过小的分群结论

## 示例 Prompt

```text
请用 retention-cohort-analysis 分析新用户留存：

Cohort 起点：注册日期
留存行为：任意一次打开 App
窗口：D1、D7、D30
维度：渠道、设备、首日是否完成关键行为
```

