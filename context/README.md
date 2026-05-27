# 上下文模板

这个目录提供 Skill 使用时可复制的上下文模板和预制上下文包。

Skill 可以独立使用，但不应该脱离上下文。上下文越清楚，Agent 给出的结论越可靠。

## 模板列表

| 模板 | 适用场景 |
| --- | --- |
| [data-task-context.md](templates/data-task-context.md) | 通用数据任务、需求澄清、临时分析 |
| [metric-context.md](templates/metric-context.md) | 指标定义、指标审查、口径对齐 |
| [table-context.md](templates/table-context.md) | 表设计、表结构审查、数仓建模 |
| [sql-review-context.md](templates/sql-review-context.md) | SQL 审查、SQL 优化、上线前 Review |
| [analysis-context.md](templates/analysis-context.md) | EDA、漏斗、留存、专题分析 |
| [experiment-context.md](templates/experiment-context.md) | A/B 实验设计、实验结果解读 |
| [report-context.md](templates/report-context.md) | 分析报告、复盘报告、经营分析 |
| [presentation-context.md](templates/presentation-context.md) | PPT 大纲、管理层汇报、项目演示 |

## 预制上下文包

| 上下文包 | 用途 |
| --- | --- |
| [ecommerce-growth-demo.md](packs/ecommerce-growth-demo.md) | 用于演示转化、留存、实验、报告和 PPT 类 Skill |

## 行业上下文包

行业上下文包用于给通用 Skill 补充业务语义。比如同样是“转化下降”，电商看访问、加购、下单、支付和退款；SaaS 看注册、激活、试用、转付费和流失；内容社区看曝光、点击、消费、互动和回访。

| 行业 | 用途 |
| --- | --- |
| [电商](industries/ecommerce.md) | GMV、订单、转化、渠道、商品、退款、库存、活动 |
| [SaaS](industries/saas.md) | MRR、ARR、激活、试用转付费、续费、流失、席位 |
| [内容社区](industries/content-community.md) | DAU、留存、内容供给、曝光、点击、互动、创作者生态 |

## 使用方式

复制对应模板，填入你已知的信息，然后和 Skill 一起发给 Agent。

```text
请使用 funnel-analysis 分析下面的问题。

上下文：
[粘贴 analysis-context.md 中的内容并填写]
```

不确定的信息可以留空，但不要编造。

如果任务强依赖行业业务，建议同时粘贴一个行业上下文包中的相关部分。
