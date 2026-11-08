# 输入格式

`scripts/funnel.py analyze` 接受两种输入，二选一。

## 方式一：事件明细 CSV（`--events`，推荐）

每行一个事件，至少包含用户、事件名、事件时间三列：

```csv
user_id,event_name,event_time,device_type
u001,register_success,2026-05-03 09:00:00,mobile
u001,product_view,2026-05-03 09:05:00,mobile
```

| 参数 | 说明 |
| --- | --- |
| `--user-col` / `--event-col` / `--time-col` | 列名，默认 `user_id` / `event_name` / `event_time` |
| `--step 名称=事件` | 按漏斗顺序重复填写；一个步骤对应多个事件时用 `\|` 分隔，例如 `--step 浏览=product_view\|search_click` |
| `--period 名称=开始..结束` | 按**入口事件时间**划分时期，日期含首尾；不填则所有用户算一个时期 |
| `--baseline 名称` | 作为对比基准的时期 |
| `--window-days N` | 转化窗口：入口后 N 天内完成才算；观察期还不满 N 天的用户会被排除并在检查里报告 |
| `--users users.csv` | 用户属性表，按 `--user-col` 关联，用于分群 |
| `--segment 列名` | 分群维度，可重复；有 `--users` 时取用户属性，否则取入口事件那一行的值 |

时间支持 `YYYY-MM-DD HH:MM:SS`、`YYYY-MM-DDTHH:MM:SS`、`YYYY/MM/DD` 等常见格式。

脚本按严格有序漏斗计算：第 k 步必须发生在第 k−1 步之后（且在窗口内）。同时检查：

- 有后续步骤但没有入口事件的用户
- 跳过某一步直接到下一步的用户（埋点缺失或存在绕行路径）
- 时间顺序颠倒的用户（客户端时间不准、补报）
- 多次入口事件（按最早一次计算）
- 观察期不足：未设窗口时，对比各时期观察期长度与全漏斗转化耗时 P90

纯 Python 实现，适合几十万到几百万行事件。更大的数据先用 [漏斗 SQL 模板](funnel-sql.md) 在仓库里汇总。

## 方式二：汇总 JSON（`--summary`）

已经算好每一步人数时使用。完整示例见 [`assets/example_summary.json`](../assets/example_summary.json)。

```json
{
  "name": "SaaS 试用到付费漏斗",
  "steps": ["注册试用", "完成 onboarding", "邀请团队成员", "创建核心工作流", "升级付费"],
  "baseline": "3 月",
  "data": [
    {"period": "3 月", "counts": [4200, 1890, 1020, 760, 290]},
    {"period": "4 月", "counts": [5100, 2091, 1004, 742, 281]},
    {"period": "4 月", "segment": {"注册渠道": "信息流广告"}, "counts": [2200, 739, 296, 202, 63]}
  ]
}
```

- 每个时期必须有一行不带 `segment` 的整体数据
- 分群行的 `segment` 只写一个维度；多个维度分别写多行
- `counts` 必须是**有序漏斗**人数：只有完成上一步的用户才计入下一步。如果后一步人数多于前一步，脚本会判定口径错误
- 汇总数据无法检查顺序、窗口和观察期，报告中会提示人工确认
