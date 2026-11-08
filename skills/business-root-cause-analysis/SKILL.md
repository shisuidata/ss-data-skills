---
name: business-root-cause-analysis
description: Use when diagnosing business metric changes or anomalies such as GMV decline, conversion drop, retention loss, churn increase, revenue change, lead decline, or active user fluctuation with a structured root cause analysis plan. 中文触发词：指标归因、为什么下降、异常排查、GMV 下滑、指标波动原因。
metadata:
  category: 数据分析
  aliases: 指标归因、异常归因、业务指标诊断
---

# Business Root Cause Analysis

## 目标

把“某个业务指标变差了”拆成可验证的归因假设、数据检查路径和行动建议。

这个 Skill 不负责凭空给出唯一原因，而是帮助用户建立一套可执行的排查框架。

## 使用场景

使用这个 Skill，当用户需要：

- 分析 GMV、转化率、留存、活跃、收入、线索、续费等指标异常
- 把老板的一句“为什么下降了”拆成分析任务
- 为业务复盘准备归因树和验证路径
- 判断是流量、转化、结构、供给、价格、产品体验还是数据口径问题
- 给数据分析师或业务负责人输出下一步排查清单

## 不适用场景

不要使用这个 Skill 处理：

- 没有任何指标、时间范围或对比基准的泛泛讨论
- 只做单一有序路径转化，应使用 `funnel-analysis`
- 只做留存矩阵，应使用 `retention-cohort-analysis`
- 只写最终报告，应使用 `data-analysis-report-writer`
- 需要判断 SQL 是否算错，应使用 `sql-reviewer`
- 有随机分组的实验结果，应使用 `ab-test-analysis`
- 指标口径本身有争议，先用 `metric-definition-reviewer`
- 数据能不能用还不清楚，先用 `exploratory-data-analysis`
- 需要行业或竞品的外部信息，应使用 `market-research-analyst`

## 输入信息

最少输入：

- 异常指标
- 异常时间范围
- 对比基准：环比、同比、上周同期、实验对照等
- 已知现象或初步数据

推荐输入：

- 指标口径和计算逻辑
- 可用维度：渠道、地区、端、用户类型、商品、套餐、内容类型等
- 相关业务事件：活动、改版、投放、价格、库存、算法、系统故障
- 历史波动范围
- 数据表、看板或 SQL 结果
- 日粒度时间序列 CSV、按时期和维度汇总的 CSV（可以直接用脚本计算）
- 业务方已经排除或怀疑的原因

## 上下文建议

优先使用这些模板准备上下文：

- [分析上下文模板](../../context/templates/analysis-context.md)：适合指标异常和专题归因
- [指标上下文模板](../../context/templates/metric-context.md)：适合口径不清或指标争议
- [报告上下文模板](../../context/templates/report-context.md)：适合后续沉淀成复盘报告

如果问题明显属于某个行业，建议补充行业上下文：

- [电商行业上下文](../../context/industries/ecommerce.md)
- [SaaS 行业上下文](../../context/industries/saas.md)
- [内容社区行业上下文](../../context/industries/content-community.md)

上下文不足时，先输出假设树和验证数据需求，不要直接断言原因。

## 分析流程

1. 确认异常是否真实：口径、数据延迟、采集、分母变化、节假日和自然波动。
2. 拆解指标公式，识别核心驱动因子。
3. 按时间、结构、人群、渠道、地域、产品、供给、体验等维度定位异常集中点。
4. 将可能原因分成数据问题、流量问题、转化问题、结构问题、供给问题、产品问题、外部因素。
5. 为每个假设设计验证指标、查询维度和所需数据。
6. 按影响大小、可验证性、可行动性排序。
7. 输出结论边界：哪些能确认，哪些只是待验证。

## 可用脚本

有数据且能执行代码时，数字由 `scripts/decompose.py` 计算，不要心算：

```bash
# 1. 异常是否真实：和同星期的历史窗口比较
python3 scripts/decompose.py confirm --csv daily.csv --date-col dt --value-col gmv --start 2026-05-13 --end 2026-05-19

# 2. 乘法公式拆解：GMV = 流量 × 转化率 × 客单价
python3 scripts/decompose.py factors --factor 流量=120000,131000 --factor 转化率=0.042,0.031 --factor 客单价=180,176 --target GMV

# 3. 维度贡献排序，比率指标拆成结构效应和转化效应
python3 scripts/decompose.py dimensions --csv segments.csv --period-col period --base 上期 --current 本期 \
  --dim channel --dim device --numerator paid --denominator uv --html rca.html
```

示例数据见 `assets/`，全部参数见 [命令行参数](references/cli.md)。

- `confirm` 的结论是 `data_issue` 时先排查数据；是 `normal` 时说明这可能只是正常波动，不要进入业务归因。
- `dimensions` 要求同一粒度的数据。各维度合计不一致时会报错，这通常是数据被重复计算。
- `dimensions` 只说明变化集中在哪里，不等于原因。原因要靠假设树继续验证。
- 不能执行代码时，按同样的结构人工计算，并写明“未经脚本计算”。

## 输出格式

```markdown
## 归因分析结论

## 异常确认

## 指标拆解

核心指标 = 驱动因子 A * 驱动因子 B * 驱动因子 C

## 假设树

| 假设 | 可能机制 | 需要验证的数据 | 优先级 |
| --- | --- | --- | --- |

## 已知证据

## 下一步验证计划

| 步骤 | 要查什么 | 维度/口径 | 预期判断 |
| --- | --- | --- | --- |

## 可行动建议

## 待确认问题
```

## 质量标准

输出必须：

- 先确认异常是否真实，再讨论原因
- 明确指标公式和拆解维度
- 不把相关性直接写成因果
- 每个假设都要对应验证数据
- 有数据时，异常确认和贡献拆解的数字来自脚本
- 建议要区分“立刻能做”和“验证后再做”
- 对数据口径、样本量、季节性和业务事件保持敏感

## 完成后的下一步

- 定位到转化路径或留存：`funnel-analysis`、`retention-cohort-analysis`
- 结论需要因果验证：`ab-test-analysis`
- 怀疑 SQL 算错：`sql-reviewer`
- 把排查路径固化到看板：`dashboard-reviewer`
- 写报告：`data-analysis-report-writer`
- 同步进展：`daily-report-writer`、`weekly-monthly-report-writer`、`data-presentation-architect`

## 示例 Prompt

```text
请用 business-root-cause-analysis 分析这个问题。

背景：SaaS 产品 5 月第 3 周新用户激活率从 42% 降到 31%。
激活口径：注册后 7 天内完成创建工作区、邀请成员、完成一次核心任务中的任意 2 个。
对比基准：过去 4 周均值。
已知变化：
- 5 月 15 日上线了新版引导页
- 付费投放渠道 B 的注册占比从 20% 提升到 38%
- 产品团队反馈没有大面积故障
可用维度：渠道、设备、地区、注册类型、是否进入引导页。

请输出归因假设树、验证路径和下一步建议。
```

```text
请用 business-root-cause-analysis 分析这个问题。

背景：SaaS 产品 5 月 ARR 增速从 18% 降到 11%，Churn 率同期从 3.2% 升到 4.8%。
对比基准：Q1 季度均值。
已知变化：
- 4 月底新了一批付费投放带来的中小企业客户
- 产品 5 月上线功能权限分级，部分用户主动降级套餐
- 客户成功团队 4 月有 2 名 CSM 离职
可用维度：客户规模、行业、套餐类型、注册渠道、使用活跃度分层。
```
