# 技能索引

这个索引用来帮助你快速找到应该使用哪个技能。

如果你是第一次使用，建议先看 [快速开始](QUICK_START.md)。

如果你还不知道 Skill 是什么，先看 [Skill 入门教程](docs/skill-tutorial.md)。

如果你要准备更完整的业务、指标、表结构或汇报上下文，可以查看 [上下文使用指南](CONTEXT_GUIDE.md) 和 [上下文模板](context/README.md)。

如果你想先看输入输出样例，可以查看 [示例索引](examples/README.md)。

## 一句话选择

| 你现在要做什么 | 推荐技能 |
| --- | --- |
| 把一句模糊的数据需求变成可执行任务 | [数据需求澄清](skills/data-requirement-clarifier/SKILL.md) |
| 审查一个指标口径是否严谨 | [指标口径审查](skills/metric-definition-reviewer/SKILL.md) |
| 设计或审查一张数仓表 | [数仓表设计建议](skills/table-design-advisor/SKILL.md) |
| 审查一段 SQL 是否会算错或跑慢 | [SQL 审查](skills/sql-reviewer/SKILL.md) |
| 给一张表或任务补质量规则 | [数据质量规则生成](skills/data-quality-rule-generator/SKILL.md) |
| 评估字段、表或指标变更影响 | [血缘影响分析](skills/data-lineage-impact-analyzer/SKILL.md) |
| 规划数据库、API 或三方工具接入 | [数据工具集成规划](skills/data-tool-integration-planner/SKILL.md) |
| 设计 Flink、Spark Streaming、Kafka 或 CDC 实时管道 | [实时管道设计](skills/stream-pipeline-designer/SKILL.md) |
| 拿到一份新数据，先摸清结构和质量 | [探索性数据分析](skills/exploratory-data-analysis/SKILL.md) |
| 分析某个业务指标为什么异常 | [业务归因分析](skills/business-root-cause-analysis/SKILL.md) |
| 分析注册、下单、支付等转化漏斗 | [漏斗分析](skills/funnel-analysis/SKILL.md) |
| 分析留存、复购、活跃回访和 Cohort | [留存 Cohort 分析](skills/retention-cohort-analysis/SKILL.md) |
| 设计或解读 A/B 实验、算样本量 | [A/B 实验分析](skills/ab-test-analysis/SKILL.md) |
| 审查一个看板是否能支持业务决策 | [看板审查](skills/dashboard-reviewer/SKILL.md) |
| 做行业、竞品或市场机会研究 | [行业市场调研](skills/market-research-analyst/SKILL.md) |
| 从原始数据字段设计模型特征 | [特征工程建议](skills/feature-engineering-advisor/SKILL.md) |
| 审查机器学习模型评估方案是否合理 | [模型评估审查](skills/model-evaluation-reviewer/SKILL.md) |
| 写日报 | [日报写作](skills/daily-report-writer/SKILL.md) |
| 写周报、月报或项目进展 | [周报月报写作](skills/weekly-monthly-report-writer/SKILL.md) |
| 给表、任务、指标或看板写数据文档 | [数据文档写作](skills/data-doc-writer/SKILL.md) |
| 写数据事故复盘 | [数据事故复盘](skills/data-incident-postmortem-writer/SKILL.md) |
| 把分析结果写成报告 | [数据分析报告写作](skills/data-analysis-report-writer/SKILL.md) |
| 把报告或材料整理成 PPT 大纲 | [数据汇报 PPT 架构](skills/data-presentation-architect/SKILL.md) |
| 把分析结果画成图、做成 HTML 报告 | [拾穗图表规范](skills/data-viz-kit/SKILL.md) |

## 按工作阶段找

### 1. 接需求

| 场景 | 推荐技能 | 产出 |
| --- | --- | --- |
| 业务说"帮我看一下最近为什么下降" | [数据需求澄清](skills/data-requirement-clarifier/SKILL.md) | 一句话目标、阻塞问题，或完整的任务拆解 |
| 业务已有指标名，但口径不清楚 | [指标口径审查](skills/metric-definition-reviewer/SKILL.md) | 指标定义、分子分母、边界条件、待确认问题 |
| 业务已经确认某个指标异常 | [业务归因分析](skills/business-root-cause-analysis/SKILL.md) | 脚本确认异常、拆解贡献，给出假设树和验证路径 |
| 需要调研一个行业或业务方向 | [行业市场调研](skills/market-research-analyst/SKILL.md) | 研究边界、信息源、竞品框架、机会判断 |

### 2. 做开发

