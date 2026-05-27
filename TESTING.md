# 测试说明

这个仓库里的 Skill 主要是文档型能力，不是传统代码库。所以测试分两层：

1. 自动化结构测试
2. 人工样例评测

当前已经提供自动化结构测试脚本：

```bash
node scripts/check-library.mjs
```

## 自动化测试检查什么

脚本会检查：

- 每个 `skills/<skill-name>/SKILL.md` 是否存在
- Skill 目录名和 frontmatter `name` 是否一致
- frontmatter 是否包含 `description`
- Skill 是否包含必备章节
- 每个 Skill 是否有“上下文建议”
- 每个 Skill 是否有对应示例
- 每个示例是否包含适用场景、示例输入、预期输出和使用说明
- 仓库级文档是否存在
- 上下文模板是否齐全
- README、索引、贡献指南中关键链接是否存在

通过示例：

```text
Library check passed.
Skills: 12
Context templates: 8
```

## 自动化测试不检查什么

当前脚本不判断：

- Agent 最终输出质量是否足够好
- SQL 改写是否真的能在某个引擎执行
- 分析结论是否业务上完全正确
- PPT 结构是否真的适合某个具体公司
- 每个 Skill 在不同模型上的表现差异

这些需要人工评测或后续接入模型评测。

## 人工样例评测

每个 Skill 都有一个示例文件：

```text
examples/<skill-name>.md
```

人工评测建议流程：

1. 打开一个示例文件。
2. 复制“示例输入”给支持 Skill 的 Agent。
3. 指定对应 Skill。
4. 对照“预期输出”检查结果。
5. 判断输出是否满足质量标准。

评测时重点看：

- 是否正确识别任务边界
- 是否主动使用上下文
- 是否区分事实、假设和建议
- 是否暴露待确认问题
- 输出是否能直接用于工作
- 是否有空泛正确但不可执行的内容

## 评测记录模板

```markdown
## Skill

## 测试日期

## 测试输入

## 实际输出摘要

## 通过情况

- [ ] 能识别任务
- [ ] 能使用上下文
- [ ] 能暴露风险
- [ ] 能给出可执行建议
- [ ] 没有编造事实

## 问题

## 建议修改
```

## 后续可扩展测试

后续可以继续补：

- `tests/cases/`：保存更多评测用例
- `tests/rubrics/`：保存每个 Skill 的评分 Rubric
- `scripts/run-evals.mjs`：调用模型批量跑示例
- CI：在 PR 中自动运行 `node scripts/check-library.mjs`

当前阶段先保证 Skill 库结构完整、示例齐全、上下文契约明确。

