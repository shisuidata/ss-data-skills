# 命令行参数

这份文档由脚本的参数定义生成，修改参数后请重新生成，不要手改。所有脚本都把结果以 JSON 打印到标准输出。

## `ab_test.py analyze`

解读实验结果

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--summary` | 否 | — | 汇总数据 JSON（见 references/input-schema.md） |
| `--csv` | 否 | — | 用户粒度 CSV，每行一个实验单元 |
| `--variant-col` | 否 | variant | — |
| `--control` | 否 | — | 对照组取值，默认取排序后的第一个 |
| `--metric`（可重复） | 否 | — | 主指标 列名:proportion\|mean[:higher\|lower]，或 分子列/分母列:ratio[:higher\|lower]，可重复 |
| `--secondary`（可重复） | 否 | — | 辅助指标，格式同 --metric |
| `--guardrail`（可重复） | 否 | — | 护栏指标，格式同 --metric |
| `--cuped`（可重复） | 否 | — | CUPED 方差缩减：指标列=实验前协变量列 |
| `--allocation` | 否 | — | 预期分流比例，如 A=0.9,B=0.1；默认均分，非均分实验必须填写 |
| `--days` | 否 | — | 实验已运行天数 |
| `--planned-days` | 否 | — | 计划运行天数 |
| `--name` | 否 | — | 实验名称 |
| `--alpha` | 否 | — | 显著性水平，默认 0.05 |
| `--html` | 否 | — | 输出 HTML 报告路径 |
| `--json` | 否 | — | 同时把 JSON 写入文件 |

## `ab_test.py plan`

实验前样本量与周期规划

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--metric-type` | 否 | proportion | 可选：proportion、mean |
| `--baseline` | 是 | — | 对照组基线：比例如 0.07，均值如 4.2 |
| `--std` | 否 | — | 均值指标的标准差 |
| `--mde-rel` | 否 | — | 最小可检测相对效应，如 0.05 表示 5% |
| `--mde-abs` | 否 | — | 最小可检测绝对效应，如 0.005 表示 0.5pp |
| `--alpha` | 否 | 0.05 | — |
| `--power` | 否 | 0.8 | — |
| `--groups` | 否 | 2 | 总组数（含对照组） |
| `--daily-users` | 否 | — | 每天进入实验的总用户数 |
