---
name: ab-test-analysis
description: Use when designing, checking, or interpreting A/B tests and experiments. Computes significance, confidence intervals, sample ratio mismatch, power, CUPED, and sample size with a bundled zero-dependency script, then judges validity risks, guardrails, and ship/iterate/rollback decisions and renders an HTML experiment report. 中文触发词：A/B 实验、AB 测试、实验解读、显著性、样本量计算、能不能全量。
metadata:
  category: 数据分析
  aliases: AB 实验、实验分析、实验解读、样本量计算
---

# A/B Test Analysis

## 目标

设计、审查或解读 A/B 实验，判断实验是否可信、效果是否真实、业务上是否值得推广。

核心原则：**数字由脚本算，判断由人做**。显著性、置信区间、SRM、功效和样本量全部用 `scripts/ab_test.py` 计算，不心算、不估算；模型负责检查实验设计、解释结果、补充业务判断。

## 使用场景

- 实验前：确定样本量和实验周期（`plan`）
- 实验中：有人想“看一眼结果”，判断能不能提前停
- 实验后：解读结果，判断全量、继续观察、回滚还是重做
- 审查别人写的实验结论是否站得住
- 排查分流异常、结果离谱、指标打架

典型输入：

```text
这个实验转化率提升了 0.3 个百分点，p 值 0.04，可以全量吗？
```

## 不适用场景

- 没有随机分组的前后对比、自然实验：请使用 `business-root-cause-analysis`，并明确说明这不是实验
- 普通漏斗分析：使用 `funnel-analysis`
- 留存分析：使用 `retention-cohort-analysis`
- 指标定义本身有争议：先用 `metric-definition-reviewer`

没有对照组、实验组和核心指标数据时，不要给实验结论。

## 输入信息

最少输入（汇总数据即可）：

- 每组样本量
- 核心指标的结果：比例指标给成功数，均值指标给均值和标准差，比率指标（如点击率）给用户粒度的分子和分母
- 实验天数

推荐输入：

- 实验假设、分流比例、计划周期
- 护栏指标结果（错误率、性能、投诉、退款等）及可接受的恶化幅度
- 预期分流比例（非均分实验必须提供，否则无法判断 SRM）
- 用户粒度明细 CSV（可做 CUPED 方差缩减）
- 实验前同一指标的数据（CUPED 协变量）

输入字段详见 [输入格式](references/input-schema.md)。

## 上下文建议

推荐使用 [实验分析上下文模板](../../context/templates/experiment-context.md)。

最有价值的上下文是：分流方式、计划周期、护栏指标、实验期间是否有大促或版本发布。缺少护栏指标时，不能建议直接全量。

## 工作流程

1. **整理输入**：把用户给的数字写成 `summary.json`（格式见 references），或直接使用用户的 CSV。
2. **运行脚本**（能执行代码时必须运行）：

   ```bash
   python3 scripts/ab_test.py analyze --summary summary.json --html ab_report.html
   # 或用户粒度数据：
   python3 scripts/ab_test.py analyze --csv users.csv --variant-col variant --control A \
     --metric paid:proportion --metric gmv:mean --guardrail refund:proportion:lower \
     --cuped gmv=pre_gmv --days 14 --html ab_report.html
   ```

   脚本输出 JSON：`srm`、`comparisons`、`checks`、`verdict`。`verdict` 是规则给出的**最低结论**，不能比它更乐观。

   CSV 可以是 UTF-8 或 GBK，比例列支持 0/1、true/false、是/否、Y/N。非均分实验加 `--allocation A=0.9,B=0.1`；比率指标写成 `clicks/views:ratio`。全部参数见 [命令行参数](references/cli.md)。
3. **逐项检查有效性**：对照 [有效性检查清单](references/validity-checklist.md)，补充脚本无法判断的风险（污染、新奇效应、大促、版本发布、埋点变更）。
4. **形成决策**：在脚本结论基础上加入业务判断：收益是否覆盖成本、风险是否可控。
5. **交付**：Markdown 结论 + HTML 报告路径。

实验前规划：

