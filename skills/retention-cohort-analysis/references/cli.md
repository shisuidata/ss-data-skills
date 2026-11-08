# 命令行参数

这份文档由脚本的参数定义生成，修改参数后请重新生成，不要手改。所有脚本都把结果以 JSON 打印到标准输出。

## `retention.py analyze`

计算留存矩阵并生成报告

| 参数 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- |
| `--summary` | 否 | — | 汇总数据 JSON（见 references/input-schema.md） |
| `--events` | 否 | — | 事件明细 CSV，每行一个事件 |
| `--user-col` | 否 | user_id | — |
| `--event-col` | 否 | event_name | — |
| `--time-col` | 否 | event_time | — |
| `--tz` | 否 | +08:00 | 业务时区，带时区的时间会换算到这里，默认 +08:00 |
| `--start-event` | 否 | — | 起点事件，多个用 \| 分隔；取每个用户最早一次 |
| `--start-col` | 否 | — | 改用用户表中的起点时间列（需要 --users） |
| `--return-event` | 否 | — | 回访事件，多个用 \| 分隔；不填则任意事件都算回访 |
| `--users` | 否 | — | 用户属性 CSV，按 --user-col 关联 |
| `--segment`（可重复） | 否 | — | 分群列；有 --users 时取用户属性，否则取起点事件所在行 |
| `--unit` | 否 | day | Cohort 和留存周期的粒度。可选：day、week、month |
| `--periods` | 否 | — | 要计算的周期，如 1,3,7,14,30 |
| `--mode` | 否 | on | on：第 N 期当期回访；within：第 1~N 期内有过回访。可选：on、within |
| `--boundary` | 否 | natural | 按日时：natural 自然日；rolling 滚动 24 小时。可选：natural、rolling |
| `--data-end` | 否 | — | 数据截止日（含），默认取事件最大时间所在日 |
| `--key-period` | 否 | — | 重点对比的周期，默认 7（或最接近的周期） |
| `--period`（可重复） | 否 | — | 批次分组：名称=开始..结束（按 Cohort 日期） |
| `--baseline` | 否 | — | 作为对比基准的批次分组名称 |
| `--name` | 否 | — | 报告标题 |
| `--html` | 否 | — | 输出 HTML 报告路径 |
| `--json` | 否 | — | 同时把 JSON 写入文件 |
