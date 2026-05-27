# 技能索引

这个索引用来帮助你快速找到应该使用哪个技能。

如果你已经知道英文 Skill ID，可以直接进入对应目录。如果你只是知道“我现在要做什么”，从下面的场景入口开始。

第一次使用建议先看 [快速开始](QUICK_START.md)。

如果你想先看输入输出样例，可以查看 [示例索引](examples/README.md)。

如果你要准备更完整的业务、指标、表结构或汇报上下文，可以查看 [上下文使用指南](CONTEXT_GUIDE.md) 和 [上下文模板](context/README.md)。

如果你想检查技能库是否结构完整，可以查看 [测试说明](TESTING.md)。

## 一句话选择

| 你现在要做什么 | 中文技能名 | 英文 ID |
| --- | --- | --- |
| 把一句模糊的数据需求变成可执行任务 | 数据需求澄清 | `data-requirement-clarifier` |
| 审查一个指标口径是否严谨 | 指标口径审查 | `metric-definition-reviewer` |
| 设计或审查一张数仓表 | 数仓表设计建议 | `table-design-advisor` |
| 审查一段 SQL 是否会算错或跑慢 | SQL 审查 | `sql-reviewer` |
| 给一张表或任务补质量规则 | 数据质量规则生成 | `data-quality-rule-generator` |
| 审查一个看板是否能支持业务决策 | 看板审查 | `dashboard-reviewer` |
| 拿到一份新数据，先摸清结构和质量 | 探索性数据分析 | `exploratory-data-analysis` |
| 分析某个业务指标为什么异常 | 业务归因分析 | `business-root-cause-analysis` |
| 分析注册、下单、支付等转化漏斗 | 漏斗分析 | `funnel-analysis` |
| 分析留存、复购、活跃回访和 Cohort | 留存 Cohort 分析 | `retention-cohort-analysis` |
| 设计或解读 A/B 实验 | A/B 实验分析 | `ab-test-analysis` |
| 给表、任务、指标或看板写数据文档 | 数据文档写作 | `data-doc-writer` |
| 写数据事故复盘 | 数据事故复盘 | `data-incident-postmortem-writer` |
| 把分析结果写成报告 | 数据分析报告写作 | `data-analysis-report-writer` |
| 写周报、月报或项目进展 | 周报月报写作 | `weekly-monthly-report-writer` |
| 把报告或材料整理成 PPT 大纲 | 数据汇报 PPT 架构 | `data-presentation-architect` |

使用时建议同时写中文名和英文 ID：

```text
请用 SQL 审查（sql-reviewer）处理下面的问题。
```

## 按工作阶段找

### 1. 接需求

| 场景 | 推荐技能 | 产出 |
| --- | --- | --- |
| 业务说“帮我看一下最近为什么下降” | 数据需求澄清（`data-requirement-clarifier`） | 目标、指标、维度、范围、任务拆解 |
| 业务已有指标名，但口径不清楚 | 指标口径审查（`metric-definition-reviewer`） | 指标定义、分子分母、边界条件、待确认问题 |
| 业务已经确认某个指标异常 | 业务归因分析（`business-root-cause-analysis`） | 异常确认、假设树、验证路径、行动建议 |

### 2. 做开发

| 场景 | 推荐技能 | 产出 |
| --- | --- | --- |
| 要沉淀一张新表 | 数仓表设计建议（`table-design-advisor`） | 表粒度、字段、分区、更新策略 |
| SQL 写完准备上线 | SQL 审查（`sql-reviewer`） | 逻辑风险、性能风险、改写建议 |
| 任务上线前要补质量校验 | 数据质量规则生成（`data-quality-rule-generator`） | 质量规则、告警级别、校验 SQL |
| 表、指标或任务要交接给别人 | 数据文档写作（`data-doc-writer`） | 数据文档、字段字典、使用边界、待补充项 |

### 3. 做分析

| 场景 | 推荐技能 | 产出 |
| --- | --- | --- |
| 新拿到一份数据，不知道能不能用 | 探索性数据分析（`exploratory-data-analysis`） | 数据画像、质量问题、异常、下一步方向 |
| 核心指标异常，需要定位原因 | 业务归因分析（`business-root-cause-analysis`） | 指标拆解、归因假设、验证计划 |
| 想知道用户在哪一步流失 | 漏斗分析（`funnel-analysis`） | 漏斗表现、关键流失点、分群差异 |
| 想知道用户是不是留下来了 | 留存 Cohort 分析（`retention-cohort-analysis`） | 留存矩阵、Cohort 差异、异常批次 |
| 想判断实验是否可以全量 | A/B 实验分析（`ab-test-analysis`） | 实验可信度、指标结果、上线建议 |
| 看板上线前或改版前要审查 | 看板审查（`dashboard-reviewer`） | 看板目标、指标层级、图表和下钻建议 |

### 4. 做汇报

