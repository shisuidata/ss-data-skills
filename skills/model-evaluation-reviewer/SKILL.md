---
name: model-evaluation-reviewer
description: Use when reviewing or designing the evaluation framework for a machine learning model. Checks metric selection, train-test split, offline-online gap, cold start, business translation of model scores, and monitoring strategy. 中文触发词：模型评估、AUC、模型能不能上线、模型效果审查。
metadata:
  category: 数据科学
  aliases: 模型评估、模型评估审查、离线评估方案
---

# Model Evaluation Reviewer

## 目标

审查机器学习模型的评估方案是否合理：指标是否匹配业务目标，测试集划分是否可信，离线结论是否支撑上线决策，业务影响是否可量化。

这个 Skill 不负责调参或架构设计，而是帮用户在上线前判断"这个评估方案是否足以支撑业务决策"。

## 使用场景

使用这个 Skill，当用户需要：

- 为分类、回归、排序或推荐模型选择评估指标
- 审查训练集/验证集/测试集划分方式
- 判断离线指标提升是否意味着线上业务改善
- 分析冷启动问题和模型覆盖率
- 把模型分数翻译成业务可用的行动依据
- 设计模型上线后的监控方案

典型输入：

```text
我们的流失预测模型 AUC 从 0.71 提升到 0.79，可以上线吗？
```

## 不适用场景

不要用这个 Skill 直接完成：

- 特征工程设计，请使用 `feature-engineering-advisor`
- 数据探索分析，请使用 `exploratory-data-analysis`
- A/B 实验线上效果分析，请使用 `ab-test-analysis`
- SQL 审查，请使用 `sql-reviewer`

如果没有提供模型类型、业务目标和评估数据，不要直接给出"可以上线"的结论。

## 输入信息

最少输入：

- 模型类型：分类、回归、排序、推荐
- 业务目标
- 当前评估指标和数值

可选输入：

- 测试集构造方式
- 正负样本比例
- 特征列表
- 模型用途：触发干预、排序展示、辅助决策
- 是否有基线模型
- 是否已有线上流量实验结果
- 预期上线覆盖率
- 预测文件：包含真实值和模型分数的 CSV（可以直接用脚本计算）

## 上下文建议

推荐使用 [机器学习上下文模板](../../context/templates/ml-context.md)。

最有价值的上下文是：业务目标、模型用途、样本构造方式、正负样本比、指标数值和基线。缺少测试集构造说明时，不能确认离线结论可信。

## 审查框架

1. 确认业务目标：模型输出要支撑什么决策。
2. 检查评估指标：指标是否与业务目标一致，是否适合正负样本不均衡场景。分类看 AUC、PR-AUC、Top-K、校准；回归看 RMSE、MAE、MAPE、偏差；排序看 NDCG、MRR、Recall@K。先核对数字是否自洽：Precision@K × K 不能超过正样本率，Recall@K 应约等于 Precision@K × K ÷ 正样本率。对不上时先确认口径，不要基于这些数字下结论。
3. 检查测试集：时间切分是否正确，是否存在数据泄露，正负样本比是否反映真实分布。
4. 检查覆盖率和冷启动：模型预测覆盖多少用户/客户，新用户如何处理。
5. 检查阈值选择：Precision 和 Recall 在业务上的权衡。
6. 检查离线/在线差距：是否存在特征分布漂移、线上特征获取延迟、标签定义差异。
7. 给出上线建议：直接全量、先灰度 A/B，还是继续优化。
8. 给出监控方案：生产环境中哪些指标需要持续追踪。

## 可用脚本

有预测文件时，数字由 `scripts/eval_metrics.py` 计算：

```bash
python3 scripts/eval_metrics.py classify --csv preds.csv --label y --score p --baseline-col old_p \
  --top 0.05,0.2 --benefit-tp 300 --cost-fp 20 --time-col dt --html eval.html
python3 scripts/eval_metrics.py regress --csv preds.csv --y y --pred yhat --baseline-col old_yhat
python3 scripts/eval_metrics.py rank --csv preds.csv --query q --relevance r --score s --k 10
python3 scripts/eval_metrics.py psi --base train.csv --current online.csv --col score
```

示例见 `assets/example_predictions.csv`，全部参数见 [命令行参数](references/cli.md)。

脚本给出置信区间、基线差异、校准、收益最大的阈值和时间稳定性。测试集是否泄露、指标是否匹配业务，脚本判断不了，要按上面的框架审查。没有预测文件时，用用户给的数字审查，并说明无法核算置信区间。

## 输出格式

```markdown
## 模型评估审查

### 1. 审查结论

### 2. 业务目标与模型对齐检查

### 3. 评估指标审查

| 指标 | 当前值 | 是否合适 | 风险 | 建议 |
| --- | --- | --- | --- | --- |

### 4. 测试集构造检查

### 5. 覆盖率与冷启动

### 6. 离线/在线差距风险

### 7. 阈值与业务翻译

### 8. 上线建议

### 9. 监控方案

### 10. 待确认问题
```

## 风险等级

- P0：评估方案存在数据泄露、标签泄露或正样本定义错误，结论不可信
- P1：指标选择与业务目标不匹配，或测试集构造不合理
- P2：离线/在线差距未评估，或缺少监控方案

## 质量标准

输出必须：

- 先确认业务目标，再讨论指标
- 不只看 AUC，还要看精确率、召回率和业务阈值权衡
- 用户给的指标互相矛盾时明确指出，不基于矛盾的数字下结论
- 明确测试集是否存在泄露
- 给出覆盖率和冷启动的处理建议
- 区分"可以尝试灰度"和"可以全量上线"
- 有预测文件时，指标、置信区间和基线差异来自脚本

## 完成后的下一步

- 线上验证：`ab-test-analysis`
- 特征有问题：`feature-engineering-advisor`
- 线上监控规则：`data-quality-rule-generator`
- 写效果报告：`data-analysis-report-writer`

## 示例 Prompt

```text
请用 model-evaluation-reviewer 审查下面这个流失预测模型评估方案。

模型：SaaS 客户流失二分类模型
业务目标：在续费日 30 天前识别高风险客户，CSM 团队优先跟进
当前评估：
- 测试集：最近 3 个月流失数据（随机切分）
- AUC：0.79（基线 0.71）
- Precision@Top5%：38%
- 样本：流失客户 3%，正常续费 97%
上线用途：每周更新一次高风险客户名单
疑问：随机切分的测试集能支撑上线判断吗？模型是否覆盖新签 30 天内的客户？
```

```text
请用 model-evaluation-reviewer 评估以下电商用户点击率预测模型是否适合上线。

模型：首页信息流内容排序的 CTR 预估模型
业务目标：提升用户点击率和购买转化
当前离线评估：
- 测试集：过去 7 天随机 20% 数据
- AUC：0.82
- 基线（规则排序）估算 AUC：0.74
覆盖率：98% 有历史行为的用户，新用户约 15% 无法预测
疑问：新用户排序如何处理？离线 AUC 和在线 CTR 是否通常一致？
```
