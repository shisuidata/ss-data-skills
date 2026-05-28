---
name: data-lineage-impact-analyzer
description: Use when analyzing upstream and downstream impact for table changes, metric changes, field deprecation, pipeline migration, dashboard breakage, data governance review, or data asset dependency communication.
---

# Data Lineage Impact Analyzer

## 目标

分析数据表、字段、指标、任务或口径变更会影响哪些下游，并输出可执行的影响评估和沟通方案。

这个 Skill 关注变更影响，而不是完整血缘系统建设。

## 使用场景

使用这个 Skill，当用户需要：

- 修改表结构、字段、分区、口径前做影响评估
- 下线字段、迁移表、重构任务或切换数据源
- 排查某个上游异常会影响哪些看板、报表、模型和业务方
- 数据治理中梳理资产依赖和通知范围
- 为变更评审会准备影响分析材料

## 不适用场景

不要使用这个 Skill 处理：

- 从零建设数据血缘平台
- 审查 SQL 正确性，应使用 `sql-reviewer`
- 设计新表，应使用 `table-design-advisor`
- 写事故复盘，应使用 `data-incident-postmortem-writer`
- 没有任何表、字段、任务或下游信息时断言影响范围

## 输入信息

最少输入：

- 变更对象：表、字段、指标、任务或数据源
- 变更类型：新增、修改、删除、迁移、下线、口径调整
- 已知上下游信息

推荐输入：

- 表结构、字段说明、分区和更新频率
- 上游来源、调度依赖、任务名
- 下游表、看板、报表、指标、模型、接口
- SQL 片段或血缘导出
- 变更时间、灰度策略、回滚方案
- 业务负责人、数据负责人、通知对象

## 上下文建议

优先使用这些模板准备上下文：

- [表设计上下文模板](../../context/templates/table-context.md)
- [SQL 审查上下文模板](../../context/templates/sql-review-context.md)
- [通用数据任务上下文](../../context/templates/data-task-context.md)
- [报告上下文模板](../../context/templates/report-context.md)

上下文不足时，只能输出影响评估框架和待补充血缘信息，不要假设不存在的下游。

## 分析流程

1. 明确变更对象和变更类型。
2. 拆分影响面：字段、指标、任务、表、看板、报表、接口、模型、业务流程。
3. 识别影响等级：P0 阻断、P1 口径变化、P2 展示变化、P3 无直接影响。
4. 判断是否需要兼容期、双跑、回滚和补数。
5. 输出通知对象和沟通节奏。
6. 列出上线前检查、上线后验证和回滚条件。

## 输出格式

```markdown
## 影响评估结论

## 变更说明

## 已知血缘

## 影响清单

| 对象 | 类型 | 影响等级 | 影响说明 | 处理建议 |
| --- | --- | --- | --- | --- |

## 风险与缓解措施

## 上线 / 下线计划

## 通知与协作清单

## 待确认信息
```

## 质量标准

输出必须：

- 区分已知影响和待确认影响
- 不凭空编造下游对象
- 影响等级要说明原因
- 对破坏性变更给出兼容、双跑或回滚建议
- 明确需要通知谁、什么时候通知、通知什么
- 给出上线后验证指标或检查点

## 示例 Prompt

```text
请用 data-lineage-impact-analyzer 评估下面这个字段下线变更。

变更对象：dwd_order_detail_d.old_channel_id
变更类型：字段下线。
原因：渠道归因统一切换到 channel_id_v2。
计划时间：2026-06-10 起停止写入 old_channel_id，2026-06-30 删除字段。
已知下游：
- ads_channel_gmv_1d 使用 old_channel_id 聚合渠道 GMV
- 经营日报渠道模块读取 ads_channel_gmv_1d
- 渠道投放复盘 SQL 中有历史查询使用 old_channel_id
希望输出：影响等级、兼容方案、通知对象、上线前检查和回滚条件。
```
