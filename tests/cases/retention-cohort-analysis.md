# 测试用例：留存 Cohort 分析

## Skill

`retention-cohort-analysis`

## 测试目标

检查 Skill 是否能定义 Cohort、留存行为和时间窗口，并识别样本限制。

## 测试输入

```text
请使用 retention-cohort-analysis 设计并解读下面的新用户留存分析。

业务背景：
某电商平台想判断渠道 A 带来的新用户是否只是首日访问，后续是否还会回来。

Cohort 起点：
注册日期。

留存行为：
用户在注册后第 N 天发生任意一次 product_view 或 app_open 事件。

统计对象：
user_id。

时间窗口：
D1、D3、D7。

mock 汇总数据：

| Cohort | channel_id | register_users | D1_retained | D3_retained | D7_retained |
| --- | --- | --- | --- | --- | --- |
| 2026-04-20 | organic | 20 | 10 | 7 | 5 |
| 2026-04-20 | channel_a | 20 | 8 | 4 | 2 |
| 2026-05-03 | organic | 20 | 9 | 6 | 4 |
| 2026-05-03 | channel_a | 40 | 12 | 5 | 2 |

希望输出：
请给出 Cohort 定义、留存矩阵、关键发现、可能原因、口径风险和下一步建议。
```

## 通过标准

- 必须明确 Cohort 起点和留存行为。
- 必须指出 channel_a 的 D7 留存偏低。
- 必须区分渠道质量假设和已验证事实。
- 必须提出自然日 / 滚动窗口、app_open 埋点、样本量等口径风险。
- 不得把 mock 小样本写成确定业务结论。

