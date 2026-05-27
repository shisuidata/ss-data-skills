# 2026-05-28 测试门禁基线记录

## 测试范围

本轮目标是为当前 Skill 库建立“只有通过测试才能 push”的基础门禁。

覆盖范围：

- 16 个正式 Skill
- 16 个测试用例
- 16 个示例文件
- 8 个上下文模板
- 1 个电商增长 mock 数据包
- 1 个通用人工评测 Rubric

## 自动化门禁

执行命令：

```bash
node scripts/pre-push-check.mjs
```

门禁包含：

```text
node scripts/check-library.mjs
node scripts/check-tests.mjs
node scripts/summarize-ecommerce-fixture.mjs
git diff --check HEAD
git diff --check <upstream>..HEAD
```

## 当前结论

当前 16 个 Skill 已通过基础测试门禁：

- 每个 Skill 都有 `SKILL.md`
- 每个 Skill 都有示例
- 每个 Skill 都有测试用例
- 每个 Skill 都有上下文建议
- `skills/catalog.json` 包含中文展示名、英文 ID、分类和别名
- mock 数据可复算并得到预期漏斗事实

## 边界说明

这次门禁证明的是基础可维护性和 mock 测试覆盖，不等于所有 Skill 的真实模型输出已经在所有场景中完全稳定。

后续新增或重大修改 Skill 时，需要额外执行人工输出评测，并把评分记录到 `tests/results/`。

## 发布规则

从本记录开始，push 前必须运行：

```bash
node scripts/pre-push-check.mjs
```

如果需要本地强制执行：

```bash
git config core.hooksPath .githooks
```
