# 2026-05-27 首轮人工评测记录

## 测试范围

本轮使用 `tests/fixtures/ecommerce-growth/` 的 mock 电商增长场景，评测 5 个代表性 Skill：

- `data-requirement-clarifier`
- `sql-reviewer`
- `funnel-analysis`
- `data-analysis-report-writer`
- `data-presentation-architect`

## 自动化检查

```text
Library check passed.
Skills: 12
Context templates: 8

Test check passed.
Cases: 5
Fixtures: 5

Ecommerce fixture summary:
previous: registered=12, product_view=10, add_to_cart=7, order_submit=5, pay_success=4, pay_rate=33.3%
current: registered=12, product_view=9, add_to_cart=5, order_submit=3, pay_success=2, pay_rate=16.7%
Fixture validation passed.
```

## 测试中发现的问题

首次运行 `scripts/summarize-ecommerce-fixture.mjs` 时，发现 `expected-summary.md` 中当前周期的 `product_view` 和 `add_to_cart` 预期值与 CSV 实际计算结果不一致：

- 文档原写：`product_view=8`，实际为 `9`
- 文档原写：`add_to_cart=4`，实际为 `5`

处理方式：

- 保留 mock CSV 数据不变
- 修正 `expected-summary.md`
- 修正脚本中的 expected 值
- 修正 `TESTING.md` 中的示例输出

这说明测试脚本有效捕捉到了测试材料自身的不一致。

## 人工评测结果

### data-requirement-clarifier

| 维度 | 分数 | 说明 |
| --- | --- | --- |
| 任务识别 | 2 | 能识别为专题分析 + 异常排查 |
| 上下文使用 | 2 | 能使用业务背景、周期、数据表和关注维度 |
| 风险识别 | 2 | 能提出 7 日窗口、退款、渠道归因等待确认问题 |
| 输出可执行 | 2 | 能拆成指标、维度、数据范围和任务步骤 |
| 事实纪律 | 2 | 不需要编造数据结果 |

总分：10/10

结论：通过。

### sql-reviewer

| 维度 | 分数 | 说明 |
| --- | --- | --- |
| 任务识别 | 2 | 能识别为上线前 SQL Review |
| 上下文使用 | 2 | 能结合引擎、粒度、支付窗口和分区字段判断 |
| 风险识别 | 2 | 能发现 left join 右表 where 过滤、窗口缺失、分区缺失 |
| 输出可执行 | 2 | 能给出将右表过滤前置、先按用户打标再聚合的改写方向 |
| 事实纪律 | 2 | 不把未知字段唯一性当成事实 |

总分：10/10

结论：通过。

### funnel-analysis

| 维度 | 分数 | 说明 |
| --- | --- | --- |
| 任务识别 | 2 | 能识别为有序转化路径分析 |
| 上下文使用 | 2 | 能使用 mock 数据的周期、步骤、事件映射 |
| 风险识别 | 2 | 能标记小样本、渠道结构和移动端差异风险 |
| 输出可执行 | 2 | 能定位“浏览商品 -> 加购”和后续排查动作 |
| 事实纪律 | 1 | 需要明确说明 mock 数据只用于测试，不能统计归因 |

总分：9/10

结论：通过。建议在用例中继续强调“小样本不做显著性判断”。

### data-analysis-report-writer

| 维度 | 分数 | 说明 |
| --- | --- | --- |
| 任务识别 | 2 | 能识别为业务分析报告 |
| 上下文使用 | 2 | 能使用转化率、漏斗流失、渠道和设备事实 |
| 风险识别 | 2 | 能写出口径、样本和归因限制 |
| 输出可执行 | 2 | 能给出排查移动端、复核渠道、补埋点等动作 |
| 事实纪律 | 2 | 能区分已知事实和原因假设 |

总分：10/10

结论：通过。

### data-presentation-architect

| 维度 | 分数 | 说明 |
| --- | --- | --- |
| 任务识别 | 2 | 能识别为面向业务负责人的演示结构设计 |
| 上下文使用 | 2 | 能使用受众、时长、页数和决策诉求 |
| 风险识别 | 2 | 能保留 mock 小样本限制和附录口径 |
| 输出可执行 | 2 | 能给出结论式标题、图表建议和讲稿提示 |
| 事实纪律 | 2 | 不把假设包装为确定结论 |

总分：10/10

结论：通过。

## 总体结论

本轮 5 个代表性 Skill 均通过人工评测。

当前仓库可以支持三类测试：

1. Skill 库结构完整性测试
2. mock 数据事实校验
3. 基于固定用例的人工输出质量评测

## 下一步建议

- 为剩余 7 个 Skill 补测试用例
- 将人工评测结果拆成更细的 Rubric
- 后续接入模型自动评测脚本 `scripts/run-evals.mjs`
- 在 GitHub Actions 中运行 `check-library`、`check-tests` 和 fixture summary

