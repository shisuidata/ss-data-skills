# 测试用例

这个目录保存 Skill 的 mock 测试材料。

测试目标不是证明某个模型永远正确，而是让我们能用固定上下文检查 Skill 是否真的可用。

## 目录结构

```text
tests/
  fixtures/      # mock 数据和上下文
  cases/         # 测试用例，每个用例对应一个 Skill 或工作流
  rubrics/       # 人工评测标准
  results/       # 人工评测记录
```

## 当前测试场景

`fixtures/ecommerce-growth/` 是一个虚构电商增长场景：

- 新用户首购转化下降
- 渠道 A 占比提升
- 移动端流失更明显
- 支付页性能可能恶化
- SQL 中存在一个典型 left join 过滤错误

## 运行检查

```bash
node scripts/check-library.mjs
node scripts/check-tests.mjs
node scripts/summarize-ecommerce-fixture.mjs
```

## 人工评测流程

1. 打开 `tests/cases/<case>.md`。
2. 复制“测试输入”给 Agent。
3. 指定使用对应 Skill。
4. 对照“通过标准”和 `tests/rubrics/common.md` 评分。
5. 把结果记录到 `tests/results/`。

## 当前覆盖

第一批测试覆盖 5 个代表性 Skill：

- `data-requirement-clarifier`
- `sql-reviewer`
- `funnel-analysis`
- `data-analysis-report-writer`
- `data-presentation-architect`

后续可以继续补齐 12 个 Skill 的完整测试矩阵。

## 评测记录

- [2026-05-27 首轮人工评测记录](results/2026-05-27-manual-eval.md)