| 场景 | 推荐技能 | 产出 |
| --- | --- | --- |
| 数据已经算完，要写正式报告 | 数据分析报告写作（`data-analysis-report-writer`） | 执行摘要、发现、解释、建议 |
| 每周或每月要向上同步 | 周报月报写作（`weekly-monthly-report-writer`） | 重点进展、价值、风险、下周期计划 |
| 要把分析讲给老板或业务方 | 数据汇报 PPT 架构（`data-presentation-architect`） | PPT 结构、每页标题、图表建议、讲稿提示 |
| 数据事故需要复盘和同步 | 数据事故复盘（`data-incident-postmortem-writer`） | 影响范围、时间线、根因、预防措施 |

## 按角色找

### 数据分析师

常用技能：

- `data-requirement-clarifier`
- `metric-definition-reviewer`
- `exploratory-data-analysis`
- `business-root-cause-analysis`
- `funnel-analysis`
- `retention-cohort-analysis`
- `ab-test-analysis`
- `dashboard-reviewer`
- `data-analysis-report-writer`
- `data-presentation-architect`

典型链路：

```text
需求澄清 -> 指标口径 -> 数据探索 -> 专项分析 -> 分析报告 -> PPT 汇报
```

### 数据开发 / 数据工程师

常用技能：

- `data-requirement-clarifier`
- `metric-definition-reviewer`
- `table-design-advisor`
- `sql-reviewer`
- `data-quality-rule-generator`
- `data-doc-writer`
- `data-incident-postmortem-writer`
- `weekly-monthly-report-writer`

典型链路：

```text
需求澄清 -> 指标口径 -> 表设计 -> SQL 审查 -> 质量规则 -> 上线同步
```

### BI / 数据产品

常用技能：

- `metric-definition-reviewer`
- `dashboard-reviewer`
- `business-root-cause-analysis`
- `funnel-analysis`
- `retention-cohort-analysis`
- `data-doc-writer`
- `data-analysis-report-writer`
- `data-presentation-architect`

典型链路：

```text
指标定义 -> 分析拆解 -> 看板/报告口径 -> 汇报材料
```

### 数据团队负责人

常用技能：

- `data-analysis-report-writer`
- `weekly-monthly-report-writer`
- `data-presentation-architect`
- `dashboard-reviewer`
- `business-root-cause-analysis`
- `data-incident-postmortem-writer`
- `data-quality-rule-generator`
- `sql-reviewer`

典型链路：

```text
团队进展 -> 风险识别 -> 质量保障 -> 管理层汇报
```

## 按输入材料找

| 你手上有什么 | 推荐技能 |
| --- | --- |
| 一句话业务需求 | `data-requirement-clarifier` |
| 指标名称和粗略描述 | `metric-definition-reviewer` |
| 表结构或建表想法 | `table-design-advisor` |
| SQL | `sql-reviewer` |
| 表结构、SQL 或任务说明 | `data-quality-rule-generator` |
| 看板截图、指标列表或页面结构 | `dashboard-reviewer` |
| CSV、Excel、字段列表或数据样例 | `exploratory-data-analysis` |
| 业务指标异常描述和对比数据 | `business-root-cause-analysis` |
| 漏斗步骤和每步人数 | `funnel-analysis` |
| 用户 ID、时间字段、回访行为 | `retention-cohort-analysis` |
| 实验组、对照组、指标结果 | `ab-test-analysis` |
| 表结构、SQL、指标说明或看板说明 | `data-doc-writer` |
| 事故摘要、影响范围和时间线 | `data-incident-postmortem-writer` |
| 已有分析结论和数据结果 | `data-analysis-report-writer` |
| 零散工作事项 | `weekly-monthly-report-writer` |
| 报告、提纲或项目材料 | `data-presentation-architect` |

## 常见组合

### 新需求开发

```text
data-requirement-clarifier
-> metric-definition-reviewer
-> table-design-advisor
-> sql-reviewer
-> data-quality-rule-generator
-> data-doc-writer
```

### 转化下降分析

```text
data-requirement-clarifier
-> exploratory-data-analysis
-> business-root-cause-analysis
-> funnel-analysis
-> data-analysis-report-writer
-> data-presentation-architect
```

### 经营看板改版

```text
metric-definition-reviewer
-> dashboard-reviewer
-> data-doc-writer
```

### 指标异常归因

```text
metric-definition-reviewer
-> business-root-cause-analysis
-> exploratory-data-analysis
-> data-analysis-report-writer
```

### 留存专题分析

```text
metric-definition-reviewer
-> exploratory-data-analysis
-> retention-cohort-analysis
-> data-analysis-report-writer
```

### 实验复盘

```text
metric-definition-reviewer
-> ab-test-analysis
-> data-analysis-report-writer
-> data-presentation-architect
```

### 向上汇报

```text
weekly-monthly-report-writer
-> data-presentation-architect
```

### 数据事故复盘

```text
sql-reviewer
-> data-quality-rule-generator
-> data-incident-postmortem-writer
```

## 不确定用哪个怎么办

如果你不确定该用哪个技能，先用“数据需求澄清”（`data-requirement-clarifier`）。

它会帮你把问题拆清楚，再判断是否需要进入指标、开发、分析或汇报类技能。
