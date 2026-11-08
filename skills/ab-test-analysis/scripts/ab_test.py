#!/usr/bin/env python3
"""A/B 实验计算器：显著性、置信区间、SRM、功效、CUPED、样本量规划（仅依赖 Python 标准库）。

两个子命令：

  analyze  解读实验结果，输出 JSON（给 Agent 读）和可选的 HTML 报告（给人看）
  plan     实验前规划：给定基线和最小可检测效应，算每组样本量和需要跑几天

示例：
  python3 ab_test.py analyze --summary experiment.json --html report.html
  python3 ab_test.py analyze --csv users.csv --variant-col group --control A \\
      --metric paid:proportion --metric gmv:mean --guardrail refund:proportion:lower \\
      --cuped gmv=pre_gmv --days 14 --html report.html
  python3 ab_test.py analyze --csv users.csv --metric clicks/views:ratio --allocation A=0.9,B=0.1 --days 14
  python3 ab_test.py plan --baseline 0.07 --mde-rel 0.05 --daily-users 6000

输入格式见 ../references/input-schema.md。数字全部由脚本计算，不要在报告里手算替换。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from statistics import NormalDist

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_viz as viz  # noqa: E402
import sskit_io as sio  # noqa: E402

N = NormalDist()
SRM_ALPHA = 0.001
TWYMAN_REL = 0.30
ALLOCATION_SKEW = 0.10
METRIC_TYPES = ("proportion", "mean", "ratio")
SUMMARY_FIELDS = {"proportion": ("successes",), "mean": ("mean", "std"),
                  "ratio": ("num_mean", "den_mean", "num_std", "den_std", "cov")}
# 这些检查未通过时，主指标显著也不能给出 ship
VALIDITY_BLOCKERS = {
    "duration": "按整周跑满计划周期后重新运行本脚本",
    "peeking": "跑满计划周期后再复核，不要因为中期显著而放量",
    "early_stop": "用独立一轮实验或完整周期复验，提前停止的结果不能直接放量",
    "twyman": "先排查埋点、口径和分流，确认提升不是数据问题",
    "sample": "扩大样本后重新判断，小样本的显著结果很不稳定",
    "guardrail": "扩大样本或与业务确认容忍度，直到能证明护栏恶化没有超过容忍度",
}
EPS = 3e-14
FPMIN = 1e-300


# ---------------------------------------------------------------------------
# 分布函数（标准库没有 t / 卡方分布，这里用 Numerical Recipes 的连分式实现）
# ---------------------------------------------------------------------------

def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > FPMIN else FPMIN)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > FPMIN else FPMIN)
        c = 1 + aa / c
        c = c if abs(c) > FPMIN else FPMIN
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > FPMIN else FPMIN)
        c = 1 + aa / c
        c = c if abs(c) > FPMIN else FPMIN
        delta = d * c
        h *= delta
        if abs(delta - 1) < EPS:
            break
    return h


def betai(a: float, b: float, x: float) -> float:
    """正则化不完全 Beta 函数 I_x(a, b)。"""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    log_front = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(log_front) * _betacf(a, b, x) / a
    return 1 - math.exp(log_front) * _betacf(b, a, 1 - x) / b


def t_two_sided_p(t: float, df: float) -> float:
    if df > 1e7:
        return 2 * (1 - N.cdf(abs(t)))
    return betai(df / 2, 0.5, df / (df + t * t))


def t_ppf(q: float, df: float) -> float:
    """t 分布分位数（q > 0.5），二分法求解。"""
    if df > 1e7:
        return N.inv_cdf(q)
    target = 2 * (1 - q)
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_two_sided_p(mid, df) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def chi2_sf(x: float, k: int) -> float:
    """卡方分布上尾概率，即正则化上不完全 Gamma 函数 Q(k/2, x/2)。"""
    a, x = k / 2, x / 2
    if x <= 0:
        return 1.0
    log_front = -x + a * math.log(x) - math.lgamma(a)
    if x < a + 1:
        ap, total, term = a, 1 / a, 1 / a
        for _ in range(1000):
            ap += 1
            term *= x / ap
            total += term
            if abs(term) < abs(total) * EPS:
                break
        return 1 - total * math.exp(log_front)
    b = x + 1 - a
    c, d = 1 / FPMIN, 1 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1 / (d if abs(d) > FPMIN else FPMIN)
        c = b + an / c
        c = c if abs(c) > FPMIN else FPMIN
        delta = d * c
        h *= delta
        if abs(delta - 1) < EPS:
            break
    return math.exp(log_front) * h


def holm(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted = [0.0] * len(p_values)
    running = 0.0
    m = len(p_values)
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted


# ---------------------------------------------------------------------------
# 检验与样本量
# ---------------------------------------------------------------------------

def compare_proportion(sa: int, na: int, sb: int, nb: int, alpha: float, power: float) -> dict:
    pa, pb = sa / na, sb / nb
    diff = pb - pa
    pooled = (sa + sb) / (na + nb)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / na + 1 / nb))
    se = math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)
    z = diff / se_pooled if se_pooled > 0 else 0.0
    p_value = 2 * (1 - N.cdf(abs(z)))
    crit = N.inv_cdf(1 - alpha / 2)
    rel, rel_low, rel_high = None, None, None
    if pa > 0 and pb > 0:
        rel = pb / pa - 1
        se_log = math.sqrt((1 - pa) / (na * pa) + (1 - pb) / (nb * pb))
        rel_low = math.exp(math.log(pb / pa) - crit * se_log) - 1
        rel_high = math.exp(math.log(pb / pa) + crit * se_log) - 1
    mde_abs = (crit + N.inv_cdf(power)) * se_pooled
    return {
        "control_value": pa, "treatment_value": pb, "abs_diff": diff,
        "ci_abs": [diff - crit * se, diff + crit * se],
        "rel_lift": rel, "ci_rel": [rel_low, rel_high] if rel is not None else None,
        "statistic": z, "test": "双样本比例 z 检验", "p_value": p_value,
        "mde_abs": mde_abs, "mde_rel": mde_abs / pa if pa > 0 else None,
        "control_ci": _wilson(sa, na, crit), "treatment_ci": _wilson(sb, nb, crit),
    }


def _wilson(s: int, n: int, z: float) -> list[float]:
    p = s / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [centre - half, centre + half]


def compare_mean(ma: float, sa: float, na: int, mb: float, sb: float, nb: int, alpha: float, power: float) -> dict:
    va, vb = sa * sa / na, sb * sb / nb
    se = math.sqrt(va + vb)
    diff = mb - ma
    df = (va + vb) ** 2 / ((va * va) / (na - 1) + (vb * vb) / (nb - 1)) if se > 0 else float(na + nb - 2)
    t = diff / se if se > 0 else 0.0
    p_value = t_two_sided_p(t, df)
    crit = t_ppf(1 - alpha / 2, df)
    rel, ci_rel = None, None
    if ma > 0 and mb > 0:
        rel = mb / ma - 1
        se_log = math.sqrt(va / (ma * ma) + vb / (mb * mb))
        ci_rel = [math.exp(math.log(mb / ma) - crit * se_log) - 1, math.exp(math.log(mb / ma) + crit * se_log) - 1]
    mde_abs = (N.inv_cdf(1 - alpha / 2) + N.inv_cdf(power)) * se
    return {
        "control_value": ma, "treatment_value": mb, "abs_diff": diff,
        "ci_abs": [diff - crit * se, diff + crit * se],
        "rel_lift": rel, "ci_rel": ci_rel,
        "statistic": t, "df": df, "test": "Welch t 检验", "p_value": p_value,
        "mde_abs": mde_abs, "mde_rel": mde_abs / ma if ma > 0 else None,
        "control_ci": [ma - crit * math.sqrt(va), ma + crit * math.sqrt(va)],
        "treatment_ci": [mb - crit * math.sqrt(vb), mb + crit * math.sqrt(vb)],
    }


def _ratio_stats(d: dict, n: int) -> tuple[float, float]:
    """比率 = 分子均值 / 分母均值。分子分母都随用户波动，用 delta 方法估计比率的方差。"""
    den = float(d["den_mean"])
    if den <= 0:
        raise SystemExit("比率指标的分母均值必须大于 0")
    ratio = float(d["num_mean"]) / den
    var = (float(d["num_std"]) ** 2 - 2 * ratio * float(d["cov"]) + ratio * ratio * float(d["den_std"]) ** 2) / (n * den * den)
    return ratio, max(var, 0.0)


def compare_ratio(a: dict, na: int, b: dict, nb: int, alpha: float, power: float) -> dict:
    ra, va = _ratio_stats(a, na)
    rb, vb = _ratio_stats(b, nb)
    se = math.sqrt(va + vb)
    diff = rb - ra
    z = diff / se if se > 0 else 0.0
    p_value = 2 * (1 - N.cdf(abs(z)))
    crit = N.inv_cdf(1 - alpha / 2)
    rel, ci_rel = None, None
    if ra > 0 and rb > 0:
        rel = rb / ra - 1
        se_log = math.sqrt(va / (ra * ra) + vb / (rb * rb))
        ci_rel = [math.exp(math.log(rb / ra) - crit * se_log) - 1, math.exp(math.log(rb / ra) + crit * se_log) - 1]
    mde_abs = (crit + N.inv_cdf(power)) * se
    return {
        "control_value": ra, "treatment_value": rb, "abs_diff": diff,
        "ci_abs": [diff - crit * se, diff + crit * se],
        "rel_lift": rel, "ci_rel": ci_rel,
        "statistic": z, "test": "比率指标 delta 方法 z 检验", "p_value": p_value,
        "mde_abs": mde_abs, "mde_rel": mde_abs / ra if ra > 0 else None,
        "control_ci": [ra - crit * math.sqrt(va), ra + crit * math.sqrt(va)],
        "treatment_ci": [rb - crit * math.sqrt(vb), rb + crit * math.sqrt(vb)],
    }


def n_per_group_proportion(p1: float, p2: float, alpha: float, power: float) -> int:
    za, zb = N.inv_cdf(1 - alpha / 2), N.inv_cdf(power)
    pbar = (p1 + p2) / 2
    numerator = za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return math.ceil(numerator ** 2 / (p2 - p1) ** 2)


def n_per_group_mean(std: float, delta: float, alpha: float, power: float) -> int:
    za, zb = N.inv_cdf(1 - alpha / 2), N.inv_cdf(power)
    return math.ceil(2 * (za + zb) ** 2 * std * std / (delta * delta))


def srm_test(groups: dict, allocation: dict) -> dict:
    total = sum(g["users"] for g in groups.values())
    share_total = sum(allocation.values())
    chi2, rows = 0.0, []
    for name, g in groups.items():
        expected = total * allocation[name] / share_total
        chi2 += (g["users"] - expected) ** 2 / expected
        rows.append({"group": name, "observed": g["users"], "expected": expected,
                     "observed_share": g["users"] / total, "expected_share": allocation[name] / share_total})
    p_value = chi2_sf(chi2, len(groups) - 1)
    return {"chi2": chi2, "p_value": p_value, "threshold": SRM_ALPHA,
            "status": "fail" if p_value < SRM_ALPHA else "pass", "groups": rows}


# ---------------------------------------------------------------------------
# 输入
# ---------------------------------------------------------------------------

def load_summary(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        spec = json.load(handle)
    for key in ("groups", "metrics"):
        if key not in spec:
            raise SystemExit(f"输入缺少字段：{key}")
    spec.setdefault("control", next(iter(spec["groups"])))
    if spec["control"] not in spec["groups"]:
        raise SystemExit(f"control={spec['control']} 不在 groups 中")
    for metric in spec["metrics"]:
        kind = metric.get("type", "proportion")
        if kind not in METRIC_TYPES:
            raise SystemExit(f"指标 {metric.get('name')} 的 type 应为 {' / '.join(METRIC_TYPES)}，收到：{kind}")
        for group in spec["groups"]:
            row = (metric.get("data") or {}).get(group)
            if row is None:
                raise SystemExit(f"指标 {metric.get('name')} 缺少分组 {group} 的数据")
            missing = [f for f in SUMMARY_FIELDS[kind] if f not in row]
            if missing:
                raise SystemExit(f"指标 {metric.get('name')} 的分组 {group} 缺少字段：{'、'.join(missing)}")
    return spec


def _parse_metric(text: str, role: str) -> dict:
    parts = text.split(":")
    if len(parts) < 2 or parts[1] not in METRIC_TYPES:
        raise SystemExit(f"指标格式应为 列名:proportion|mean[:higher|lower] 或 分子列/分母列:ratio[:higher|lower]，收到：{text}")
    direction = parts[2] if len(parts) > 2 else "higher"
    metric = {"name": parts[0], "column": parts[0], "type": parts[1], "role": role, "higher_is_better": direction != "lower"}
    if parts[1] == "ratio":
        numerator, _, denominator = parts[0].partition("/")
        if not numerator or not denominator:
            raise SystemExit(f"比率指标应写成 分子列/分母列:ratio，收到：{text}")
        metric.update({"column": numerator, "denominator": denominator})
    return metric


def _ratio_data(rows: list[dict], variant_col: str, groups: dict, numerator: str, denominator: str) -> dict:
    if denominator not in rows[0]:
        raise SystemExit(f"CSV 缺少分母列：{denominator}")
    data = {}
    for name in groups:
        pairs = [(sio.parse_number(r[numerator], numerator), sio.parse_number(r[denominator], denominator))
                 for r in rows if r[variant_col] == name]
        pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
        n = len(pairs)
        if n < 2:
            raise SystemExit(f"分组 {name} 的比率指标 {numerator}/{denominator} 有效样本不足")
        mx, my = sum(x for x, _ in pairs) / n, sum(y for _, y in pairs) / n
        sx = math.sqrt(sum((x - mx) ** 2 for x, _ in pairs) / (n - 1))
        sy = math.sqrt(sum((y - my) ** 2 for _, y in pairs) / (n - 1))
        cov = sum((x - mx) * (y - my) for x, y in pairs) / (n - 1)
        data[name] = {"num_mean": mx, "den_mean": my, "num_std": sx, "den_std": sy, "cov": cov, "n": n}
    return data


def load_csv(args: argparse.Namespace) -> dict:
    metrics = ([_parse_metric(m, "primary") for m in args.metric]
               + [_parse_metric(m, "secondary") for m in args.secondary]
               + [_parse_metric(m, "guardrail") for m in args.guardrail])
    if not metrics:
        raise SystemExit("CSV 模式至少需要一个 --metric")
    cuped = dict(item.split("=", 1) for item in args.cuped)

    rows = sio.read_csv(args.csv)
    if not rows or args.variant_col not in rows[0]:
        raise SystemExit(f"CSV 为空或缺少分组列：{args.variant_col}")
    rows = [row for row in rows if (row[args.variant_col] or "").strip()]
    if not rows:
        raise SystemExit(f"分组列 {args.variant_col} 全部为空")

    groups: dict[str, dict] = {}
    for row in rows:
        groups.setdefault(row[args.variant_col], {"users": 0})["users"] += 1
    control = args.control or sorted(groups)[0]
    if control not in groups:
        raise SystemExit(f"--control {control} 不在分组列取值中：{sorted(groups)}")

    for metric in metrics:
        column = metric["column"]
        if column not in rows[0]:
            raise SystemExit(f"CSV 缺少指标列：{column}")
        if metric["type"] == "ratio":
            metric["data"] = _ratio_data(rows, args.variant_col, groups, column, metric["denominator"])
            continue
        parse = sio.parse_flag if metric["type"] == "proportion" else sio.parse_number

        def number(value: str | None, name: str = column) -> float | None:
            return parse(value, name)

        covariate = cuped.get(column)
        if covariate and metric["type"] != "mean":
            raise SystemExit(f"CUPED 只用于均值指标：{column}")
        pairs = [(row[args.variant_col], number(row[column]), sio.parse_number(row[covariate], covariate) if covariate else None) for row in rows]
        pairs = [p for p in pairs if p[1] is not None and (not covariate or p[2] is not None)]

        if covariate:
            ys = [p[1] for p in pairs]
            xs = [p[2] for p in pairs]
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            var_x = sum((x - mx) ** 2 for x in xs) / (len(xs) - 1)
            cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) - 1)
            theta = cov / var_x if var_x > 0 else 0.0
            var_y = sum((y - my) ** 2 for y in ys) / (len(ys) - 1)
            adjusted = [(g, y - theta * (x - mx)) for g, y, x in pairs]
            var_adj = sum((v - my) ** 2 for _, v in adjusted) / (len(adjusted) - 1)
            metric["cuped"] = {"covariate": covariate, "theta": theta,
                               "variance_reduction": 1 - var_adj / var_y if var_y > 0 else 0.0}
            values = adjusted
        else:
            values = [(g, y) for g, y, _ in pairs]

        data = {}
        for name in groups:
            vs = [v for g, v in values if g == name]
            if len(vs) < 2:
                raise SystemExit(f"分组 {name} 的指标 {column} 有效样本不足")
            if metric["type"] == "proportion":
                if any(v not in (0.0, 1.0) for v in vs):
                    raise SystemExit(f"比例指标 {column} 只能是 0/1 型取值")
                data[name] = {"successes": int(sum(vs)), "n": len(vs)}
            else:
                mean = sum(vs) / len(vs)
                std = math.sqrt(sum((v - mean) ** 2 for v in vs) / (len(vs) - 1))
                data[name] = {"mean": mean, "std": std, "n": len(vs)}
        metric["data"] = data

    allocation = None
    if args.allocation:
        try:
            allocation = {k.strip(): float(v) for k, v in (item.split("=", 1) for item in args.allocation.split(","))}
        except ValueError:
            raise SystemExit(f"--allocation 格式应为 A=0.9,B=0.1，收到：{args.allocation}") from None
    return {
        "name": args.name or os.path.splitext(os.path.basename(args.csv))[0],
        "control": control, "groups": groups, "metrics": metrics,
        "allocation": allocation, "days": args.days, "planned_days": args.planned_days,
    }


# ---------------------------------------------------------------------------
# 分析与决策
# ---------------------------------------------------------------------------

def analyze(spec: dict) -> dict:
    alpha = float(spec.get("alpha", 0.05))
    power = float(spec.get("power", 0.8))
    control = spec["control"]
    groups = spec["groups"]
    treatments = [g for g in groups if g != control]
    allocation = spec.get("allocation") or {g: 1.0 for g in groups}
    missing = [g for g in groups if g not in allocation]
    if missing:
        raise SystemExit(f"分流比例缺少分组：{'、'.join(missing)}（现有：{'、'.join(allocation)}）")
    srm = srm_test(groups, allocation)
    srm["allocation_assumed"] = not spec.get("allocation")

    comparisons = []
    for metric in spec["metrics"]:
        role = metric.get("role", "primary")
        higher = metric.get("higher_is_better", True)
        data = metric["data"]
        for treatment in treatments:
            a, b = data[control], data[treatment]
            na = int(a.get("n", groups[control]["users"]))
            nb = int(b.get("n", groups[treatment]["users"]))
            if metric.get("type", "proportion") == "proportion":
                result = compare_proportion(int(a["successes"]), na, int(b["successes"]), nb, alpha, power)
            elif metric["type"] == "ratio":
                result = compare_ratio(a, na, b, nb, alpha, power)
            else:
                result = compare_mean(float(a["mean"]), float(a["std"]), na, float(b["mean"]), float(b["std"]), nb, alpha, power)
            result.update({
                "metric": metric["name"], "role": role, "type": metric.get("type", "proportion"),
                "higher_is_better": higher, "control": control, "treatment": treatment,
                "control_n": na, "treatment_n": nb,
                "max_worsening_rel": metric.get("max_worsening_rel"),
                "cuped": metric.get("cuped"),
            })
            comparisons.append(result)

    primary = [c for c in comparisons if c["role"] == "primary"]
    for c, adjusted in zip(primary, holm([c["p_value"] for c in primary])):
        c["p_adjusted"] = adjusted
    for c in comparisons:
        c.setdefault("p_adjusted", c["p_value"])
        c["significant"] = c["p_adjusted"] < alpha
        if not c["significant"] or c["abs_diff"] == 0:
            c["direction"] = "flat"
        else:
            improved = c["abs_diff"] > 0 if c["higher_is_better"] else c["abs_diff"] < 0
            c["direction"] = "improved" if improved else "worsened"

    checks = build_checks(spec, srm, comparisons, alpha)
    verdict = build_verdict(spec, srm, comparisons, checks, alpha, power)
    return {
        "experiment": {
            "name": spec.get("name", "A/B 实验"), "hypothesis": spec.get("hypothesis"),
            "control": control, "treatments": treatments, "alpha": alpha, "power": power,
            "days": spec.get("days"), "planned_days": spec.get("planned_days"),
            "groups": groups, "guardrails_pending": spec.get("guardrails_pending", []),
        },
        "srm": srm,
        "comparisons": comparisons,
        "checks": checks,
        "verdict": verdict,
    }


def _pct(value: float | None) -> str:
    return viz.fmt_signed_pct(value, 1)


def build_checks(spec: dict, srm: dict, comparisons: list[dict], alpha: float) -> list[dict]:
    checks = []
    shares = "，".join(f"{g['group']} {g['observed_share'] * 100:.1f}%" for g in srm["groups"])
    unknown = _allocation_unknown(srm)
    checks.append({
        "id": "srm", "status": "warn" if unknown else srm["status"],
        "title": "未提供分流比例，无法判断样本是否失衡" if unknown else "样本比例（SRM）" + ("正常" if srm["status"] == "pass" else "异常：分流或数据管道有问题"),
        "detail": f"实际占比 {shares}；卡方 p={srm['p_value']:.4g}（阈值 {SRM_ALPHA}）",
    })

    days, planned = spec.get("days"), spec.get("planned_days")
    if days is None:
        checks.append({"id": "duration", "status": "warn", "title": "未提供实验天数",
                       "detail": "无法判断是否覆盖完整周期，请补充实验起止日期"})
    elif days < 7 or days % 7 != 0:
        checks.append({"id": "duration", "status": "warn", "title": f"实验周期 {days} 天，未覆盖整周",
                       "detail": "工作日与周末用户行为不同，建议按整周（7 的倍数）运行"})
    else:
        checks.append({"id": "duration", "status": "pass", "title": f"实验周期 {days} 天，覆盖整周"})
    if planned and days and days < planned:
        checks.append({"id": "peeking", "status": "warn", "title": f"提前查看：已运行 {days} / 计划 {planned} 天",
                       "detail": "现在的结果只是中期快照；如果因为“已经显著”而提前停止，假阳性率会远高于 α，结论要按计划周期复核"})
    if spec.get("early_stopped"):
        checks.append({"id": "early_stop", "status": "warn", "title": "实验被提前停止",
                       "detail": "提前停止会夸大效应，显著结果需要复验"})

    primary = [c for c in comparisons if c["role"] == "primary"]
    if len(primary) > 1:
        checks.append({"id": "multiple", "status": "info", "title": f"多重比较：{len(primary)} 组主指标比较已做 Holm 校正",
                       "detail": "显著性按校正后的 p 值判断"})
    for c in primary:
        if c["significant"] and c["rel_lift"] is not None and abs(c["rel_lift"]) > TWYMAN_REL:
            checks.append({"id": "twyman", "status": "warn",
                           "title": f"{c['metric']} 变化 {_pct(c['rel_lift'])}，幅度异常大",
                           "detail": "越离谱的结果越可能是埋点、口径或分流错误（Twyman 定律），先排查数据再庆祝"})
    small = [g for g, v in spec["groups"].items() if v["users"] < 1000]
    if small:
        checks.append({"id": "sample", "status": "warn", "title": f"样本量偏小：{', '.join(small)} 不足 1000",
                       "detail": "小样本下正态近似不稳定，结论只能作为方向参考"})

    guardrails = [c for c in comparisons if c["role"] == "guardrail"]
    pending = spec.get("guardrails_pending", [])
    if not guardrails:
        checks.append({"id": "guardrail", "status": "fail", "title": "没有护栏指标数据",
                       "detail": "无法确认实验没有伤害体验或收入；待补：" + ("、".join(pending) if pending else "错误率、性能、投诉、退款等")})
    else:
        for c in guardrails:
            if c["direction"] == "worsened":
                checks.append({"id": "guardrail", "status": "fail", "title": f"护栏 {c['metric']} 显著恶化 {_pct(c['rel_lift'])}",
                               "detail": f"p={c['p_value']:.3g}"})
            elif c.get("max_worsening_rel") is not None and c["ci_rel"]:
                worst = c["ci_rel"][1] if not c["higher_is_better"] else -c["ci_rel"][0]
                tolerance = c["max_worsening_rel"]
                status = "pass" if worst <= tolerance else "warn"
                checks.append({"id": "guardrail", "status": status,
                               "title": f"护栏 {c['metric']} " + ("可证明未超过容忍度" if status == "pass" else "未能排除超过容忍度的恶化"),
                               "detail": f"95% 区间内最坏恶化 {worst * 100:.1f}%，容忍度 {tolerance * 100:.1f}%"})
            else:
                checks.append({"id": "guardrail", "status": "pass", "title": f"护栏 {c['metric']} 未见显著恶化",
                               "detail": "未设置容忍度（max_worsening_rel），只能说明没有检测到恶化，不等于证明没有恶化"})
        if pending:
            checks.append({"id": "guardrail_pending", "status": "warn", "title": "部分护栏指标尚未提供",
                           "detail": "待补：" + "、".join(pending)})
    return checks


def _days_needed(spec: dict, n_per_group: int) -> int | None:
    days = spec.get("days")
    if not days:
        return None
    total_users = sum(g["users"] for g in spec["groups"].values())
    daily = total_users / days
    needed = math.ceil(n_per_group * len(spec["groups"]) / daily) if daily > 0 else None
    return None if needed is None else max(7, math.ceil(needed / 7) * 7)


def _allocation_unknown(srm: dict) -> bool:
    """没给分流比例且实际占比明显偏离均分时，更可能是 90/10 这类设计，而不是分流故障。"""
    skew = max(abs(g["observed_share"] - g["expected_share"]) for g in srm["groups"])
    return bool(srm.get("allocation_assumed")) and srm["status"] == "fail" and skew >= ALLOCATION_SKEW


def _validity_blockers(checks: list[dict]) -> list[dict]:
    return [c for c in checks if c["status"] == "warn" and c["id"] in VALIDITY_BLOCKERS]


def build_verdict(spec: dict, srm: dict, comparisons: list[dict], checks: list[dict], alpha: float, power: float) -> dict:
    primary = [c for c in comparisons if c["role"] == "primary"]
    guardrails = [c for c in comparisons if c["role"] == "guardrail"]
    pending = spec.get("guardrails_pending", [])
    reasons, steps = [], []

    if _allocation_unknown(srm):
        shares = "，".join(f"{g['group']} {g['observed_share'] * 100:.1f}%" for g in srm["groups"])
        return {"code": "allocation_unknown", "level": "warning", "title": "未提供分流比例，无法判断样本是否失衡",
                "reasons": [f"实际占比 {shares}，明显偏离默认的均分假设，这通常是实验本来就不是均分"],
                "next_steps": ["确认实验设计的分流比例", "用 --allocation A=0.9,B=0.1（CSV）或 allocation 字段（JSON）重新运行",
                               "如果设计就是均分，这是严重的分流异常，不要解读任何指标"]}

    if srm["status"] == "fail":
        return {"code": "invalid_srm", "level": "bad", "title": "实验分流异常（SRM），结果不可信",
                "reasons": [f"样本比例显著偏离预期（p={srm['p_value']:.2g}），说明分流、曝光记录或数据过滤存在系统性问题"],
                "next_steps": ["不要解读任何指标差异", "按分流日志、客户端版本、渠道、日期拆分样本比例，定位哪里丢了用户",
                               "修复后重新开始实验，不要沿用已有数据"]}

    worsened_guard = [c for c in guardrails if c["direction"] == "worsened"]
    if worsened_guard:
        names = "、".join(f"{c['metric']}（{_pct(c['rel_lift'])}）" for c in worsened_guard)
        return {"code": "guardrail_regression", "level": "bad", "title": "护栏指标显著恶化，不建议全量",
                "reasons": [f"护栏恶化：{names}"],
                "next_steps": ["定位恶化来源（哪类用户、哪个端、哪个环节）", "评估主指标收益是否值得这个代价，需要业务方明确决策",
                               "修复后重新实验"]}

    worsened = [c for c in primary if c["direction"] == "worsened"]
    improved = [c for c in primary if c["direction"] == "improved"]
    if worsened:
        names = "、".join(f"{c['metric']}（{_pct(c['rel_lift'])}）" for c in worsened)
        return {"code": "primary_regression", "level": "bad", "title": "主指标显著下降，建议回滚",
                "reasons": [f"显著下降：{names}"], "next_steps": ["回滚实验组", "复盘假设为什么不成立"]}

    if improved:
        blockers = _validity_blockers(checks)
        names = "、".join(f"{c['metric']}（{_pct(c['rel_lift'])}，p={c['p_adjusted']:.3g}）" for c in improved)
        reasons.append(f"主指标显著提升：{names}")
        if not guardrails or pending:
            missing = "、".join(pending) if pending else "护栏指标"
            reasons.append(f"缺少护栏数据：{missing}")
            reasons += [b["title"] for b in blockers]
            return {"code": "win_unverified", "level": "warning", "title": "主指标显著提升，但护栏未验证，暂不全量",
                    "reasons": reasons,
                    "next_steps": [f"补齐 {missing} 的分组结果后重新运行本脚本", "护栏无恶化后按 10% → 50% → 100% 逐步放量"]
                    + [VALIDITY_BLOCKERS[b["id"]] for b in blockers]}
        if blockers:
            return {"code": "win_needs_validation", "level": "warning", "title": "主指标显著提升，但有效性检查未通过，暂不放量",
                    "reasons": reasons + [b["title"] for b in blockers],
                    "next_steps": list(dict.fromkeys(VALIDITY_BLOCKERS[b["id"]] for b in blockers))}
        return {"code": "ship", "level": "good", "title": "建议逐步放量",
                "reasons": reasons + ["护栏指标未见显著恶化"],
                "next_steps": ["按 10% → 50% → 100% 放量，每档观察至少一个完整周期",
                               "放量后继续监控主指标和护栏，警惕新奇效应衰减"]}

    for c in primary:
        observed = abs(c["abs_diff"])
        mde_rel = c["mde_rel"]
        text = f"{c['metric']}：观测变化 {_pct(c['rel_lift'])}，p={c['p_adjusted']:.3g}，未达到显著"
        if mde_rel:
            text += f"；当前样本在 {int(power * 100)}% 功效下只能可靠检测 ≥{mde_rel * 100:.1f}% 的相对变化"
        reasons.append(text)
        if observed > 0:
            if c["type"] == "proportion":
                need = n_per_group_proportion(c["control_value"], c["control_value"] + observed, alpha, power)
            else:
                pooled_std = c["mde_abs"] / (N.inv_cdf(1 - alpha / 2) + N.inv_cdf(power)) / math.sqrt(
                    1 / c["control_n"] + 1 / c["treatment_n"])
                need = n_per_group_mean(pooled_std, observed, alpha, power)
            days = _days_needed(spec, need)
            msg = f"若真实效应就是观测到的 {_pct(c['rel_lift'])}，每组需要约 {viz.fmt_num(need)} 样本"
            if days:
                msg += f"，按当前流量约需运行 {days} 天"
            steps.append(msg)
    steps += ["在业务上先确定“值得上线的最小效应”，用 plan 子命令重新规划样本量", "不显著 ≠ 没有效果，不要把它写成“新方案无效”"]
    return {"code": "inconclusive", "level": "warning", "title": "结果不显著，暂不能下结论", "reasons": reasons, "next_steps": steps}


# ---------------------------------------------------------------------------
# HTML 报告
# ---------------------------------------------------------------------------

def _value_fmt(c: dict):
    if c["type"] == "proportion" or (c["type"] == "ratio" and abs(c["control_value"]) <= 1):
        return lambda v: viz.fmt_pct(v, 2)
    return lambda v: viz.fmt_num(v, 2)


def render_html(result: dict) -> str:
    exp, verdict = result["experiment"], result["verdict"]
    comps = result["comparisons"]
    primary = [c for c in comps if c["role"] == "primary"]
    role_name = {"primary": "主指标", "secondary": "辅助指标", "guardrail": "护栏指标"}
    blocks = []

    body = "".join(f"<div>· {viz.esc(r)}</div>" for r in verdict["reasons"])
    blocks.append(viz.callout(verdict["level"], verdict["title"], body, raw_body=True))

    if primary:
        c = primary[0]
        vf = _value_fmt(c)
        tone = viz.delta_tone(c["rel_lift"], c["higher_is_better"], c["significant"])
        sig = "显著" if c["significant"] else "不显著"
        tiles = [
            {"label": f"{c['metric']} · {c['control']}", "value": vf(c["control_value"]), "note": f"n = {viz.fmt_num(c['control_n'])}"},
            {"label": f"{c['metric']} · {c['treatment']}", "value": vf(c["treatment_value"]),
             "delta": f"{viz.arrow(c['rel_lift'])} {_pct(c['rel_lift'])}（{sig}）", "tone": tone,
             "note": f"n = {viz.fmt_num(c['treatment_n'])}"},
            {"label": "p 值" + ("（Holm 校正）" if len(primary) > 1 else ""), "value": f"{c['p_adjusted']:.3f}",
             "note": f"显著性水平 α = {exp['alpha']}"},
        ]
        if c["mde_rel"]:
            tiles.append({"label": "当前可检测最小效应", "value": f"±{c['mde_rel'] * 100:.1f}%",
                          "note": f"{int(exp['power'] * 100)}% 功效下的相对变化"})
        blocks.append(viz.section("核心结果", viz.stat_tiles(tiles)))

    rows = []
    for c in comps:
        if c["rel_lift"] is None or not c["ci_rel"]:
            continue
        label = c["metric"] if len(exp["treatments"]) == 1 else f"{c['metric']} · {c['treatment']}"
        sub = role_name[c["role"]] + ("" if c["higher_is_better"] else " · 越低越好") + (" · CUPED" if c.get("cuped") else "")
        rows.append({"label": label, "sub": sub, "estimate": c["rel_lift"], "low": c["ci_rel"][0], "high": c["ci_rel"][1],
                     "tone": viz.delta_tone(c["rel_lift"], c["higher_is_better"], c["significant"])})
    table_rows = [[
        c["metric"], role_name[c["role"]], c["treatment"], _value_fmt(c)(c["control_value"]), _value_fmt(c)(c["treatment_value"]),
        _pct(c["rel_lift"]),
        f"[{_pct(c['ci_rel'][0])}, {_pct(c['ci_rel'][1])}]" if c["ci_rel"] else "—",
        f"{c['p_adjusted']:.3g}", "是" if c["significant"] else "否",
    ] for c in comps]
    blocks.append(viz.section(
        "各指标相对变化",
        viz.interval_chart(rows, caption="点为相对变化估计，横线为 95% 置信区间；区间跨过 0 线即不显著，只有显著的变化才上色。"),
        viz.table(["指标", "类型", "实验组", "对照值", "实验值", "相对变化", "95% 区间", "p 值", "显著"], table_rows, numeric=(3, 4, 5, 6, 7)),
        lead="一张图同时看方向、幅度和不确定性。",
    ))

    if primary:
        c = primary[0]
        names = [exp["control"]] + exp["treatments"]
        values, errors = [], []
        for name in names:
            match = next((x for x in primary if x["metric"] == c["metric"] and x["treatment"] == name), None)
            if name == exp["control"]:
                values.append(c["control_value"])
                errors.append(tuple(c["control_ci"]))
            elif match:
                values.append(match["treatment_value"])
                errors.append(tuple(match["treatment_ci"]))
        colors = ["var(--neutral)"] + [f"var(--series-{i + 1})" for i in range(len(names) - 1)]
        blocks.append(viz.section(
            f"{c['metric']}：分组对比",
            viz.bar_chart(names, values, errors=errors, fmt=_value_fmt(c), colors=colors,
                          caption="误差线为各组自身的 95% 置信区间。两组误差线重叠不等于差异不显著，以上方的差值区间为准。"),
        ))

    blocks.append(viz.section("实验有效性检查", viz.checklist(result["checks"])))
    blocks.append(viz.section("下一步", viz.checklist([{"status": "info", "title": s} for s in verdict["next_steps"]])))

    srm = result["srm"]
    blocks.append(viz.section("样本分流", viz.table(
        ["分组", "实际样本", "预期样本", "实际占比", "预期占比"],
        [[g["group"], viz.fmt_num(g["observed"]), viz.fmt_num(round(g["expected"])), viz.fmt_pct(g["observed_share"], 1),
          viz.fmt_pct(g["expected_share"], 1)] for g in srm["groups"]],
        numeric=(1, 2, 3, 4),
    ), viz.paragraph(
        "方法说明：比例指标用双样本 z 检验，相对变化区间用对数比的 delta 方法；均值指标用 Welch t 检验；比率指标用 delta 方法估计方差；"
        "SRM 用卡方拟合优度检验（p < 0.001 判定异常）；多个主指标比较用 Holm 校正。"
    )))

    subtitle_parts = [exp.get("hypothesis") or "", f"周期 {exp['days']} 天" if exp.get("days") else ""]
    return viz.html_report(exp["name"], blocks, subtitle=" · ".join(p for p in subtitle_parts if p) or None,
                           brand="拾穗数据 · A/B 实验报告")


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
    if bool(args.summary) == bool(args.csv):
        raise SystemExit("--summary 与 --csv 二选一")
    spec = load_summary(args.summary) if args.summary else load_csv(args)
    if args.alpha:
        spec["alpha"] = args.alpha
    result = _round(analyze(spec))
    if args.html:
        viz.save(args.html, render_html(result))
        result["html_report"] = os.path.abspath(args.html)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    if (args.mde_rel is None) == (args.mde_abs is None):
        raise SystemExit("--mde-rel 与 --mde-abs 二选一")
    delta = args.mde_abs if args.mde_abs is not None else args.baseline * args.mde_rel
    if args.metric_type == "proportion":
        if not 0 < args.baseline < 1:
            raise SystemExit("比例指标的 --baseline 应在 0 到 1 之间，例如 0.07")
        n = n_per_group_proportion(args.baseline, args.baseline + delta, args.alpha, args.power)
    else:
        if not args.std:
            raise SystemExit("均值指标需要 --std（指标的标准差）")
        n = n_per_group_mean(args.std, delta, args.alpha, args.power)
    total = n * args.groups
    result = {
        "metric_type": args.metric_type, "baseline": args.baseline, "mde_abs": delta,
        "mde_rel": delta / args.baseline if args.baseline else None,
        "alpha": args.alpha, "power": args.power, "groups": args.groups,
        "n_per_group": n, "n_total": total,
    }
    if args.daily_users:
        raw_days = math.ceil(total / args.daily_users)
        result["days_raw"] = raw_days
        result["days_recommended"] = max(7, math.ceil(raw_days / 7) * 7)
        result["note"] = "推荐天数已向上取整到整周，并且不少于 7 天，以覆盖周内效应"
    print(json.dumps(_round(result), ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="A/B 实验计算器（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="解读实验结果")
    a.add_argument("--summary", help="汇总数据 JSON（见 references/input-schema.md）")
    a.add_argument("--csv", help="用户粒度 CSV，每行一个实验单元")
    a.add_argument("--variant-col", default="variant")
    a.add_argument("--control", help="对照组取值，默认取排序后的第一个")
    a.add_argument("--metric", action="append", default=[], help="主指标 列名:proportion|mean[:higher|lower]，或 分子列/分母列:ratio[:higher|lower]，可重复")
    a.add_argument("--secondary", action="append", default=[], help="辅助指标，格式同 --metric")
    a.add_argument("--guardrail", action="append", default=[], help="护栏指标，格式同 --metric")
    a.add_argument("--cuped", action="append", default=[], help="CUPED 方差缩减：指标列=实验前协变量列")
    a.add_argument("--allocation", help="预期分流比例，如 A=0.9,B=0.1；默认均分，非均分实验必须填写")
    a.add_argument("--days", type=int, help="实验已运行天数")
    a.add_argument("--planned-days", type=int, help="计划运行天数")
    a.add_argument("--name", help="实验名称")
    a.add_argument("--alpha", type=float, help="显著性水平，默认 0.05")
    a.add_argument("--html", help="输出 HTML 报告路径")
    a.add_argument("--json", help="同时把 JSON 写入文件")
    a.set_defaults(func=cmd_analyze)

    p = sub.add_parser("plan", help="实验前样本量与周期规划")
    p.add_argument("--metric-type", choices=["proportion", "mean"], default="proportion")
    p.add_argument("--baseline", type=float, required=True, help="对照组基线：比例如 0.07，均值如 4.2")
    p.add_argument("--std", type=float, help="均值指标的标准差")
    p.add_argument("--mde-rel", type=float, help="最小可检测相对效应，如 0.05 表示 5%%")
    p.add_argument("--mde-abs", type=float, help="最小可检测绝对效应，如 0.005 表示 0.5pp")
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--power", type=float, default=0.8)
    p.add_argument("--groups", type=int, default=2, help="总组数（含对照组）")
    p.add_argument("--daily-users", type=float, help="每天进入实验的总用户数")
    p.set_defaults(func=cmd_plan)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(sio.run_cli(main))
