---
name: feature-engineering-advisor
description: Use when designing, reviewing, or selecting features for machine learning models. Advises on feature types, missing value treatment, encoding, interaction terms, time-series features, leakage risks, and feature importance evaluation strategies. 中文触发词：特征工程、特征设计、特征选择、数据泄漏。
metadata:
  category: 数据科学
  aliases: 特征工程、特征设计、特征选择
---

# Feature Engineering Advisor

## 目标

帮助数据科学家和算法工程师设计、评估和审查模型特征，减少数据泄露、无效特征和工程实现风险。

这个 Skill 不直接输出可运行的训练代码，而是负责特征方案决策：选什么、怎么处理、有什么风险。

## 使用场景

使用这个 Skill，当用户需要：

- 为分类、回归、排序或推荐模型设计原始特征
- 审查现有特征方案是否存在数据泄露
- 判断缺失值、离群值和高基数字段的处理方式
- 设计时序特征、行为序列特征或用户画像聚合特征
- 判断哪些特征最值得优先纳入，哪些应该剔除

典型输入：

```text
我要为 SaaS 客户流失预测模型设计特征，目前有用户行为日志、订阅表和支持工单表，请帮我设计特征方案。
```

## 不适用场景

不要用这个 Skill 直接完成：

- 模型结构选择或超参调优（本库暂无对应 Skill）
- 模型评估方案和上线判断，应使用 `model-evaluation-reviewer`
- 原始数据摸底，应使用 `exploratory-data-analysis`
- 指标口径审查，应使用 `metric-definition-reviewer`
- SQL 审查，应使用 `sql-reviewer`

如果用户没有提供数据结构或业务目标，先列出需要确认的问题，不要直接生成特征方案。

## 输入信息

最少输入：

- 建模目标：预测什么，对谁预测
- 可用数据表或字段说明

可选输入：

- 目标变量定义
- 预测时间点（样本截止时间）
- 预测时间范围（预测未来多久）
- 特征工程平台：Spark、Python/Pandas、Flink 实时特征
- 已有特征版本或基线模型
- 业务约束：禁用字段、隐私限制、合规要求

## 上下文建议

推荐使用 [机器学习上下文模板](../../context/templates/ml-context.md) 补充建模目标、样本定义和数据来源。

最有价值的上下文是：预测目标、样本构造时间点、可用表结构和已知高价值信号。缺少真实数据样例时，先设计特征框架和待确认清单。

## 设计框架

1. 明确预测目标和时间点，确定样本构造方式。
2. 识别特征来源：行为特征、属性特征、关系特征、时序特征。
3. 逐类设计特征方案：原始值、聚合统计、差分、比率、桶分类、Embedding。
4. 检查数据泄露：特征是否使用了预测时间点之后的数据。
5. 检查高基数字段：是否需要编码或降维。
6. 检查缺失值：是否与业务含义有关（缺失本身即为信号）。
7. 给出特征优先级：预期影响力、工程成本、稳定性。
8. 标记监控建议：特征分布漂移、上线后稳定性检查。

## 可用脚本

有特征表时，先做泄漏筛查：

```bash
python3 scripts/leakage_check.py check --csv features.csv --label churned --asof-col snapshot_time \
  --feature-time logins_30d=last_login_time --exclude customer_id
```

示例见 `assets/example_features.csv`，全部参数见 [命令行参数](references/cli.md)。

脚本检查时间穿越、单特征异常强、缺失与标签强相关和结果类字段名。结果是线索，要结合特征生成时间确认。没有发现问题不能证明没有泄漏，多个特征组合造成的泄漏查不出来。

## 输出格式

```markdown
## 特征工程方案

### 1. 建模目标与样本定义

### 2. 特征清单

| 特征名 | 来源表 | 类型 | 处理方式 | 数据泄露风险 | 优先级 |
| --- | --- | --- | --- | --- | --- |

### 3. 关键设计决策

### 4. 缺失值与异常值处理

| 字段 | 缺失率预估 | 缺失含义 | 处理方案 |
| --- | --- | --- | --- |

### 5. 数据泄露风险清单

### 6. 特征监控建议

### 7. 待确认问题
```

## 质量标准

输出必须：

- 明确样本构造时间点和预测时间范围
- 每个特征都说明来源表和处理逻辑
- 对所有涉及预测时间点之后数据的特征标记泄露风险
- 区分低成本高价值特征和高成本特征，给出优先级
- 缺失值处理要结合业务含义，不能一律填均值

## 完成后的下一步

- 评估模型：`model-evaluation-reviewer`
- 特征口径有争议：`metric-definition-reviewer`

## 示例 Prompt

```text
请用 feature-engineering-advisor 设计 SaaS 客户流失预测特征方案。

建模目标：预测企业客户在续费日前 30 天是否会流失。
样本：每个客户在"续费日 -30 天"那天的状态快照。
可用数据：
- 订阅表：company_id, plan, mrr, start_date, end_date, seats
- 用户行为日志：company_id, user_id, event_time, event_type
- 支持工单：company_id, ticket_time, ticket_type, resolution_time
- NPS 记录：company_id, survey_time, score
时间范围：过去 18 个月历史数据。
禁用字段：不能使用续费日之后的任何数据。
```

```text
请用 feature-engineering-advisor 审查下面这份特征方案是否有数据泄露风险。

建模目标：预测电商用户首购转化（注册后 7 天内完成首购）。
特征草案：
1. 注册渠道
2. 注册设备
3. 注册后 3 天内浏览商品数
4. 注册后 7 天内收藏商品数
5. 首次支付金额
6. 是否使用优惠券
请判断哪些特征存在泄露，并给出修改建议。
```
