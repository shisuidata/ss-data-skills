#!/usr/bin/env python3
"""模型评估计算器：分类、回归、排序指标，校准、阈值收益、基线对比、分布漂移（仅依赖 Python 标准库）。

  python3 eval_metrics.py classify --csv preds.csv --label y --score p --top 0.05,0.2 --baseline-col old_p \\
      --benefit-tp 300 --cost-fp 20 --time-col dt --html eval.html
  python3 eval_metrics.py regress --csv preds.csv --y y --pred yhat --baseline-col old_yhat
  python3 eval_metrics.py rank --csv preds.csv --query q --relevance r --score s --k 10
  python3 eval_metrics.py psi --base train.csv --current online.csv --col score

脚本只负责把数算对。测试集是否泄露、指标是否匹配业务，由 Agent 按 SKILL.md 的审查框架判断。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from collections import Counter, defaultdict
from statistics import NormalDist

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_viz as viz  # noqa: E402
import sskit_io as sio  # noqa: E402

BOOTSTRAP_LIMIT = 50000
TIME = sio.TimeParser()


def _round(obj):
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    return obj


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


def _require(rows: list[dict], columns: list[str]) -> None:
    if not rows:
        raise SystemExit("CSV 为空")
    absent = [c for c in columns if c and c not in rows[0]]
    if absent:
        raise SystemExit(f"CSV 缺少列：{'、'.join(absent)}（现有列：{list(rows[0])}）")


def auc(labels: list[int], scores: list[float]) -> float | None:
    """Mann–Whitney 秩和，平局取平均秩。"""
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


def average_precision(labels: list[int], scores: list[float]) -> float | None:
    pos = sum(labels)
    if not pos:
        return None
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    hits, total = 0, 0.0
    for rank, i in enumerate(order, 1):
        if labels[i]:
            hits += 1
            total += hits / rank
    return total / pos


def _bootstrap(labels: list[int], scores: list[float], baseline: list[float] | None, times: int, seed: int) -> dict:
    n = len(labels)
    rng = random.Random(seed)
    if n > BOOTSTRAP_LIMIT:
        chosen = rng.sample(range(n), BOOTSTRAP_LIMIT)
        labels, scores = [labels[i] for i in chosen], [scores[i] for i in chosen]
        baseline = [baseline[i] for i in chosen] if baseline else None
        n = BOOTSTRAP_LIMIT
    aucs, aps, deltas = [], [], []
    for _ in range(times):
        picks = [rng.randrange(n) for _ in range(n)]
        y = [labels[i] for i in picks]
        s = [scores[i] for i in picks]
        a = auc(y, s)
        if a is None:
            continue
        aucs.append(a)
        aps.append(average_precision(y, s))
        if baseline:
            b = auc(y, [baseline[i] for i in picks])
            if b is not None:
                deltas.append(a - b)

    def ci(values: list[float]) -> list[float] | None:
        if len(values) < 20:
            return None
        ordered = sorted(values)
        return [ordered[int(0.025 * len(ordered))], ordered[int(0.975 * len(ordered)) - 1]]
    return {"auc_ci": ci(aucs), "pr_auc_ci": ci(aps), "delta_auc_ci": ci(deltas) if baseline else None}


def _calibration(labels: list[int], scores: list[float], bins: int = 10) -> dict:
    buckets = defaultdict(lambda: [0, 0.0, 0])
    for y, s in zip(labels, scores):
        b = min(int(s * bins), bins - 1)
        buckets[b][0] += 1
        buckets[b][1] += s
        buckets[b][2] += y
    rows, ece, n = [], 0.0, len(labels)
    for b in sorted(buckets):
        count, total, hits = buckets[b]
        mean_p, rate = total / count, hits / count
        ece += count / n * abs(mean_p - rate)
        rows.append({"bin": f"{b / bins:.1f}-{(b + 1) / bins:.1f}", "n": count, "mean_score": mean_p, "observed_rate": rate})
    return {"ece": ece, "bins": rows}


def _top_k(labels: list[int], scores: list[float], shares: list[float]) -> list[dict]:
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    n, pos = len(labels), sum(labels)
    out = []
    for share in shares:
        k = max(1, int(round(n * share)))
        hits = sum(labels[i] for i in order[:k])
        out.append({"top_share": share, "k": k, "precision": hits / k, "recall": hits / pos if pos else None,
                    "lift": (hits / k) / (pos / n) if pos else None, "threshold": scores[order[k - 1]]})
    return out


def _confusion(labels: list[int], scores: list[float], threshold: float) -> dict:
    tp = sum(1 for y, s in zip(labels, scores) if y and s >= threshold)
    fp = sum(1 for y, s in zip(labels, scores) if not y and s >= threshold)
    fn = sum(1 for y, s in zip(labels, scores) if y and s < threshold)
    tn = len(labels) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    return {"threshold": threshold, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1,
            "coverage": (tp + fp) / len(labels)}


def _best_profit(labels: list[int], scores: list[float], benefit: float, cost: float) -> dict:
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    best = {"profit": 0.0, "k": 0, "threshold": None}
    profit = 0.0
    for rank, i in enumerate(order, 1):
        profit += benefit if labels[i] else -cost
        if (rank == len(order) or scores[order[rank]] != scores[i]) and profit > best["profit"]:
            best = {"profit": profit, "k": rank, "threshold": scores[i]}
    best["coverage"] = best["k"] / len(labels)
    best["benefit_tp"], best["cost_fp"] = benefit, cost
    return best


def cmd_classify(args: argparse.Namespace) -> int:
    rows = sio.read_csv(args.csv)
    _require(rows, [args.label, args.score, args.baseline_col, args.time_col])
    labels, scores, baseline, times, dropped = [], [], [] if args.baseline_col else None, [], 0
    for row in rows:
        y, s = sio.parse_flag(row[args.label], args.label), sio.parse_number(row[args.score], args.score)
        b = sio.parse_number(row[args.baseline_col], args.baseline_col) if args.baseline_col else 0.0
        if y is None or s is None or b is None:
            dropped += 1
            continue
        labels.append(int(y))
        scores.append(s)
        if baseline is not None:
            baseline.append(b)
        if args.time_col:
            moment = TIME(row[args.time_col])
            times.append(moment)
    n, pos = len(labels), sum(labels)
    if not pos or pos == n:
        raise SystemExit("标签只有一类，无法评估")
    shares = [float(x) for x in args.top.split(",")]
    result: dict = {"n": n, "dropped": dropped, "positive": pos, "positive_rate": pos / n,
                    "auc": auc(labels, scores), "pr_auc": average_precision(labels, scores),
                    "pr_auc_baseline_random": pos / n, "top_k": _top_k(labels, scores, shares)}
    checks = []
    bounded = all(0 <= s <= 1 for s in scores)
    if bounded:
        result["brier"] = sum((s - y) ** 2 for s, y in zip(scores, labels)) / n
        eps = 1e-15
        result["log_loss"] = -sum(y * math.log(max(s, eps)) + (1 - y) * math.log(max(1 - s, eps)) for s, y in zip(scores, labels)) / n
        result["calibration"] = _calibration(labels, scores)
        if result["calibration"]["ece"] > 0.05:
            checks.append({"id": "calibration", "status": "warn", "title": f"校准偏差较大（ECE={result['calibration']['ece']:.3f}）",
                           "detail": "分数不能直接当概率用；业务要按概率计算收益时先做校准"})
    else:
        checks.append({"id": "calibration", "status": "info", "title": "分数不在 0 到 1 之间，跳过校准和 log loss"})
    if args.bootstrap:
        result.update(_bootstrap(labels, scores, baseline, args.bootstrap, args.seed))
    if baseline is not None:
        result["baseline"] = {"auc": auc(labels, baseline), "pr_auc": average_precision(labels, baseline),
                              "top_k": _top_k(labels, baseline, shares)}
        result["delta_auc"] = result["auc"] - result["baseline"]["auc"]
        ci = result.get("delta_auc_ci")
        if ci and ci[0] <= 0 <= ci[1]:
            checks.append({"id": "delta_auc", "status": "warn", "title": "相对基线的 AUC 提升在 95% 区间内包含 0", "detail": "这个测试集上无法确认新模型更好"})
    if args.threshold is not None:
        result["at_threshold"] = _confusion(labels, scores, args.threshold)
    if args.benefit_tp is not None and args.cost_fp is not None:
        result["best_profit"] = _best_profit(labels, scores, args.benefit_tp, args.cost_fp)
    if args.time_col:
        periods = defaultdict(list)
        for i, moment in enumerate(times):
            if moment is not None:
                key = moment.strftime("%Y-%m") if args.time_unit == "month" else f"{moment.isocalendar()[0]}-W{moment.isocalendar()[1]:02d}"
                periods[key].append(i)
        stability = [{"period": k, "n": len(ix), "positive_rate": sum(labels[i] for i in ix) / len(ix),
                      "auc": auc([labels[i] for i in ix], [scores[i] for i in ix])} for k, ix in sorted(periods.items())]
        result["by_period"] = stability
        values = [p["auc"] for p in stability if p["auc"] is not None]
        if len(values) >= 2 and max(values) - min(values) > 0.05:
            checks.append({"id": "stability", "status": "warn", "title": f"不同时期 AUC 相差 {max(values) - min(values):.3f}", "detail": "模型表现随时间波动，检查是否存在漂移或测试集构造差异"})
    if pos / n < 0.05:
        checks.append({"id": "imbalance", "status": "warn", "title": f"正样本只占 {viz.fmt_pct(pos / n, 1)}", "detail": "AUC 在严重不均衡时容易显得很高，决策应看 PR-AUC 和 Top-K 精确率"})
    if pos < 100:
        checks.append({"id": "positives", "status": "warn", "title": f"正样本只有 {pos} 个", "detail": "指标波动很大，结论只能作为方向参考"})
    if len(set(scores)) <= 1:
        checks.append({"id": "constant", "status": "fail", "title": "所有分数相同", "detail": "模型输出可能有问题"})
    result["checks"] = checks
    result["limits"] = ["这里只计算指标，不判断测试集是否泄露", "分数高不等于线上业务改善，需要 A/B 实验验证"]
    return _emit(result, args, _classify_html(result, args) if args.html else None)


def _classify_html(result: dict, args: argparse.Namespace) -> str:
    blocks = [viz.section("核心指标", viz.stat_tiles([
        {"label": "AUC", "value": f"{result['auc']:.3f}", "note": f"基线 {result['baseline']['auc']:.3f}" if result.get("baseline") else None},
        {"label": "PR-AUC", "value": f"{result['pr_auc']:.3f}", "note": f"随机水平 {result['pr_auc_baseline_random']:.3f}"},
        {"label": "正样本占比", "value": viz.fmt_pct(result["positive_rate"], 2), "note": f"n = {viz.fmt_num(result['n'])}"}]))]
    rows = [[viz.fmt_pct(t["top_share"], 0), viz.fmt_num(t["k"]), viz.fmt_pct(t["precision"], 1), viz.fmt_pct(t["recall"], 1), f"{t['lift']:.2f}"] for t in result["top_k"]]
    blocks.append(viz.section("Top-K 表现", viz.table(["覆盖比例", "样本数", "精确率", "召回率", "Lift"], rows, numeric=(1, 2, 3, 4))))
    if result.get("calibration"):
        cal = result["calibration"]["bins"]
        blocks.append(viz.section("校准", viz.line_chart([c["bin"] for c in cal], [{"name": "预测均值", "values": [c["mean_score"] for c in cal]},
                                                                                   {"name": "实际比例", "values": [c["observed_rate"] for c in cal]}],
                                                       fmt=lambda v: viz.fmt_pct(v, 0), caption="两条线越接近，分数越能当概率用。")))
    if result["checks"]:
        blocks.append(viz.section("检查项", viz.checklist(result["checks"])))
    return viz.html_report(args.name or "模型评估", blocks, brand="拾穗数据 · 模型评估")


def cmd_regress(args: argparse.Namespace) -> int:
    rows = sio.read_csv(args.csv)
    _require(rows, [args.y, args.pred, args.baseline_col])

    def metrics(ys: list[float], ps: list[float]) -> dict:
        n = len(ys)
        errors = [p - y for y, p in zip(ys, ps)]
        mean_y = sum(ys) / n
        ss_tot = sum((y - mean_y) ** 2 for y in ys)
        nonzero = [(y, p) for y, p in zip(ys, ps) if y != 0]
        return {"n": n, "rmse": math.sqrt(sum(e * e for e in errors) / n), "mae": sum(abs(e) for e in errors) / n,
                "mape": sum(abs((p - y) / y) for y, p in nonzero) / len(nonzero) if nonzero else None,
                "mape_excluded_zero": n - len(nonzero), "bias": sum(errors) / n,
                "r2": 1 - sum(e * e for e in errors) / ss_tot if ss_tot else None}

    triples = [(sio.parse_number(r[args.y], args.y), sio.parse_number(r[args.pred], args.pred),
                sio.parse_number(r[args.baseline_col], args.baseline_col) if args.baseline_col else 0.0) for r in rows]
    triples = [t for t in triples if None not in t]
    if not triples:
        raise SystemExit("没有有效样本")
    result = {"model": metrics([t[0] for t in triples], [t[1] for t in triples]), "dropped": len(rows) - len(triples), "checks": []}
    if args.baseline_col:
        result["baseline"] = metrics([t[0] for t in triples], [t[2] for t in triples])
        result["rmse_improvement"] = 1 - result["model"]["rmse"] / result["baseline"]["rmse"] if result["baseline"]["rmse"] else None
    if result["model"]["mape_excluded_zero"]:
        result["checks"].append({"id": "mape_zero", "status": "warn", "title": f"{result['model']['mape_excluded_zero']} 个真实值为 0，已从 MAPE 中排除", "detail": "销量、金额类长尾指标建议同时看 MAE 或 WAPE"})
    bias_ratio = abs(result["model"]["bias"]) / result["model"]["mae"] if result["model"]["mae"] else 0
    if bias_ratio > 0.3:
        result["checks"].append({"id": "bias", "status": "warn", "title": "预测存在系统性偏差", "detail": "偏差占 MAE 的比例较高，检查标签定义或样本时间窗"})
    return _emit(result, args)


def cmd_rank(args: argparse.Namespace) -> int:
    rows = sio.read_csv(args.csv)
    _require(rows, [args.query, args.relevance, args.score])
    groups = defaultdict(list)
    for r in rows:
        rel, score = sio.parse_number(r[args.relevance], args.relevance), sio.parse_number(r[args.score], args.score)
        if rel is not None and score is not None:
            groups[r[args.query]].append((score, rel))

    def dcg(values: list[float]) -> float:
        return sum((2 ** v - 1) / math.log2(i + 2) for i, v in enumerate(values))

    ndcgs, mrrs, recalls = [], [], []
    no_relevant = 0
    for items in groups.values():
        ordered = [rel for _, rel in sorted(items, key=lambda x: -x[0])]
        relevant = sum(1 for rel in ordered if rel > 0)
        if not relevant:
            no_relevant += 1
            continue
        ideal = dcg(sorted(ordered, reverse=True)[: args.k])
        ndcgs.append(dcg(ordered[: args.k]) / ideal if ideal else 0.0)
        first = next((i for i, rel in enumerate(ordered, 1) if rel > 0), None)
        mrrs.append(1 / first if first else 0.0)
        recalls.append(sum(1 for rel in ordered[: args.k] if rel > 0) / relevant)
    if not ndcgs:
        raise SystemExit("没有任何查询包含相关结果")
    checks = []
    if no_relevant:
        checks.append({"id": "no_relevant", "status": "warn", "title": f"{no_relevant} 个查询没有相关结果，已排除", "detail": "排除后指标偏乐观，冷启动用户或长尾查询要单独评估"})
    return _emit({"queries": len(ndcgs), "excluded_queries": no_relevant, "k": args.k, f"ndcg@{args.k}": sum(ndcgs) / len(ndcgs),
                  "mrr": sum(mrrs) / len(mrrs), f"recall@{args.k}": sum(recalls) / len(recalls), "checks": checks}, args)


def cmd_psi(args: argparse.Namespace) -> int:
    base_rows, cur_rows = sio.read_csv(args.base), sio.read_csv(args.current)
    _require(base_rows, [args.col])
    _require(cur_rows, [args.col])
    base_raw, cur_raw = [r[args.col] for r in base_rows if not sio.is_null(r[args.col])], [r[args.col] for r in cur_rows if not sio.is_null(r[args.col])]

    def numeric(values: list[str]) -> list[float] | None:
        try:
            return [float(v) for v in values]
        except ValueError:
            return None

    base_num, cur_num = numeric(base_raw), numeric(cur_raw)
    if base_num is not None and cur_num is not None and len(set(base_num)) > args.bins:
        ordered = sorted(base_num)
        cuts = sorted({ordered[int(len(ordered) * i / args.bins)] for i in range(1, args.bins)})

        def bucket(x: float) -> int:
            return sum(1 for c in cuts if x > c)
        base_counts, cur_counts = Counter(bucket(x) for x in base_num), Counter(bucket(x) for x in cur_num)
        labels = list(range(len(cuts) + 1))
        kind = "numeric"
    else:
        base_counts, cur_counts = Counter(base_raw), Counter(cur_raw)
        labels = sorted(set(base_counts) | set(cur_counts), key=str)
        kind = "categorical"
    total_base, total_cur = sum(base_counts.values()), sum(cur_counts.values())
    eps = 1e-4
    psi, rows = 0.0, []
    for label in labels:
        a = max(base_counts.get(label, 0) / total_base, eps)
        b = max(cur_counts.get(label, 0) / total_cur, eps)
        contribution = (b - a) * math.log(b / a)
        psi += contribution
        rows.append({"bin": label, "base_share": a, "current_share": b, "psi": contribution})
    level, title = ("good", "分布稳定") if psi < 0.1 else (("warning", "存在一定漂移，需要观察") if psi < 0.25 else ("bad", "分布显著漂移，模型结果可能不再可靠"))
    return _emit({"column": args.col, "kind": kind, "psi": psi, "bins": rows, "verdict": {"level": level, "title": f"PSI={psi:.3f}，{title}"},
                  "thresholds": "PSI < 0.1 稳定；0.1–0.25 轻度漂移；> 0.25 显著漂移（经验阈值）"}, args)


def main() -> int:
    parser = argparse.ArgumentParser(description="模型评估计算器（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("classify", help="二分类：AUC、PR-AUC、Top-K、校准、阈值收益、基线对比")
    c.add_argument("--csv", required=True, help="预测结果 CSV，一行一个样本")
    c.add_argument("--label", required=True, help="真实标签列")
    c.add_argument("--score", required=True, help="模型分数列")
    c.add_argument("--baseline-col", help="基线模型分数列")
    c.add_argument("--top", default="0.05,0.1,0.2,0.3", help="Top-K 覆盖比例，逗号分隔")
    c.add_argument("--threshold", type=float, help="评估某个固定阈值")
    c.add_argument("--benefit-tp", type=float, help="命中一个正样本的收益")
    c.add_argument("--cost-fp", type=float, help="误判一个负样本的成本")
    c.add_argument("--time-col", help="时间列，用于检查不同时期的稳定性")
    c.add_argument("--time-unit", choices=["week", "month"], default="month")
    c.add_argument("--bootstrap", type=int, default=200, help="Bootstrap 次数，0 表示跳过")
    c.add_argument("--seed", type=int, default=42)
    c.add_argument("--name", help="报告标题")
    c.add_argument("--html", help="输出 HTML 报告路径")
    c.add_argument("--json", help="同时把 JSON 写入文件")
    c.set_defaults(func=cmd_classify)

    r = sub.add_parser("regress", help="回归：RMSE、MAE、MAPE、偏差、R²")
    r.add_argument("--csv", required=True)
    r.add_argument("--y", required=True, help="真实值列")
    r.add_argument("--pred", required=True, help="预测值列")
    r.add_argument("--baseline-col", help="基线预测列")
    r.add_argument("--json", help="同时把 JSON 写入文件")
    r.add_argument("--html", help=argparse.SUPPRESS)
    r.set_defaults(func=cmd_regress)

    k = sub.add_parser("rank", help="排序或推荐：NDCG@K、MRR、Recall@K")
    k.add_argument("--csv", required=True)
    k.add_argument("--query", required=True, help="查询或用户列")
    k.add_argument("--relevance", required=True, help="相关度列，0 表示不相关")
    k.add_argument("--score", required=True, help="排序分数列")
    k.add_argument("--k", type=int, default=10)
    k.add_argument("--json", help="同时把 JSON 写入文件")
    k.add_argument("--html", help=argparse.SUPPRESS)
    k.set_defaults(func=cmd_rank)

    p = sub.add_parser("psi", help="分布漂移：训练集和线上数据的 PSI")
    p.add_argument("--base", required=True, help="基准数据 CSV")
    p.add_argument("--current", required=True, help="当前数据 CSV")
    p.add_argument("--col", required=True, help="要比较的列")
    p.add_argument("--bins", type=int, default=10)
    p.add_argument("--json", help="同时把 JSON 写入文件")
    p.add_argument("--html", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_psi)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(sio.run_cli(main))
