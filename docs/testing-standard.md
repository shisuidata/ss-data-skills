# Skill 测试标准

这份文档定义拾穗数据技能库的测试标准和发布门禁。

结论先写清楚：

> 只有通过测试门禁的 Skill 才能提交和 push。

当前仓库的 16 个 Skill 已经具备自动化测试覆盖：每个 Skill 都有 `SKILL.md`、示例、测试用例和上下文建议；电商 mock 数据可被脚本复算并校验。真实模型输出质量仍属于人工评测层，需要在重要新增或修改时补评测记录。

## 测试分层

### L0 结构测试

目标：确认 Skill 包装完整，能被用户和 Agent 找到。

检查内容：

- `skills/<skill-id>/SKILL.md` 存在
- 目录名和 frontmatter `name` 一致
- `description` 存在并能说明触发场景
- 必备章节完整：目标、使用场景、不适用场景、输入信息、上下文建议、输出格式、质量标准、示例 Prompt
- `skills/catalog.json` 中有中文展示名、英文 ID、分类和别名

执行：

```bash
node scripts/check-library.mjs
```

### L1 用例覆盖测试

目标：确认每个 Skill 至少有一个固定测试用例，可以用同一份上下文反复评测。

检查内容：

- `tests/cases/<skill-id>.md` 存在
- 测试用例包含 Skill、测试目标、测试输入、通过标准
- 测试输入使用 `text` 代码块，便于复制给 Agent
- 测试用例引用的 Skill 必须真实存在

执行：

```bash
node scripts/check-tests.mjs
```

### L2 Mock 数据校验

目标：确认测试数据本身可靠，不让错误 fixture 误导 Skill 评测。

当前固定场景：

- `tests/fixtures/ecommerce-growth/`
- 新用户首购转化下降
- SQL 中包含 left join 右表过滤错误
- 预期漏斗事实可由脚本复算

执行：

```bash
node scripts/summarize-ecommerce-fixture.mjs
```

### L3 人工输出评测

目标：确认 Agent 使用 Skill 后，真实输出足够可用。

评测方式：

1. 打开 `tests/cases/<skill-id>.md`
2. 复制“测试输入”给 Agent
3. 指定使用对应 Skill
4. 按 [通用人工评测 Rubric](../tests/rubrics/common.md) 打分
5. 将结果记录到 `tests/results/YYYY-MM-DD-<name>.md`

通过标准：

- 8 分及以上：通过
- 6-7 分：勉强通过，需要记录改进项
- 5 分及以下：不通过，不应发布该 Skill

## 发布门禁

每次 commit 或 push 前，必须运行：

```bash
node scripts/pre-push-check.mjs
```

这个脚本会依次执行：

1. `node scripts/check-library.mjs`
2. `node scripts/check-tests.mjs`
3. `node scripts/summarize-ecommerce-fixture.mjs`
4. 工作区和未推送提交的空白检查

只有全部通过，才允许 push。

## Git Hook

如果希望本地强制执行，可以启用仓库内置 hook：

```bash
git config core.hooksPath .githooks
```

启用后，每次 `git push` 前会自动运行：

```bash
node scripts/pre-push-check.mjs
```

## 新增或修改 Skill 的测试要求

新增 Skill 必须同时提交：

- `skills/<skill-id>/SKILL.md`
- `examples/<skill-id>.md`
- `tests/cases/<skill-id>.md`
- `skills/catalog.json` 中的中文展示名和英文 ID
- 必要的上下文模板或行业上下文包

修改 Skill 时：

- 如果只改错别字或链接，至少跑 L0-L2
- 如果改动输出格式、工作流程、质量标准或上下文建议，必须跑 L0-L3
- 如果新增 mock 数据，必须增加或更新 fixture 校验脚本

## 当前测试结论

截至 2026-05-28：

- 自动化结构测试：已覆盖全部 16 个 Skill
- 测试用例覆盖：已覆盖全部 16 个 Skill
- Mock 数据校验：电商增长场景通过
- 人工评测：已有历史评测记录，但新增或重大修改仍需补充对应输出评测

因此，当前可以说：

> 这些 Skill 已经通过基础测试门禁；但模型输出质量评测仍需要按变更范围持续补充。