```bash
python3 scripts/ab_test.py plan --baseline 0.07 --mde-rel 0.05 --daily-users 6000
```

不能执行代码时：按同样的检查顺序人工分析，并在结论中写明“未经脚本计算，数值为近似”。

## 输出格式

```markdown
## A/B 实验分析

### 1. 结论
<一句话：全量 / 逐步放量 / 继续实验 / 回滚 / 重做，以及最关键的理由>

### 2. 指标结果
| 指标 | 类型 | 对照组 | 实验组 | 变化（pp / 相对） | 95% 区间 | p 值 | 显著 |
| --- | --- | --- | --- | --- | --- | --- | --- |

### 3. 有效性检查
| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| 样本比例（SRM） |  |  |
| 实验周期 / 整周 |  |  |
| 提前查看 / 提前停止 |  |  |
| 护栏指标 |  |  |
| 多重比较 |  |  |
| 外部干扰（大促、发版、埋点） |  |  |

### 4. 如何理解这个结果
<功效与最小可检测效应；不显著时说明“检测不到”和“没有效果”的区别>

### 5. 决策建议与下一步

### 6. 需要补充的数据

报告文件：<ab_report.html 路径>
```

## 决策规则

脚本的 `verdict.code` 对应以下规则，人工判断只能更保守，不能更激进：

| code | 含义 | 默认动作 |
| --- | --- | --- |
| `allocation_unknown` | 没给分流比例，且实际占比明显偏离均分 | 确认设计比例后用 `--allocation` 重跑 |
| `invalid_srm` | 分流异常 | 不解读任何指标，排查后重做 |
| `guardrail_regression` | 护栏显著恶化 | 不全量，由业务方明确是否接受代价 |
| `primary_regression` | 主指标显著下降 | 回滚 |
| `win_unverified` | 主指标显著提升，护栏缺失 | 补护栏后再决定 |
| `win_needs_validation` | 主指标显著提升，但周期不足、提前查看或停止、提升异常大、样本偏小，或护栏未证明在容忍度内 | 暂不放量，按 `next_steps` 逐项复核 |
| `ship` | 主指标提升，护栏未见恶化，有效性检查全部通过 | 按 10% → 50% → 100% 逐步放量 |
| `inconclusive` | 不显著 | 不下结论；按功效计算延长或重新规划 |

另外：

- 提升幅度异常大（> 30%）先怀疑数据，再庆祝
- 统计显著但收益很小：结合上线和维护成本判断
- 业务提升明显但不显著：说明需要多少样本，而不是“方向是对的，可以上”

## 质量标准

输出必须：

- 所有统计量来自脚本输出，或明确标注为近似值
- 比率指标的变化同时写百分点和相对变化
- 给出置信区间，不只给 p 值
- 不显著时写出当前样本的最小可检测效应，不写“新方案无效”
- 检查 SRM、周期、提前停止、护栏和多重比较
- 把“数据显示提升”和“建议上线”分开表达
- `verdict` 是 `win_needs_validation` 或 `allocation_unknown` 时，不能写成“建议放量”

## 完成后的下一步

- 写成报告：`data-analysis-report-writer`，把 `--json` 的结果作为来源
- 向管理层汇报：`data-presentation-architect`

## 示例 Prompt

```text
请用 ab-test-analysis 解读这个实验，并生成 HTML 报告：

假设：新版会员页能提高开通转化率
对照组：旧版页面，10000 UV，转化 310
实验组：新版页面，10050 UV，转化 355
护栏指标：退款率、页面加载时间、客服投诉（还没汇总）
周期：7 天，原计划 14 天
```

```text
请用 ab-test-analysis 规划实验：
支付成功率基线 7%，希望能检测到 5% 的相对提升，每天约 6000 个下单用户进入实验，分两组。
需要多少样本、跑几天？
```

```text
请用 ab-test-analysis 分析 users.csv：
分组列 variant，对照组 A；主指标 paid（是否下单）和 gmv；护栏 refund（越低越好）；
pre_gmv 是实验前 28 天 GMV，请用 CUPED。实验跑了 14 天。
```
