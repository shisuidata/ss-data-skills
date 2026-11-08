---
name: data-lineage-impact-analyzer
description: Use when analyzing upstream and downstream impact for table changes, metric changes, field deprecation, pipeline migration, dashboard breakage, data governance review, or data asset dependency communication. 中文触发词：血缘分析、影响评估、字段下线、改口径的影响范围、下游影响。
metadata:
  category: 数据开发
  aliases: 血缘分析、影响评估、字段下线评估
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
- 血缘边表 CSV（`upstream`、`downstream`，可选 `upstream_column`）、dbt 的 `manifest.json`，或生产 SQL 文件
- 资产表 CSV（`name`、`type`、`owner`、`importance`），用于分级和通知清单
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
3. 识别影响等级：P0 下游会立刻报错，或核心对象的数字含义改变；P1 需要同步修改或口径变化；P2 间接影响；P3 无直接影响。
4. 判断是否需要兼容期、双跑、回滚和补数。
5. 输出通知对象和沟通节奏。
6. 列出上线前检查、上线后验证和回滚条件。

## 可用脚本

有血缘数据时，用脚本算下游闭包，不要靠记忆列举：

```bash
# 从 SQL 文件提取表级血缘（可选）
python3 scripts/lineage.py edges --sql job_a.sql --sql job_b.sql --out edges.csv

# 计算影响。字段级写成 表名:字段名
python3 scripts/lineage.py impact --edges edges.csv --assets assets.csv \
  --target dwd_order_detail_d:old_channel_id --change drop_column

# dbt 项目
python3 scripts/lineage.py impact --manifest target/manifest.json --target fct_orders --change semantic_change
```

示例见 `assets/`，全部参数见 [命令行参数](references/cli.md)。

结果只覆盖已知血缘。临时 SQL、Excel 和外部系统通常不在血缘里，字段或表下线前要用查询日志核对最近的读取记录。

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

## 回滚触发条件与操作

| 触发条件 | 回滚操作 | 验证方式 |
| --- | --- | --- |

## 通知与协作清单

## 待确认信息
```

## 质量标准

输出必须：

- 区分已知影响和待确认影响
- 有血缘数据时，影响清单来自脚本，并说明血缘覆盖不到的范围
- 不凭空编造下游对象
- 影响等级要说明原因
- 对破坏性变更给出兼容、双跑或回滚建议
- 明确需要通知谁、什么时候通知、通知什么
- 给出上线后验证指标或检查点

## 完成后的下一步

- 需要修改下游 SQL：`sql-reviewer`
- 上线后验证：`data-quality-rule-generator`
- 更新文档和变更记录：`data-doc-writer`
- 同步进展：`daily-report-writer`、`weekly-monthly-report-writer`
- 变更已造成错误：`data-incident-postmortem-writer`

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

```text
请用 data-lineage-impact-analyzer 评估下面这个口径变更的下游影响。

变更对象：SaaS 活跃用户认定口径
变更类型：口径调整
变化内容：活跃用户从"30 天内有任意登录"改为"30 天内完成核心任务至少一次"
计划时间：下月 1 日起生效，需要历史数据回填
已知下游：
- 客户健康度评分模型（使用活跃用户数作为核心特征）
- CSM 续费风险看板活跃度模块
- NPS 触发条件（活跃 30 天以上才触发调研）
希望输出：影响等级、回填方案、兼容窗口、通知清单和回滚触发条件。
```
