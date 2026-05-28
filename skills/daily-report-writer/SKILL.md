---
name: daily-report-writer
description: Use when writing a concise daily report, daily worklog, standup update, shift handoff, or end-of-day summary for data analysis, data development, BI, governance, or operations work.
---

# Daily Report Writer

## 目标

把一天内零散的数据工作整理成清楚、克制、可同步的日报。

这个 Skill 关注：

- 今天完成了什么
- 对业务或项目有什么价值
- 当前风险和阻塞是什么
- 明天要推进什么
- 哪些事项需要他人协助

## 使用场景

使用这个 Skill，当用户需要：

- 写数据分析、数据开发、BI、治理或项目日报
- 整理 standup 发言稿
- 做跨团队日终同步
- 写值班交接、上线观察或问题跟进日报
- 把零散工作记录整理成可发给主管或项目群的版本

## 不适用场景

不要使用这个 Skill 处理：

- 周报或月报，应使用 `weekly-monthly-report-writer`
- 正式分析报告，应使用 `data-analysis-report-writer`
- 数据事故复盘，应使用 `data-incident-postmortem-writer`
- 没有任何事实材料时凭空写工作成果

## 输入信息

最少输入：

- 日期
- 今天做过的事项列表
- 明天计划

推荐输入：

- 每个事项的状态：完成、进行中、阻塞、待确认
- 产出物：SQL、看板、报告、表、会议结论、问题定位结果
- 影响对象：业务方、项目、指标、任务、表、看板
- 风险和阻塞
- 需要同步或求助的人
- 目标读者：直属主管、项目群、业务方、团队内部

## 上下文建议

优先使用这些模板准备上下文：

- [通用数据任务上下文](../../context/templates/data-task-context.md)
- [报告上下文模板](../../context/templates/report-context.md)

如果日报涉及行业业务，可以补充：

- [电商行业上下文](../../context/industries/ecommerce.md)
- [SaaS 行业上下文](../../context/industries/saas.md)
- [内容社区行业上下文](../../context/industries/content-community.md)

上下文不足时，只整理已知事项，不要编造成果、进度或风险。

## 写作流程

1. 识别日报读者和发送场景。
2. 将事项按完成、推进中、风险阻塞、明日计划归类。
3. 把动作改写为结果，说明产出和影响。
4. 删除流水账、情绪表达和过细过程。
5. 对阻塞事项写清需要谁做什么。
6. 输出一个可直接发送的版本。

## 输出格式

```markdown
## 今日日报

### 今日完成

| 事项 | 产出/结果 | 影响 |
| --- | --- | --- |

### 进行中

| 事项 | 当前进展 | 下一步 |
| --- | --- | --- |

### 风险与阻塞

| 问题 | 影响 | 需要支持 |
| --- | --- | --- |

### 明日计划

### 可直接发送版本
```

## 质量标准

输出必须：

- 基于用户提供的事实，不编造成果
- 把“做了什么”写成“产出了什么”
- 风险和阻塞要可行动
- 语气适合职场同步，避免夸张和邀功
- 读者不同，篇幅和重点要不同
- 保留待确认项，不强行写成已完成

## 示例 Prompt

```text
请用 daily-report-writer 帮我写今天的数据项目日报。

日期：2026-05-28
读者：数据团队负责人和增长项目群。
今天事项：
- 修复新用户激活率看板中渠道 B 口径问题，已完成补数。
- 和产品确认新版引导页实验的核心指标，护栏指标还缺页面加载耗时。
- 写了 dws_user_activation_1d 的字段说明，分区字段和 SLA 还没补。
- 排查支付转化下降，发现移动端支付页 add_to_cart 到 submit 流失变高。
明天计划：
- 补充护栏指标埋点校验。
- 完成激活表文档。
- 和前端确认移动端支付页性能数据。
```
