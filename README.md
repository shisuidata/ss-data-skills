# 拾穗 DATA

面向数据开发者的 AI Agent Skill 开源库。

这个项目用于沉淀数据开发日常工作中的标准动作：需求澄清、指标口径审查、表设计、SQL 审查、数据质量规则生成等。每个动作都会被包装成一个可独立使用的 Skill，既能单独调用，也能被组合成完整的数据开发工作流。

## 项目定位

数据开发里有大量重复但不应该粗糙处理的细节：

- 一个模糊需求如何变成可开发任务
- 一个指标口径是否真的严谨
- 一张表的粒度、分区、更新策略是否合理
- 一段 SQL 是否存在逻辑漏洞或性能风险
- 一张产出表应该配置哪些质量校验

这些不是“提示词技巧”，而是可复用的工作方法。这个仓库会把它们整理成面向 AI Agent 的 Skill，让数据开发者可以在日常工作中直接使用。

## 设计原则

1. 每个 Skill 必须独立可用
2. 每个 Skill 只解决一个明确问题
3. 每个 Skill 必须有清晰的输入、输出和使用场景
4. Skill 不依赖私有上下文，缺失信息要显式列为假设或待确认问题
5. 多个 Skill 可以自然组合，但不能互相强依赖

一句话：

> 单独可用是底线，串联协作是加分项。

## 首批 Skill

| Skill | 用途 |
| --- | --- |
| `data-requirement-clarifier` | 把模糊的数据需求澄清成可开发任务 |
| `metric-definition-reviewer` | 审查指标口径、统计粒度、边界条件和业务风险 |
| `table-design-advisor` | 设计或审查数仓表结构、分层、粒度、分区和更新策略 |
| `sql-reviewer` | 审查 SQL 的逻辑正确性、性能风险和口径一致性 |
| `data-quality-rule-generator` | 根据表结构、SQL 或指标定义生成数据质量规则 |

这些 Skill 可以单独使用，也可以组成一条常见的数据开发链路：

```text
需求澄清 -> 指标口径 -> 表设计 -> SQL 审查 -> 质量规则
```

## 目录结构

```text
skills/
  README.md
  _template/
    SKILL.md
  data-requirement-clarifier/
    SKILL.md
  metric-definition-reviewer/
    SKILL.md
  table-design-advisor/
    SKILL.md
  sql-reviewer/
    SKILL.md
  data-quality-rule-generator/
    SKILL.md
```

每个 Skill 目录都以 `SKILL.md` 作为核心文件。必要时可以增加：

- `references/`：放较长的领域参考资料
- `scripts/`：放可执行脚本
- `assets/`：放模板、图片、示例文件等资源

## 使用方式

把某个 Skill 目录复制或安装到支持 Skill 的 Agent 环境中，然后用自然语言触发即可。

例如：

```text
请用 sql-reviewer 帮我审查下面这段 Spark SQL，重点看指标口径和性能风险。
```

或者：

```text
请用 data-requirement-clarifier 把这个需求整理成数据开发任务：
老板想看最近转化率为什么下降。
```

## 维护方向

第一阶段先沉淀数据开发高频动作。

第二阶段可以继续扩展：

- `pipeline-debugger`
- `backfill-planner`
- `lineage-explainer`
- `flink-job-reviewer`
- `data-incident-postmortem-writer`
- `data-dev-pr-reviewer`
- `warehouse-naming-linter`
- `data-doc-writer`
- `agent-skill-packager`

## 同步约定

这个仓库面向 GitHub 公共发布。可以同步的内容包括：

- 可独立使用的 Skill
- 面向用户的说明文档
- 可复用示例
- 经过整理的脚本、模板和参考资料

不应同步的内容包括：

- 临时草稿
- Agent 运行中间态
- 本地调试缓存
- 私有配置和环境变量
- 未脱敏的业务数据、日志或截图

中间材料统一放入 `tmp/`、`scratch/` 或 `workbench/`，这些目录默认不会进入 Git。
