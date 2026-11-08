---
name: data-doc-writer
description: Use when writing or improving data documentation for warehouse tables, metrics, dashboards, SQL jobs, data products, or handover materials so other people and agents can understand data purpose, grain, fields, logic, ownership, and usage constraints. 中文触发词：数据文档、字段字典、表说明、交接文档、数据资产说明。
metadata:
  category: 文档协作
  aliases: 数据文档、数据资产文档、交接文档
---

# Data Doc Writer

## 目标

把表结构、SQL、指标口径、看板说明或任务逻辑整理成可交接、可维护、可复用的数据文档。

这个 Skill 的重点不是写漂亮文案，而是降低数据资产使用和维护成本。

## 使用场景

使用这个 Skill，当用户需要：

- 给新上线的数仓表写说明文档
- 给指标、看板或数据产品补使用说明
- 把 SQL 任务逻辑整理成交接文档
- 做数据资产盘点、知识库沉淀或新人 onboarding
- 为检索系统、语义层或自动化工具准备结构化数据说明

## 不适用场景

不要使用这个 Skill 处理：

- 从业务需求推导表结构，应使用 `table-design-advisor`
- 审查 SQL 正确性，应使用 `sql-reviewer`
- 生成质量规则，应使用 `data-quality-rule-generator`
- 写分析报告，应使用 `data-analysis-report-writer`
- 在缺少表名、用途、字段或计算逻辑时编造文档

## 输入信息

最少输入：

- 文档对象：表、指标、看板、SQL 任务或数据产品
- 用途说明
- 字段列表、指标列表或主要逻辑

推荐输入：

- 表名、主题域、分层、数据粒度
- 主键、分区字段、更新频率、保留周期
- 字段名称、类型、含义、枚举值、是否可空
- DDL、生产 SQL、`eda.py` 的体检结果（可以直接生成初稿）
- 上游来源、下游使用方、负责人
- SQL 或伪代码
- 指标口径、边界条件和常见误用
- 数据质量规则和 SLA

## 上下文建议

优先使用这些模板准备上下文：

- [表设计上下文模板](../../context/templates/table-context.md)：适合表说明和字段字典
- [SQL 审查上下文模板](../../context/templates/sql-review-context.md)：适合 SQL 任务文档
- [指标上下文模板](../../context/templates/metric-context.md)：适合指标口径文档
- [报告上下文模板](../../context/templates/report-context.md)：适合看板或数据产品说明

如果文档面向特定业务域，建议补充行业上下文：

- [电商行业上下文](../../context/industries/ecommerce.md)
- [SaaS 行业上下文](../../context/industries/saas.md)
- [内容社区行业上下文](../../context/industries/content-community.md)

上下文不足时，输出可填写的文档骨架，并把缺失信息列为待补充项。

## 写作流程

1. 识别文档对象和目标读者：开发、分析、业务、管理者或工具使用方。
2. 提炼数据用途、业务含义、统计粒度和使用边界。
3. 整理字段字典、指标口径、计算逻辑、上下游关系。
4. 标记风险：易误用字段、延迟、历史变更、口径限制、权限限制。
5. 给出查询示例或使用示例。
6. 形成可维护的 Markdown 文档，并保留待补充清单。

## 可用脚本

有 DDL、SQL 或体检结果时，先生成草稿，再补业务含义：

```bash
python3 scripts/doc_gen.py draft --ddl table.sql --sql job.sql --eda eda.json --eda-table orders --format md --out doc.md
```

`--format` 可选 `md`、`yaml`、`dbt`。给检索系统、语义层或自动化工具用时输出 `yaml` 或 `dbt`。示例 DDL 见 `assets/example_ddl.sql`，全部参数见 [命令行参数](references/cli.md)。

脚本只整理能从材料里确定的信息，业务含义、使用边界和负责人写成【待补充】。你可以根据用户提供的上下文填写，不能猜测。

## 输出格式

```markdown
# 数据文档：对象名称

## 1. 基本信息

| 项目 | 内容 |
| --- | --- |

## 2. 业务用途

## 3. 数据粒度与更新策略

## 4. 字段字典 / 指标字典

| 字段/指标 | 类型 | 含义 | 口径/枚举 | 注意事项 |
| --- | --- | --- | --- | --- |

## 5. 生产逻辑

## 6. 上下游关系

## 7. 使用示例

## 8. 质量规则与 SLA

## 9. 常见误用与风险

## 10. 待补充信息
```

用于检索系统、语义层或自动化工具时，同时给出结构化版本（YAML 或 dbt `schema.yml`），字段含义和 Markdown 版本保持一致。

## 质量标准

输出必须：

- 说明数据对象的用途和适用边界
- 明确粒度、主键、分区、更新频率和数据延迟
- 字段说明要能让非作者理解，不能只重复字段名
- 指标口径要写清分子、分母、时间窗口和过滤条件
- 标出常见误用，而不是只写正向说明
- 缺失信息用待补充项，不编造负责人、口径或血缘

## 完成后的下一步

- 写文档时发现口径有争议：`metric-definition-reviewer`
- 文档对象要变更或下线：`data-lineage-impact-analyzer`
- 缺校验：`data-quality-rule-generator`

## 示例 Prompt

```text
请用 data-doc-writer 为下面这张表写数据文档。

表名：dws_user_activation_1d
用途：统计 SaaS 产品新注册用户在注册后 7 天内的激活情况。
粒度：register_date + channel + user_id。
更新频率：每天 8 点产出上一日数据。
字段：
- register_date string 注册日期
- user_id string 用户 ID
- channel string 注册渠道
- create_workspace_flag int 是否创建工作区
- invite_member_flag int 是否邀请成员
- complete_task_flag int 是否完成核心任务
- activated_flag int 是否激活，任意两个 flag 为 1 即激活
下游：激活率看板、周报、增长实验分析。

请输出可交接的 Markdown 文档，并列出待补充信息。
```

```text
请用 data-doc-writer 为下面这张 DWS 汇总表写数据文档。

表名：dws_order_channel_summary_1d
用途：支撑渠道投放经营日报和渠道 GMV 看板。
粒度：dt + channel_id。
更新频率：每天 T+1 10:00 前产出。
字段：
- dt string 日期分区
- channel_id string 渠道 ID
- channel_name string 渠道名称
- new_user_cnt bigint 新用户数
- order_cnt bigint 订单数
- gmv decimal 成交金额（已支付，不含退款）
- first_purchase_user_cnt bigint 首购用户数
- conversion_rate decimal 注册到首购转化率
下游：渠道 GMV 看板、经营日报、投放效果周报。
上游：ods_order_detail、dwd_user_register_d。
```
