# 报告规格（spec）说明

`report.py build` 读取一个 JSON 规格。除 `title` 外都可以省略，但缺少一句话结论、证据、建议或限制时会给出警告。

完整示例：[../assets/example_spec.json](../assets/example_spec.json)

## 顶层字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | 文本 | 报告标题，写成结论或问题，不写“XX 分析报告” |
| `subtitle` | 文本 | 副标题，例如分析对象和对比周期 |
| `audience` | 文本 | 读者，显示在页眉 |
| `date` | 文本 | 例如“数据截至 2026-04-30” |
| `question` | 文本 | 这份报告要回答的业务问题 |
| `background` | 文本 | 同期发生了什么：发版、投放、活动、节假日 |
| `decision` | 文本 | 希望读者做出的决策，显示在结论下方 |
| `sources` | 对象 | `{名称: JSON 路径}`，路径相对规格文件所在目录；命令行 `--source` 同名时覆盖 |
| `facts` | 对象 | 外部数字和派生数字，见下文 |
| `headline` | 文本 | 一句话结论，必须带最关键的数字 |
| `level` | 文本 | 结论横幅的语气：`good` / `warning` / `bad` / `info` |
| `kpis` | 列表 | 指标卡：`{label, value, delta?, tone?, note?}`；`tone` 为 `good` / `bad` / `warning` / `neutral` |
| `summary` | 列表 | 执行摘要，3 条以内 |
| `scope` | 列表或对象 | 口径表：`[["对比", "4 月 vs 3 月"], ...]` |
| `findings` | 列表 | 核心发现，见下文 |
| `hypotheses` | 列表 | `{hypothesis, evidence, verify, status}`；`status` 为 `pending` / `supported` / `rejected` |
| `actions` | 列表 | `{priority, action, expected, cost, owner, due}`；按 P0 / P1 / P2 排序 |
| `limitations` | 列表 | 风险与限制 |
| `next_steps` | 列表 | 下一步 |

所有文本字段都可以写引用，也可以用 `**加粗**`。

## 引用语法

```text
{{来源:路径|格式}}
```

- **来源**：`sources` 里的名称；省略来源时指向 `facts`，例如 `{{lost_paid|int}}`
- **路径**：
  - 用 `.` 分隔键名；
  - 用 `[0]` 取列表下标；
  - 用 `[字段=值]` 按字段选列表元素，比下标稳。例如：

  ```text
  comparison.steps[transition=完成 onboarding → 邀请团队成员].rate_current
  ```

  - 键名可以含空格和中文，例如 `periods.4 月.overall`。
- **格式**：

| 格式 | 示例输入 | 显示 | 用于 |
| --- | --- | --- | --- |
| `pct` / `pct.0` / `pct.2` | 0.055098 | 5.5% / 6% / 5.51% | 比例 |
| `pp` / `pp.2` | −0.01395 | −1.4pp | 两个比例的差（带符号） |
| `spct` | 0.1098 | +11.0% | 相对变化（带符号） |
| `num` / `num.1` | 18250 | 1.83万 | 金额、人数等大数 |
| `snum` | −3200 | −3,200 | 带符号的绝对变化 |
| `int` | 71.1 | 71 | 整数计数 |
| `fixed.1` | 3.42 | 3.4 | 不压缩的小数 |
| `times` | 1.62 | 1.6 倍 | 倍数 |
| `p` | 0.0053 / 0.00001 | p=0.005 / p<0.001 | p 值（自带 `p=`） |

格式前可以加变换：`abs`（取绝对值）、`neg`（取反）、`len`（列表长度），例如 `{{rel_drop|abs|pct.0}}` 显示“20%”，适合写在“下降”后面。

区间（两元素列表）直接引用即可，例如 `{{funnel:comparison.overall.ci|pp}}` 显示 `[−2.4pp, −0.4pp]`。

文本字段也能引用，例如 `{{funnel:verdict.title}}`、`{{funnel:checks[id=definition].detail}}`。

不确定路径时用 `refs` 查：

```bash
python3 scripts/report.py refs --source funnel=funnel.json --grep 邀请
python3 scripts/report.py refs --source eda=eda.json --strings --grep issues
```

## facts：外部数字和派生数字