| 场景 | 推荐技能 | 产出 |
| --- | --- | --- |
| 要沉淀一张新表 | [数仓表设计建议](skills/table-design-advisor/SKILL.md) | 表粒度、字段、分区、更新策略 |
| SQL 写完准备上线 | [SQL 审查](skills/sql-reviewer/SKILL.md) | 静态检查结果、逻辑风险、性能风险、改写建议 |
| 任务上线前要补质量校验 | [数据质量规则生成](skills/data-quality-rule-generator/SKILL.md) | 质量规则、告警级别、校验 SQL、dbt 和 Great Expectations 配置 |
| 表、指标或任务要交接给别人 | [数据文档写作](skills/data-doc-writer/SKILL.md) | 数据文档、字段字典、使用边界、待补充项，可输出 YAML 和 dbt |
| 字段、表或口径要变更 | [血缘影响分析](skills/data-lineage-impact-analyzer/SKILL.md) | 脚本计算的下游影响、风险等级、兼容和通知方案 |
| 要接数据库、API、BI 或调度工具 | [数据工具集成规划](skills/data-tool-integration-planner/SKILL.md) | 接入方式、配置模板、安全检查、验证步骤 |
| 要构建实时数据管道或 CDC 链路 | [实时管道设计](skills/stream-pipeline-designer/SKILL.md) | 引擎选型、容量估算、一致性保证、监控 |

### 3. 做分析

| 场景 | 推荐技能 | 产出 |
| --- | --- | --- |
| 新拿到一份数据，不知道能不能用 | [探索性数据分析](skills/exploratory-data-analysis/SKILL.md) | 数据体检报告：P0/P1/P2 问题清单、字段画像、关联完整性、下一步方向 |
| 核心指标异常，需要定位原因 | [业务归因分析](skills/business-root-cause-analysis/SKILL.md) | 因子和维度贡献、归因假设、验证计划、HTML 报告 |
| 想知道用户在哪一步流失 | [漏斗分析](skills/funnel-analysis/SKILL.md) | 有序漏斗、步骤贡献拆解、渠道结构 vs 转化拆解、HTML 漏斗报告 |
| 想知道用户是不是留下来了 | [留存 Cohort 分析](skills/retention-cohort-analysis/SKILL.md) | 留存矩阵热力表、固定批次留存曲线、构成调整后的异常批次、HTML 报告 |
| 想判断实验是否可以全量 | [A/B 实验分析](skills/ab-test-analysis/SKILL.md) | 脚本计算的显著性与 SRM、上线建议、HTML 实验报告 |
| 看板上线前或改版前要审查 | [看板审查](skills/dashboard-reviewer/SKILL.md) | 评分、问题清单、改版 HTML 原型 |

### 4. 做建模

| 场景 | 推荐技能 | 产出 |
| --- | --- | --- |
| 拿到数据后需要设计模型特征 | [特征工程建议](skills/feature-engineering-advisor/SKILL.md) | 特征清单、处理方案、脚本筛查的泄漏风险、优先级 |
| 模型训练完需要评估是否可上线 | [模型评估审查](skills/model-evaluation-reviewer/SKILL.md) | 脚本计算的指标和置信区间、测试集检查、上线建议 |

### 5. 做汇报和同步

| 场景 | 推荐技能 | 产出 |
| --- | --- | --- |
| 当天工作要同步 | [日报写作](skills/daily-report-writer/SKILL.md) | 今日完成、进行中、风险、明日计划 |
| 每周或每月要向上同步 | [周报月报写作](skills/weekly-monthly-report-writer/SKILL.md) | 重点进展、价值、风险、下周期计划 |
| 数据已经算完，要写正式报告 | [数据分析报告写作](skills/data-analysis-report-writer/SKILL.md) | HTML + Markdown 报告：结论、发现、假设、建议，数字可溯源 |
| 要把分析讲给老板或业务方 | [数据汇报 PPT 架构](skills/data-presentation-architect/SKILL.md) | PPT 结构、每页标题、图表建议、讲稿提示 |
| 要把结论画成图或发一份数据报告页面 | [拾穗图表规范](skills/data-viz-kit/SKILL.md) | 选图、配色、中文数字格式、自包含 HTML 报告 |
| 数据事故需要复盘和同步 | [数据事故复盘](skills/data-incident-postmortem-writer/SKILL.md) | 影响范围、时间线、根因、预防措施 |

## 按角色找

### 数据分析师

常用技能：

- [数据需求澄清](skills/data-requirement-clarifier/SKILL.md)
- [指标口径审查](skills/metric-definition-reviewer/SKILL.md)
- [探索性数据分析](skills/exploratory-data-analysis/SKILL.md)
- [业务归因分析](skills/business-root-cause-analysis/SKILL.md)
- [漏斗分析](skills/funnel-analysis/SKILL.md)
- [留存 Cohort 分析](skills/retention-cohort-analysis/SKILL.md)
- [A/B 实验分析](skills/ab-test-analysis/SKILL.md)
- [行业市场调研](skills/market-research-analyst/SKILL.md)
- [数据分析报告写作](skills/data-analysis-report-writer/SKILL.md)
- [数据汇报 PPT 架构](skills/data-presentation-architect/SKILL.md)
- [拾穗图表规范](skills/data-viz-kit/SKILL.md)

典型链路：

```text
需求澄清 -> 指标口径 -> 数据探索 -> 专项分析 -> 分析报告 -> PPT 汇报
```

### 数据运营

