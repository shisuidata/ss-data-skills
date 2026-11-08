#!/usr/bin/env python3
"""看板审查工具：按结构化描述打分、列问题，并把改版方案渲染成自包含 HTML 原型（仅依赖 Python 标准库）。

  python3 dashboard_kit.py review --spec dashboard.json --html prototype.html

脚本只检查能从结构判断的问题。业务上该不该看这些指标，由 Agent 结合上下文判断。
原型中的数字全部来自 spec，缺数据的图显示“暂无数据”，不会生成任何假数字。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_viz as viz  # noqa: E402
import sskit_io as sio  # noqa: E402

LEVELS = ("primary", "process", "explain", "guardrail")
BAD_CHARTS = {"dual_axis": "双 Y 轴会制造虚假相关，拆成两张图或做指数化", "pie_3d": "3D 饼图会扭曲比例", "gauge": "仪表盘占用大、信息少，用指标卡加目标值替代"}
MAX_PRIMARY, MAX_PIE_SLICES, MAX_MODULES = 5, 5, 12
SEVERITY = {"P0": 0, "P1": 1, "P2": 2}


def review(spec: dict) -> dict:
    modules = spec.get("modules") or []
    if not modules:
        raise SystemExit("spec 缺少 modules（看板模块列表）")
    findings: list[dict] = []

    def add(severity: str, where: str, problem: str, impact: str, fix: str) -> None:
        findings.append({"severity": severity, "where": where, "problem": problem, "impact": impact, "fix": fix})

    scores = {}
    # 决策服务
    score = 2
    if not spec.get("audience"):
        score -= 1
        add("P0", "整体", "没有写明目标受众", "无法判断指标和粒度是否合适", "写清谁在什么场景下看这个看板")
    if not spec.get("decisions"):
        score -= 1
        add("P0", "整体", "没有写明看板要支持的决策", "容易退化成指标陈列", "列出看完后要做的 1 到 3 个决策")
    no_question = [m["name"] for m in modules if not m.get("question")]
    if no_question:
        score = max(score - (1 if len(no_question) < len(modules) else 2), 0)
        add("P1", "、".join(no_question[:6]), f"{len(no_question)} 个模块没有说明回答什么问题", "只有展示价值，读者不知道该看什么", "为每个模块写一句业务问题，答不出来就删除")
    scores["决策服务"] = score

    # 指标层级
    by_level = {level: [m["name"] for m in modules if m.get("level") == level] for level in LEVELS}
    score = 2
    if not by_level["primary"]:
        score -= 1
        add("P0", "整体", "没有主指标", "读者不知道先看哪个数", "选定 1 到 3 个主指标放在首屏")
    elif sum(len(m.get("metrics") or [m]) for m in modules if m.get("level") == "primary") > MAX_PRIMARY:
        score -= 1
        add("P1", "主指标", "主指标超过 5 个", "重点被稀释", "收敛到 3 个以内，其余降级为过程指标")
    if not by_level["explain"] and not by_level["process"]:
        score -= 1
        add("P1", "整体", "只有结果指标，没有过程或解释指标", "发现下降后无法定位原因", "补充能拆解主指标的过程指标")
    if not by_level["guardrail"]:
        add("P2", "整体", "没有护栏指标", "容易为了主指标牺牲体验或利润", "补充退款、投诉、毛利等护栏")
    if len(modules) > MAX_MODULES:
        score = max(score - 1, 0)
        add("P2", "整体", f"模块过多（{len(modules)} 个）", "加载慢，读者抓不住主线", "拆成总览页和专题页")
    scores["指标层级"] = max(score, 0)

    # 图表匹配
    score = 2
    for m in modules:
        chart = (m.get("chart") or "").lower()
        if chart in BAD_CHARTS:
            score = max(score - 1, 0)
            add("P1", m["name"], f"使用了 {chart}", BAD_CHARTS[chart], "改用条形图、折线图或指标卡")
        if chart == "pie" and (m.get("categories") or 0) > MAX_PIE_SLICES:
            score = max(score - 1, 0)
            add("P1", m["name"], f"饼图有 {m['categories']} 个分类", "小扇区无法比较", "改用排序条形图，把长尾合并为“其他”")
        if chart == "table" and m.get("level") == "primary":
            add("P2", m["name"], "主指标用表格展示", "读者需要自己找重点", "改用指标卡加趋势")
    if any(not m.get("chart") for m in modules):
        score = max(score - 1, 0)
        add("P2", "部分模块", "没有写图表类型", "无法审查图表是否匹配问题", "补充每个模块的图表形式")
    scores["图表匹配"] = score

    # 定位与行动
    has_dims = any(m.get("dimensions") for m in modules) or bool(spec.get("filters"))
    no_drill = [m["name"] for m in modules if m.get("level") in ("primary", "process") and not m.get("drilldown") and not m.get("dimensions")]
    no_action = [m["name"] for m in modules if m.get("level") == "primary" and not m.get("action")]
    score = 2
    if not has_dims:
        score -= 2
        add("P0", "整体", "没有维度或筛选", "发现异常后无法定位问题", "加入渠道、地区、人群等能定位问题的维度")
    elif no_drill:
        score -= 1
        add("P1", "、".join(no_drill[:6]), "主要指标没有下钻路径", "看得到结果，定位不了原因", "明确从这个指标下钻到哪个维度或明细")
    if no_action:
        score = max(score - 1, 0)
        add("P1", "、".join(no_action[:6]), "主指标没有对应动作", "看完不知道该做什么", "写明指标异常时谁来做什么")
    scores["定位与行动"] = max(score, 0)

    # 数据可信
    metrics = [x for m in modules for x in (m.get("metrics") or []) if isinstance(x, dict)]
    no_definition = [x.get("name") for x in metrics if not x.get("definition")]
    score = 2
    if not metrics or len(no_definition) > len(metrics) / 2:
        score -= 1
        add("P1", "指标说明", "多数指标没有口径说明", "不同读者理解不一致，容易指标打架", "为每个指标写分子、分母、时间窗口和过滤条件")
    elif no_definition:
        add("P2", "指标说明", f"{len(no_definition)} 个指标没有口径说明", "存在理解偏差", "补齐口径说明")
    if not spec.get("refresh"):
        score -= 1
        add("P1", "整体", "没有写明刷新频率和数据延迟", "读者可能拿未产出的数据做判断", "在看板上显示数据更新时间")
    if not spec.get("owner"):
        add("P2", "整体", "没有写明负责人", "问题没人跟进", "写明看板负责人和反馈渠道")
    scores["数据可信"] = max(score, 0)

    total = sum(scores.values())
    findings.sort(key=lambda f: SEVERITY[f["severity"]])
    p0 = sum(1 for f in findings if f["severity"] == "P0")
    if p0 or total < 5:
        verdict = {"level": "bad", "code": "rework", "title": f"{total}/10 分：不能支持决策，需要重新梳理目标和指标"}
    elif total < 8:
        verdict = {"level": "warning", "code": "revise", "title": f"{total}/10 分：结构可用，按问题清单修改后上线"}
    else:
        verdict = {"level": "good", "code": "ok", "title": f"{total}/10 分：结构基本合格；业务判断仍需人工审查"}
    return {"name": spec.get("name", "看板"), "score": total, "max_score": 10, "scores": scores, "summary": {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITY},
            "findings": findings, "verdict": verdict, "limits": ["只检查结构，判断不了业务上该不该看这些指标"]}


def _chart(row: dict) -> str:
    kind = (row.get("chart") or "").lower()
    title, note = row.get("title"), row.get("question")
    categories, values = row.get("categories") or [], row.get("values") or []
    fmt = {"pct": (lambda v: viz.fmt_pct(v, 1)), "num": viz.fmt_num}.get(row.get("fmt"), viz.fmt_num)
    if kind == "line":
        return viz.line_chart(categories, row.get("series") or [{"name": title or "指标", "values": values}], title=title, caption=note, fmt=fmt)
    if kind == "paired_bar":
        return viz.paired_bar_chart(categories, row.get("current") or [], row.get("baseline") or [], title=title, caption=note, fmt=fmt)
    if kind == "diverging":
        return viz.diverging_bar_chart(categories, values, title=title, caption=note)
    if kind == "table":
        return viz.section(title or "明细", viz.table(row.get("headers") or [], row.get("rows") or []), lead=note)
    return viz.bar_chart(categories, values, title=title, caption=note, fmt=fmt)


def render(spec: dict, result: dict) -> str:
    plan = spec.get("redesign") or {}
    blocks = [viz.callout("warning", "这是改版原型，不是线上看板", "图中的数字来自审查输入，用于确认结构和读图路径。缺数据的图显示“暂无数据”。")]
    if plan.get("headline"):
        blocks.append(viz.callout("neutral", plan["headline"]))
    if plan.get("kpis"):
        blocks.append(viz.section("首屏：主指标", viz.stat_tiles(plan["kpis"])))
    for group in plan.get("sections") or []:
        blocks.append(viz.section(group.get("title", ""), *[_chart(row) for row in group.get("rows") or []], lead=group.get("lead")))
    rows = [[f["severity"], f["where"], f["problem"], f["fix"]] for f in result["findings"]]
    blocks.append(viz.section(f"审查结果：{result['score']}/10", viz.table(["维度", "得分"], [[k, f"{v}/2"] for k, v in result["scores"].items()], numeric=(1,)),
                              viz.table(["级别", "位置", "问题", "建议"], rows) if rows else viz.paragraph("没有发现结构问题。")))
    return viz.html_report(plan.get("title") or f"{result['name']} · 改版原型", blocks, subtitle=spec.get("audience"), brand="拾穗数据 · 看板审查")


def cmd_review(args: argparse.Namespace) -> int:
    with open(args.spec, encoding=sio.detect_encoding(args.spec)) as handle:
        spec = json.load(handle)
    result = review(spec)
    if args.html:
        viz.save(args.html, render(spec, result))
        result["html_prototype"] = os.path.abspath(args.html)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="看板审查工具（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("review", help="结构审查并生成改版原型")
    r.add_argument("--spec", required=True, help="看板描述 JSON，见 references/spec-format.md")
    r.add_argument("--html", help="输出改版原型 HTML")
    r.add_argument("--json", help="同时把 JSON 写入文件")
    r.set_defaults(func=cmd_review)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(sio.run_cli(main))
