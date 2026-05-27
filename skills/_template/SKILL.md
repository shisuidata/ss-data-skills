---
name: skill-template
description: Template for creating a standalone data development skill. Use this as a starting point when packaging a repeatable data development action into a Skill.
---

# Skill Template

## 目标

说明这个 Skill 解决什么问题。只写一个核心目标，不要把多个动作混在一起。

## 使用场景

使用这个 Skill，当用户需要：

- 场景 1
- 场景 2
- 场景 3

## 不适用场景

不要使用这个 Skill 处理：

- 超出本 Skill 边界的任务
- 需要另一个专门 Skill 处理的任务
- 缺少必要信息且无法合理假设的高风险决策

## 输入信息

最少输入：

- 信息 1
- 信息 2

可选输入：

- 背景信息
- 表结构
- SQL
- 指标口径
- 执行引擎
- 业务约束

## 工作流程

1. 识别用户要解决的问题。
2. 提取已知信息、假设和缺失信息。
3. 按本 Skill 的检查框架逐项分析。
4. 给出结论、风险、建议和待确认问题。
5. 在信息不足时，不编造事实，明确标记假设。

## 输出格式

```markdown
## 结论

## 已知信息

## 关键分析

## 风险与建议

## 待确认问题

## 下一步
```

## 质量标准

输出必须：

- 具体
- 可执行
- 区分事实、假设和建议
- 说明风险等级
- 给出必要的示例或模板

## 示例 Prompt

```text
请用这个 Skill 帮我处理下面的问题：

[粘贴需求、SQL、表结构或上下文]
```