```json
"facts": {
  "ad_spend_mom": {"value": 0.62, "label": "信息流广告 4 月消耗环比", "source": "投放后台"},
  "invite_release": {"value": "4 月 8 日上线新版邀请流程", "source": "产品发版记录"},
  "rel_drop": {"expr": "{funnel:comparison.overall.diff} / {funnel:periods.3 月.overall}", "label": "整体转化相对变化"},
  "lost_paid": {"expr": "-{funnel:comparison.overall.diff} * {funnel:periods.4 月.counts[0]}"}
}
```

- **外部数字**：用户口述的数字、看板截图里的数字。必须写 `source`，它会出现在附录的数字溯源表里。
- **派生数字**：写成 `expr`。
  - 支持 `+ - * /`、括号、`abs` / `min` / `max`。
  - 用单花括号 `{来源:路径}` 引用来源；也可以引用其他 fact，写作 `{facts:名称}`。
- 可以只写值，例如 `"window_days": 7`；这种写法没有出处，只适合写定义参数。

## findings：核心发现

```json
{
  "title": "下降集中在 onboarding 前后两步",
  "type": "fact",
  "confidence": "high",
  "evidence": ["完成 onboarding → 邀请团队成员：{{...rate_baseline|pct}} → {{...rate_current|pct}}"],
  "chart": {"preset": "contribution", "source": "funnel"},
  "interpretation": "……",
  "impact": "……"
}
```

- `type`：
  - `fact`：数据直接显示；
  - `inference`：推断；
  - `experiment`：随机实验结论，是唯一可以写因果的类型。
- `confidence`：`high` / `medium` / `low`。
- `evidence`：每条至少一个引用。没有任何引用时，报告会标“证据不足”。

## 图表

**来源的标准图（preset）**：数据直接取自来源 JSON，不用自己抄数。

| 来源类型 | preset | 图 |
| --- | --- | --- |
| funnel | `steps` | 各步转化率，两期成对条形图 |
| funnel | `counts` | 本期各步人数 |
| funnel | `contribution` | 各步对整体变化的贡献（正负条形图，显著的才上色） |
| funnel | `segments` | 分群结构拆解表；可用 `"dim"` 指定维度 |
| ab | `effects` | 各指标相对提升与 95% 区间（森林图） |
| retention | `curve` | 固定批次留存曲线，含分群；`"segments": false` 只画整体 |
| retention | `matrix` | 留存矩阵热力表 |
| retention | `segments` | 批次对比的结构拆解表 |
| eda | `issues` | 问题清单；`"levels": ["P0"]`、`"limit": 10` |

通用字段：`source`（默认第一个来源）、`title`、`caption`。

**自定义图**：数据写成引用或数字。数字也要能在来源里找到，否则会被报告为未溯源。

```json
{"type": "bar", "categories": ["自然搜索", "信息流广告"], "values": ["{{funnel:periods.4 月.segments.注册渠道.自然搜索.overall}}", "{{funnel:periods.4 月.segments.注册渠道.信息流广告.overall}}"], "fmt": "pct", "title": "4 月各渠道转化"}
```

自定义图的 `type` 可选：

- `bar`、`diverging`：`values`；diverging 可加 `tones`。
- `paired`：`current`、`baseline`、`names`。
- `line`：`series: [{name, values}]`。

## 构建检查

| 输出字段 | 含义 | 处理 |
| --- | --- | --- |
| `errors` | 引用写错（键名、选择器、格式），会列出可用的选项 | 必须修正，否则退出码为 1 |
| `numbers.unmatched` | 正文里手写的数字在所有来源中都找不到 | 改成引用；外部数字写进 `facts` |
| `numbers.matched_unbound` | 手写数字和来源一致但没有绑定 | 建议改成引用，来源更新后才会跟着变 |
| `warnings` | 缺一句话结论、证据不足、因果措辞、空洞建议、缺负责人、缺限制、还有待补充、来源有阻断问题 | `--strict` 下必须清零 |

数字扫描会忽略这些写法：

- 日期、年份；
- 带字母的编号（W2、P0、D7、Q2）；
- 12 以内的整数（序号、计数）；
- 时间窗口参数（“7 天”）；
- 方法参数（“95% 区间”）。
