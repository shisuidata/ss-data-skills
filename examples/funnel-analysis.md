# funnel-analysis 示例

## 适用场景

转化率变了，需要知道变化来自哪一步、是“来了不一样的用户”还是“同样的用户转化变差”，以及这个变化是不是真的。

## 示例输入

```text
请用 funnel-analysis 分析新用户首购漏斗，并生成 HTML 报告：

数据：dwd_user_event_d.csv（user_id, event_name, event_time），dwd_user_register_d.csv（user_id, channel_id, device_type）
步骤：注册成功 register_success -> 浏览商品 product_view -> 加购 add_to_cart -> 提交订单 order_submit -> 支付成功 pay_success
本期：2026-05-01 到 2026-05-14；对比期：2026-04-17 到 2026-04-30
分群：渠道、设备
```

## 预期输出

Agent 运行：

```bash
python3 skills/funnel-analysis/scripts/funnel.py analyze --events dwd_user_event_d.csv \
  --step 注册成功=register_success --step 浏览商品=product_view --step 加购=add_to_cart \
  --step 提交订单=order_submit --step 支付成功=pay_success \
  --users dwd_user_register_d.csv --segment channel_id --segment device_type \
  --period 本期=2026-05-01..2026-05-14 --period 上期=2026-04-17..2026-04-30 --baseline 上期 \
  --html funnel_report.html
```

然后基于脚本结果输出：

```markdown
## 漏斗分析结果

### 1. 结论

首购转化 33.3% → 16.7%（−16.7pp），方向上值得关注，但每期只有 12 个入口用户，变化未达显著（p=0.35），且本期观察期远短于对比期，目前只能作为预警。

### 3. 漏斗表现

| 步骤 | 本期人数 | 单步转化 | 累计转化 | 对比期单步转化 |
| --- | --- | --- | --- | --- |
| 注册成功 | 12 | — | 100.0% | — |
| 浏览商品 | 9 | 75.0% | 75.0% | 83.3% |
| 加购 | 5 | 55.6% | 41.7% | 70.0% |
| 提交订单 | 3 | 60.0% | 25.0% | 71.4% |
| 支付成功 | 2 | 66.7% | 16.7% | 80.0% |

### 4. 变化来自哪一步

“浏览商品 → 加购”贡献了整体下降的 33%，是最大来源；这一步恢复到对比期水平，整体转化可回到 21.0%。

### 5. 变化来自哪类用户

- 渠道：结构效应 −13.9pp，转化效应 −2.8pp。channel_a 占比从 25% 升到 58%，下降主要是**获客结构**变了，而不是各渠道自身变差。
- 设备：结构效应 −1.9pp，转化效应 −14.8pp。mobile 自身转化 28.6% → 0.0%，移动端体验值得排查。

### 6. 数据质量与口径

- 样本量：每期 12 人，结论只能作为方向参考
- 右截断：本期观察期中位数 1.6 天，对比期 14.6 天；建议统一 7 天转化窗口后复核
- 未发现跳步、乱序或缺失入口

### 7. 可能原因与验证动作

| 假设 | 支持证据 | 如何验证 |
| --- | --- | --- |
| channel_a 投放带来低意向用户 | 渠道结构效应占主导 | 拉 channel_a 各素材 / 计划的首购率，和投放团队核对 5 月起的定向变化 |
| 移动端商品页到加购有体验问题 | mobile 自身转化下降，浏览→加购贡献最大 | 查移动端 5 月发版记录、加购按钮点击与报错日志 |

报告文件：funnel_report.html
```

## 使用说明

- 先看质量检查，再看拆解结果。口径或观察期有问题时，拆解出来的数字也不可信。
- 结构效应大，找增长和投放；转化效应大，找产品和研发。
- 数据量很大时用 `references/funnel-sql.md` 在仓库里汇总，再用 `--summary` 输入。
- 文件可以是 GBK。带时区的时间会按业务时区换算，默认 +08:00，可用 `--tz` 修改。
