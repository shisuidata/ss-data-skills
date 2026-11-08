---
name: data-viz-kit
description: Use when producing any chart, data report page, KPI tile, or visual data deliverable for Chinese business audiences. Provides chart-choice rules, Chinese number and period conventions (万/亿, 同比/环比, 涨跌色), a validated light/dark palette, and a zero-dependency Python kit that renders self-contained HTML reports. 中文触发词：图表规范、选图、配色、数据可视化、HTML 数据报告。
metadata:
  category: 表达交付
  aliases: 拾穗图表规范、图表规范、数据可视化、HTML 数据报告
---

# Data Viz Kit

## 目标

让所有数据交付物的图表**一次做对**：选对图形、数字格式符合中文业务习惯、颜色经过计算校验、亮暗模式都可读，并且能直接产出一个可以发给老板的自包含 HTML 报告。

这个 Skill 是其他分析和汇报类 Skill 的视觉底座。它不负责分析本身，只负责“把结论画对、画好看”。

## 使用场景

使用这个 Skill，当你要：

- 为分析结论画图（趋势、对比、构成、分布、实验效果）
- 生成一份 HTML 数据报告、周报页面或实验报告
- 设计指标卡、结论横幅、表格视图
- 审查一张已有图表是否误导、是否难读
- 给看板或 PPT 定配色和数字格式规范

## 不适用场景

- 决定分析什么、怎么归因：先用对应的分析 Skill（如 `funnel-analysis`、`ab-test-analysis`）
- PPT 叙事结构：使用 `data-presentation-architect`
- 看板是否支持决策的整体审查：使用 `dashboard-reviewer`，本 Skill 只补充图表层面的意见
- 品牌视觉设计、营销海报

## 输入信息

最少输入：

- 要表达的结论（一句话）
- 数据（表格、JSON、CSV 或已计算好的数值）

推荐输入：

- 受众（管理层 / 业务 / 技术 / 金融交易类）
- 指标方向：越高越好还是越低越好
- 涨跌色约定：好坏色（默认）还是红涨绿跌
- 输出形式：HTML 报告、单张图、给 BI 工具的配置建议

## 上下文建议

推荐使用 [报告上下文模板](../../context/templates/report-context.md) 说明受众和决策场景；汇报类任务同时参考 [PPT 汇报上下文模板](../../context/templates/presentation-context.md)。

受众决定涨跌色约定和信息密度。缺少受众时按“业务负责人 + 好坏色约定”处理，并在输出中写明假设。

## 工作流程

按顺序做，颜色永远最后考虑：

1. **先写结论句**：这张图要让读者记住哪一句话？写不出来就先别画。
2. **选图形**：按 [选图规则](references/chart-choice.md) 从“数据的任务”出发选图，有时答案是一个指标卡而不是图。
3. **定数字格式**：按 [中文业务约定](references/cn-conventions.md) 处理万/亿、百分点、同比环比、周口径和涨跌色。
4. **上色**：按颜色承担的任务分配（分类 / 顺序 / 发散 / 状态），使用 [拾穗配色](references/palette.md)，不要自创颜色。
5. **校验**：改过配色就运行 `python3 scripts/check_palette.py`，FAIL 必须修。
6. **生成**：能执行代码时，用 `scripts/sskit_viz.py` 生成 HTML（见下方“工具”），不要手写 SVG 坐标。
7. **对照反模式检查**：逐条过一遍 [常见错误](references/chart-choice.md#常见错误)。

## 工具

`scripts/` 下的脚本只依赖 Python 3.9+ 标准库：

| 文件 | 作用 |
| --- | --- |
| `sskit_viz.py` | 图表与版面组件：`interval_chart`（区间图）、`bar_chart`、`paired_bar_chart`（两期对比）、`diverging_bar_chart`（正负贡献）、`heatmap_table`（留存矩阵热力表）、`line_chart`、`stat_tiles`、`callout`、`checklist`、`table`、`html_report`，以及 `fmt_num` / `fmt_pct` / `fmt_pp` / `fmt_signed_pct` / `delta_tone` |
| `sskit_io.py` | 其他 Skill 共用的读取工具：编码识别、CSV 和 xlsx 读取、时区换算 |
| `check_palette.py` | 配色校验：明度带、彩度、色觉障碍区分度、正常视觉区分度、对比度 |
| `demo_report.py` | 示例经营周报，展示全部组件用法：`python3 scripts/demo_report.py out.html` |

最小用法：

```python
import sys; sys.path.insert(0, "<本 Skill 目录>/scripts")
import sskit_viz as viz

html = viz.html_report("5 月第 4 周经营周报", [
    viz.callout("warning", "GMV 同比转负：工作日下滑", "主要来自信息流投放"),
    viz.section("核心指标", viz.stat_tiles([
        {"label": "近 7 日 GMV", "value": viz.fmt_num(12690000), "delta": "▼ −2.6% 同比", "tone": "bad"},
    ])),
])
viz.save("report.html", html)
```

生成的 HTML 无外部依赖，自动适配亮暗模式，自带深浅色切换，可离线打开、直接发送。

## 输出格式

产出 HTML 报告时：

```markdown
## 图表交付

- 报告文件：<路径>
- 核心结论：<一句话>
- 图表清单：
  | 图 | 回答的问题 | 图形 | 为什么选它 |
  | --- | --- | --- | --- |
- 采用的约定：涨跌色 <好坏色 / 红涨绿跌>，数字单位 <万 / 亿 / 原值>，同比口径 <按周对齐 / 按日期对齐>
- 假设与待确认：
```

审查已有图表时：

```markdown
## 图表审查

| 图 | 问题 | 影响 | 修改建议 | 优先级 |
| --- | --- | --- | --- | --- |
```

## 质量标准

输出必须：

- 每张图都有一句结论式标题或导语，而不是“趋势图”这种主题词
- 绝不使用双 Y 轴；量纲不同就拆成两张图或做指数化
- 颜色不单独承载含义：涨跌配 ▲▼ 和正负号，状态配图标和文字
- 不显著或未经证实的变化不上色
- 两个及以上序列一定有图例
- 每张图都能找到对应的表格视图或明确数值
- 数字统一格式：同一张表里不混用“12,345”和“1.23万”
- 配色改动后必须通过 `check_palette.py`

## 完成后的下一步

- 完整的分析报告：`data-analysis-report-writer`
- 做成汇报：`data-presentation-architect`
- 看板层面的审查：`dashboard-reviewer`

## 示例 Prompt

```text
请用 data-viz-kit 把下面的周度经营数据做成一份 HTML 周报。
受众：电商运营负责人，看完要决定是否调整信息流预算。
核心结论：GMV 同比 −2.6%，下滑集中在工作日和信息流投放渠道。
数据：[粘贴每日 GMV、渠道 GMV、去年同期数据]
```

```text
请用 data-viz-kit 审查这张看板截图里的图表：
受众是证券业务部门，他们习惯红涨绿跌。
[附截图]
```