常用技能：

- [业务归因分析](skills/business-root-cause-analysis/SKILL.md)
- [漏斗分析](skills/funnel-analysis/SKILL.md)
- [留存 Cohort 分析](skills/retention-cohort-analysis/SKILL.md)
- [看板审查](skills/dashboard-reviewer/SKILL.md)
- [日报写作](skills/daily-report-writer/SKILL.md)
- [周报月报写作](skills/weekly-monthly-report-writer/SKILL.md)
- [行业市场调研](skills/market-research-analyst/SKILL.md)

典型链路：

```text
看板观察 -> 业务归因 -> 专项分析 -> 日报 / 周报同步
```

### 数据开发 / 数据工程师

常用技能：

- [数据需求澄清](skills/data-requirement-clarifier/SKILL.md)
- [指标口径审查](skills/metric-definition-reviewer/SKILL.md)
- [数仓表设计建议](skills/table-design-advisor/SKILL.md)
- [SQL 审查](skills/sql-reviewer/SKILL.md)
- [数据质量规则生成](skills/data-quality-rule-generator/SKILL.md)
- [血缘影响分析](skills/data-lineage-impact-analyzer/SKILL.md)
- [实时管道设计](skills/stream-pipeline-designer/SKILL.md)
- [数据文档写作](skills/data-doc-writer/SKILL.md)
- [数据事故复盘](skills/data-incident-postmortem-writer/SKILL.md)

典型链路：

```text
需求澄清 -> 指标口径 -> 表设计 -> SQL 审查 -> 质量规则 -> 数据文档
```

### 数据架构 / 数据治理

常用技能：

- [数仓表设计建议](skills/table-design-advisor/SKILL.md)
- [指标口径审查](skills/metric-definition-reviewer/SKILL.md)
- [数据质量规则生成](skills/data-quality-rule-generator/SKILL.md)
- [血缘影响分析](skills/data-lineage-impact-analyzer/SKILL.md)
- [实时管道设计](skills/stream-pipeline-designer/SKILL.md)
- [数据工具集成规划](skills/data-tool-integration-planner/SKILL.md)
- [数据文档写作](skills/data-doc-writer/SKILL.md)
- [数据事故复盘](skills/data-incident-postmortem-writer/SKILL.md)

典型链路：

```text
标准制定 -> 影响评估 -> 工具接入 -> 质量保障 -> 文档沉淀
```

### 数据科学家

常用技能：

- [探索性数据分析](skills/exploratory-data-analysis/SKILL.md)
- [特征工程建议](skills/feature-engineering-advisor/SKILL.md)
- [模型评估审查](skills/model-evaluation-reviewer/SKILL.md)
- [A/B 实验分析](skills/ab-test-analysis/SKILL.md)
- [指标口径审查](skills/metric-definition-reviewer/SKILL.md)
- [数据分析报告写作](skills/data-analysis-report-writer/SKILL.md)

典型链路：

```text
数据探索 -> 特征工程 -> 模型评估 -> A/B 实验验证 -> 效果报告
```

### 数据团队负责人

常用技能：

- [看板审查](skills/dashboard-reviewer/SKILL.md)
- [业务归因分析](skills/business-root-cause-analysis/SKILL.md)
- [行业市场调研](skills/market-research-analyst/SKILL.md)
- [日报写作](skills/daily-report-writer/SKILL.md)
- [周报月报写作](skills/weekly-monthly-report-writer/SKILL.md)
- [数据汇报 PPT 架构](skills/data-presentation-architect/SKILL.md)
- [数据事故复盘](skills/data-incident-postmortem-writer/SKILL.md)

典型链路：

```text
团队进展 -> 风险识别 -> 业务判断 -> 管理层汇报
```

## 常见组合

### 新需求开发

```text
数据需求澄清 -> 指标口径审查 -> 数仓表设计建议 -> SQL 审查 -> 数据质量规则生成 -> 数据文档写作
```

### 指标异常归因

```text
指标口径审查 -> 业务归因分析 -> 探索性数据分析 -> 数据分析报告写作
```

### 经营看板改版

```text
指标口径审查 -> 看板审查 -> 数据文档写作
```

### 字段或口径变更

```text
血缘影响分析 -> SQL 审查 -> 数据质量规则生成 -> 日报 / 周报同步
```

### 市场调研汇报

```text
行业市场调研 -> 数据分析报告写作 -> 数据汇报 PPT 架构
```

### 特征与模型建设

```text
探索性数据分析 -> 特征工程建议 -> 模型评估审查 -> A/B 实验分析 -> 数据分析报告写作
```

### 实时数仓建设

```text
数据需求澄清 -> 实时管道设计 -> SQL 审查 -> 数据质量规则生成 -> 数据文档写作
```

## 不确定用哪个怎么办

如果你不确定该用哪个技能，先用 [数据需求澄清](skills/data-requirement-clarifier/SKILL.md)。

它会帮你把问题拆清楚，再判断是否需要进入指标、开发、分析、建模或汇报类技能。
