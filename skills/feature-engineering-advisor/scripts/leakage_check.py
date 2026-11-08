#!/usr/bin/env python3
"""特征泄漏筛查：时间穿越、单特征异常强、缺失与标签强相关、结果类字段名（仅依赖 Python 标准库）。

  python3 leakage_check.py check --csv features.csv --label churn --asof-col snapshot_time \\
      --feature-time last_login=last_login_time --exclude customer_id

结果只是筛查线索。单特征 AUC 高不等于一定泄漏，要结合特征的生成时间和业务含义确认。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_io as sio  # noqa: E402

TIME = sio.TimeParser()
OUTCOME_NAME = re.compile(r"after|post_|_post|final|result|outcome|label|target|refund|renew|churn|cancel|close|settle|future|之后|结果|最终|未来|退款|续费|流失", re.I)
LEAK_AUC, SUSPECT_AUC, MISSING_GAP = 0.95, 0.85, 0.30
SEVERITY = {"P0": 0, "P1": 1, "P2": 2}


def auc(labels: list[int], scores: list[float]) -> float | None:
    pos = sum(labels)
    neg = len(labels) - pos
    if not pos or not neg:
        return None
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    rank_sum, i = 0.0, 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        average = (i + j) / 2 + 1
        rank_sum += sum(average for k in range(i, j + 1) if labels[order[k]])
        i = j + 1
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def as_number(value: str) -> float | None:
    if sio.is_null(value):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def cmd_check(args: argparse.Namespace) -> int:
    rows = sio.read_csv(args.csv)
    if not rows or args.label not in rows[0]:
        raise SystemExit(f"CSV 为空或缺少标签列：{args.label}")
    feature_time = dict(item.split("=", 1) for item in args.feature_time)
    columns = list(rows[0])
    absent = [c for c in ([args.asof_col] if args.asof_col else []) + list(feature_time.values()) if c not in columns]
    if absent:
        raise SystemExit(f"CSV 缺少列：{'、'.join(absent)}")
    excluded = set(args.exclude) | {args.label} | set(feature_time.values()) | ({args.asof_col} if args.asof_col else set())
    labels = [sio.parse_flag(r[args.label], args.label) for r in rows]
    usable = [(r, int(y)) for r, y in zip(rows, labels) if y is not None]
    if not usable or len({y for _, y in usable}) < 2:
        raise SystemExit("标签只有一类，无法检查")
    n = len(usable)
    y_all = [y for _, y in usable]
    findings, profiles = [], []

    def add(severity: str, feature: str, kind: str, message: str, fix: str) -> None:
        findings.append({"severity": severity, "feature": feature, "kind": kind, "message": message, "fix": fix})

    for name in columns:
        if name in excluded:
            continue
        raw = [r[name] for r, _ in usable]
        missing = [sio.is_null(v) for v in raw]
        distinct = len({v for v, m in zip(raw, missing) if not m})
        profile = {"feature": name, "missing_rate": sum(missing) / n, "distinct": distinct, "single_feature_auc": None}
        profiles.append(profile)
        if distinct <= 1:
            add("P2", name, "constant", "只有一个取值，没有信息量", "删除")
            continue
        present = [i for i, m in enumerate(missing) if not m]
        numbers = [as_number(raw[i]) for i in present]
        if all(v is not None for v in numbers):
            ys = [y_all[i] for i in present]
            score = auc(ys, numbers)
        else:
            # 类别特征：按标签均值编码后算 AUC。高基数时会虚高，下面单独提示
            totals, hits = Counter(), Counter()
            for i in present:
                totals[raw[i]] += 1
                hits[raw[i]] += y_all[i]
            ys = [y_all[i] for i in present]
            score = auc(ys, [hits[raw[i]] / totals[raw[i]] for i in present])
            if distinct >= 0.5 * len(present):
                add("P2", name, "high_cardinality", f"有 {distinct} 个取值，接近 ID，直接使用会过拟合", "删除，或做目标编码并严格按时间切分")
                score = None
        strength = None if score is None else max(score, 1 - score)
        profile["single_feature_auc"] = strength
        if strength is not None and strength >= LEAK_AUC:
            add("P0", name, "too_strong", f"单特征 AUC 达到 {strength:.3f}，几乎能单独预测标签，极可能是标签泄漏", "确认这个字段在预测时间点是否已经可得")
        elif strength is not None and strength >= SUSPECT_AUC:
            add("P1", name, "suspicious_strength", f"单特征 AUC 为 {strength:.3f}，强得不寻常", "确认特征的生成时间和业务含义")
        if 0 < len(present) < n:
            miss_rate = sum(y for y, m in zip(y_all, missing) if m) / sum(missing)
            have_rate = sum(y for y, m in zip(y_all, missing) if not m) / len(present)
            if abs(miss_rate - have_rate) >= MISSING_GAP:
                add("P1", name, "missing_leak", f"缺失样本的正例率 {miss_rate:.1%}，非缺失样本 {have_rate:.1%}，缺失本身高度预测标签", "确认缺失是否由结果导致，例如流失后才不再写入")
        if OUTCOME_NAME.search(name):
            add("P1", name, "outcome_name", "字段名看起来是结果或事后信息", "确认它在预测时间点是否已经产生")

    time_checks = []
    if args.asof_col and feature_time:
        for feature, column in feature_time.items():
            late = checked = 0
            for row, _ in usable:
                asof, event = TIME(row[args.asof_col]), TIME(row[column])
                if asof is None or event is None:
                    continue
                checked += 1
                late += int(event > asof)
            time_checks.append({"feature": feature, "time_column": column, "checked": checked, "after_asof": late})
            if late:
                add("P0", feature, "time_travel", f"{late} / {checked} 行的特征时间晚于预测时间点，模型用到了未来信息", "按预测时间点重新截断特征窗口")
    elif not args.asof_col:
        add("P2", "(整体)", "no_asof", "没有提供预测时间点，无法检查时间穿越", "用 --asof-col 和 --feature-time 补充")

    findings.sort(key=lambda f: (SEVERITY[f["severity"]], f["feature"]))
    counts = Counter(f["severity"] for f in findings)
    if counts["P0"]:
        verdict = {"level": "bad", "title": f"{counts['P0']} 个特征高度疑似泄漏，确认前不要用它们训练或评估"}
    elif counts["P1"]:
        verdict = {"level": "warning", "title": f"{counts['P1']} 个特征需要人工确认"}
    else:
        verdict = {"level": "good", "title": "没有发现明显泄漏线索；这不能证明没有泄漏，时间口径仍需人工确认"}
    profiles.sort(key=lambda p: -(p["single_feature_auc"] or 0))
    result = {"samples": n, "positive_rate": sum(y_all) / n, "summary": dict(counts), "findings": findings, "time_checks": time_checks,
              "features": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in p.items()} for p in profiles], "verdict": verdict,
              "limits": ["单特征检查发现不了多个特征组合造成的泄漏", "必须结合特征生成时间和业务含义确认"]}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="特征泄漏筛查（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="检查特征表")
    c.add_argument("--csv", required=True, help="特征表 CSV，一行一个样本")
    c.add_argument("--label", required=True, help="标签列")
    c.add_argument("--asof-col", help="预测时间点列")
    c.add_argument("--feature-time", action="append", default=[], help="特征=该特征的生成时间列，可重复")
    c.add_argument("--exclude", action="append", default=[], help="不参与检查的列，如 ID")
    c.add_argument("--tz", default="+08:00", help="业务时区，默认 +08:00")
    c.add_argument("--json", help="同时把 JSON 写入文件")
    c.set_defaults(func=cmd_check)
    args = parser.parse_args()
    TIME.configure(args.tz)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(sio.run_cli(main))
