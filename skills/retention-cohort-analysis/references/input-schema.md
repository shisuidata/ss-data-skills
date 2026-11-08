# 输入格式

`scripts/retention.py analyze` 接受两种输入，二选一。

## 方式一：事件明细 CSV（`--events`，推荐）

每行一个事件：

```csv
user_id,event_name,event_time
u00001,register_success,2026-03-02 21:14:05
u00001,app_open,2026-03-03 08:02:11
```

| 参数 | 说明 |
| --- | --- |
| `--start-event` | 起点事件，取每个用户最早一次；多个用 `\|` 分隔 |
| `--start-col` | 改为从用户表取起点时间（例如 `register_time`），需要 `--users` |
| `--return-event` | 回访事件，多个用 `\|` 分隔。**不填则任意事件都算回访**，推送到达、后台唤醒会虚高留存 |
| `--users` / `--segment` | 用户属性表与分群列；没有 `--users` 时取起点事件那一行的列 |
| `--unit` | `day` / `week` / `month`：Cohort 分批与留存周期的粒度。周从周一开始 |
| `--periods` | 要计算的周期，如 `1,3,7,14,30`；默认日 1,3,7,14,30、周 1,2,3,4,6,8、月 1,2,3,6,12 |
| `--mode` | `on`（默认）：第 N 期当期有回访；`within`：第 1~N 期内有过回访（累计，只升不降） |
| `--boundary` | 按日时：`natural`（默认）自然日，注册当天 23:00、次日 08:00 打开算 D1；`rolling` 滚动 24 小时，需在注册后 24~48 小时内回访 |
| `--data-end` | 数据截止日（含）。默认取事件最大时间所在日，并假设这一天数据完整；当天数据还在落表时请指定为前一天 |
| `--key-period` | 重点对比的周期，默认 7 或最接近的周期 |
| `--period 名称=开始..结束` + `--baseline` | 把批次分成两组做对比，按 Cohort 日期划分 |

成熟度规则：一个单元格只有在批次内**所有**用户都已完整观察到该周期后才计算，否则留空。

## 方式二：汇总 JSON（`--summary`）

完整示例见 [`assets/example_summary.json`](../assets/example_summary.json)。

```json
{
  "name": "SaaS 企业客户订阅留存",
  "unit": "month",
  "mode": "on",
  "periods": [1, 3, 6],
  "data": [
    {"cohort": "2026-03", "size": 310, "retained": {"1": 284, "3": 253, "6": 225}},
    {"cohort": "2026-04", "segment": {"套餐": "starter"}, "size": 290, "retained": {"1": 255, "3": 218, "6": null}}
  ]
}
```

- `cohort`：日 / 周用 `YYYY-MM-DD`（周填周一），月用 `YYYY-MM`
- `retained` 的键是周期序号，值是留存人数；**尚未成熟的周期必须填 `null`，不能填 0**
- 每个批次可以给一行不带 `segment` 的整体数据；没有时，脚本用第一个分群维度的各行相加
- 汇总数据无法验证成熟度和时间边界，报告会提示人工确认
