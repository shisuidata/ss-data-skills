#!/usr/bin/env python3
"""业务指标归因计算器：异常是否真实、指标因子拆解、维度贡献排序（仅依赖 Python 标准库）。

  python3 decompose.py confirm --csv daily.csv --date-col dt --value-col gmv --start 2026-05-13 --end 2026-05-19
  python3 decompose.py factors --factor 流量=120000,131000 --factor 转化率=0.042,0.031 --factor 客单价=180,176 --target GMV
  python3 decompose.py dimensions --csv segments.csv --period-col period --base 上期 --current 本期 \\
      --dim channel --dim device --numerator paid --denominator uv

脚本只回答“变化集中在哪里”，不回答“为什么”。原因要靠假设树和进一步验证。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from statistics import NormalDist, median

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_viz as viz  # noqa: E402
import sskit_io as sio  # noqa: E402

N = NormalDist()
TIME = sio.TimeParser()
MIN_HISTORY = 4


def _emit(result: dict, args: argparse.Namespace, html: str | None = None) -> int:
    if html and args.html:
        viz.save(args.html, html)
        result["html_report"] = os.path.abspath(args.html)
    text = json.dumps(_round(result), ensure_ascii=False, indent=2)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0


def _round(obj):
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# confirm：异常是否真实
# ---------------------------------------------------------------------------

def cmd_confirm(args: argparse.Namespace) -> int:
    series: dict[date, float] = {}
    rows = sio.read_csv(args.csv)
    if not rows or args.date_col not in rows[0] or args.value_col not in rows[0]:
        raise SystemExit(f"CSV 为空或缺少列：{args.date_col}、{args.value_col}")
    for row in rows:
        moment, value = TIME(row[args.date_col]), sio.parse_number(row[args.value_col], args.value_col)
        if moment is not None and value is not None:
            series[moment.date()] = series.get(moment.date(), 0.0) + value
    start, end = TIME(args.start).date(), TIME(args.end).date()
    if end < start:
        raise SystemExit("--end 不能早于 --start")
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    missing = [d.isoformat() for d in days if d not in series]
    present = [series[d] for d in days if d in series]
    if not present:
        raise SystemExit("异常窗口内没有数据")
    current = sum(present) / len(present)

    # 用历史上同星期的同长度窗口做基准，避开周内效应
    history = []
    shift = max(1, math.ceil(len(days) / 7)) * 7
    for k in range(1, args.history_windows + 1):
        window = [d - timedelta(days=shift * k) for d in days]
        if all(d in series for d in window):
            history.append({"start": window[0].isoformat(), "value": sum(series[d] for d in window) / len(window)})
    if not history:
        raise SystemExit("历史数据不足：没有任何完整的同星期历史窗口")
    values = [h["value"] for h in history]
    med = median(values)
    mad = median([abs(v - med) for v in values])
    scale = mad or (abs(med) * 0.01) or 1.0
    robust_z = 0.6745 * (current - med) / scale
    outside = current < min(values) or current > max(values)
    change = (current - med) / med if med else None

    checks = []
    if len(history) < MIN_HISTORY:
        checks.append({"id": "history", "status": "warn", "title": f"只有 {len(history)} 个历史窗口，判断不稳定"})
    if missing:
        checks.append({"id": "missing_days", "status": "fail", "title": f"异常窗口缺 {len(missing)} 天数据：{'、'.join(missing[:5])}",
                       "detail": "先确认是否数据延迟或任务失败，再讨论业务原因"})
    if end >= max(series):
        checks.append({"id": "latest", "status": "warn", "title": "异常窗口包含数据的最后一天",
                       "detail": "最后一天的分区可能还没产出完整，确认后再下结论"})
    if abs(robust_z) >= 3 and outside:
        result = {"level": "bad", "code": "real", "title": f"异常成立：窗口均值偏离历史中位数 {viz.fmt_signed_pct(change, 1)}，超出历史波动范围"}
    elif abs(robust_z) >= 2 or outside:
        result = {"level": "warning", "code": "borderline", "title": f"疑似异常：偏离 {viz.fmt_signed_pct(change, 1)}，处在历史波动边缘"}
    else:
        result = {"level": "good", "code": "normal", "title": f"属于正常波动：偏离 {viz.fmt_signed_pct(change, 1)}，在历史范围内"}
    if any(c["status"] == "fail" for c in checks):
        result = {"level": "bad", "code": "data_issue", "title": "数据不完整，先排查数据问题，不要进入业务归因"}
    return _emit({"window": {"start": start.isoformat(), "end": end.isoformat(), "days": len(days), "mean": current},
                  "baseline": {"median": med, "min": min(values), "max": max(values), "windows": history},
                  "change_vs_median": change, "robust_z": robust_z, "outside_history": outside, "checks": checks, "verdict": result}, args)


# ---------------------------------------------------------------------------
# factors：LMDI 因子拆解
# ---------------------------------------------------------------------------

def _log_mean(a: float, b: float) -> float:
    return a if a == b else (a - b) / (math.log(a) - math.log(b))


def cmd_factors(args: argparse.Namespace) -> int:
    factors = []
    for spec in args.factor:
        name, _, values = spec.partition("=")
        parts = values.split(",")
        if len(parts) != 2:
            raise SystemExit(f"--factor 格式应为 名称=基期,当期，收到：{spec}")
        base, current = float(parts[0]), float(parts[1])
        if base <= 0 or current <= 0:
            raise SystemExit(f"LMDI 拆解要求因子为正数：{spec}")
        factors.append({"name": name, "base": base, "current": current})
    if len(factors) < 2:
        raise SystemExit("至少需要两个 --factor")
    v0, v1 = math.prod(f["base"] for f in factors), math.prod(f["current"] for f in factors)
    weight = _log_mean(v1, v0)
    total = v1 - v0
    for f in factors:
        f["change"] = f["current"] / f["base"] - 1
        f["contribution"] = weight * math.log(f["current"] / f["base"])
        f["share_of_change"] = f["contribution"] / total if total else None
        f["counterfactual_target"] = v1 * f["base"] / f["current"]
    factors.sort(key=lambda f: -abs(f["contribution"]))
    top = factors[0]
    result = {"target": args.target, "base": v0, "current": v1, "change": total, "change_rel": total / v0, "factors": factors,
              "check_sum": sum(f["contribution"] for f in factors) - total,
              "verdict": {"level": "info", "title": f"{args.target} 变化 {viz.fmt_signed_pct(total / v0, 1)}，最大贡献来自 {top['name']}（{viz.fmt_signed_pct(top['change'], 1)}）"},
              "method": "LMDI 对数平均分解，各因子贡献相加严格等于总变化，且与因子排列顺序无关"}
    return _emit(result, args)


# ---------------------------------------------------------------------------
# dimensions：维度贡献排序
# ---------------------------------------------------------------------------

def _js_divergence(p: float, q: float) -> float:
    def term(a: float, b: float) -> float:
        return 0.0 if a <= 0 or b <= 0 else a * math.log(a / b)
    m = (p + q) / 2
    return 0.5 * term(p, m) + 0.5 * term(q, m)


def _additive(rows: dict, total0: float, total1: float) -> list[dict]:
    diff = total1 - total0
    out = []
    for value, (a, b) in rows.items():
        out.append({"value": value, "base": a, "current": b, "change": b - a, "share_of_change": (b - a) / diff if diff else None,
                    "surprise": _js_divergence(a / total0 if total0 else 0, b / total1 if total1 else 0)})
    return sorted(out, key=lambda r: -abs(r["change"]))


def _rate(rows: dict, totals: tuple[float, float, float, float]) -> dict:
    n0, s0, n1, s1 = totals
    r0, r1 = s0 / n0, s1 / n1
    detail, mix, effect = [], 0.0, 0.0
    for value, (d0, x0, d1, x1) in rows.items():
        share0, share1 = d0 / n0, d1 / n1
        rate0, rate1 = (x0 / d0 if d0 else r0), (x1 / d1 if d1 else r1)
        m = (share1 - share0) * (rate0 - r0)
        e = share1 * (rate1 - rate0)
        mix += m
        effect += e
        detail.append({"value": value, "base_share": share0, "current_share": share1, "base_rate": rate0 if d0 else None, "current_rate": rate1 if d1 else None,
                       "mix_effect": m, "rate_effect": e, "total_effect": m + e, "share_of_change": (m + e) / (r1 - r0) if r1 != r0 else None,
                       "base_denominator": d0, "current_denominator": d1})
    detail.sort(key=lambda r: -abs(r["total_effect"]))
    return {"rows": detail, "mix_effect": mix, "rate_effect": effect}


def _concentration(shares: list[float | None]) -> float:
    return max((abs(s) for s in shares if s is not None), default=0.0)


def cmd_dimensions(args: argparse.Namespace) -> int:
    additive = args.metric is not None
    if additive == bool(args.numerator or args.denominator) or (not additive and not (args.numerator and args.denominator)):
        raise SystemExit("--metric（可加指标）与 --numerator + --denominator（比率指标）二选一")
    rows = sio.read_csv(args.csv)
    if not rows:
        raise SystemExit("CSV 为空")
    needed = [args.period_col] + args.dim + ([args.metric] if additive else [args.numerator, args.denominator])
    absent = [c for c in needed if c not in rows[0]]
    if absent:
        raise SystemExit(f"CSV 缺少列：{'、'.join(absent)}（现有列：{list(rows[0])}）")
    periods = {r[args.period_col] for r in rows}
    for p in (args.base, args.current):
        if p not in periods:
            raise SystemExit(f"时期 {p} 不在 {args.period_col} 列中：{sorted(periods)}")

    def measure(row: dict) -> tuple[float, float]:
        if additive:
            return sio.parse_number(row[args.metric], args.metric) or 0.0, 0.0
        return sio.parse_number(row[args.denominator], args.denominator) or 0.0, sio.parse_number(row[args.numerator], args.numerator) or 0.0

    per_dim, totals_by_dim = {}, {}
    for dim in args.dim:
        grouped = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
        for row in rows:
            if row[args.period_col] not in (args.base, args.current):
                continue
            a, b = measure(row)
            slot = grouped[row[dim] or "未知"]
            offset = 0 if row[args.period_col] == args.base else 2
            slot[offset] += a
            slot[offset + 1] += b
        per_dim[dim] = grouped
        totals_by_dim[dim] = tuple(sum(v[i] for v in grouped.values()) for i in range(4))

    checks, first = [], totals_by_dim[args.dim[0]]
    for dim, totals in totals_by_dim.items():
        if any(abs(a - b) > 1e-6 * max(abs(a), 1) for a, b in zip(totals, first)):
            checks.append({"id": "totals", "status": "fail", "title": f"维度 {dim} 的合计与 {args.dim[0]} 不一致",
                           "detail": "同一批数据按不同维度汇总应该相等。不一致通常是每行只含部分维度的明细被重复计算，请改用同一粒度的数据"})
    dims, overall = {}, None
    n0, s0, n1, s1 = first
    if additive:
        total0, total1 = first[0], first[2]
        if not total0:
            raise SystemExit("基期合计为 0，无法拆解")
        overall = {"type": "additive", "base": total0, "current": total1, "change": total1 - total0, "change_rel": (total1 - total0) / total0}
        for dim, grouped in per_dim.items():
            items = _additive({k: (v[0], v[2]) for k, v in grouped.items()}, total0, total1)
            dims[dim] = {"rows": items, "concentration": _concentration([r["share_of_change"] for r in items])}
    else:
        if n0 <= 0 or n1 <= 0:
            raise SystemExit("基期或当期分母合计为 0")
        r0, r1 = s0 / n0, s1 / n1
        pooled = (s0 + s1) / (n0 + n1)
        se = math.sqrt(pooled * (1 - pooled) * (1 / n0 + 1 / n1)) if 0 < pooled < 1 else 0
        p_value = 2 * (1 - N.cdf(abs((r1 - r0) / se))) if se else None
        overall = {"type": "rate", "base": r0, "current": r1, "change": r1 - r0, "change_rel": (r1 - r0) / r0 if r0 else None, "p_value": p_value,
                   "base_denominator": n0, "current_denominator": n1}
        for dim, grouped in per_dim.items():
            detail = _rate(dict(grouped), first)
            detail["concentration"] = _concentration([r["share_of_change"] for r in detail["rows"]])
            detail["structure_share"] = detail["mix_effect"] / (r1 - r0) if r1 != r0 else None
            dims[dim] = detail
            small = [r["value"] for r in detail["rows"] if min(r["base_denominator"], r["current_denominator"]) < 30]
            if small:
                checks.append({"id": "small_segment", "status": "warn", "title": f"维度 {dim} 有 {len(small)} 个取值样本不足 30",
                               "detail": "这些取值的转化率波动很大，贡献排序仅供参考"})

    ranking = sorted(dims, key=lambda d: -dims[d]["concentration"])
    top_dim = ranking[0]
    top = dims[top_dim]["rows"][0]
    if any(c["status"] == "fail" for c in checks):
        result = {"level": "bad", "title": "数据口径不一致，贡献拆解不可信"}
    elif additive:
        result = {"level": "info", "title": f"变化最集中的维度是 {top_dim}，其中 {top['value']} 贡献了 {viz.fmt_pct(abs(top['share_of_change'] or 0), 0)}"}
    else:
        text = "用户结构变化" if abs(dims[top_dim]["mix_effect"]) > abs(dims[top_dim]["rate_effect"]) else "各分群自身转化变化"
        result = {"level": "info", "title": f"按 {top_dim} 看，变化主要来自{text}；贡献最大的是 {top['value']}（{viz.fmt_pct(abs(top['share_of_change'] or 0), 0)}）"}
    if not additive and overall.get("p_value") is not None and overall["p_value"] >= 0.05:
        checks.append({"id": "significance", "status": "warn", "title": f"整体变化不显著（p={overall['p_value']:.3f}）", "detail": "变化可能只是正常波动，拆解结果不要过度解读"})
    output = {"overall": overall, "dimensions": dims, "ranking": ranking, "checks": checks, "verdict": result,
              "limits": ["这里只说明变化集中在哪里，不等于原因", "多个维度同时高度集中时，可能是同一批用户被不同维度重复解释"]}
    return _emit(output, args, _dimensions_html(output, args) if args.html else None)


def _dimensions_html(result: dict, args: argparse.Namespace) -> str:
    overall = result["overall"]
    fmt = (lambda v: viz.fmt_pct(v, 2)) if overall["type"] == "rate" else viz.fmt_num
    blocks = [viz.callout(result["verdict"]["level"] if result["verdict"]["level"] != "info" else "neutral", result["verdict"]["title"]),
              viz.section("整体变化", viz.stat_tiles([
                  {"label": args.base, "value": fmt(overall["base"])},
                  {"label": args.current, "value": fmt(overall["current"]), "delta": viz.fmt_signed_pct(overall["change_rel"], 1)}]))]
    for dim in result["ranking"]:
        detail = result["dimensions"][dim]
        rows = detail["rows"][:10]
        key = "total_effect" if overall["type"] == "rate" else "change"
        chart_fmt = (lambda v: viz.fmt_pp(v, 2)) if overall["type"] == "rate" else viz.fmt_signed
        blocks.append(viz.section(f"按 {dim} 拆解", viz.diverging_bar_chart([str(r["value"]) for r in rows], [r[key] for r in rows], fmt=chart_fmt,
                                                                          caption="这里只说明变化集中在哪里，不等于原因。")))
    if result["checks"]:
        blocks.append(viz.section("数据与口径检查", viz.checklist(result["checks"])))
    return viz.html_report(args.name or "指标归因拆解", blocks, brand="拾穗数据 · 业务归因")


def main() -> int:
    parser = argparse.ArgumentParser(description="业务指标归因计算器（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("confirm", help="判断异常是否真实：和同星期历史窗口比较")
    c.add_argument("--csv", required=True, help="日粒度 CSV")
    c.add_argument("--date-col", default="dt")
    c.add_argument("--value-col", required=True)
    c.add_argument("--start", required=True, help="异常窗口开始日期")
    c.add_argument("--end", required=True, help="异常窗口结束日期（含）")
    c.add_argument("--history-windows", type=int, default=8, help="向前取多少个同星期窗口，默认 8")
    c.add_argument("--json", help="同时把 JSON 写入文件")
    c.add_argument("--html", help=argparse.SUPPRESS)
    c.set_defaults(func=cmd_confirm)

    f = sub.add_parser("factors", help="把乘法公式的指标变化拆到各因子（LMDI）")
    f.add_argument("--factor", action="append", default=[], required=True, help="名称=基期,当期，可重复")
    f.add_argument("--target", default="目标指标", help="目标指标名称")
    f.add_argument("--json", help="同时把 JSON 写入文件")
    f.add_argument("--html", help=argparse.SUPPRESS)
    f.set_defaults(func=cmd_factors)

    d = sub.add_parser("dimensions", help="按维度排序变化贡献，比率指标拆成结构效应和转化效应")
    d.add_argument("--csv", required=True, help="按时期和维度汇总的 CSV")
    d.add_argument("--period-col", default="period")
    d.add_argument("--base", required=True, help="基期取值")
    d.add_argument("--current", required=True, help="当期取值")
    d.add_argument("--dim", action="append", default=[], required=True, help="维度列，可重复")
    d.add_argument("--metric", help="可加指标列，如 gmv")
    d.add_argument("--numerator", help="比率指标的分子列")
    d.add_argument("--denominator", help="比率指标的分母列")
    d.add_argument("--name", help="报告标题")
    d.add_argument("--html", help="输出 HTML 报告路径")
    d.add_argument("--json", help="同时把 JSON 写入文件")
    d.set_defaults(func=cmd_dimensions)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(sio.run_cli(main))
