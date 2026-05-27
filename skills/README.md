# Skills 收录规范

这个目录收录面向数据从业者真实工作的原子 Skill。每个 Skill 都应该是一个可以独立执行的标准动作。

当前 Skill 覆盖三类场景：

- 数据开发：需求、指标、表设计、SQL、质量规则
- 数据分析：EDA、漏斗、留存、实验分析
- 表达交付：分析报告、周报月报、PPT 叙事

如果需要按工作场景选择 Skill，请先看仓库根目录的 [Skill 索引](../SKILL_INDEX.md)。

如果需要参考输入输出样例，请看 [示例索引](../examples/README.md)。

如果需要准备业务、数据、指标或汇报上下文，请看 [上下文使用指南](../CONTEXT_GUIDE.md) 和 [上下文模板](../context/README.md)。

## 基本结构

```text
skill-name/
  SKILL.md
  references/   # 可选
  scripts/      # 可选
  assets/       # 可选
```

`SKILL.md` 是必需文件，必须包含 YAML frontmatter：

```yaml
---
name: skill-name
description: Use when...
---
```

## 写作要求

每个 Skill 必须说明：

- 使用场景
- 不适用场景
- 输入信息
- 工作流程
- 输出格式
- 质量标准
- 示例 Prompt

## 设计边界

每个 Skill 只能解决一个明确问题。

例如：

- `sql-reviewer` 只负责 SQL 审查，不负责完整需求澄清
- `metric-definition-reviewer` 只负责指标口径，不负责设计整套数仓模型
- `data-quality-rule-generator` 只负责质量规则，不负责调度平台配置
- `funnel-analysis` 只负责有序转化路径，不负责所有业务归因
- `data-analysis-report-writer` 只负责报告写作，不负责凭空生成数据结论
- `data-presentation-architect` 只负责 PPT 叙事结构，不负责视觉美化或制作二进制 PPT 文件

如果一个任务需要多个动作，应新增 Workflow 类 Skill，而不是让原子 Skill 变得臃肿。

## 独立可用原则

每个 Skill 都必须在缺少上下文时仍然能工作：

- 信息充分时，给出明确结论
- 信息不足时，列出假设
- 事实不确定时，标记待确认
- 不能凭空编造表结构、业务规则或公司内部规范

## 输出风格

默认输出 Markdown。

输出要适合数据开发者直接使用，避免空泛建议。优先给出：

- 风险点
- 修改建议
- 可执行清单
- SQL 示例
- 待确认问题
- 验收标准
- 数据证据
- 业务解释
- 汇报结构

## 新增 Skill 检查清单

- [ ] Skill 名称使用小写英文和连字符
- [ ] `description` 明确写出触发场景
- [ ] 可以独立使用
- [ ] 有输入和输出说明
- [ ] 有可复制的输出模板
- [ ] 有至少一个示例 Prompt
- [ ] 没有依赖私有上下文
- [ ] 缺失信息会被标记为假设或待确认
