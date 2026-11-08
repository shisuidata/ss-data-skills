#!/usr/bin/env python3
"""留存 / Cohort 计算器：留存矩阵、成熟度屏蔽、加权留存曲线、分群对比、异常批次、批次间结构拆解（仅依赖 Python 标准库）。

两种输入：

  事件明细 CSV（推荐）：脚本按用户重建起点和回访
    python3 retention.py analyze --events events.csv --user-col user_id --event-col event_name --time-col event_time \\
      --start-event register_success --return-event "app_open|product_view" \\
      --users users.csv --segment channel_id --unit day --periods 1,3,7,14,30 --html retention_report.html

  汇总 JSON：已经在 SQL 里算好每个 Cohort 的留存人数
    python3 retention.py analyze --summary cohorts.json --html retention_report.html

输入格式见 ../references/input-schema.md。数字全部由脚本计算，不要在报告里手算替换。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import NormalDist

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_viz as viz  # noqa: E402
import sskit_io as sio  # noqa: E402

N = NormalDist()
Z95 = N.inv_cdf(0.975)
SMALL_COHORT = 100
TIME = sio.TimeParser()
DEFAULT_PERIODS = {"day": [1, 3, 7, 14, 30], "week": [1, 2, 3, 4, 6, 8], "month": [1, 2, 3, 6, 12]}
PREFIX = {"day": "D", "week": "W", "month": "M"}


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
    if n1 <= 0 or n0 <= 0 or s1 > n1 or s0 > n0:
        return None
    p1, p0 = s1 / n1, s0 / n0
    pooled = (s1 + s0) / (n1 + n0)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n0))
    se = math.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
    diff = p1 - p0
    p_value = 2 * (1 - N.cdf(abs(diff / se_pooled))) if se_pooled > 0 else 1.0
    return {"diff": diff, "ci": [diff - Z95 * se, diff + Z95 * se], "p_value": p_value}


# ---------------------------------------------------------------------------
# 时间
# ---------------------------------------------------------------------------

def parse_time(text: str | None) -> datetime | None:
    return TIME(text)


def cohort_key(d: date, unit: str) -> str:
    if unit == "week":
        monday = d - timedelta(days=d.weekday())
        return monday.isoformat()
    if unit == "month":
        return d.strftime("%Y-%m")
    return d.isoformat()


def period_index(start: datetime, ts: datetime, unit: str, boundary: str) -> int:
    if unit == "day":
        if boundary == "rolling":
            return math.floor((ts - start).total_seconds() / 86400)
        return (ts.date() - start.date()).days
    if unit == "week":
        return (ts.date() - start.date()).days // 7
    return (ts.year - start.year) * 12 + ts.month - start.month


def observable_max(start: datetime, data_end: datetime, unit: str, boundary: str) -> int:
    """最后一个被完整观察到的周期序号。数据截止日按完整的一天处理。"""
    if unit == "day":
        if boundary == "rolling":
            return math.floor((data_end - start).total_seconds() / 86400) - 1
        return (data_end.date() - start.date()).days
    if unit == "week":
        return ((data_end.date() - start.date()).days + 1) // 7 - 1
    last_full_month = data_end.date() + timedelta(days=1)
    return (last_full_month.year - start.year) * 12 + last_full_month.month - start.month - 1


# ---------------------------------------------------------------------------
# 输入：事件明细
# ---------------------------------------------------------------------------

def load_events(args: argparse.Namespace) -> dict:
    TIME.configure(args.tz)
    unit, boundary, mode = args.unit, args.boundary, args.mode
    periods = sorted({int(p) for p in args.periods.split(",")}) if args.periods else DEFAULT_PERIODS[unit]
    start_events = set(args.start_event.split("|")) if args.start_event else None
    return_events = set(args.return_event.split("|")) if args.return_event else None
    if not start_events and not args.start_col:
        raise SystemExit("需要 --start-event（事件表中的起点事件）或 --start-col（用户表中的起点时间列）")

    attributes: dict[str, dict] = {}
    if args.users:
        with sio.open_csv(args.users) as reader:
            if args.user_col not in reader.fieldnames:
                raise SystemExit(f"用户 CSV 缺少列：{args.user_col}（现有列：{reader.fieldnames}）")
            for row in reader:
                attributes[row[args.user_col]] = row

    starts: dict[str, tuple[datetime, dict]] = {}
    if args.start_col:
        if not args.users:
            raise SystemExit("--start-col 需要配合 --users 使用")
        for user, row in attributes.items():
            started = parse_time(row.get(args.start_col))
            if started is not None:
                starts[user] = (started, row)

    activity: dict[str, list[datetime]] = defaultdict(list)
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
            user, event = row[args.user_col], row[args.event_col]
            if start_events and event in start_events and not args.start_col:
                if user not in starts or ts < starts[user][0]:
                    starts[user] = (ts, row)
            if return_events is None or event in return_events:
                activity[user].append(ts)
    if args.data_end:
        data_end = datetime.combine(parse_time(args.data_end).date(), datetime.max.time())
    if not starts or data_end is None:
        raise SystemExit("没有找到任何起点事件")

    def build(boundary_mode: str) -> tuple[dict, dict]:
        cells = defaultdict(lambda: {"size": 0, "retained": defaultdict(int), "min_obs": None,
                                     "segments": defaultdict(lambda: defaultdict(lambda: {"size": 0, "retained": defaultdict(int)}))})
        overall = {"users": 0, "retained": defaultdict(int), "mature": defaultdict(int)}
        for user, (start, start_row) in starts.items():
            key = cohort_key(start.date(), unit)
            obs = observable_max(start, data_end, unit, boundary_mode)
            idx = {period_index(start, ts, unit, boundary_mode) for ts in activity.get(user, []) if ts >= start}
            idx.discard(0)
            first_return = min((i for i in idx if i > 0), default=None)
            cell = cells[key]
            cell["size"] += 1
            cell["min_obs"] = obs if cell["min_obs"] is None else min(cell["min_obs"], obs)
            segs = []
            for dim in args.segment:
                source = attributes.get(user) if args.users else start_row
                segs.append((dim, (source or {}).get(dim) or "未知"))
            for dim, value in segs:
                cell["segments"][dim][value]["size"] += 1
            overall["users"] += 1
            for p in periods:
                hit = (p in idx) if mode == "on" else (first_return is not None and first_return <= p)
                if obs >= p:
                    overall["mature"][p] += 1
                    overall["retained"][p] += int(hit)
                if hit:
                    cell["retained"][p] += 1
                    for dim, value in segs:
                        cell["segments"][dim][value]["retained"][p] += 1
        return cells, overall

    cells, _ = build(boundary)
    cohorts = []
    for key in sorted(cells):
        cell = cells[key]
        mature = {p: cell["min_obs"] >= p for p in periods}
        cohorts.append({
            "cohort": key, "size": cell["size"],
            "retained": {p: (cell["retained"][p] if mature[p] else None) for p in periods},
            "segments": {dim: {v: {"size": s["size"], "retained": {p: (s["retained"][p] if mature[p] else None) for p in periods}}
                               for v, s in values.items()} for dim, values in cell["segments"].items()},
        })

    sensitivity = None
    if unit == "day" and 1 in periods:
        other = "rolling" if boundary == "natural" else "natural"
        _, a = build(boundary)
        _, b = build(other)
        if a["mature"][1] and b["mature"][1]:
            sensitivity = {"boundary": boundary, "other": other,
                           "d1": a["retained"][1] / a["mature"][1], "d1_other": b["retained"][1] / b["mature"][1]}

    return {"name": args.name or "留存分析", "unit": unit, "mode": mode, "boundary": boundary, "periods": periods,
            "cohorts": cohorts, "source": "events", "data_end": data_end.strftime("%Y-%m-%d %H:%M"),
            "sensitivity": sensitivity, "return_events": sorted(return_events) if return_events else None,
            "timezone_check": TIME.check()}


# ---------------------------------------------------------------------------
# 输入：汇总 JSON
# ---------------------------------------------------------------------------

def load_summary(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        spec = json.load(handle)
    periods = [int(p) for p in spec.get("periods", [])]
    if not periods:
        raise SystemExit("汇总 JSON 需要 periods，例如 [1, 7, 30]")
    totals: dict[str, dict] = {}
    segmented: dict[str, dict] = defaultdict(lambda: defaultdict(dict))
    for row in spec.get("data", []):
        retained = {int(k): v for k, v in row.get("retained", {}).items()}
        entry = {"size": int(row["size"]), "retained": {p: retained.get(p) for p in periods}}
        segment = row.get("segment") or {}
        if segment:
            ((dim, value),) = segment.items()
            segmented[row["cohort"]][dim][value] = entry
        else:
            totals[row["cohort"]] = entry

    cohorts = []
    for key in sorted(set(totals) | set(segmented)):
        segs = segmented.get(key, {})
        total = totals.get(key)
        if total is None:
            dim = next(iter(segs))
            parts = list(segs[dim].values())
            total = {"size": sum(p["size"] for p in parts),
                     "retained": {p: (None if any(x["retained"][p] is None for x in parts) else sum(x["retained"][p] for x in parts))
                                  for p in periods}}
        cohorts.append({"cohort": key, **total, "segments": {d: dict(v) for d, v in segs.items()}})
    return {"name": spec.get("name", "留存分析"), "unit": spec.get("unit", "day"), "mode": spec.get("mode", "on"),
            "boundary": spec.get("boundary", "natural"), "periods": periods, "cohorts": cohorts,
            "source": "summary", "data_end": spec.get("data_end"), "sensitivity": None, "return_events": None}


# ---------------------------------------------------------------------------
# 分析
# ---------------------------------------------------------------------------

def curve_horizon(cohorts: list[dict], periods: list[int]) -> tuple[int, list[dict]]:
    """曲线使用的固定批次集合：至少一半批次（且不少于 2 个）都已成熟的最长周期。

    如果每个周期各用各的成熟批次，长周期只剩早期批次，曲线会被批次构成扭曲（例如后段反而上升）。
    """
    need = max(2, math.ceil(len(cohorts) / 2))
    horizon = periods[0]
    for p in periods:
        if sum(1 for c in cohorts if c["retained"].get(p) is not None) >= need:
            horizon = p
    fixed = [c for c in cohorts if c["retained"].get(horizon) is not None]
    return horizon, fixed or cohorts


def curve(cohorts: list[dict], periods: list[int], pick=lambda c: c, horizon: int | None = None) -> list[dict]:
    """按 Cohort 规模加权的留存曲线，只使用已成熟的单元格；超过 horizon 的周期不画。"""
    points = []
    for p in periods:
        if horizon is not None and p > horizon:
            points.append({"period": p, "retained": 0, "users": 0, "cohorts": 0, "rate": None, "ci": None})
            continue
        s = n = k = 0
        for c in cohorts:
            entry = pick(c)
            if entry and entry["retained"].get(p) is not None:
                s += entry["retained"][p]
                n += entry["size"]
                k += 1
        points.append({"period": p, "retained": s, "users": n, "cohorts": k,
                       "rate": s / n if n else None, "ci": wilson(s, n)})
    return points


def shift_share(cur: dict, base: dict) -> dict:
    """批次间留存变化 = 结构效应（分群占比变化）+ 留存效应（分群自身变化），逐行结构效应已中心化。"""
    n1 = sum(v["size"] for v in cur.values())
    n0 = sum(v["size"] for v in base.values())
    r0_all = sum(v["retained"] for v in base.values()) / n0 if n0 else 0.0
    rows, mix, rate = [], 0.0, 0.0
    for seg in sorted(set(cur) | set(base), key=lambda s: -cur.get(s, {"size": 0})["size"]):
        c1, c0 = cur.get(seg), base.get(seg)
        w1 = c1["size"] / n1 if c1 and n1 else 0.0
        w0 = c0["size"] / n0 if c0 and n0 else 0.0
        r1 = c1["retained"] / c1["size"] if c1 and c1["size"] else None
        r0 = c0["retained"] / c0["size"] if c0 and c0["size"] else None
        r0e = r0 if r0 is not None else r0_all
        m = (w1 - w0) * (r0e - r0_all)
        r = w1 * ((r1 if r1 is not None else r0e) - r0e)
        mix += m
        rate += r
        rows.append({"segment": seg, "share_current": w1, "share_baseline": w0, "rate_current": r1, "rate_baseline": r0,
                     "mix_effect": m, "rate_effect": r})
    return {"mix_effect": mix, "rate_effect": rate, "rows": rows}


def analyze(data: dict, key_period: int | None, period_specs: list[str], baseline: str | None) -> dict:
    periods, cohorts = data["periods"], data["cohorts"]
    key = key_period if key_period in periods else next((p for p in (7, 4, 3, 1) if p in periods), periods[0])
    label = lambda p: f"{PREFIX[data['unit']]}{p}"  # noqa: E731

    overall = curve(cohorts, periods)
    horizon, fixed = curve_horizon(cohorts, periods)
    fixed_curve = curve(fixed, periods, horizon=horizon)
    dims = sorted({d for c in cohorts for d in c["segments"]})
    segment_curves = {}
    segment_tests = {}
    for dim in dims:
        values = sorted({v for c in cohorts for v in c["segments"].get(dim, {})},
                        key=lambda v: -sum(c["segments"].get(dim, {}).get(v, {"size": 0})["size"] for c in cohorts))
        segment_curves[dim] = {v: curve(fixed, periods, lambda c, d=dim, v=v: c["segments"].get(d, {}).get(v), horizon) for v in values}
        tests = []
        for v in values:
            # 显著性检验使用关键周期上全部成熟的批次，与“其余用户”口径一致
            this = curve(cohorts, periods, lambda c, d=dim, v=v: c["segments"].get(d, {}).get(v))[periods.index(key)]
            rest_s = overall[periods.index(key)]["retained"] - this["retained"]
            rest_n = overall[periods.index(key)]["users"] - this["users"]
            t = two_prop(this["retained"], this["users"], rest_s, rest_n) if this["users"] else None
            tests.append({"segment": v, "rate": this["rate"], "users": this["users"], "vs_rest": t})
        segment_tests[dim] = tests

    # 异常批次：关键周期上与“按本批次用户构成调整后的预期”比较，Bonferroni 校正。
    # 不做构成调整时，渠道结构变化会让整批批次都显得“异常”，掩盖真正的事故批次。
    anomalies = []
    mature = [c for c in cohorts if c["retained"].get(key) is not None]
    adjust_dim = dims[0] if dims else None
    for c in mature:
        others = [o for o in mature if o is not c]
        if len(others) < 2:
            break
        n_c, s_c = c["size"], c["retained"][key]
        expected = None
        if adjust_dim and c["segments"].get(adjust_dim):
            rates = {}
            for v in c["segments"][adjust_dim]:
                ss = sum(o["segments"].get(adjust_dim, {}).get(v, {"retained": {key: 0}})["retained"][key] or 0 for o in others)
                nn = sum(o["segments"].get(adjust_dim, {}).get(v, {"size": 0})["size"] for o in others)
                rates[v] = ss / nn if nn else None
            if all(r is not None for r in rates.values()):
                expected = sum(e["size"] * rates[v] for v, e in c["segments"][adjust_dim].items()) / n_c
        if expected is None:
            expected = sum(o["retained"][key] for o in others) / sum(o["size"] for o in others)
        if not 0 < expected < 1:
            continue
        z = (s_c / n_c - expected) / math.sqrt(expected * (1 - expected) / n_c)
        p_adj = min(1.0, 2 * (1 - N.cdf(abs(z))) * len(mature))
        if p_adj < 0.05:
            anomalies.append({"cohort": c["cohort"], "rate": s_c / n_c, "expected": expected,
                              "diff": s_c / n_c - expected, "p_adjusted": p_adj, "adjusted_by": adjust_dim})

    comparison = None
    if period_specs:
        groups: dict[str, list[dict]] = {}
        for spec in period_specs:
            name, _, span = spec.partition("=")
            start, _, end = span.partition("..")
            groups[name] = [c for c in cohorts if start[:len(c["cohort"])] <= c["cohort"] <= end[:len(c["cohort"])]]
        if baseline not in groups:
            raise SystemExit(f"--baseline {baseline} 不在 --period 列表中")
        current = next(n for n in groups if n != baseline)
        cur_c = [c for c in groups[current] if c["retained"].get(key) is not None]
        base_c = [c for c in groups[baseline] if c["retained"].get(key) is not None]
        if cur_c and base_c:
            s1, n1 = sum(c["retained"][key] for c in cur_c), sum(c["size"] for c in cur_c)
            s0, n0 = sum(c["retained"][key] for c in base_c), sum(c["size"] for c in base_c)
            seg_ss = {}
            for dim in dims:
                def agg(cs, d=dim):
                    out: dict[str, dict] = {}
                    for c in cs:
                        for v, e in c["segments"].get(d, {}).items():
                            slot = out.setdefault(v, {"size": 0, "retained": 0})
                            slot["size"] += e["size"]
                            slot["retained"] += e["retained"][key]
                    return out
                seg_ss[dim] = shift_share(agg(cur_c), agg(base_c))
            comparison = {"current": current, "baseline": baseline, "key_period": key,
                          "current_cohorts": [c["cohort"] for c in cur_c], "baseline_cohorts": [c["cohort"] for c in base_c],
                          "rate_current": s1 / n1, "rate_baseline": s0 / n0, "test": two_prop(s1, n1, s0, n0),
                          "segments": seg_ss}
        else:
            comparison = {"current": current, "baseline": baseline, "key_period": key, "unavailable": True}

    result = {
        "retention": {"name": data["name"], "unit": data["unit"], "mode": data["mode"], "boundary": data["boundary"],
                      "periods": periods, "labels": [label(p) for p in periods], "key_period": key,
                      "key_label": label(key), "source": data["source"], "data_end": data.get("data_end"),
                      "return_events": data.get("return_events")},
        "matrix": [{"cohort": c["cohort"], "size": c["size"],
                    "rates": [None if c["retained"][p] is None else c["retained"][p] / c["size"] for p in periods],
                    "retained": [c["retained"][p] for p in periods]} for c in cohorts],
        "curve": fixed_curve,
        "curve_horizon": horizon,
        "curve_cohorts": [c["cohort"] for c in fixed],
        "curve_all_mature": overall,
        "segment_curves": segment_curves,
        "segment_tests": segment_tests,
        "anomalies": anomalies,
        "comparison": comparison,
        "sensitivity": data.get("sensitivity"),
    }
    result["checks"] = build_checks(data, result)
    result["verdict"] = build_verdict(result)
    return result


def build_checks(data: dict, result: dict) -> list[dict]:
    r = result["retention"]
    checks = []
    immature = sum(1 for row in result["matrix"] for v in row["rates"] if v is None)
    if immature:
        checks.append({"id": "maturity", "status": "info", "title": f"{immature} 个单元格尚未观察完整，已留空",
                       "detail": "未成熟的单元格不是 0；曲线和对比只使用已成熟的单元格"})
    if result["curve_horizon"] < r["periods"][-1]:
        checks.append({"id": "horizon", "status": "info",
                       "title": f"留存曲线只画到 {r['labels'][r['periods'].index(result['curve_horizon'])]}",
                       "detail": "更长周期的成熟批次不到一半，只在留存矩阵中展示，不进入曲线"})
    small = [row["cohort"] for row in result["matrix"] if row["size"] < SMALL_COHORT]
    if small:
        checks.append({"id": "sample", "status": "warn", "title": f"{len(small)} 个 Cohort 不足 {SMALL_COHORT} 人",
                       "detail": "小批次的留存率波动很大，单个批次的高低不要过度解读：" + "、".join(small[:6]) + ("…" if len(small) > 6 else "")})
    for row in result["matrix"]:
        rates = [v for v in row["rates"] if v is not None]
        if r["mode"] == "within" and any(b < a - 1e-9 for a, b in zip(rates, rates[1:])):
            checks.append({"id": "monotonic", "status": "fail", "title": f"Cohort {row['cohort']} 的累计留存出现下降",
                           "detail": "“N 日内回访”口径下留存只能随 N 增加而上升，说明上游统计口径有误"})
            break
    sens = result.get("sensitivity")
    if sens:
        gap = sens["d1"] - sens["d1_other"]
        name = {"natural": "自然日", "rolling": "滚动 24 小时"}
        status = "warn" if abs(gap) >= 0.02 else "info"
        checks.append({"id": "boundary", "status": status,
                       "title": f"D1 口径敏感度：{name[sens['boundary']]} {viz.fmt_pct(sens['d1'], 1)}，{name[sens['other']]} {viz.fmt_pct(sens['d1_other'], 1)}",
                       "detail": f"两种口径相差 {viz.fmt_pp(gap, 1)}。和其他报表对比之前，先确认对方用的是哪种口径"})
    if data["source"] == "summary":
        checks.append({"id": "definition", "status": "info", "title": "汇总数据无法验证成熟度和口径",
                       "detail": "请确认未成熟的单元格填的是 null 而不是 0，并确认 D1 是自然日还是滚动 24 小时"})
    if r["source"] == "events" and not r["return_events"]:
        checks.append({"id": "return_event", "status": "warn", "title": "未指定回访事件，所有事件都算作回访",
                       "detail": "推送到达、后台唤醒等被动事件会虚高留存，建议用 --return-event 指定主动行为"})
    if data.get("timezone_check"):
        checks.append(data["timezone_check"])
    return checks


def build_verdict(result: dict) -> dict:
    r = result["retention"]
    key, key_label = r["key_period"], r["key_label"]
    point = result["curve_all_mature"][r["periods"].index(key)]
    reasons, steps = [], []

    if any(c["id"] == "monotonic" for c in result["checks"]):
        return {"level": "bad", "title": "留存口径错误：累计留存随时间下降", "reasons": ["见数据质量检查"],
                "next_steps": ["修正上游统计口径后重新运行"]}

    comp = result.get("comparison")
    if comp and not comp.get("unavailable"):
        t = comp["test"]
        sig = t["p_value"] < 0.05
        title = (f"{key_label} 留存 {viz.fmt_pct(comp['rate_baseline'], 1)} → {viz.fmt_pct(comp['rate_current'], 1)}"
                 f"（{viz.fmt_pp(t['diff'], 1)}）" + ("" if sig else "，变化未达显著"))
        level = ("bad" if t["diff"] < 0 else "good") if sig else "warning"
        reasons.append(f"{comp['current']} 与 {comp['baseline']} 的差异：p={t['p_value']:.3g}，95% 区间 "
                       f"[{viz.fmt_pp(t['ci'][0], 1)}, {viz.fmt_pp(t['ci'][1], 1)}]")
        for dim, ss in comp["segments"].items():
            total = ss["mix_effect"] + ss["rate_effect"]
            if not total:
                continue
            text = f"按 {dim} 拆：结构效应 {viz.fmt_pp(ss['mix_effect'], 1)}，留存效应 {viz.fmt_pp(ss['rate_effect'], 1)}"
            share = ss["mix_effect"] / total
            if share > 0.4:
                mover = max(ss["rows"], key=lambda x: abs(x["mix_effect"]))
                shift = f"{mover['segment']} 占比 {viz.fmt_pct(mover['share_baseline'], 0)} → {viz.fmt_pct(mover['share_current'], 0)}"
                text += f"；{shift}，批次留存变化主要来自用户构成"
                steps.append(f"弄清 {dim} 构成为什么变了（{shift}）：投放、定价、销售策略还是活动，这更像获客问题而非产品留存问题")
            elif share < 0.4:
                driver = max(ss["rows"], key=lambda x: abs(x["rate_effect"]))
                if driver["rate_current"] is not None and driver["rate_baseline"] is not None:
                    text += f"；主要来自 {driver['segment']} 自身留存 {viz.fmt_pct(driver['rate_baseline'], 1)} → {viz.fmt_pct(driver['rate_current'], 1)}"
                    steps.append(f"排查 {dim}={driver['segment']} 用户在这段时间的产品体验、版本和活动变化")
            reasons.append(text)
    else:
        title = f"{key_label} 留存 {viz.fmt_pct(point['rate'], 1)}（{viz.fmt_num(point['users'])} 名已成熟用户，{point['cohorts']} 个批次）"
        level = "info"
        if comp and comp.get("unavailable"):
            reasons.append(f"对比期中没有已成熟到 {key_label} 的批次，无法对比")

    for dim, tests in result["segment_tests"].items():
        sig = [t for t in tests if t["vs_rest"] and t["vs_rest"]["p_value"] < 0.05]
        if sig:
            low = min(sig, key=lambda t: t["vs_rest"]["diff"])
            if low["vs_rest"]["diff"] < 0:
                reasons.append(f"{dim}={low['segment']} 的 {key_label} 留存 {viz.fmt_pct(low['rate'], 1)}，显著低于其他用户"
                               f"（{viz.fmt_pp(low['vs_rest']['diff'], 1)}）")
                if not any(dim in s for s in steps):
                    steps.append(f"拆解 {dim}={low['segment']} 用户首日做了什么：是否完成关键行为、是否只为领取激励")
    for a in result["anomalies"][:3]:
        direction = "高于" if a["diff"] > 0 else "低于"
        basis = f"按 {a['adjusted_by']} 构成调整后的预期" if a.get("adjusted_by") else "其他批次"
        reasons.append(f"异常批次 {a['cohort']}：{key_label} 留存 {viz.fmt_pct(a['rate'], 1)}，显著{direction}{basis} "
                       f"{viz.fmt_pct(a['expected'], 1)}（{viz.fmt_pp(a['diff'], 1)}）")
        steps.append(f"对照 {a['cohort']} 前后的发版、活动、节假日和投放记录")

    tail = [p["rate"] for p in result["curve"] if p["rate"] is not None]
    if len(tail) >= 3:
        drop = tail[-2] - tail[-1]
        if drop < 0.01:
            reasons.append(f"留存曲线在 {r['labels'][len(tail) - 1]} 附近趋平（{viz.fmt_pct(tail[-1], 1)}），存在稳定的长期用户群")
    if any(c["id"] == "sample" for c in result["checks"]):
        steps.append("批次样本偏小：按周或按月合并 Cohort 后再判断趋势")
    steps.append("分群和批次差异只说明相关；要确认某个改动能提升留存，需要做实验")
    return {"level": level, "title": title, "reasons": reasons, "next_steps": steps}


# ---------------------------------------------------------------------------
# HTML 报告
# ---------------------------------------------------------------------------

def render_html(result: dict) -> str:
    r = result["retention"]
    labels, periods = r["labels"], r["periods"]
    key_idx = periods.index(r["key_period"])
    verdict = result["verdict"]
    comp = result.get("comparison")
    blocks = []

    body = "".join(f"<div>· {viz.esc(x)}</div>" for x in verdict["reasons"])
    blocks.append(viz.callout(verdict["level"], verdict["title"], body, raw_body=True))

    tiles = [{"label": "Cohort 用户", "value": viz.fmt_num(sum(row["size"] for row in result["matrix"])),
              "note": f"{len(result['matrix'])} 个批次"}]
    horizon_idx = periods.index(result["curve_horizon"])
    for idx in sorted({0, key_idx, horizon_idx}):
        point = result["curve_all_mature"][idx]
        tile = {"label": f"{labels[idx]} 留存", "value": viz.fmt_pct(point["rate"], 1) if point["rate"] is not None else "—",
                "note": f"{viz.fmt_num(point['users'])} 名已成熟用户" if point["users"] else "尚无成熟批次"}
        if comp and not comp.get("unavailable") and idx == key_idx:
            sig = comp["test"]["p_value"] < 0.05
            tile["delta"] = f"{viz.arrow(comp['test']['diff'])} {viz.fmt_pp(comp['test']['diff'], 1)} vs {comp['baseline']}" + ("" if sig else "（不显著）")
            tile["tone"] = viz.delta_tone(comp["test"]["diff"], True, sig)
        tiles.append(tile)
    blocks.append(viz.section("核心结果", viz.stat_tiles(tiles)))

    shown = horizon_idx + 1
    series = [{"name": "全部用户", "values": [p["rate"] for p in result["curve"][:shown]], "color": "var(--neutral)"}]
    for dim, curves in list(result["segment_curves"].items())[:1]:
        for k, (value, points) in enumerate(list(curves.items())[:4]):
            series.append({"name": f"{value}", "values": [p["rate"] for p in points[:shown]], "color": f"var(--series-{k + 1})"})
    mode_text = "第 N 期当期有回访" if r["mode"] == "on" else "第 1~N 期内有过回访"
    blocks.append(viz.section(
        "留存曲线",
        viz.line_chart(labels[:shown], series, fmt=lambda v: viz.fmt_pct(v, 0),
                       caption=f"固定使用 {len(result['curve_cohorts'])} 个已观察到 {labels[periods.index(result['curve_horizon'])]} 的批次"
                               f"（{result['curve_cohorts'][0]} 至 {result['curve_cohorts'][-1]}），按规模加权，避免批次构成变化扭曲曲线形状。口径：{mode_text}。"),
        lead="曲线后段趋平，说明有稳定留下来的用户；一路下滑到底，说明还没找到长期价值。",
    ))

    rows = result["matrix"]
    blocks.append(viz.section(
        "留存矩阵",
        viz.heatmap_table([row["cohort"] for row in rows], labels, [row["rates"] for row in rows],
                          row_notes=[viz.fmt_num(row["size"]) for row in rows], note_header="人数", corner="Cohort",
                          caption="颜色在同一列内比较：同一时期里越深代表这个批次留存越好。斜纹格表示尚未观察到，不是 0。"),
    ))

    for dim, tests in result["segment_tests"].items():
        iv = []
        for t in tests:
            vr = t["vs_rest"]
            if not vr:
                continue
            sig = vr["p_value"] < 0.05
            iv.append({"label": t["segment"], "sub": f"{viz.fmt_pct(t['rate'], 1)} · {viz.fmt_num(t['users'])} 人",
                       "estimate": vr["diff"], "low": vr["ci"][0], "high": vr["ci"][1], "tone": viz.delta_tone(vr["diff"], True, sig)})
        if iv:
            blocks.append(viz.section(
                f"按 {dim} 对比 {r['key_label']} 留存",
                viz.interval_chart(iv, fmt=lambda v: viz.fmt_pp(v, 1),
                                   caption="每个分群与其余用户的留存差及 95% 区间；跨过 0 线即不显著。"),
            ))

    if comp and not comp.get("unavailable"):
        overall_sig = comp["test"]["p_value"] < 0.05
        for dim, ss in comp["segments"].items():
            effects = [ss["mix_effect"], ss["rate_effect"]]
            tones = [("bad" if v < 0 else "good") if overall_sig else "neutral" for v in effects]
            seg_rows = [[x["segment"], viz.fmt_pct(x["share_current"], 1), viz.fmt_pct(x["share_baseline"], 1),
                         viz.fmt_pct(x["rate_current"], 1) if x["rate_current"] is not None else "—",
                         viz.fmt_pct(x["rate_baseline"], 1) if x["rate_baseline"] is not None else "—",
                         viz.fmt_pp(x["mix_effect"], 1), viz.fmt_pp(x["rate_effect"], 1)] for x in ss["rows"]]
            blocks.append(viz.section(
                f"{comp['current']} vs {comp['baseline']}：按 {dim} 拆 {r['key_label']} 留存变化",
                viz.diverging_bar_chart(["结构效应（用户构成变化）", "留存效应（分群自身变化）"], effects,
                                        fmt=lambda v: viz.fmt_pp(v, 1), tones=tones,
                                        caption="两项相加等于整体变化。结构效应大，问题更可能在拉新；留存效应大，问题更可能在产品。"),
                viz.table([dim, "本期占比", "对比期占比", "本期留存", "对比期留存", "结构效应", "留存效应"], seg_rows, numeric=(1, 2, 3, 4, 5, 6)),
            ))

    blocks.append(viz.section("数据质量与口径", viz.checklist(result["checks"])))
    blocks.append(viz.section("下一步", viz.checklist([{"status": "info", "title": s} for s in verdict["next_steps"]]),
                              viz.paragraph("方法说明：Cohort 按起点时间分批；单元格只有在批次内所有用户都观察完整后才计算；"
                                            "曲线按批次规模加权；比例区间用 Wilson 方法，差异用双样本比例 z 检验；"
                                            "异常批次与其余批次比较并做 Bonferroni 校正；批次间变化用结构效应 + 留存效应拆解。")))
    unit_text = {"day": "按日", "week": "按周", "month": "按月"}[r["unit"]]
    subtitle = f"{unit_text} Cohort · {mode_text}" + (f" · 数据截至 {r['data_end']}" if r.get("data_end") else "")
    return viz.html_report(r["name"], blocks, subtitle=subtitle, brand="拾穗数据 · 留存分析报告")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _round(obj):
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {str(k): _round(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    return obj


def cmd_analyze(args: argparse.Namespace) -> int:
    if bool(args.summary) == bool(args.events):
        raise SystemExit("--summary 与 --events 二选一")
    if args.period and not args.baseline:
        raise SystemExit("使用 --period 时需要 --baseline 指定对比基准")
    data = load_summary(args.summary) if args.summary else load_events(args)
    if args.name:
        data["name"] = args.name
    result = _round(analyze(data, args.key_period, args.period, args.baseline))
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
    parser = argparse.ArgumentParser(description="留存 / Cohort 计算器（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="计算留存矩阵并生成报告")
    a.add_argument("--summary", help="汇总数据 JSON（见 references/input-schema.md）")
    a.add_argument("--events", help="事件明细 CSV，每行一个事件")
    a.add_argument("--user-col", default="user_id")
    a.add_argument("--event-col", default="event_name")
    a.add_argument("--time-col", default="event_time")
    a.add_argument("--tz", default="+08:00", help="业务时区，带时区的时间会换算到这里，默认 +08:00")
    a.add_argument("--start-event", help="起点事件，多个用 | 分隔；取每个用户最早一次")
    a.add_argument("--start-col", help="改用用户表中的起点时间列（需要 --users）")
    a.add_argument("--return-event", help="回访事件，多个用 | 分隔；不填则任意事件都算回访")
    a.add_argument("--users", help="用户属性 CSV，按 --user-col 关联")
    a.add_argument("--segment", action="append", default=[], help="分群列；有 --users 时取用户属性，否则取起点事件所在行")
    a.add_argument("--unit", choices=["day", "week", "month"], default="day", help="Cohort 和留存周期的粒度")
    a.add_argument("--periods", help="要计算的周期，如 1,3,7,14,30")
    a.add_argument("--mode", choices=["on", "within"], default="on", help="on：第 N 期当期回访；within：第 1~N 期内有过回访")
    a.add_argument("--boundary", choices=["natural", "rolling"], default="natural", help="按日时：natural 自然日；rolling 滚动 24 小时")
    a.add_argument("--data-end", help="数据截止日（含），默认取事件最大时间所在日")
    a.add_argument("--key-period", type=int, help="重点对比的周期，默认 7（或最接近的周期）")
    a.add_argument("--period", action="append", default=[], help="批次分组：名称=开始..结束（按 Cohort 日期）")
    a.add_argument("--baseline", help="作为对比基准的批次分组名称")
    a.add_argument("--name", help="报告标题")
    a.add_argument("--html", help="输出 HTML 报告路径")
    a.add_argument("--json", help="同时把 JSON 写入文件")
    a.set_defaults(func=cmd_analyze)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(sio.run_cli(main))
