# 2026-05-27 全 Skill 覆盖测试记录

## 测试范围

本轮将测试用例从 5 个代表性 Skill 扩展到全部 12 个 Skill。

覆盖 Skill：

- `ab-test-analysis`
- `data-analysis-report-writer`
- `data-presentation-architect`
- `data-quality-rule-generator`
- `data-requirement-clarifier`
- `exploratory-data-analysis`
- `funnel-analysis`
- `metric-definition-reviewer`
- `retention-cohort-analysis`
- `sql-reviewer`
- `table-design-advisor`
- `weekly-monthly-report-writer`

## 自动化检查

```text
Library check passed.
Skills: 12
Context templates: 8

Test check passed.
Cases: 12
Skills covered: 12
Fixtures: 5

Ecommerce fixture summary:
previous: registered=12, product_view=10, add_to_cart=7, order_submit=5, pay_success=4, pay_rate=33.3%
current: registered=12, product_view=9, add_to_cart=5, order_submit=3, pay_success=2, pay_rate=16.7%
Fixture validation passed.
```

## 本轮新增测试用例

| Skill | 测试重点 | 预期能力 |
| --- | --- | --- |
| `metric-definition-reviewer` | 新用户 7 日首购转化率 | 拆清分子分母、时间窗口、退款、渠道归因 |
| `table-design-advisor` | 渠道转化汇总表设计 | 明确表粒度、字段、分区、更新策略和 7 日回看 |
| `data-quality-rule-generator` | ADS 汇总表质量规则 | 覆盖产出、唯一、非空、范围、逻辑一致性和波动 |
| `exploratory-data-analysis` | 三张 mock 表的数据探索 | 设计字段、粒度、时间、事件顺序和质量检查 |
| `retention-cohort-analysis` | 渠道留存 Cohort | 定义 Cohort、留存行为、窗口和样本限制 |
| `ab-test-analysis` | 新版支付页实验 | 不只看转化率，必须检查护栏指标和实验有效性 |
| `weekly-monthly-report-writer` | 测试工作周报 | 把零散事项归纳成进展、价值、风险和计划 |

## 结论

从自动化测试角度看，当前仓库已经达到第一阶段全覆盖：

- 12 个 Skill 都有测试用例
- 12 个 Skill 都有示例
- 12 个 Skill 都有上下文建议
- 8 个上下文模板可用
- mock 数据能被脚本复算并校验

这说明 Skill 库已经具备可维护性：新增或修改 Skill 时，至少能通过脚本发现结构缺失、示例缺失、上下文缺失和测试用例缺失。

## 仍未覆盖

当前测试还没有做到：

- 调用真实模型批量生成输出
- 保存每个 Skill 的真实模型输出
- 自动给输出打分
- 在真实会员业务场景中验证稳定性

所以当前结论是：

> Skill 库已经完成结构、上下文、示例和测试用例全覆盖；真实输出质量还需要下一阶段模型评测和会员实战验证。

## 下一步建议

1. 为每个测试用例保存一次真实 Agent 输出。
2. 增加 `tests/outputs/` 目录。
3. 增加 `scripts/run-evals.mjs`，未来接入模型自动跑测试。
4. 为每个 Skill 建立更细的专属 Rubric。

