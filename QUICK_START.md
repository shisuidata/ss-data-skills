# 快速开始

这份说明面向第一次使用“拾穗数据技能库”的数据从业者。

你不需要先理解所有 Agent、Skill、MCP 的概念。把它当成一套“数据工作标准动作说明书”就可以。

## 30 秒用起来

1. 打开 [技能索引](SKILL_INDEX.md)，按你正在做的事情选一个技能。
2. 打开对应的 `skills/<skill-id>/SKILL.md`。
3. 复制技能说明、你的任务和上下文，发给你正在使用的 AI 助手。

推荐 Prompt：

```text
请按【技能中文名】这个技能的工作方式处理下面的问题。

技能说明：
[粘贴 skills/<skill-id>/SKILL.md]

我的任务：
[写清楚你要解决的问题]

上下文：
[粘贴 context/templates/ 中的模板，按实际情况填写]

输出要求：
[说明你希望得到清单、报告、表格、SQL 建议还是 PPT 大纲]
```

## 不知道选哪个技能

先从这几个入口选：

| 你的任务 | 中文技能名 | 英文 ID |
| --- | --- | --- |
| 业务需求很模糊 | 数据需求澄清 | `data-requirement-clarifier` |
| 指标口径说不清 | 指标口径审查 | `metric-definition-reviewer` |
| SQL 写完怕算错 | SQL 审查 | `sql-reviewer` |
| 表要上线或交接 | 数据文档写作 | `data-doc-writer` |
| 看板没人用 | 看板审查 | `dashboard-reviewer` |
| 指标突然下降 | 业务归因分析 | `business-root-cause-analysis` |
| 要写分析报告 | 数据分析报告写作 | `data-analysis-report-writer` |
| 要做汇报 PPT | 数据汇报 PPT 架构 | `data-presentation-architect` |

完整选择方式见 [技能索引](SKILL_INDEX.md)。

## 中文名和英文 ID 怎么理解

这个项目有两套名称：

- 中文名：给人看的，例如“SQL 审查”“看板审查”
- 英文 ID：给工具和目录用的，例如 `sql-reviewer`、`dashboard-reviewer`

你和 AI 对话时，建议同时写：

```text
请用 SQL 审查（sql-reviewer）处理下面的问题。
```

这样既符合国内用户的阅读习惯，也能让支持 Skill 的 Agent 更稳定地识别。

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
- [报告写作上下文](context/templates/report-context.md)
- [PPT 汇报上下文](context/templates/presentation-context.md)

如果问题和行业强相关，再补一个行业上下文：

- [电商行业上下文](context/industries/ecommerce.md)
- [SaaS 行业上下文](context/industries/saas.md)
- [内容社区行业上下文](context/industries/content-community.md)

## 三个常用示例

### SQL 审查

```text
请用 SQL 审查（sql-reviewer）帮我审查下面这段 Spark SQL。

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
请用业务归因分析（business-root-cause-analysis）分析下面的问题。

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
请用数据汇报 PPT 架构（data-presentation-architect）把下面的分析结果整理成 8 页 PPT 大纲。

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

