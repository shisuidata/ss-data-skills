# Skill 生产 SOP

这份 SOP 用来规范拾穗数据 Skills 的生产流程。

以后新增或改造 Skill，都按这条链路走：

```text
需求定义 -> 场景建模 -> Skill 开发 -> 上下文包装 -> 示例编写 -> 测试用例 -> 评测记录 -> 发布维护
```

目标不是把流程做复杂，而是避免 Skill 变成零散提示词。每个 Skill 都必须能独立使用、能被测试、能被维护。

## 0. 判断是否值得做成 Skill

只有满足下面条件，才建议新增 Skill：

- 是数据从业者真实工作中的高频动作
- 可以被标准化
- 有明确输入和输出
- 能独立完成一个任务
- 不依赖某家公司私有流程
- 对用户有复用价值

不适合做成 Skill：

- 一次性问题
- 只有观点，没有操作流程
- 依赖未公开内部系统
- 太大太泛，什么都想管
- 只是提示词集合，没有工作标准

## 1. 需求定义

先写 Skill Brief。

模板：

[docs/templates/skill-brief.md](docs/templates/skill-brief.md)

必须说清楚：

- 这个 Skill 解决什么问题
- 用户是谁
- 典型输入是什么
- 预期输出是什么
- 不应该处理什么
- 需要哪些上下文
- 如何判断它有用

产物：

```text
docs/templates/skill-brief.md 的一份填写稿
```

## 2. 场景建模

把需求拆成真实工作场景。

至少回答：

- 用户会在什么情况下触发它
- 用户手上通常有什么材料
- 用户缺什么信息
- Agent 应该先问什么
- 输出要进入哪个下游动作

产物：

```text
Skill 的使用场景、不适用场景、输入信息、上下文建议
```

## 3. Skill 开发

在 `skills/<skill-name>/SKILL.md` 中开发 Skill。

必须包含：

- YAML frontmatter
- 目标
- 使用场景
- 不适用场景
- 输入信息
- 上下文建议
- 工作流程
- 输出格式
- 质量标准
- 示例 Prompt

参考模板：

[skills/_template/SKILL.md](skills/_template/SKILL.md)

产物：

```text
skills/<skill-name>/SKILL.md
```

## 4. 上下文包装

每个 Skill 都要说明上下文要求。

如果已有模板能覆盖，直接引用：

- [context/templates/data-task-context.md](context/templates/data-task-context.md)
- [context/templates/metric-context.md](context/templates/metric-context.md)
- [context/templates/table-context.md](context/templates/table-context.md)
- [context/templates/sql-review-context.md](context/templates/sql-review-context.md)
- [context/templates/analysis-context.md](context/templates/analysis-context.md)
- [context/templates/experiment-context.md](context/templates/experiment-context.md)
- [context/templates/report-context.md](context/templates/report-context.md)
- [context/templates/presentation-context.md](context/templates/presentation-context.md)

如果现有模板不够，先扩展 `context/templates/`，再写 Skill。

产物：

```text
Skill 中的“上下文建议”小节
必要时新增 context/templates/<template>.md
```

## 5. 示例编写

每个 Skill 必须有示例。

示例放在：

```text
examples/<skill-name>.md
```

必须包含：

- 适用场景
- 示例输入
- 预期输出
- 使用说明

示例必须脱敏。

产物：

```text
examples/<skill-name>.md
```

## 6. 测试用例

每个 Skill 必须有测试用例。

测试用例放在：

```text
tests/cases/<skill-name>.md
```

必须包含：

- Skill
- 测试目标
- 测试输入
- 通过标准

如果需要 mock 数据，放在：

```text
tests/fixtures/<scenario>/
```

产物：

```text
tests/cases/<skill-name>.md
必要时新增 tests/fixtures/<scenario>/
```

## 7. 自动检查

提交前必须运行：

```bash
node scripts/check-library.mjs
node scripts/check-tests.mjs
```

如果改动了电商 mock 数据，还要运行：

```bash
node scripts/summarize-ecommerce-fixture.mjs
```

通过标准：

```text
Library check passed.
Test check passed.
Fixture validation passed.
```

## 8. 人工评测

新增重要 Skill 或修改核心逻辑时，要写评测记录。

放在：

```text
tests/results/YYYY-MM-DD-<name>.md
```

评测维度参考：

[tests/rubrics/common.md](tests/rubrics/common.md)

至少说明：

- 测试范围
- 使用的测试用例
- 是否通过
- 发现的问题
- 修改建议

## 9. 更新索引

新增 Skill 后必须更新：

- [README.md](README.md)
- [SKILL_INDEX.md](SKILL_INDEX.md)
- [examples/README.md](examples/README.md)
- [tests/README.md](tests/README.md)

如果新增上下文模板，还要更新：

- [CONTEXT_GUIDE.md](CONTEXT_GUIDE.md)
- [context/README.md](context/README.md)

## 10. 发布

提交信息建议：

```text
Add <skill-name> skill
Improve <skill-name> context
Add tests for <skill-name>
```

发布前确认：

- [ ] Skill 本体完成
- [ ] 上下文建议完成
- [ ] 示例完成
- [ ] 测试用例完成
- [ ] 索引更新
- [ ] 自动检查通过
- [ ] 没有敏感信息

## 维护原则

每个 Skill 都要回答一句话：

> 它能不能让一个数据人更稳定地完成一个真实工作动作？

如果答案不清楚，就不要急着新增。

