---
name: data-analysis-report-writer
description: Use when turning analysis results, metrics, SQL outputs, or investigation notes into a structured data analysis report for business readers. Composes a bundled zero-dependency script's report spec into a self-contained HTML report plus Markdown, where every number is bound to a source JSON (outputs of ab-test, funnel, retention, EDA scripts or user-supplied facts) via {{source:path|format}} references, traced in an appendix, and linted for unsourced numbers, missing evidence, causal overclaiming, and vague actions. 中文触发词：分析报告、数据报告、专题报告、报告数字核对。
metadata:
  category: 表达交付
  aliases: 分析报告、数据报告、报告写作、分析结论
---

# Data Analysis Report Writer

## 目标

把分析结果写成一份业务方、管理者能直接拿来做决策的报告：先结论、再证据、再建议，事实和判断分开写。

核心原则：**报告里的数字不手写**。每个数字都用 `{{来源:路径|格式}}` 引用来源 JSON，由 `scripts/report.py` 取值、格式化，并在附录里列出出处。模型负责结构、判断、措辞和建议；脚本保证数字和来源一致，并检查证据缺失、因果措辞和空洞建议。

## 使用场景

- 漏斗、留存、实验、数据体检做完后，整理成一份给业务看的报告
- 转化下降、指标异常的原因分析报告
- 活动复盘、专题分析、看板解读说明
- 把多个分析结果合成一份报告（例如“体检 + 漏斗 + 留存”）
- 检查一份已经写好的报告：里面的数字能否在数据里找到

典型输入：

```text
漏斗和留存都跑完了（funnel.json、retention.json），帮我写成给增长负责人的分析报告。
```

## 不适用场景

- 还没有分析结果：先用 `exploratory-data-analysis`、`funnel-analysis`、`retention-cohort-analysis`、`ab-test-analysis` 产出结果
- 还不知道变化集中在哪里：先用 `business-root-cause-analysis`
- 周报、月报这类固定节奏的经营汇报：使用 `weekly-monthly-report-writer`
- 汇报 PPT 的结构和页面：使用 `data-presentation-architect`
- 数据事故复盘：使用 `data-incident-postmortem-writer`

用户只给结论、不给任何数据时，只能写报告框架，所有发现都要标为“证据不足”，不能替用户编数字。

## 输入信息

最少输入：

- 分析主题和目标读者
- 分析结果：分析脚本的 `--json` 输出，或用户提供的关键数字（会写进 `facts`，并注明出处）

推荐输入：

- 希望推动的决策
- 业务背景：同期发生了什么（发版、投放、活动、节假日）
- 口径说明、已知限制
- 行动的负责人和时间

## 上下文建议

推荐使用 [报告写作上下文模板](../../context/templates/report-context.md)。

最有价值的上下文是：读者是谁、他们要做什么决策、同期发生了哪些业务事件。缺少读者和决策时，报告容易写成“数据罗列”。

## 工作流程

1. **准备来源**：用各分析 Skill 的脚本输出 JSON（例如 `funnel.py analyze ... --json funnel.json`）。用户直接给的数字写进规格的 `facts`，每条注明 `source`（来自哪个看板、哪份文档）。
2. **生成草稿**：

   ```bash
   python3 scripts/report.py skeleton --source funnel=funnel.json --source ret=retention.json --out spec.json
   ```

   草稿已经绑定好关键数字和标准图表，叙述部分用「【待补充…】」占位。
3. **改写规格**：按 [写作指南](references/writing-guide.md) 改写标题、一句话结论、摘要、发现的解释和影响、原因假设、建议动作。需要别的数字时：

   ```bash
   python3 scripts/report.py refs --source funnel=funnel.json --grep segments
   ```

   派生数字（相对变化、损失的客户数）写成 `facts` 里的 `expr`，不要心算。规格格式见 [规格说明](references/spec-schema.md)。
