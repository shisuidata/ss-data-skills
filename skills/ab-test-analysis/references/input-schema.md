# 输入格式

`scripts/ab_test.py analyze` 接受两种输入，二选一。

## 方式一：汇总数据 JSON（`--summary`）

适合用户只给了“每组多少人、转化多少”的场景。完整示例见 [`assets/example_summary.json`](../assets/example_summary.json)。

```json
{
  "name": "新版移动端支付页实验",
  "hypothesis": "减少支付页步骤可以提升支付成功率",
  "alpha": 0.05,
  "power": 0.8,
  "control": "旧版",
  "allocation": {"旧版": 0.5, "新版": 0.5},
  "days": 7,
  "planned_days": 14,
  "early_stopped": false,
  "groups": {
    "旧版": {"users": 5000},
    "新版": {"users": 5020}
  },
  "metrics": [
    {
      "name": "支付成功率",
      "role": "primary",
      "type": "proportion",
      "higher_is_better": true,
      "data": {"旧版": {"successes": 350}, "新版": {"successes": 390}}
    },
    {
      "name": "人均支付金额",
      "role": "secondary",
      "type": "mean",
      "data": {"旧版": {"mean": 86.2, "std": 140.5}, "新版": {"mean": 88.9, "std": 151.0}}
    },
    {
      "name": "支付页错误率",
      "role": "guardrail",
      "type": "proportion",
      "higher_is_better": false,
      "max_worsening_rel": 0.05,
      "data": {"旧版": {"successes": 120}, "新版": {"successes": 118}}
    }
  ],
  "guardrails_pending": ["客服投诉", "退款率"]
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `groups.<组名>.users` | 是 | 进入实验的单元数，用于 SRM 检验和默认样本量 |
| `metrics[].type` | 是 | `proportion`（给 `successes`）、`mean`（给 `mean`、`std`）或 `ratio`（给 `num_mean`、`den_mean`、`num_std`、`den_std`、`cov`） |
| `metrics[].data.<组名>.n` | 否 | 指标样本量与分组人数不同时填写（例如只统计下单用户的客单价） |
| `metrics[].role` | 否 | `primary`（默认）/ `secondary` / `guardrail` |
| `metrics[].higher_is_better` | 否 | 默认 `true`；退款率、错误率、耗时填 `false` |
| `metrics[].max_worsening_rel` | 否 | 护栏可接受的最大相对恶化，例如 `0.05`。填了才能“证明没有恶化”，否则只能说“没检测到恶化” |
| `control` | 否 | 对照组名，默认 `groups` 的第一个 |
| `allocation` | 否 | 预期分流比例，默认均分；90/10 实验必须填写，否则 SRM 会误报 |
| `days` / `planned_days` | 否 | 已运行天数 / 计划天数，用于周期和提前查看检查，以及估算还需要几天 |
| `guardrails_pending` | 否 | 已知但还没拿到数据的护栏，会阻止 `ship` 结论 |

多于两组（A/B/n）时，每个实验组都与对照组比较，主指标用 Holm 方法校正多重比较。

## 方式二：用户粒度 CSV（`--csv`）

每行一个实验单元（通常是用户）。示例：

```csv
user_id,variant,paid,gmv,pre_gmv,refund
u00001,A,1,128.5,96.2,0
u00002,B,0,0,45.1,0
```

```bash
python3 scripts/ab_test.py analyze --csv users.csv --variant-col variant --control A \
  --metric paid:proportion \
  --metric gmv:mean \
  --guardrail refund:proportion:lower \
  --cuped gmv=pre_gmv \
  --days 14 --planned-days 14 \
  --html ab_report.html
```

- 指标写法：`列名:proportion|mean[:higher|lower]`，比率指标写 `分子列/分母列:ratio[:higher|lower]`
- 比例指标的列支持 0/1、true/false、yes/no、Y/N、是/否、对/错
- 文件可以是 UTF-8 或 GBK，分隔符可以是逗号、制表符、分号或竖线
- 非均分实验必须加 `--allocation A=0.9,B=0.1`；没加且实际占比明显偏离均分时，结论是 `allocation_unknown`
- 空值的行在该指标上被跳过
- `--cuped 指标列=协变量列`：用实验前的同一指标做协变量，通常能把方差降低 30%–70%，相当于免费增加样本量。协变量必须是**实验开始前**的数据，否则会把实验效应一起减掉

## 实验前规划（`plan`）

```bash
# 比例指标：基线 7%，希望检测 5% 的相对提升
python3 scripts/ab_test.py plan --baseline 0.07 --mde-rel 0.05 --daily-users 6000

# 均值指标：基线 86.2，标准差 140，希望检测 3 元的绝对提升
python3 scripts/ab_test.py plan --metric-type mean --baseline 86.2 --std 140 --mde-abs 3 --daily-users 6000
```

输出每组样本量、总样本量，以及向上取整到整周的推荐天数。多组实验用 `--groups`，显著性和功效用 `--alpha`、`--power`。全部参数见 [命令行参数](cli.md)。

## 比率指标

按用户分流、指标是点击率或人均下单金额这类比率时，分子和分母都随用户波动。按曝光行直接算比例会低估方差，结果显得过于显著。

用户粒度 CSV 写成 `clicks/views:ratio`，脚本按 delta 方法估计方差。只有汇总数据时，用 SQL 算出每组的分子均值、分母均值、两者标准差和协方差，填进 JSON：

```json
{"name": "点击率", "type": "ratio", "data": {"A": {"num_mean": 1.2, "den_mean": 10.5, "num_std": 2.1, "den_std": 12.3, "cov": 18.4, "n": 50000}, "B": {"num_mean": 1.3, "den_mean": 10.4, "num_std": 2.2, "den_std": 12.1, "cov": 18.9, "n": 50100}}}
```
