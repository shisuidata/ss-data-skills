# 贡献指南

感谢你愿意参与维护拾穗数据 Skills。

这个仓库收录的是面向数据从业者真实工作的 AI Agent Skill。我们欢迎拾穗数据会员和外部用户一起共建，但这里不是提示词堆放区。每个贡献都应该帮助数据人更稳定地完成一个具体工作动作。

## 可以贡献什么

适合提交：

- 新 Skill
- 现有 Skill 的改进
- 脱敏后的示例输入和输出
- 更清晰的使用场景
- 更准确的输出模板
- 针对某个数据工作流的边界补充
- 可公开复用的行业上下文包
- 发现 Skill 之间职责重叠后的整理建议

不适合提交：

- 未脱敏的公司内部数据
- 真实业务系统截图
- 生产表名、字段名、日志、密钥、账号信息
- 只适用于单家公司内部流程的规则
- 没有明确场景的提示词合集
- 大而全、什么都想管的万能 Skill

## 新增 Skill 标准

新增 Skill 前，先判断它是不是一个“可重复的标准动作”。

完整流程请按 [Skill 生产 SOP](SOP.md) 执行。需求定义建议先填写 [Skill Brief 模板](docs/templates/skill-brief.md)。

一个合格的 Skill 应该满足：

- 可以独立使用
- 只解决一个明确问题
- 有清晰触发场景
- 有输入要求
- 有工作流程
- 有输出格式
- 有质量标准
- 有示例 Prompt
- 有清晰的上下文要求
- 信息不足时会列假设和待确认问题
- 涉及行业差异时，优先引用行业上下文包，而不是复制出多个行业版 Skill

目录结构：

```text
skills/skill-name/
  SKILL.md
```

命名规则：

- 使用小写英文
- 单词之间用连字符
- 名称要表达动作，不要太抽象

好的例子：

```text
dashboard-reviewer
business-root-cause-analysis
data-incident-postmortem-writer
```

不好的例子：

```text
data-helper
super-analysis
work-assistant
```

## SKILL.md 必备结构

每个 `SKILL.md` 必须包含 YAML frontmatter：

```yaml
---
name: skill-name
description: Use when...
---
```

正文建议包含：

- 目标
- 使用场景
- 不适用场景
- 输入信息
- 上下文要求
- 工作流程
- 输出格式
- 质量标准
- 示例 Prompt

可以参考：

[skills/_template/SKILL.md](skills/_template/SKILL.md)

上下文要求可以参考：

[CONTEXT_GUIDE.md](CONTEXT_GUIDE.md)

行业上下文包可以参考：

[context/industries/README.md](context/industries/README.md)

## 示例贡献标准

示例统一放在：

```text
examples/
```

每个 Skill 至少可以配一份示例：

```text
examples/skill-name.md
```

示例应包含：

- 适用场景
- 示例输入
- 预期输出
- 使用说明

示例必须脱敏：

- 用户名改成 `user_001`
- 表名改成 `dwd_order_detail_d` 这类通用名称
- 公司名改成 `某电商平台`、`某 SaaS 产品`
- 金额、用户量、转化率可以保留量级，但不能暴露真实业务数据
- 截图不要直接提交，除非确认可公开

## 脱敏原则

提交前请检查：

- 是否包含真实公司、客户、部门、员工姓名
- 是否包含真实手机号、邮箱、用户 ID、订单 ID
- 是否包含真实生产库、生产表、接口地址
- 是否包含内部系统截图、日志、报错栈
- 是否包含商业机密、未公开策略、真实财务数据

如果不确定能不能公开，就不要提交。

## 修改现有 Skill

修改现有 Skill 时，优先做小而清晰的改动：

- 补充缺失场景
- 修正边界说明
- 优化输出模板
- 增加风险提示
- 删除空泛表达

不要在一个 PR 里同时改很多无关 Skill。

## Pull Request 建议

PR 标题建议：

```text
Add dashboard-reviewer skill
Improve sql-reviewer output template
Add examples for funnel-analysis
```

PR 描述建议包含：

- 改了什么
- 为什么改
- 影响哪些 Skill
- 是否新增示例
- 是否涉及脱敏材料

提交前检查：

- [ ] Skill 名称和目录名一致
- [ ] `description` 能说明什么时候触发
- [ ] 输出模板可直接复制使用
- [ ] 示例没有敏感信息
- [ ] 涉及行业上下文时已更新 `context/README.md` 和 `CONTEXT_GUIDE.md`
- [ ] Markdown 渲染正常
- [ ] 没有提交临时文件、缓存、日志
- [ ] `node scripts/check-library.mjs` 通过
- [ ] `node scripts/check-tests.mjs` 通过

测试方式见 [TESTING.md](TESTING.md)。

## 维护原则

这个仓库服务的是数据从业者的真实工作。

我们更看重：

- 清楚
- 可执行
- 可复用
- 能暴露风险
- 能减少返工

不追求：

- 术语堆砌
- 大而全
- 空泛正确
- 看起来很智能但无法落地

## License

提交到本仓库的内容默认遵循仓库的 MIT License。
