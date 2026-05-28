# 快速开始

这份说明面向第一次使用“拾穗数据技能库”的数据从业者。

你不需要先理解任何复杂概念。把它当成一套“数据工作标准动作说明书”就可以。

如果你第一次听说 Skill，建议先花几分钟读 [Skill 入门教程](docs/skill-tutorial.md)，理解它和普通提示词的区别。

## 30 秒用起来

1. 打开 [技能索引](SKILL_INDEX.md)，按你正在做的事情选一个技能。
2. 进入对应技能文档，复制其中的说明。
3. 把技能说明、你的任务材料和上下文一起发给你正在使用的工具。

推荐 Prompt：

```text
请按下面这个技能的工作方式处理我的任务。

技能说明：
[粘贴对应技能文档]

我的任务：
[写清楚你要解决的问题]

上下文：
[粘贴 context/templates/ 中的模板，按实际情况填写]

输出要求：
[说明你希望得到清单、报告、表格、SQL 建议还是 PPT 大纲]
```

## 不知道选哪个技能

先从这几个入口选：

| 你的任务 | 推荐技能 |
| --- | --- |
| 业务需求很模糊 | [数据需求澄清](skills/data-requirement-clarifier/SKILL.md) |
| 指标口径说不清 | [指标口径审查](skills/metric-definition-reviewer/SKILL.md) |
| SQL 写完怕算错 | [SQL 审查](skills/sql-reviewer/SKILL.md) |
| 表要上线或交接 | [数据文档写作](skills/data-doc-writer/SKILL.md) |
| 看板没人用 | [看板审查](skills/dashboard-reviewer/SKILL.md) |
| 指标突然下降 | [业务归因分析](skills/business-root-cause-analysis/SKILL.md) |
| 要写日报、周报或月报 | [日报写作](skills/daily-report-writer/SKILL.md) / [周报月报写作](skills/weekly-monthly-report-writer/SKILL.md) |
| 要做行业或竞品研究 | [行业市场调研](skills/market-research-analyst/SKILL.md) |
| 要做汇报 PPT | [数据汇报 PPT 架构](skills/data-presentation-architect/SKILL.md) |

完整选择方式见 [技能索引](SKILL_INDEX.md)。

## 上下文怎么给

技能不是魔法。上下文越清楚，输出越可靠。

最小上下文：

```text
目标：
我想解决什么问题。

材料：
SQL / 表结构 / 指标口径 / 看板说明 / 数据结果。

输出要求：
我希望得到什么格式。
```

更推荐使用模板：

- [通用数据任务上下文](context/templates/data-task-context.md)
- [指标口径上下文](context/templates/metric-context.md)
- [表设计上下文](context/templates/table-context.md)
- [SQL 审查上下文](context/templates/sql-review-context.md)
- [数据分析上下文](context/templates/analysis-context.md)
- [工具集成上下文](context/templates/tool-integration-context.md)
- [报告写作上下文](context/templates/report-context.md)
- [PPT 汇报上下文](context/templates/presentation-context.md)

如果问题和行业强相关，再补一个行业上下文：

- [电商行业上下文](context/industries/ecommerce.md)
- [SaaS 行业上下文](context/industries/saas.md)
- [内容社区行业上下文](context/industries/content-community.md)

## 三个常用示例

### SQL 审查

```text
请用 SQL 审查帮我检查下面这段 Spark SQL。

背景：
计算每天每个渠道的新用户首购转化率。

SQL：
[粘贴 SQL]

重点检查：
1. 是否会算错
2. 是否有口径风险
3. 是否有性能风险
4. 应该如何改写
```

### 业务归因分析

```text
请用业务归因分析处理下面的问题。

异常指标：
新用户 7 日激活率从 42% 降到 31%。

时间范围：
2026-05-13 至 2026-05-19。

已知变化：
新版引导页上线，渠道 B 注册占比提高。

请输出：
归因假设树、验证路径、下一步建议。
```

### 数据汇报 PPT

```text
请用数据汇报 PPT 架构把下面的分析结果整理成 8 页 PPT 大纲。

受众：
业务负责人。

核心结论：
[粘贴分析结论]

输出要求：
每页标题、核心信息、建议图表、讲述重点。
```

## 使用边界

- 不要让技能凭空编造表结构、指标口径或业务规则。
- 不确定的信息可以留空，但要让 AI 标记为待确认。
- 一个任务太复杂时，拆成多个技能串起来用。
- 真实公司数据、截图、日志和表结构要先脱敏。

想进一步理解 Skill 的原理、组成和常见误区，可以继续看 [Skill 入门教程](docs/skill-tutorial.md)。
