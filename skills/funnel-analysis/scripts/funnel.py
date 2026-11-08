#!/usr/bin/env python3
"""漏斗计算器：严格有序漏斗、两期对比、步骤贡献拆解、分群结构拆解、埋点质量检查（仅依赖 Python 标准库）。

两种输入：

  事件明细 CSV（推荐）：脚本按时间顺序重建每个用户的漏斗路径
    python3 funnel.py analyze --events events.csv --user-col user_id --event-col event_name --time-col event_time \\
      --step 注册=register_success --step 浏览商品=product_view --step 加购=add_to_cart \\
      --step 提交订单=order_submit --step 支付成功=pay_success \\
      --users users.csv --segment channel_id --segment device_type \\
      --period 本期=2026-05-01..2026-05-14 --period 上期=2026-04-17..2026-04-30 --baseline 上期 \\
      --html funnel_report.html

  汇总 JSON：已经在 SQL 里算好每一步人数
    python3 funnel.py analyze --summary funnel.json --html funnel_report.html

输入格式见 ../references/input-schema.md。数字全部由脚本计算，不要在报告里手算替换。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import NormalDist

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_viz as viz  # noqa: E402
import sskit_io as sio  # noqa: E402

N = NormalDist()
Z95 = N.inv_cdf(0.975)
SMALL_SAMPLE = 100
TIME = sio.TimeParser()


# ---------------------------------------------------------------------------
# 统计
# ---------------------------------------------------------------------------

def wilson(s: int, n: int) -> list[float] | None:
    if n <= 0 or s > n:
        return None
    p = s / n
    denom = 1 + Z95 * Z95 / n
    centre = (p + Z95 * Z95 / (2 * n)) / denom
    half = Z95 * math.sqrt(p * (1 - p) / n + Z95 * Z95 / (4 * n * n)) / denom
    return [centre - half, centre + half]


def two_prop(s1: int, n1: int, s0: int, n0: int) -> dict | None:
    """本期（1）相对对比期（0）的比例差：差值、95% 区间、双侧 p 值。"""
    if n1 <= 0 or n0 <= 0 or s1 > n1 or s0 > n0:
        return None
    p1, p0 = s1 / n1, s0 / n0
    pooled = (s1 + s0) / (n1 + n0)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n0))
    se = math.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
    diff = p1 - p0
    p_value = 2 * (1 - N.cdf(abs(diff / se_pooled))) if se_pooled > 0 else 1.0
    return {"diff": diff, "ci": [diff - Z95 * se, diff + Z95 * se], "p_value": p_value}


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def fmt_duration(minutes: float | None) -> str:
    if minutes is None:
        return "—"
    if minutes < 1:
        return "< 1 分钟"
    if minutes < 60:
        return f"{minutes:.0f} 分钟"
    if minutes < 60 * 24:
        return f"{minutes / 60:.1f} 小时"
    return f"{minutes / 1440:.1f} 天"


# ---------------------------------------------------------------------------
# 输入：事件明细
# ---------------------------------------------------------------------------

def parse_time(text: str | None) -> datetime | None:
    return TIME(text)


def parse_steps(specs: list[str]) -> list[tuple[str, set[str]]]:
    if len(specs) < 2:
        raise SystemExit("至少需要两个 --step，格式：步骤名=事件名，多个事件用 | 分隔")
    steps, seen = [], {}
    for spec in specs:
        name, _, events = spec.partition("=")
        names = {e.strip() for e in (events or name).split("|") if e.strip()}
        for event in names:
            if event in seen:
                raise SystemExit(f"事件 {event} 同时出现在步骤「{seen[event]}」和「{name}」中")
            seen[event] = name
        steps.append((name.strip(), names))
    return steps


def parse_periods(specs: list[str]) -> list[tuple[str, datetime, datetime]]:
    periods = []
    for spec in specs:
        name, _, span = spec.partition("=")
        start, _, end = span.partition("..")
        if not (name and start and end):
            raise SystemExit(f"--period 格式应为 名称=YYYY-MM-DD..YYYY-MM-DD，收到：{spec}")
        periods.append((name, parse_time(start), parse_time(end) + timedelta(days=1)))
    return periods


def load_events(args: argparse.Namespace) -> dict:
    TIME.configure(args.tz)
    steps = parse_steps(args.step)
    step_of = {event: k for k, (_, events) in enumerate(steps) for event in events}
    periods = parse_periods(args.period) if args.period else []

    attributes: dict[str, dict] = {}
    if args.users:
        with sio.open_csv(args.users) as reader:
            if args.user_col not in reader.fieldnames:
                raise SystemExit(f"用户 CSV 缺少列：{args.user_col}（现有列：{reader.fieldnames}）")
            for row in reader:
                attributes[row[args.user_col]] = row

    user_events: dict[str, list[tuple[datetime, int, dict]]] = defaultdict(list)
    data_end = None
    with sio.open_csv(args.events) as reader:
        for col in (args.user_col, args.event_col, args.time_col):
            if col not in (reader.fieldnames or []):
                raise SystemExit(f"事件 CSV 缺少列：{col}（现有列：{reader.fieldnames}）")
        for row in reader:
            ts = parse_time(row[args.time_col])
            if ts is None:
                continue
            data_end = ts if data_end is None or ts > data_end else data_end
            k = step_of.get(row[args.event_col])
            if k is not None:
                user_events[row[args.user_col]].append((ts, k, row))
    if not user_events:
        raise SystemExit("事件 CSV 中没有匹配任何 --step 的事件")

    window = timedelta(days=args.window_days) if args.window_days else None
    n_steps = len(steps)
    by_period: dict[str, dict] = {}
    quality = {"no_entry_users": 0, "outside_periods": 0, "immature": defaultdict(int),
               "skip": [0] * n_steps, "out_of_order": [0] * n_steps, "repeat_entry": 0}
    gaps: list[list[float]] = [[] for _ in range(n_steps)]
    total_minutes: list[float] = []
    observation: dict[str, list[float]] = defaultdict(list)

    for user, items in user_events.items():
        items.sort(key=lambda x: x[0])
        entries = [x for x in items if x[1] == 0]
        if not entries:
            quality["no_entry_users"] += 1
            continue
        if len(entries) > 1:
            quality["repeat_entry"] += 1
        entry_time, _, entry_row = entries[0]

        if periods:
            period = next((name for name, start, end in periods if start <= entry_time < end), None)
            if period is None:
                quality["outside_periods"] += 1
                continue
        else:
            period = "全部"

        observed_minutes = (data_end - entry_time).total_seconds() / 60
        if window and data_end - entry_time < window:
            quality["immature"][period] += 1
            continue
        observation[period].append(observed_minutes)

        limit = entry_time + window if window else None
        reached, t = 1, entry_time
        times = [entry_time]
        for k in range(1, n_steps):
            nxt = next((ts for ts, sk, _ in items if sk == k and ts >= t and (limit is None or ts <= limit)), None)
            if nxt is None:
                break
            gaps[k].append((nxt - t).total_seconds() / 60)
            t = nxt
            times.append(nxt)
            reached += 1
        if reached == n_steps:
            total_minutes.append((times[-1] - entry_time).total_seconds() / 60)

        has = {sk for _, sk, _ in items}
        for k in range(1, n_steps):
            if k in has and k >= reached:
                if (k - 1) not in has:
                    quality["skip"][k] += 1
                elif k == reached and all(ts < times[k - 1] for ts, sk, _ in items if sk == k):
                    # 有晚于上一步的事件却没到达，只可能是超出窗口，属于正常未转化，不算乱序
                    quality["out_of_order"][k] += 1

        bucket = by_period.setdefault(period, {"counts": [0] * n_steps, "segments": defaultdict(lambda: defaultdict(lambda: [0] * n_steps))})
        for k in range(reached):
            bucket["counts"][k] += 1
        for dim in args.segment:
            source = attributes.get(user) if args.users else entry_row
            value = (source or {}).get(dim) or "未知"
            seg = bucket["segments"][dim][value]
            for k in range(reached):
                seg[k] += 1

    if not by_period:
        raise SystemExit("没有任何用户落在 --period 指定的区间内")

    p90 = quantile(total_minutes, 0.9)
    maturity = {}
    for period, values in observation.items():
        maturity[period] = {
            "median_observation_minutes": quantile(values, 0.5),
            "users_below_p90_conversion_time": sum(1 for v in values if p90 is not None and v < p90),
            "users": len(values),
        }

    names = [name for name, _, _ in periods] or ["全部"]
    return {
        "name": args.name or "漏斗分析",
        "steps": [name for name, _ in steps],
        "periods": {name: _freeze(by_period[name]) for name in names if name in by_period},
        "baseline": args.baseline,
        "source": "events",
        "window_days": args.window_days,
        "data_end": data_end.strftime("%Y-%m-%d %H:%M"),
        "quality": {**quality, "immature": dict(quality["immature"])},
        "timing": {
            "step_median_minutes": [quantile(g, 0.5) for g in gaps],
            "step_p90_minutes": [quantile(g, 0.9) for g in gaps],
            "total_p90_minutes": p90,
        },
        "maturity": maturity,
        "timezone_check": TIME.check(),
    }


def _freeze(bucket: dict) -> dict:
    return {"counts": bucket["counts"],
            "segments": {dim: {v: list(c) for v, c in values.items()} for dim, values in bucket["segments"].items()}}


# ---------------------------------------------------------------------------
# 输入：汇总 JSON
# ---------------------------------------------------------------------------

def load_summary(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        spec = json.load(handle)
    steps = spec.get("steps")
    if not steps or len(steps) < 2:
        raise SystemExit("汇总 JSON 需要 steps（至少两步）")
    periods: dict[str, dict] = {}
    for row in spec.get("data", []):
        period = row.get("period", "全部")
        counts = row["counts"]
        if len(counts) != len(steps):
            raise SystemExit(f"counts 长度应等于步骤数 {len(steps)}：{row}")
        bucket = periods.setdefault(period, {"counts": None, "segments": {}})
        segment = row.get("segment") or {}
        if not segment:
            bucket["counts"] = counts
        else:
            ((dim, value),) = segment.items()
            bucket["segments"].setdefault(dim, {})[value] = counts
    for name, bucket in periods.items():
        if bucket["counts"] is None:
            raise SystemExit(f"时期 {name} 缺少整体行（不带 segment 的 counts）")
    return {"name": spec.get("name", "漏斗分析"), "steps": steps, "periods": periods,
            "baseline": spec.get("baseline"), "source": "summary", "quality": None, "timing": None, "maturity": None}


# ---------------------------------------------------------------------------
# 分析
# ---------------------------------------------------------------------------

def funnel_table(counts: list[int]) -> list[dict]:
    rows = []
    for k, n in enumerate(counts):
        prev = counts[k - 1] if k else None
        rows.append({
            "count": n,
            "step_rate": n / prev if prev else (1.0 if k == 0 else None),
            "step_ci": wilson(n, prev) if prev else None,
            "cum_rate": n / counts[0] if counts[0] else None,
            "drop": prev - n if prev is not None else 0,
        })
    return rows


def shift_share(cur: dict, base: dict, base_overall: float) -> dict:
    """整体转化率变化 = 结构效应（各分群占比变化）+ 转化效应（各分群自身转化变化），两项相加精确等于总变化。

    逐行结构效应按 (占比变化) × (该分群对比期转化 − 对比期整体转化) 计算：
    低转化分群占比上升记为负、高转化分群占比上升记为正，各行加总与未中心化的公式相同。
    """
    n1 = sum(c[0] for c in cur.values())
    n0 = sum(c[0] for c in base.values())
    if n0:
        base_overall = sum(c[-1] for c in base.values()) / n0
    rows, mix, rate = [], 0.0, 0.0
    for value in sorted(set(cur) | set(base), key=lambda v: -(cur.get(v, [0])[0])):
        c1, c0 = cur.get(value), base.get(value)
        w1 = c1[0] / n1 if c1 and n1 else 0.0
        w0 = c0[0] / n0 if c0 and n0 else 0.0
        r1 = c1[-1] / c1[0] if c1 and c1[0] else None
        r0 = c0[-1] / c0[0] if c0 and c0[0] else None
        r0_eff = r0 if r0 is not None else base_overall
        m = (w1 - w0) * (r0_eff - base_overall)
        r = w1 * ((r1 if r1 is not None else r0_eff) - r0_eff)
        mix += m
        rate += r
        rows.append({"segment": value, "n_current": c1[0] if c1 else 0, "n_baseline": c0[0] if c0 else 0,
                     "share_current": w1, "share_baseline": w0, "conv_current": r1, "conv_baseline": r0,
                     "mix_effect": m, "rate_effect": r})
    return {"mix_effect": mix, "rate_effect": rate, "rows": rows}


def analyze(data: dict) -> dict:
    steps = data["steps"]
    names = list(data["periods"])
    baseline = data.get("baseline")
    if baseline and baseline not in data["periods"]:
        raise SystemExit(f"--baseline {baseline} 不在时期列表中：{names}")
    current = next((n for n in names if n != baseline), names[0])

    periods = {}
    for name, bucket in data["periods"].items():
        counts = bucket["counts"]
        periods[name] = {
            "counts": counts,
            "table": funnel_table(counts),
            "overall": counts[-1] / counts[0] if counts[0] else None,
            "segments": {dim: {v: {"counts": c, "overall": c[-1] / c[0] if c[0] else None} for v, c in values.items()}
                         for dim, values in bucket["segments"].items()},
        }

    cur = periods[current]
    transitions = [f"{steps[k - 1]} → {steps[k]}" for k in range(1, len(steps))]
    drops = [(k, cur["table"][k]) for k in range(1, len(steps))]
    worst_rate = min(drops, key=lambda x: x[1]["step_rate"] if x[1]["step_rate"] is not None else 2)
    worst_loss = max(drops, key=lambda x: x[1]["drop"])

    comparison = None
    if baseline:
        base = periods[baseline]
        c1, c0 = cur["counts"], base["counts"]
        overall = two_prop(c1[-1], c1[0], c0[-1], c0[0])
        step_changes, logs = [], []
        for k in range(1, len(steps)):
            test = two_prop(c1[k], c1[k - 1], c0[k], c0[k - 1])
            r1, r0 = cur["table"][k]["step_rate"], base["table"][k]["step_rate"]
            log = math.log(r1 / r0) if r1 and r0 else None
            logs.append(log)
            counterfactual = None
            if r1 and r0 and cur["overall"] is not None:
                counterfactual = cur["overall"] * r0 / r1
            step_changes.append({"transition": transitions[k - 1], "rate_current": r1, "rate_baseline": r0,
                                 "test": test, "log_ratio": log, "counterfactual_overall": counterfactual})
        total_log = math.log(cur["overall"] / base["overall"]) if cur["overall"] and base["overall"] else None
        decomposable = total_log not in (None, 0) and all(x is not None for x in logs)
        for change, log in zip(step_changes, logs):
            share = log / total_log if decomposable else None
            change["share_of_change"] = share
            change["contribution_pp"] = overall["diff"] * share if share is not None else None
        segments = {}
        for dim in cur["segments"]:
            if dim in base["segments"]:
                segments[dim] = shift_share(
                    {v: s["counts"] for v, s in cur["segments"][dim].items()},
                    {v: s["counts"] for v, s in base["segments"][dim].items()},
                    base["overall"] or 0.0,
                )
        comparison = {"overall": overall, "steps": step_changes, "decomposable": decomposable, "segments": segments}

    result = {
        "funnel": {"name": data["name"], "steps": steps, "transitions": transitions, "current": current,
                   "baseline": baseline, "source": data["source"], "window_days": data.get("window_days"),
                   "data_end": data.get("data_end")},
        "periods": periods,
        "drop_points": {
            "lowest_step_rate": {"transition": transitions[worst_rate[0] - 1], "step_rate": worst_rate[1]["step_rate"]},
            "largest_loss": {"transition": transitions[worst_loss[0] - 1], "lost": worst_loss[1]["drop"]},
        },
        "comparison": comparison,
        "timing": data.get("timing"),
        "maturity": data.get("maturity"),
    }
    result["checks"] = build_checks(data, result)
    result["verdict"] = build_verdict(result)
    return result


def build_checks(data: dict, result: dict) -> list[dict]:
    steps = data["steps"]
    checks = []
    for name, period in result["periods"].items():
        n = period["counts"][0]
        if n < SMALL_SAMPLE:
            checks.append({"id": "sample", "status": "warn", "title": f"{name} 只有 {n} 个入口用户",
                           "detail": "样本量小于 100，转化率的置信区间很宽，结论只能作为方向参考"})
        counts = period["counts"]
        if any(b > a for a, b in zip(counts, counts[1:])):
            checks.append({"id": "monotonic", "status": "fail", "title": f"{name} 漏斗人数出现后一步多于前一步",
                           "detail": "汇总口径不是有序漏斗（可能每步独立去重），需要改为按用户顺序统计"})

    quality = data.get("quality")
    if quality:
        if quality["no_entry_users"]:
            checks.append({"id": "no_entry", "status": "warn", "title": f"{quality['no_entry_users']} 个用户有后续步骤但没有入口事件",
                           "detail": f"可能是「{steps[0]}」埋点丢失，或用户在统计期之前进入"})
        for k in range(1, len(steps)):
            if quality["skip"][k]:
                checks.append({"id": "skip", "status": "warn", "title": f"{quality['skip'][k]} 个用户跳过「{steps[k - 1]}」直接到「{steps[k]}」",
                               "detail": "可能是埋点缺失，也可能存在绕过该步骤的产品路径；严格漏斗不计入这些用户"})
            if quality["out_of_order"][k]:
                checks.append({"id": "order", "status": "warn", "title": f"{quality['out_of_order'][k]} 个用户的「{steps[k]}」早于「{steps[k - 1]}」",
                               "detail": "时间顺序颠倒，常见原因是客户端时间不准或补报事件"})
        if quality["repeat_entry"]:
            checks.append({"id": "repeat", "status": "info", "title": f"{quality['repeat_entry']} 个用户有多次入口事件",
                           "detail": "已按最早一次入口计算"})
        if quality["outside_periods"]:
            checks.append({"id": "outside", "status": "info", "title": f"{quality['outside_periods']} 个用户的入口时间不在任何对比期内，已排除"})
        for period, count in quality["immature"].items():
            checks.append({"id": "immature", "status": "warn", "title": f"{period} 有 {count} 个用户尚未走完 {viz.fmt_num(data['window_days'])} 天转化窗口，已排除",
                           "detail": "这些用户的转化还没结束，计入会低估转化率"})
        if not any(c["id"] in ("skip", "order", "no_entry") for c in checks):
            checks.append({"id": "tracking", "status": "pass", "title": "未发现跳步、乱序或缺失入口"})
        if data.get("timezone_check"):
            checks.append(data["timezone_check"])

    maturity = data.get("maturity") or {}
    timing = data.get("timing") or {}
    if maturity and not data.get("window_days"):
        p90 = timing.get("total_p90_minutes")
        medians = {p: m["median_observation_minutes"] for p, m in maturity.items() if m["median_observation_minutes"] is not None}
        detail = "；".join(f"{p} 观察期中位数 {fmt_duration(v)}" for p, v in medians.items())
        if p90 is not None:
            detail += f"；完成全漏斗的用户 90% 在 {fmt_duration(p90)} 内完成"
        immature = {p: m["users_below_p90_conversion_time"] for p, m in maturity.items() if m["users_below_p90_conversion_time"]}
        spread = (max(medians.values()) / max(min(medians.values()), 1)) if len(medians) > 1 else 1
        if immature:
            checks.append({"id": "truncation", "status": "warn",
                           "title": "部分用户的观察期短于常见转化耗时（右截断）",
                           "detail": detail + "；观察期不足的用户：" + "、".join(f"{p} {n} 人" for p, n in immature.items())
                           + "。建议设置 --window-days 统一转化窗口"})
        elif spread > 2:
            checks.append({"id": "truncation", "status": "warn", "title": "两期用户的观察期长短差异很大",
                           "detail": detail + "。按历史耗时看截断影响有限，但慢转化用户会被低估，建议设置 --window-days 统一窗口"})
        else:
            checks.append({"id": "truncation", "status": "info", "title": "未设置转化窗口", "detail": detail})
    elif data.get("source") == "summary":
        checks.append({"id": "definition", "status": "info", "title": "汇总数据无法验证顺序和窗口",
                       "detail": "请确认上游 SQL 按用户有序统计、两期使用相同的转化窗口，并且按入口时间划分时期"})
    return checks


def build_verdict(result: dict) -> dict:
    f = result["funnel"]
    cur = result["periods"][f["current"]]
    comp = result["comparison"]
    reasons, steps_next = [], []
    broken = [c for c in result["checks"] if c["id"] == "monotonic"]
    if broken:
        return {"level": "bad", "title": "漏斗口径错误：后一步人数多于前一步，转化率没有意义",
                "reasons": [c["title"] for c in broken],
                "next_steps": ["改为按用户有序统计：只有完成了上一步的用户才计入下一步（见 references/funnel-sql.md）",
                               "修正口径后重新运行，不要解读当前的转化率"]}
    worst = result["drop_points"]["lowest_step_rate"]
    loss = result["drop_points"]["largest_loss"]

    if not comp:
        title = f"最薄弱环节：{worst['transition']}，单步转化 {viz.fmt_pct(worst['step_rate'], 1)}"
        reasons.append(f"整体转化 {viz.fmt_pct(cur['overall'], 1)}（{cur['counts'][-1]} / {cur['counts'][0]}）")
        reasons.append(f"流失人数最多：{loss['transition']}，流失 {viz.fmt_num(loss['lost'])} 人")
        steps_next += [f"拆解「{worst['transition']}」：按渠道、设备、版本看是否集中在某类用户",
                       "补一个对比期（上期 / 去年同期 / 实验对照），单期漏斗无法判断是否异常"]
        return {"level": "info", "title": title, "reasons": reasons, "next_steps": steps_next}

    base = result["periods"][f["baseline"]]
    overall = comp["overall"]
    diff = overall["diff"]
    significant = overall["p_value"] < 0.05
    direction = "下降" if diff < 0 else "上升"
    title = (f"整体转化 {viz.fmt_pct(base['overall'], 1)} → {viz.fmt_pct(cur['overall'], 1)}"
             f"（{viz.fmt_pp(diff, 1)}）")
    if significant:
        level = "bad" if diff < 0 else "good"
    else:
        level = "warning"
        title += "，变化未达显著"
        reasons.append(f"整体转化{direction}的 p={overall['p_value']:.2f}，95% 区间 [{viz.fmt_pp(overall['ci'][0], 1)}, {viz.fmt_pp(overall['ci'][1], 1)}]，"
                       "不能排除是随机波动")

    if comp["decomposable"]:
        ranked = sorted(comp["steps"], key=lambda s: s["contribution_pp"] if diff < 0 else -s["contribution_pp"])
        top = ranked[0]
        reasons.append(f"变化最大的来源：{top['transition']}，单步转化 {viz.fmt_pct(top['rate_baseline'], 1)} → "
                       f"{viz.fmt_pct(top['rate_current'], 1)}，贡献整体变化的 {top['share_of_change'] * 100:.0f}%")
        if top["counterfactual_overall"] is not None and diff < 0:
            reasons.append(f"若这一步恢复到{f['baseline']}水平，整体转化可回到 {viz.fmt_pct(top['counterfactual_overall'], 1)}")
        steps_next.append(f"优先排查「{top['transition']}」：页面改版、加载性能、价格或库存、埋点变更")

    for dim, ss in comp["segments"].items():
        total = ss["mix_effect"] + ss["rate_effect"]
        if total == 0:
            continue
        mix_share = ss["mix_effect"] / total
        mover = max(ss["rows"], key=lambda r: abs(r["mix_effect"]))
        text = (f"按 {dim} 拆：结构变化贡献 {viz.fmt_pp(ss['mix_effect'], 1)}，各分群自身转化变化贡献 {viz.fmt_pp(ss['rate_effect'], 1)}")
        if mix_share > 0.4:
            shift = f"{mover['segment']} 占比 {viz.fmt_pct(mover['share_baseline'], 0)} → {viz.fmt_pct(mover['share_current'], 0)}"
            text += f"；{shift}，用户结构变化是主要原因之一"
            steps_next.append(f"弄清 {dim} 构成为什么变了（{shift}）：投放、渠道质量还是活动，这更像获客问题而非产品问题")
        elif mix_share < 0.4:
            driver = max(ss["rows"], key=lambda r: abs(r["rate_effect"]))
            if driver["conv_current"] is not None and driver["conv_baseline"] is not None:
                text += (f"；主要来自 {driver['segment']} 自身转化 {viz.fmt_pct(driver['conv_baseline'], 1)} → "
                         f"{viz.fmt_pct(driver['conv_current'], 1)}")
                steps_next.append(f"重点看 {dim}={driver['segment']} 的体验和流程，这更像产品或流程问题")
        reasons.append(text)

    for check in result["checks"]:
        if check["id"] == "truncation" and check["status"] == "warn":
            reasons.append("两期观察期不一致，本期转化可能被低估")
            steps_next.append("用统一转化窗口（--window-days）重算，或等本期用户观察期满后复核")
            break
    if any(c["id"] == "sample" for c in result["checks"]):
        steps_next.append("样本量太小：扩大时间范围或合并周期后再下结论")
    steps_next.append("分群差异只说明相关，不说明因果；要确认因果，用 A/B 实验验证改动")
    return {"level": level, "title": title, "reasons": reasons, "next_steps": steps_next}


# ---------------------------------------------------------------------------
# HTML 报告
# ---------------------------------------------------------------------------

def render_html(result: dict) -> str:
    f = result["funnel"]
    steps = f["steps"]
    cur = result["periods"][f["current"]]
    comp = result["comparison"]
    base = result["periods"][f["baseline"]] if comp else None
    verdict = result["verdict"]
    blocks = []

    body = "".join(f"<div>· {viz.esc(r)}</div>" for r in verdict["reasons"])
    blocks.append(viz.callout(verdict["level"], verdict["title"], body, raw_body=True))

    tiles = [{"label": f"入口用户 · {f['current']}", "value": viz.fmt_num(cur["counts"][0]),
              "note": f"{steps[0]}"}]
    overall_tile = {"label": f"整体转化 · {f['current']}", "value": viz.fmt_pct(cur["overall"], 1),
                    "note": f"{steps[0]} → {steps[-1]}"}
    if comp:
        tiles[0]["delta"] = f"{f['baseline']} {viz.fmt_num(base['counts'][0])}"
        sig = comp["overall"]["p_value"] < 0.05
        overall_tile["delta"] = f"{viz.arrow(comp['overall']['diff'])} {viz.fmt_pp(comp['overall']['diff'], 1)} vs {f['baseline']}" + ("" if sig else "（不显著）")
        overall_tile["tone"] = viz.delta_tone(comp["overall"]["diff"], True, sig)
    tiles.append(overall_tile)
    worst = result["drop_points"]["lowest_step_rate"]
    tiles.append({"label": "最薄弱环节", "value": viz.fmt_pct(worst["step_rate"], 1), "note": worst["transition"]})
    loss = result["drop_points"]["largest_loss"]
    tiles.append({"label": "流失最多", "value": f"{viz.fmt_num(loss['lost'])} 人", "note": loss["transition"]})
    blocks.append(viz.section("核心结果", viz.stat_tiles(tiles)))

    if comp:
        chart = viz.paired_bar_chart(steps, [r["cum_rate"] for r in cur["table"]], [r["cum_rate"] for r in base["table"]],
                                     names=(f["current"], f["baseline"]), fmt=lambda v: viz.fmt_pct(v, 1),
                                     caption="累计转化率 = 到达该步的人数 / 入口人数。用比例而不是人数对比，两期入口规模不同也可比。")
    else:
        labels = [f"{viz.fmt_num(r['count'])} 人" + (f" · {viz.fmt_pct(r['step_rate'], 1)}" if k else "")
                  for k, r in enumerate(cur["table"])]
        chart = viz.bar_chart(steps, [r["count"] for r in cur["table"]], labels=labels,
                              caption="条末端为人数和单步转化率（相对上一步）。")
    headers = ["步骤", f"{f['current']} 人数", "单步转化", "累计转化", "流失"]
    rows = [[steps[k], viz.fmt_num(r["count"]), viz.fmt_pct(r["step_rate"], 1) if k else "—",
             viz.fmt_pct(r["cum_rate"], 1), viz.fmt_num(r["drop"]) if k else "—"] for k, r in enumerate(cur["table"])]
    if comp:
        headers += [f"{f['baseline']} 人数", f"{f['baseline']} 单步转化"]
        for k, row in enumerate(rows):
            row += [viz.fmt_num(base["table"][k]["count"]), viz.fmt_pct(base["table"][k]["step_rate"], 1) if k else "—"]
    blocks.append(viz.section("漏斗表现", chart, viz.table(headers, rows, numeric=tuple(range(1, len(headers))))))

    if comp:
        parts = []
        overall_sig = comp["overall"]["p_value"] < 0.05

        def tones_for(values):
            # 整体变化不显著时，拆解出来的每一份也只是噪声的切片，不上色
            return [("bad" if v < 0 else "good") if overall_sig else "neutral" for v in values]

        if comp["decomposable"]:
            contrib = [s["contribution_pp"] for s in comp["steps"]]
            parts.append(viz.diverging_bar_chart(
                f["transitions"], contrib, fmt=lambda v: viz.fmt_pp(v, 2),
                tones=tones_for(contrib),
                caption="整体转化率 = 各步转化率的乘积，因此整体变化可以精确拆到每一步（按对数比例分配）。各条相加等于整体变化。"))
        rows_iv = []
        for s in comp["steps"]:
            t = s["test"]
            if t is None:
                continue
            sig = t["p_value"] < 0.05
            rows_iv.append({"label": s["transition"], "sub": f"{viz.fmt_pct(s['rate_baseline'], 1)} → {viz.fmt_pct(s['rate_current'], 1)}",
                            "estimate": t["diff"], "low": t["ci"][0], "high": t["ci"][1],
                            "tone": viz.delta_tone(t["diff"], True, sig)})
        parts.append(viz.interval_chart(rows_iv, fmt=lambda v: viz.fmt_pp(v, 1),
                                        caption="单步转化率变化及 95% 区间；跨过 0 线即不显著，只有显著的变化才上色。"))
        blocks.append(viz.section("整体变化来自哪一步", *parts, lead="先看贡献，再看每一步的变化是不是真的。"))

        for dim, ss in comp["segments"].items():
            seg_rows = [[r["segment"], viz.fmt_num(r["n_current"]), viz.fmt_pct(r["share_current"], 1), viz.fmt_pct(r["share_baseline"], 1),
                         viz.fmt_pct(r["conv_current"], 1) if r["conv_current"] is not None else "—",
                         viz.fmt_pct(r["conv_baseline"], 1) if r["conv_baseline"] is not None else "—",
                         viz.fmt_pp(r["mix_effect"], 1), viz.fmt_pp(r["rate_effect"], 1)] for r in ss["rows"]]
            effects = [ss["mix_effect"], ss["rate_effect"]]
            blocks.append(viz.section(
                f"按 {dim} 拆：结构变化还是转化变化",
                viz.diverging_bar_chart(["结构效应（占比变化）", "转化效应（分群自身变化）"], effects,
                                        fmt=lambda v: viz.fmt_pp(v, 1), tones=tones_for(effects),
                                        caption="两项相加精确等于整体转化变化。结构效应大，说明问题更可能在获客；转化效应大，说明问题更可能在产品或流程。"),
                viz.table([dim, "本期人数", "本期占比", "对比期占比", "本期转化", "对比期转化", "结构效应", "转化效应"], seg_rows,
                          numeric=(1, 2, 3, 4, 5, 6, 7)),
            ))
    else:
        for dim, values in cur["segments"].items():
            seg_rows = sorted(values.items(), key=lambda kv: -kv[1]["counts"][0])
            names = [v for v, _ in seg_rows]
            rates = [s["overall"] or 0 for _, s in seg_rows]
            errors = [tuple(wilson(s["counts"][-1], s["counts"][0]) or (0, 0)) for _, s in seg_rows]
            blocks.append(viz.section(f"按 {dim} 对比整体转化", viz.bar_chart(
                names, rates, errors=errors, fmt=lambda v: viz.fmt_pct(v, 1),
                caption="误差线为 95% 置信区间；区间重叠很大的分群差异不要过度解读。")))

    timing = result.get("timing")
    if timing:
        rows_t = [[f["transitions"][k - 1], fmt_duration(timing["step_median_minutes"][k]), fmt_duration(timing["step_p90_minutes"][k])]
                  for k in range(1, len(steps))]
        rows_t.append(["全漏斗", "—", fmt_duration(timing["total_p90_minutes"])])
        blocks.append(viz.section("转化耗时", viz.table(["环节", "中位数", "P90"], rows_t, numeric=(1, 2)),
                                  lead="只统计完成该环节的用户。耗时长的环节适合做召回提醒。"))

    blocks.append(viz.section("数据质量与口径", viz.checklist(result["checks"])))
    blocks.append(viz.section("下一步", viz.checklist([{"status": "info", "title": s} for s in result["verdict"]["next_steps"]]),
                              viz.paragraph("方法说明：严格有序漏斗按事件时间判断，第 k 步必须发生在第 k−1 步之后；时期按入口时间划分；"
                                            "比例区间用 Wilson 方法，两期差异用双样本比例 z 检验；步骤贡献按对数比例拆分；"
                                            "分群拆解用结构效应 + 转化效应（shift-share）。")))

    subtitle = " → ".join(steps)
    if comp:
        subtitle += f" · {f['current']} vs {f['baseline']}"
    return viz.html_report(f["name"], blocks, subtitle=subtitle, brand="拾穗数据 · 漏斗分析报告")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _round(obj):
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    return obj


def cmd_analyze(args: argparse.Namespace) -> int:
    if bool(args.summary) == bool(args.events):
        raise SystemExit("--summary 与 --events 二选一")
    data = load_summary(args.summary) if args.summary else load_events(args)
    if args.baseline:
        data["baseline"] = args.baseline
    if args.name:
        data["name"] = args.name
    result = _round(analyze(data))
    if args.html:
        viz.save(args.html, render_html(result))
        result["html_report"] = os.path.abspath(args.html)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="漏斗计算器（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="计算漏斗并生成报告")
    a.add_argument("--summary", help="汇总数据 JSON（见 references/input-schema.md）")
    a.add_argument("--events", help="事件明细 CSV，每行一个事件")
    a.add_argument("--user-col", default="user_id")
    a.add_argument("--event-col", default="event_name")
    a.add_argument("--time-col", default="event_time")
    a.add_argument("--tz", default="+08:00", help="业务时区，带时区的时间会换算到这里，默认 +08:00")
    a.add_argument("--step", action="append", default=[], help="步骤：名称=事件名，多个事件用 | 分隔；按漏斗顺序重复填写")
    a.add_argument("--users", help="用户属性 CSV（用于分群），按 --user-col 关联")
    a.add_argument("--segment", action="append", default=[], help="分群列；有 --users 时取用户属性，否则取入口事件所在行")
    a.add_argument("--period", action="append", default=[], help="时期：名称=YYYY-MM-DD..YYYY-MM-DD，按入口时间划分")
    a.add_argument("--baseline", help="作为对比基准的时期名称")
    a.add_argument("--window-days", type=float, help="转化窗口：入口后 N 天内完成才算转化；未走完窗口的用户会被排除")
    a.add_argument("--name", help="报告标题")
    a.add_argument("--html", help="输出 HTML 报告路径")
    a.add_argument("--json", help="同时把 JSON 写入文件")
    a.set_defaults(func=cmd_analyze)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(sio.run_cli(main))
