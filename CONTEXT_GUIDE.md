# 上下文使用指南

Skill 不是孤立的提示词。

如果你还不熟悉 Skill 的基本概念，建议先看 [Skill 入门教程](docs/skill-tutorial.md)。

一个真正可用的 Skill，至少由三部分组成：

```text
Skill = 工作流程 + 上下文契约 + 输出标准
```

如果缺少上下文，任何工具都容易给出“看起来完整、实际上不可落地”的答案。比如没有指标口径就审 SQL，没有表粒度就设计质量规则，没有受众就写 PPT，这些都会制造新的返工。

如果你是第一次使用这个项目，先看 [快速开始](QUICK_START.md)，再回到这份文档准备上下文。

## 上下文分层

我们把上下文分成三层。

### L0 最小上下文

让 Skill 能启动的最少信息。

例如：

- `sql-reviewer` 至少需要 SQL
- `metric-definition-reviewer` 至少需要指标名称和当前描述
- `data-presentation-architect` 至少需要主题和目标受众

L0 可以让任务启动，但结论通常需要标记假设。

### L1 推荐上下文

让 Skill 能给出更可靠结论的信息。

例如：

- 业务背景
- 指标口径
- 表结构
- 统计粒度
- 时间范围
- 执行引擎
- 下游使用场景
- 已知风险或争议

L1 是日常使用 Skill 的推荐标准。

### L2 丰富上下文

让 Skill 能接近真实工作交付的信息。

例如：

- 数据字典
- 埋点说明
- 表血缘
- 调度依赖
- 历史波动范围
- 业务规则
- 目标读者
- 决策背景
- 既有报告或看板链接

L2 适合复杂分析、上线评审、事故复盘、管理层汇报等场景。

## 通用上下文包

提供上下文时，建议使用下面的结构。

```markdown
## 任务目标

## 业务背景

## 数据对象

## 指标口径

## 时间范围

## 表结构 / 字段说明

## SQL / 计算逻辑

## 约束条件

## 已知问题

## 希望输出
```

不需要每次都填满。关键是把你知道的信息说清楚，把不知道的信息留空或标记待确认。

## 各类 Skill 的上下文重点

| 类型 | 重点上下文 |
| --- | --- |
| 需求澄清 | 业务目标、使用方、时间范围、产出形式、截止时间 |
| 指标口径 | 指标名、业务含义、分子分母、时间窗口、过滤条件、边界规则 |
| 表设计 | 业务场景、数据粒度、上游数据、下游查询、更新频率、保留周期 |
| SQL 审查 | SQL、执行引擎、表结构、分区字段、指标口径、期望结果粒度 |
| 质量规则 | 表结构、主键、分区、更新频率、SLA、核心指标、历史波动 |
| 看板审查 | 看板目标、目标受众、指标列表、图表结构、下钻路径、刷新频率 |
| EDA | 数据样例、字段列表、数据粒度、分析目标、时间字段、主键候选 |
| 业务归因 | 异常指标、异常时间、对比基准、指标口径、可拆维度、已知业务事件 |
| 漏斗分析 | 漏斗步骤、事件定义、统计对象、时间窗口、分群维度 |
| 留存分析 | Cohort 起点、回访行为、用户 ID、时间窗口、分群维度 |
| A/B 实验 | 假设、分组、核心指标、护栏指标、样本量、实验周期 |
| 数据文档 | 文档对象、用途、粒度、字段、上游、下游、更新策略、使用边界 |
| 数据事故复盘 | 事故摘要、影响范围、时间线、修复状态、根因、预防措施 |
| 分析报告 | 主题、读者、关键发现、数据证据、希望推动的决策 |
| 周报月报 | 周期、读者、事项列表、结果、风险、下周期计划 |
| PPT 叙事 | 主题、受众、时长、页数、核心结论、决策诉求 |

## 行业上下文

很多业务类 Skill 不应该做成固定行业版本。更好的方式是：

```text
通用 Skill + 行业上下文 + 具体任务上下文
```

当前提供了三个行业上下文包：

- [电商行业上下文](context/industries/ecommerce.md)：适合 GMV、订单、转化、渠道、商品、退款、库存、活动等场景
- [SaaS 行业上下文](context/industries/saas.md)：适合 MRR、ARR、激活、试用转付费、续费、流失、席位等场景
- [内容社区行业上下文](context/industries/content-community.md)：适合 DAU、留存、内容供给、曝光、点击、互动、创作者生态等场景

行业上下文主要用于：

- `dashboard-reviewer`
- `business-root-cause-analysis`
- `funnel-analysis`
- `retention-cohort-analysis`
- `data-analysis-report-writer`
- `data-presentation-architect`

## 使用模板

我们提供了一组可复制的上下文模板：

- [通用数据任务上下文](context/templates/data-task-context.md)
- [指标口径上下文](context/templates/metric-context.md)
- [表设计上下文](context/templates/table-context.md)
- [SQL 审查上下文](context/templates/sql-review-context.md)
- [数据分析上下文](context/templates/analysis-context.md)
- [实验分析上下文](context/templates/experiment-context.md)
- [报告写作上下文](context/templates/report-context.md)
- [PPT 汇报上下文](context/templates/presentation-context.md)

也提供一个可用于演示和练习的预制上下文包：

- [电商增长分析示例上下文](context/packs/ecommerce-growth-demo.md)

行业上下文见：

- [行业上下文包索引](context/industries/README.md)

## 使用原则

1. 先给目标，再给材料。
2. 先说明事实，再说明判断。
3. 不确定的信息不要编，标记为待确认。
4. 业务规则比字段名更重要。
5. 结果要说明适用边界。
6. 复杂任务优先使用 L1 或 L2 上下文。

## 推荐 Prompt 结构

```text
请使用 [技能名称] 处理下面的任务。

目标：
[写清楚你要得到什么]

上下文：
[粘贴上下文模板]

输出要求：
[写清楚希望输出报告、表格、SQL、PPT 大纲还是检查清单]
```