4. **构建并修正**：

   ```bash
   python3 scripts/report.py build --spec spec.json --html report.html --md report.md --strict
   ```

   逐条处理输出里的 `errors`（引用写错）、`numbers.unmatched`（手写了来源里没有的数字）、`numbers.uncheckable`（用汉字写的数字，如“两成”“翻倍”“近半”）和 `warnings`（证据不足、因果措辞、空洞建议、没有负责人、还有待补充），直到 `--strict` 通过。
5. **交付**：一句话结论 + 3 条以内摘要 + HTML 报告路径；Markdown 版本可直接粘贴到飞书 / Notion。

检查已有报告：`python3 scripts/report.py lint --text report.md --source funnel=funnel.json`，会列出能对上的数字（并给出建议引用）、对不上的数字、无法核对的汉字数字，以及因果措辞和空洞建议。全部参数见 [命令行参数](references/cli.md)。

不能执行代码时：按同样的结构手写，每个数字后注明来源字段，并在结尾写明“数字未经脚本核对”。

## 输出格式

HTML 报告和 Markdown 版本的结构相同：

```markdown
# [标题]

> **一句话结论（带最关键的数字）**
> 需要的决策：……

| 指标卡 1 | 指标卡 2 | 指标卡 3 |

## 执行摘要（3 条以内，每条一个结论 + 一个数字）
## 背景与口径（要回答的问题、时间范围、指标定义、对比基线、数据来源）
## 核心发现
### 发现 1：[一句话结论]
- 标签：事实 / 推断 / 实验结论 · 置信度
- 数据证据（全部是引用）
- 图表（来源的标准图或自定义图）
- 解释判断 / 业务影响
## 原因假设（假设 | 支持证据 | 如何验证 | 状态）
## 建议动作（优先级 | 建议 | 预期收益 | 成本/风险 | 负责人 | 时间）
## 风险与限制（含各来源脚本标记的口径和质量问题）
## 下一步
附录：数字溯源（报告中的写法 | 来源路径 | 原始值）
```

对话中的回复：

```markdown
**结论**：<一句话>
1. <摘要 1>
2. <摘要 2>
3. <摘要 3>

报告：<report.html 路径>（Markdown：<report.md 路径>）
构建检查：引用 N 个数字，未溯源 0 个，警告 0 条
```

## 质量标准

输出必须：

- 先写结论，再写过程；一句话结论里有最关键的数字
- 每个核心发现至少有一条引用来源的数据证据，否则标为“证据不足”
- 正文没有来源里找不到的手写数字，也不用汉字写数字；外部数字写进 `facts` 并注明出处
- 事实、推断、建议分开写；没有实验或已验证机制时不用“导致、造成”这类因果措辞
- 来源有阻断问题（SRM 异常、漏斗人数不单调、数据体检有 P0）时，报告顶部必须提示
- 建议是具体动作，有负责人和时间，不写“持续关注”；用户没提供负责人或时间时写“待确认”，不要按角色自己拟
- 写清风险与限制，包括脚本标记的口径问题

## 完成后的下一步

- 做成汇报：`data-presentation-architect`
- 纳入周报或月报：`weekly-monthly-report-writer`
- 图表规范：`data-viz-kit`

## 示例 Prompt

```text
请用 data-analysis-report-writer 把下面的漏斗结果写成报告：

来源：funnel.json（funnel-analysis 输出，SaaS 试用到付费，4 月 vs 3 月，按注册渠道分群）
读者：增长负责人、产品负责人
背景：4 月信息流广告预算上调（投放后台显示消耗环比 +62%）；4 月 8 日上线新版邀请流程，邀请前要验证企业邮箱
希望推动的决策：是否暂停企业邮箱验证，信息流预算是否维持
```

```text
请用 data-analysis-report-writer 写一份 5 月新用户首购转化下降报告。
我没有跑脚本，只有这些数字（来自 BI 看板「新客转化日报」）：
- 首购转化 8.2% → 6.9%
- 移动端支付页加载 P75 从 1.8s 升到 3.4s
- 渠道 A 新用户占比 35% → 52%，渠道 A 转化 5.1%（大盘 6.9%）
读者：业务负责人和产品经理
```

```text
请用 data-analysis-report-writer 检查这份我手写的报告，看哪些数字在 funnel.json 里对不上：report.md
```
