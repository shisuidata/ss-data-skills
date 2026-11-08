#!/usr/bin/env python3
"""用 sskit_viz 的全部组件生成一份示例经营周报，既是上手示例，也是冒烟测试。

用法：python3 demo_report.py [输出路径]，默认写到当前目录的 sskit_demo.html
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_viz as viz  # noqa: E402

days = [f"5/{d}" for d in range(12, 26)]
gmv_this = [182e4, 175e4, 168e4, 171e4, 190e4, 236e4, 241e4, 176e4, 169e4, 158e4, 160e4, 172e4, 214e4, 220e4]
gmv_last = [170e4, 168e4, 165e4, 166e4, 181e4, 225e4, 230e4, 171e4, 167e4, 163e4, 166e4, 178e4, 222e4, 229e4]
channels = ["自然流量", "信息流投放", "达人带货", "私域社群", "搜索广告"]
channel_gmv = [812e4, 655e4, 402e4, 318e4, 236e4]

blocks = [
    viz.callout("warning", "第二周 GMV 同比转负：工作日下滑，周末持平",
                "5/19 起工作日 GMV 连续 4 天低于去年同期，主要来自信息流投放；周末大促表现基本持平。"),
    viz.section("核心指标", viz.stat_tiles([
        {"label": "近 7 日 GMV", "value": viz.fmt_num(sum(gmv_this[7:])), "delta": "▼ −2.6% 同比", "tone": "bad", "note": "去年同期 1,296万"},
        {"label": "支付用户数", "value": viz.fmt_num(38214), "delta": "▲ +1.8% 同比", "tone": "good"},
        {"label": "客单价", "value": "¥" + viz.fmt_num(330.6, 1), "delta": "▼ −4.3% 同比", "tone": "bad"},
        {"label": "退款率", "value": viz.fmt_pct(0.031, 1), "delta": "– 持平", "tone": "neutral", "note": "护栏指标，越低越好"},
    ])),
    viz.section(
        "每日 GMV：今年 vs 去年同期",
        viz.line_chart(days, [{"name": "今年", "values": gmv_this}, {"name": "去年同期", "values": gmv_last, "color": "var(--neutral)"}],
                       fmt=lambda v: viz.fmt_num(v, 0), y_zero=False, caption="去年同期按星期对齐（同比按周对齐，而不是按日期对齐）。"),
        lead="周末峰值正常，问题集中在工作日。",
    ),
    viz.section("渠道 GMV（近 14 日）", viz.bar_chart(channels, channel_gmv, fmt=lambda v: viz.fmt_num(v, 0))),
    viz.section("各渠道同比变化（含 95% 区间）", viz.interval_chart([
        {"label": "信息流投放", "sub": "付费渠道", "estimate": -0.112, "low": -0.168, "high": -0.054, "tone": "bad"},
        {"label": "达人带货", "sub": "付费渠道", "estimate": 0.064, "low": 0.012, "high": 0.118, "tone": "good"},
        {"label": "自然流量", "estimate": -0.008, "low": -0.041, "high": 0.026, "tone": "neutral"},
        {"label": "私域社群", "estimate": 0.021, "low": -0.030, "high": 0.074, "tone": "neutral"},
    ])),
    viz.section("数据可信度", viz.checklist([
        {"status": "pass", "title": "订单表 5/25 分区已完成，行数与上周同日差异 < 3%"},
        {"status": "warn", "title": "信息流投放 5/21 起 UTM 参数变更", "detail": "部分订单可能被归入自然流量，渠道拆分需谨慎"},
        {"status": "fail", "title": "搜索广告缺少 5/24 花费数据", "detail": "ROI 暂不可算"},
    ])),
    viz.section("明细", viz.table(
        ["渠道", "GMV", "占比", "同比"],
        [[c, viz.fmt_num(g, 1), viz.fmt_pct(g / sum(channel_gmv), 1), d]
         for c, g, d in zip(channels, channel_gmv, ["−0.8%", "−11.2%", "+6.4%", "+2.1%", "—"])],
        numeric=(1, 2, 3),
    )),
]

out = sys.argv[1] if len(sys.argv) > 1 else "sskit_demo.html"
viz.save(out, viz.html_report("5 月第 4 周经营周报", blocks, subtitle="电商主站 · 数据截至 2026-05-25"))
print(os.path.abspath(out))
