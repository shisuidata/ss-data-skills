#!/usr/bin/env python3
"""数据体检：字段画像、类型推断、质量问题分级、时间趋势、多表关联完整性（仅依赖 Python 标准库）。

用法：
  python3 eda.py profile --table orders=orders.csv --html eda_report.html
  python3 eda.py profile --table users=users.csv --table orders=orders.csv \\
      --key users=user_id --key orders=order_id --join orders.user_id=users.user_id \\
      --time-col orders=pay_time --html eda_report.html

输出 JSON（给 Agent 读）和可选的 HTML 报告（给人看）。字段含义和业务解释由 Agent 结合上下文判断，
脚本只报告“数据实际长什么样”。说明见 ../references/checks.md。
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from statistics import median

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_viz as viz  # noqa: E402
import sskit_io as sio  # noqa: E402

NULL_TOKENS = {""}
# 明确的空值占位：计入缺失率
EXCEL_ERRORS = {"#n/a", "#ref!", "#div/0!", "#value!", "#name?", "#num!", "#null!"}
PSEUDO_NULLS = {"null", "nan", "n/a", "\\n", "nil", "undefined", "0000-00-00", "0000-00-00 00:00:00"} | EXCEL_ERRORS
# 可能是占位、也可能是业务取值（例如 refund_status=none 表示“无退款”）：只提示，不计入缺失率
PLACEHOLDERS = {"none", "-", "--", "na", "未知", "无", "空", "其他", "unknown", "default"}
BOOL_TOKENS = {"0", "1", "true", "false", "是", "否", "y", "n", "yes", "no", "t", "f"}
INT_RE = re.compile(r"^-?\d+$")
FLOAT_RE = re.compile(r"^-?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")
FORMATTED_NUM_RE = re.compile(r"^[¥￥$]?\s?-?[\d,]+(\.\d+)?\s?(%|元|万)?$")
SCI_RE = re.compile(r"^-?\d(\.\d+)?[eE]\+?\d+$")
DATE_NAME_RE = re.compile(r"(^|_)(date|dt|day|time)($|_)|日期|时间|_at$")
DATE_PATTERNS = (("YYYY-MM-DD", re.compile(r"^\d{4}-\d{1,2}-\d{1,2}")), ("YYYY/MM/DD", re.compile(r"^\d{4}/\d{1,2}/\d{1,2}")),
                 ("YYYYMMDD", re.compile(r"^(19|20)\d{6}$")), ("YYYY年MM月DD日", re.compile(r"^\d{4}年\d{1,2}月\d{1,2}日")),
                 ("MM月DD日", re.compile(r"^\d{1,2}月\d{1,2}日")), ("MM/DD/YYYY", re.compile(r"^\d{1,2}/\d{1,2}/\d{4}")),
                 ("YYYY.MM.DD", re.compile(r"^\d{4}\.\d{1,2}\.\d{1,2}")))
TIME = sio.TimeParser()
DATETIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y%m%d",
                    "%Y年%m月%d日", "%Y.%m.%d")
PARTITION_NAMES = {"dt", "ds", "pt", "p_date", "partition_date", "stat_date", "biz_date"}
SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


# ---------------------------------------------------------------------------
# 读取
# ---------------------------------------------------------------------------

def _sample(rows: list[list[str]], max_rows: int | None) -> list[list[str]]:
    """蓄水池抽样：按时间排序的文件取前 N 行会严重有偏，这里在全表上等概率抽样（固定种子，结果可复现）。"""
    if max_rows is None or len(rows) <= max_rows:
        return rows
    rng = random.Random(42)
    kept = rows[:max_rows]
    for i in range(max_rows, len(rows)):
        j = rng.randrange(i + 1)
        if j < max_rows:
            kept[j] = rows[i]
    return kept


def read_table(path: str, max_rows: int | None, sheet: str | None = None) -> tuple[list[str], list[list[str]], dict]:
    raw = open(path, "rb").read()
    if raw[:2] == b"PK" and path.lower().endswith((".xlsx", ".xlsm")):
        header, rows, sheet_name = sio.read_xlsx(path, sheet)
        total, ragged = len(rows), sum(1 for r in rows if len(r) > len(header))
        rows = [(r + [""] * len(header))[: len(header)] for r in rows]
        kept = _sample(rows, max_rows)
        return header, kept, {"path": path, "encoding": "xlsx", "delimiter": f"工作表 {sheet_name}", "rows_total": total,
                              "rows_profiled": len(kept), "ragged_rows": ragged, "bom": False}
    encoding = sio.detect_encoding(path)
    text = raw.decode(encoding)
    sample = text[:20000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = next(reader, None)
    if not header:
        raise SystemExit(f"{path} 是空文件")
    header = [h.strip() for h in header]
    rows, ragged = [], 0
    for row in reader:
        if not row:
            continue
        if len(row) != len(header):
            ragged += 1
            row = (row + [""] * len(header))[: len(header)]
        rows.append(row)
    total = len(rows)
    rows = _sample(rows, max_rows)
    meta = {"path": path, "encoding": sio.encoding_label(encoding),
            "delimiter": {"\t": "Tab", ",": "逗号", ";": "分号", "|": "竖线"}.get(delimiter, delimiter),
            "rows_total": total, "rows_profiled": len(rows), "ragged_rows": ragged, "bom": raw.startswith(b"\xef\xbb\xbf")}
    return header, rows, meta


# ---------------------------------------------------------------------------
# 类型推断与字段画像
# ---------------------------------------------------------------------------

def parse_datetime(value: str) -> datetime | None:
    v = value.strip()
    for fmt in DATETIME_FORMATS:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return TIME.try_parse(v) if v else None


def _mixed_date_formats(distinct: Counter, present: int) -> dict | None:
    """同一列有两种以上日期写法时返回各写法的行数；不像日期或写法统一时返回 None。"""
    counts: Counter = Counter()
    for value, n in list(distinct.most_common(5000)):
        label = next((name for name, pattern in DATE_PATTERNS if pattern.match(value)), None)
        if label:
            counts[label] += n
    return dict(counts) if len(counts) >= 2 and sum(counts.values()) >= 0.9 * present else None


def to_number(value: str) -> float | None:
    v = value.strip()
    if FLOAT_RE.match(v):
        return float(v)
    return None


def formatted_to_number(value: str) -> float | None:
    v = value.strip()
    if not FORMATTED_NUM_RE.match(v):
        return None
    scale = 0.01 if v.endswith("%") else (1e4 if v.endswith("万") else 1)
    digits = re.sub(r"[¥￥$,%元万\s]", "", v)
    try:
        return float(digits) * scale
    except ValueError:
        return None


def quantiles(values: list[float], qs: tuple[float, ...]) -> list[float]:
    ordered = sorted(values)
    out = []
    for q in qs:
        pos = (len(ordered) - 1) * q
        lo, hi = math.floor(pos), math.ceil(pos)
        out.append(ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo))
    return out


def infer_column(name: str, values: list[str]) -> dict:
    n = len(values)
    stripped = [v.strip() for v in values]
    true_null = sum(1 for v in stripped if v in NULL_TOKENS)
    pseudo = Counter(v for v in stripped if v.lower() in PSEUDO_NULLS)
    present = [v for v in stripped if v not in NULL_TOKENS and v.lower() not in PSEUDO_NULLS]
    whitespace = sum(1 for v in values if v and v != v.strip())
    distinct = Counter(present)
    col = {
        "name": name, "rows": n, "null": true_null, "pseudo_null": sum(pseudo.values()),
        "pseudo_null_tokens": dict(pseudo.most_common(5)), "missing_rate": (true_null + sum(pseudo.values())) / n if n else 0,
        "placeholders": dict(Counter(v for v in stripped if v.lower() in PLACEHOLDERS).most_common(5)),
        "excel_errors": sum(c for v, c in pseudo.items() if v.lower() in EXCEL_ERRORS),
        "distinct": len(distinct), "whitespace_values": whitespace,
        "top_values": [[v, c] for v, c in distinct.most_common(8)],
    }
    if not present:
        col["type"] = "empty"
        return col

    lowered_name = name.lower()
    id_like_name = lowered_name.endswith("id") or lowered_name.endswith("_no") or lowered_name.endswith("code") or "编号" in name
    lower_set = {v.lower() for v in distinct}
    if lower_set <= BOOL_TOKENS and len(lower_set) <= 2:
        col["type"] = "boolean"
        return col

    ints = [v for v in present if INT_RE.match(v)]
    nums = [x for x in (to_number(v) for v in present) if x is not None]

    if len(ints) == len(present):
        leading_zero = sum(1 for v in ints if len(v) > 1 and v.lstrip("-").startswith("0"))
        long_digits = sum(1 for v in ints if len(v.lstrip("-")) >= 16)
        as_int = [int(v) for v in ints]
        if ("time" in lowered_name or lowered_name.endswith("_at") or lowered_name.endswith("ts")) and \
                all(946684800 <= x <= 4102444800 or 946684800000 <= x <= 4102444800000 for x in as_int):
            col["type"] = "datetime"
            col["datetime_source"] = "epoch"
            stamps = [datetime.fromtimestamp(x / 1000 if x > 1e11 else x) for x in as_int]
            col.update(_datetime_stats(stamps))
            return col
        if id_like_name or leading_zero or long_digits:
            col["type"] = "id"
            col["leading_zero_values"] = leading_zero
            col["long_digit_values"] = long_digits
            return col

    scientific = [v for v in present if SCI_RE.match(v) and abs(float(v)) >= 1e11]
    if len(scientific) >= 0.5 * len(present):
        col["scientific_values"] = len(scientific)
        col["scientific_examples"] = scientific[:3]
        if id_like_name or len(distinct) >= 0.9 * len(present):
            col["type"] = "id"
            col["scientific_id"] = True
            return col

    if DATE_NAME_RE.search(lowered_name) and len(nums) == len(present) and all(20000 <= x <= 60000 for x in nums):
        col["type"] = "datetime"
        col["datetime_source"] = "excel_serial"
        col.update(_datetime_stats([datetime(1899, 12, 30) + timedelta(days=x) for x in nums]))
        return col

    if len(nums) >= 0.98 * len(present):
        col["type"] = "integer" if len(ints) == len(present) else "number"
        col["invalid_examples"] = [v for v in distinct if to_number(v) is None][:5]
        col["invalid_count"] = len(present) - len(nums)
        col.update(_numeric_stats(nums))
        return col

    formatted = [x for x in (formatted_to_number(v) for v in present) if x is not None]
    if len(formatted) >= 0.95 * len(present) and len(formatted) > len(nums):
        col["type"] = "number_as_text"
        col["format_examples"] = [v for v in distinct if to_number(v) is None][:5]
        col.update(_numeric_stats(formatted))
        return col

    sample = list(distinct)[:300]
    parsed = [parse_datetime(v) for v in sample]
    ok = [p for p in parsed if p is not None]
    if sample and len(ok) >= 0.95 * len(sample):
        stamps = [p for p in (parse_datetime(v) for v in present) if p is not None]
        col["type"] = "datetime"
        col["invalid_count"] = len(present) - len(stamps)
        col["invalid_examples"] = [v for v in sample if parse_datetime(v) is None][:5]
        col.update(_datetime_stats(stamps))
        mixed_dates = _mixed_date_formats(distinct, len(present))
        if mixed_dates:
            col["mixed_date_formats"] = mixed_dates
        return col

    mixed_dates = _mixed_date_formats(distinct, len(present))
    if mixed_dates:
        col["mixed_date_formats"] = mixed_dates
    elif 0.05 * len(present) <= len(nums) < 0.98 * len(present):
        col["mixed_numeric_share"] = len(nums) / len(present)

    lengths = [len(v) for v in present]
    avg_len = sum(lengths) / len(lengths)
    ratio = len(distinct) / len(present)
    groups = defaultdict(set)
    for v in distinct:
        groups[re.sub(r"[\s_\-]", "", v.lower())].add(v)
    variants = [sorted(vs) for vs in groups.values() if len(vs) > 1]
    col["case_variants"] = variants[:5]
    col["length"] = {"min": min(lengths), "max": max(lengths), "avg": avg_len}
    if (ratio >= 0.9 and avg_len <= 64 and len(present) >= 20) or (id_like_name and (ratio >= 0.3 or len(distinct) > 50)):
        col["type"] = "id"
    elif avg_len > 60:
        col["type"] = "text"
    elif len(distinct) <= 50 or ratio < 0.05:
        col["type"] = "category"
    else:
        col["type"] = "string"
    return col


def _numeric_stats(nums: list[float]) -> dict:
    p = quantiles(nums, (0, 0.01, 0.25, 0.5, 0.75, 0.99, 1))
    mean = sum(nums) / len(nums)
    std = math.sqrt(sum((x - mean) ** 2 for x in nums) / (len(nums) - 1)) if len(nums) > 1 else 0.0
    iqr = p[4] - p[2]
    lo_fence, hi_fence = p[2] - 3 * iqr, p[4] + 3 * iqr
    outliers = [x for x in nums if x < lo_fence or x > hi_fence] if iqr > 0 else []
    return {"stats": {"min": p[0], "p01": p[1], "p25": p[2], "median": p[3], "p75": p[4], "p99": p[5], "max": p[6],
                      "mean": mean, "std": std},
            "zeros": sum(1 for x in nums if x == 0), "negatives": sum(1 for x in nums if x < 0),
            "outliers": len(outliers), "outlier_fences": [lo_fence, hi_fence] if iqr > 0 else None,
            "skew_ratio": (mean / p[3]) if p[3] else None}


def _datetime_stats(stamps: list[datetime]) -> dict:
    if not stamps:
        return {}
    now = datetime.now()
    good = [s for s in stamps if plausible(s)] or stamps
    lo, hi = min(good), max(good)
    midnight = sum(1 for s in stamps if s.hour == 0 and s.minute == 0 and s.second == 0)
    fmt = "%Y-%m-%d %H:%M:%S"
    return {"range": [lo.strftime(fmt), hi.strftime(fmt)],
            "raw_range": [min(stamps).strftime(fmt), max(stamps).strftime(fmt)],
            "date_only": midnight == len(stamps),
            "future": sum(1 for s in stamps if s > now + timedelta(days=1)),
            "suspicious_defaults": sum(1 for s in stamps if s.year <= 1971 or s.year >= 2099 or (s.month == 1 and s.day == 1 and s.year <= 2000)),
            "_stamps": stamps}


# ---------------------------------------------------------------------------
# 表级检查
# ---------------------------------------------------------------------------

def plausible(ts: datetime) -> bool:
    """排除占位日期和未来时间，避免 1970-01-01 把时间范围拉长几十年。"""
    return 1971 < ts.year < 2099 and not (ts.month == 1 and ts.day == 1 and ts.year <= 2000) and ts <= datetime.now() + timedelta(days=1)


def daily_counts(stamps: list[datetime]) -> dict:
    counts = Counter(s.date() for s in stamps if plausible(s))
    if not counts:
        return {}
    first, last = min(counts), max(counts)
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    series = [counts.get(d, 0) for d in days]
    missing = [d.isoformat() for d, c in zip(days, series) if c == 0]
    spikes = []
    med = median(series)
    if len(series) >= 7 and med >= 5:
        mad = median([abs(x - med) for x in series]) or 1
        for d, c in zip(days, series):
            z = 0.6745 * (c - med) / mad
            if abs(z) > 5 and c > 0:
                spikes.append({"date": d.isoformat(), "rows": c, "robust_z": round(z, 1)})
    nonzero = [x for x in series if x]
    dense = bool(nonzero) and sum(nonzero) / len(nonzero) >= 5
    return {"dates": [d.isoformat() for d in days], "rows": series, "missing_dates": missing, "spikes": spikes[:10],
            "dense": dense}


def profile_table(name: str, path: str, key: list[str] | None, time_col: str | None, max_rows: int | None,
                  sheet: str | None = None) -> dict:
    header, rows, meta = read_table(path, max_rows, sheet)
    columns = []
    for j, col_name in enumerate(header):
        columns.append(infer_column(col_name, [row[j] for row in rows]))
    by_name = {c["name"]: c for c in columns}

    row_tuples = Counter(tuple(r) for r in rows)
    duplicate_rows = sum(c - 1 for c in row_tuples.values() if c > 1)

    candidates = [c["name"] for c in columns
                  if c["distinct"] == len(rows) and c["missing_rate"] == 0 and len(rows) > 1 and c["type"] not in ("number", "datetime")]
    key_check = None
    if key:
        idx = [header.index(k) for k in key if k in header]
        if len(idx) != len(key):
            raise SystemExit(f"{name} 缺少主键列：{[k for k in key if k not in header]}")
        keys = Counter(tuple(r[i] for i in idx) for r in rows)
        dup = {k: c for k, c in keys.items() if c > 1}
        key_check = {"columns": key, "duplicate_keys": len(dup), "duplicate_rows": sum(dup.values()) - len(dup),
                     "examples": [list(k) for k in list(dup)[:5]],
                     "null_keys": sum(1 for r in rows if any(r[i].strip() == "" or r[i].strip().lower() in PSEUDO_NULLS for i in idx))}

    datetime_cols = [c for c in columns if c["type"] == "datetime"]
    chosen = by_name.get(time_col) if time_col else None
    if chosen is None:
        non_partition = [c for c in datetime_cols if c["name"].lower() not in PARTITION_NAMES]
        chosen = (non_partition or datetime_cols or [None])[0]
    trend = daily_counts(chosen["_stamps"]) if chosen else {}

    partition_check = None
    partition = next((c for c in datetime_cols if c["name"].lower() in PARTITION_NAMES), None)
    if partition and chosen and chosen is not partition and not chosen.get("date_only"):
        pi, ti = header.index(partition["name"]), header.index(chosen["name"])
        pairs = [(parse_datetime(r[pi]), parse_datetime(r[ti]) if chosen.get("datetime_source") not in ("epoch", "excel_serial") else None) for r in rows]
        pairs = [(p, t) for p, t in pairs if p and t and plausible(t)]
        if pairs:
            mismatch = [(p, t) for p, t in pairs if p.date() != t.date()]
            partition_check = {"partition": partition["name"], "time": chosen["name"], "checked": len(pairs),
                               "mismatch": len(mismatch), "late": sum(1 for p, t in mismatch if p.date() > t.date()),
                               "examples": [[p.date().isoformat(), t.strftime("%Y-%m-%d %H:%M:%S")] for p, t in mismatch[:5]]}

    numeric = [c for c in columns if c["type"] in ("integer", "number")]
    correlations = []
    if 2 <= len(numeric) <= 30:
        idx = {c["name"]: header.index(c["name"]) for c in numeric}
        for i, a in enumerate(numeric):
            for b in numeric[i + 1:]:
                xs, ys = [], []
                for r in rows:
                    x, y = to_number(r[idx[a["name"]]]), to_number(r[idx[b["name"]]])
                    if x is not None and y is not None:
                        xs.append(x)
                        ys.append(y)
                rho = pearson(xs, ys)
                if rho is not None and abs(rho) >= 0.7:
                    correlations.append({"a": a["name"], "b": b["name"], "pearson": rho, "n": len(xs)})
        correlations.sort(key=lambda x: -abs(x["pearson"]))

    for c in columns:
        c.pop("_stamps", None)
    return {"name": name, "meta": meta, "columns": columns, "duplicate_rows": duplicate_rows,
            "key_candidates": candidates[:5], "key_check": key_check, "time_column": chosen["name"] if chosen else None,
            "trend": trend, "partition_check": partition_check, "correlations": correlations[:10],
            "_header": header, "_rows": rows}


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 10:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def check_join(spec: str, tables: dict) -> dict:
    left, _, right = spec.partition("=")
    lt, _, lc = left.partition(".")
    rt, _, rc = right.partition(".")
    for t, c in ((lt, lc), (rt, rc)):
        if t not in tables or c not in tables[t]["_header"]:
            raise SystemExit(f"--join 引用了不存在的表或列：{t}.{c}")
    li, ri = tables[lt]["_header"].index(lc), tables[rt]["_header"].index(rc)
    child = [r[li].strip() for r in tables[lt]["_rows"] if r[li].strip() and r[li].strip().lower() not in PSEUDO_NULLS]
    parent = {r[ri].strip() for r in tables[rt]["_rows"] if r[ri].strip()}
    parent_counts = Counter(r[ri].strip() for r in tables[rt]["_rows"] if r[ri].strip())
    orphans = [v for v in child if v not in parent]
    child_set = set(child)
    return {"join": spec, "child_rows": len(child), "orphan_rows": len(orphans), "orphan_rate": len(orphans) / len(child) if child else 0,
            "orphan_examples": sorted(set(orphans))[:5], "parent_unique": all(c == 1 for c in parent_counts.values()),
            "parent_keys": len(parent), "parent_without_child": len(parent - child_set),
            "fanout_max": max(Counter(child).values()) if child else 0}


# ---------------------------------------------------------------------------
# 问题分级
# ---------------------------------------------------------------------------

def build_issues(tables: dict, joins: list[dict]) -> list[dict]:
    issues = []

    def add(sev: str, table: str, column: str | None, title: str, impact: str, action: str):
        issues.append({"severity": sev, "table": table, "column": column, "title": title, "impact": impact, "action": action})

    for t in tables.values():
        name, meta = t["name"], t["meta"]
        if meta["encoding"].startswith("GBK"):
            add("P2", name, None, "文件编码是 GBK/GB18030", "直接用 UTF-8 读取会乱码或报错", "导入时指定 encoding='gb18030'，或统一转成 UTF-8")
        if meta["ragged_rows"]:
            add("P0", name, None, f"{meta['ragged_rows']} 行的列数与表头不一致", "字段可能错位，后续所有统计都不可靠",
                "检查是否有未转义的分隔符或换行（常见于备注、地址字段）")
        if meta["rows_profiled"] < meta["rows_total"]:
            add("P2", name, None, f"随机抽样体检 {viz.fmt_num(meta['rows_profiled'])} 行（共 {viz.fmt_num(meta['rows_total'])} 行）",
                "分布基本可信，但重复键和孤儿键会被低估，抽样时看不到的问题不代表不存在", "主键和关联检查去掉 --max-rows 全量运行，或在 SQL 中直接校验")
        kc = t["key_check"]
        if kc and (kc["duplicate_keys"] or kc["null_keys"]):
            add("P0", name, "+".join(kc["columns"]), f"主键重复 {viz.fmt_num(kc['duplicate_keys'])} 个、空主键 {viz.fmt_num(kc['null_keys'])} 行",
                "关联时会把数据放大，计数、求和直接算错", "确认表粒度；按业务规则去重（如取最新一条）后再使用")
        if not kc and not t["key_candidates"] and len(t["_rows"]) > 1:
            add("P1", name, None, "没有找到单列唯一键", "表粒度不明确，关联时容易放大数据", "确认一行代表什么，用 --key 指定组合主键再检查")
        if t["duplicate_rows"]:
            add("P1", name, None, f"{viz.fmt_num(t['duplicate_rows'])} 行完全重复", "计数和求和偏大", "确认是重复上报还是合法重复，必要时去重")
        pc = t["partition_check"]
        if pc and pc["mismatch"]:
            rate = pc["mismatch"] / pc["checked"]
            add("P1" if rate > 0.01 else "P2", name, pc["partition"],
                f"分区 {pc['partition']} 与 {pc['time']} 日期不一致：{viz.fmt_pct(rate, 1)}（其中晚到 {viz.fmt_num(pc['late'])} 行）",
                "按分区取数会漏掉晚到数据或混入其他日期的数据，按天统计会错位", f"统计口径按 {pc['time']} 取日期，并把分区范围放宽 1~2 天")
        trend = t["trend"]
        if trend.get("missing_dates") and trend.get("dense"):
            md = trend["missing_dates"]
            add("P1", name, t["time_column"], f"{len(md)} 天没有数据：{'、'.join(md[:4])}{'…' if len(md) > 4 else ''}",
                "趋势和日均会被拉低，可能是任务失败或分区缺失", "确认这些日期是业务真空还是数据缺失，必要时补数")
        for s in trend.get("spikes", [])[:3]:
            add("P2", name, t["time_column"], f"{s['date']} 数据量异常（{viz.fmt_num(s['rows'])} 行，稳健 z={s['robust_z']}）",
                "可能是重复导入、补数或真实的业务高峰（大促）", "对照当天的任务日志和业务日历")
        for c in t["columns"]:
            col = c["name"]
            if c["type"] == "empty":
                add("P1", name, col, "整列为空", "字段无法使用", "确认上游是否已停止写入")
                continue
            if c["missing_rate"] > 0.3:
                add("P1", name, col, f"缺失率 {viz.fmt_pct(c['missing_rate'], 1)}", "基于该字段的分析会丢掉大量样本，且缺失可能不是随机的",
                    "了解缺失原因（可选填、新增字段、埋点遗漏），分析时单独列出缺失组")
            if c["pseudo_null"]:
                tokens = "、".join(f"“{k}”" for k in c["pseudo_null_tokens"])
                add("P1", name, col, f"{viz.fmt_num(c['pseudo_null'])} 个伪缺失值：{tokens}",
                    "这些值会被当成有效类别或导致类型转换失败，缺失率被低估", "统一转成 NULL；Hive 导出的 \\N 需要在读取时声明")
            if c.get("placeholders"):
                tokens = "、".join(f"“{k}”（{viz.fmt_num(v)}）" for k, v in c["placeholders"].items())
                add("P2", name, col, f"疑似占位值：{tokens}",
                    "如果它们代表“未知 / 缺失”，缺失率被低估，并会被当成一个有效类别", "确认是业务取值（如“无退款”）还是缺失；若是缺失统一转成 NULL")
            if c["distinct"] == 1 and c["rows"] > 1 and c["type"] != "empty":
                add("P2", name, col, "常量列（只有一个取值）", "对分析没有信息量", "确认是否被过滤条件写死，或直接忽略")
            if c["type"] == "number_as_text":
                add("P1", name, col, f"数值以文本存储（例如 {'、'.join(c['format_examples'][:3])}）",
                    "直接求和、排序会出错或报错", "去掉千分位、货币符号和百分号后转为数值，并确认百分比的单位")
            if c.get("mixed_numeric_share"):
                add("P1", name, col, f"混合类型：{viz.fmt_pct(c['mixed_numeric_share'], 0)} 是数字，其余是文本",
                    "类型转换会失败或静默产生空值", "列出非数字取值，确认是编码、单位还是脏数据")
            if c.get("invalid_count"):
                add("P1", name, col, f"{viz.fmt_num(c['invalid_count'])} 个无法解析的值（例如 {'、'.join(map(str, c['invalid_examples'][:3]))}）",
                    "转换时会变成空值", "确认这些值的含义后清洗")
            if c.get("excel_errors"):
                add("P1", name, col, f"{viz.fmt_num(c['excel_errors'])} 个 Excel 公式错误值（#REF!、#DIV/0! 等）",
                    "这些单元格的原始值已经丢失，计入统计会出错", "回到源表修复公式后重新导出，不要只替换成空值")
            if c.get("scientific_values"):
                sev = "P0" if c.get("scientific_id") else "P1"
                add(sev, name, col, f"{viz.fmt_num(c['scientific_values'])} 个值是科学计数法（例如 {'、'.join(c['scientific_examples'][:2])}）",
                    "超过 15 位的数字经 Excel 处理后后几位已经丢失且不可恢复，关联和去重都会出错", "回到源系统按文本重新导出，不要经过 Excel 另存")
            if c.get("datetime_source") == "excel_serial":
                add("P1", name, col, "日期以 Excel 序列号存储（例如 45000 表示 2023-03-15）",
                    "按数字读取时日期含义丢失，分区和时间过滤都会失败", "按 1899-12-30 为基准换算成日期后再使用")
            if c.get("mixed_date_formats"):
                forms = "、".join(f"{k}（{viz.fmt_num(v)}）" for k, v in c["mixed_date_formats"].items())
                add("P1", name, col, f"同一列有多种日期写法：{forms}",
                    "按单一格式解析会把另一部分变成空值，时间范围和趋势都会错", "先统一成 YYYY-MM-DD；像 5月3日 这种缺年份的写法要先确认年份")
            if c.get("leading_zero_values"):
                add("P1", name, col, f"{viz.fmt_num(c['leading_zero_values'])} 个值有前导零",
                    "按数字读取会丢掉前导零，关联不上", "该字段必须按字符串读取和存储")
            if c.get("long_digit_values"):
                add("P1", name, col, f"{viz.fmt_num(c['long_digit_values'])} 个 16 位以上的数字 ID",
                    "Excel 和部分工具会把超过 15 位的数字截断成科学计数法", "按字符串读取；不要经过 Excel 中转")
            if c.get("case_variants"):
                examples = "；".join(" / ".join(v) for v in c["case_variants"][:3])
                add("P2", name, col, f"同一取值有多种写法：{examples}", "分组统计会被拆成多组", "统一大小写和分隔符后再分组")
            if c["whitespace_values"]:
                add("P2", name, col, f"{viz.fmt_num(c['whitespace_values'])} 个值带首尾空格", "看起来相同的值关联不上、分组被拆开", "读取时去除首尾空格")
            if c["type"] == "datetime":
                if c.get("future"):
                    add("P1", name, col, f"{viz.fmt_num(c['future'])} 个未来时间", "时间范围和时长计算会错", "检查时区、客户端时间或测试数据")
                if c.get("suspicious_defaults"):
                    add("P1", name, col, f"{viz.fmt_num(c['suspicious_defaults'])} 个疑似默认日期（1970 年、2099 年或 1 月 1 日）",
                        "这些通常是“未知”的占位值，会拉偏时间分布", "转成 NULL 后再分析")
            if c["type"] in ("integer", "number", "number_as_text"):
                if c.get("outliers") and c["outliers"] / max(c["rows"], 1) > 0.001:
                    lo, hi = c["outlier_fences"]
                    add("P2", name, col, f"{viz.fmt_num(c['outliers'])} 个极端值（超出 [{viz.fmt_num(lo, 1)}, {viz.fmt_num(hi, 1)}]）",
                        "均值和求和会被少数值主导", "确认是真实大额还是脏数据；汇报时用中位数或分位数")
                money_like = any(k in col.lower() for k in ("amount", "price", "gmv", "fee", "cost", "金额", "价格"))
                if money_like and c.get("negatives"):
                    add("P2", name, col, f"{viz.fmt_num(c['negatives'])} 个负值", "可能是退款、冲正，直接求和会抵消收入", "确认负值含义，必要时分开统计")
        for corr in t["correlations"][:3]:
            if abs(corr["pearson"]) >= 0.95:
                add("P2", name, f"{corr['a']} / {corr['b']}", f"两列高度相关（r={corr['pearson']:.2f}）",
                    "可能是同一信息的两种表示，建模时会造成共线性或泄露", "确认两列的业务含义，保留一列")
    for j in joins:
        if j["orphan_rows"]:
            add("P0" if j["orphan_rate"] > 0.05 else "P1", j["join"].split(".")[0], j["join"],
                f"{viz.fmt_pct(j['orphan_rate'], 1)} 的关联键在主表中找不到（{viz.fmt_num(j['orphan_rows'])} 行）",
                "内连接会丢掉这些行，左连接会产生空维度", "确认主表是否完整、时间范围是否一致、键是否需要清洗")
        if not j["parent_unique"]:
            add("P0", j["join"].split("=")[1].split(".")[0], j["join"], "关联的主表键不唯一",
                "关联后数据被放大，指标重复计算", "先把主表去重到键粒度再关联")
    issues.sort(key=lambda x: (SEVERITY_ORDER[x["severity"]], x["table"]))
    return issues


def build_verdict(issues: list[dict]) -> dict:
    counts = Counter(i["severity"] for i in issues)
    if counts["P0"]:
        return {"level": "bad", "title": f"不建议直接使用：{counts['P0']} 个 P0 问题会导致结果算错",
                "counts": dict(counts), "next_steps": ["先处理所有 P0 问题（主键、错位、关联）再做任何分析", "P1 问题在分析口径中显式处理并写明假设"]}
    if counts["P1"]:
        return {"level": "warning", "title": f"修正后可用：{counts['P1']} 个 P1 问题需要在分析口径中处理",
                "counts": dict(counts), "next_steps": ["逐条处理 P1 问题，或在分析中显式说明影响", "确认字段含义和表粒度后进入专项分析"]}
    return {"level": "good", "title": "可以使用：未发现会影响结论的问题", "counts": dict(counts),
            "next_steps": ["确认字段含义和表粒度后进入专项分析"]}


# ---------------------------------------------------------------------------
# HTML 报告
# ---------------------------------------------------------------------------

TYPE_NAMES = {"integer": "整数", "number": "数值", "number_as_text": "文本型数字", "datetime": "时间", "boolean": "布尔",
              "id": "ID", "category": "类别", "string": "字符串", "text": "长文本", "empty": "空"}


def _field_summary(c: dict) -> str:
    t = c["type"]
    if t in ("integer", "number", "number_as_text") and c.get("stats"):
        s = c["stats"]
        return f"中位数 {viz.fmt_num(s['median'], 2)} · P99 {viz.fmt_num(s['p99'], 2)} · 最大 {viz.fmt_num(s['max'], 2)}"
    if t == "datetime" and c.get("range"):
        return f"{c['range'][0][:10]} ~ {c['range'][1][:10]}"
    if c.get("top_values"):
        return " · ".join(f"{v}（{viz.fmt_num(n)}）" for v, n in c["top_values"][:3])
    return "—"


def render_html(result: dict) -> str:
    verdict, issues = result["verdict"], result["issues"]
    blocks = []
    counts = verdict["counts"]
    body = "处理优先级：" + "；".join(verdict["next_steps"])
    blocks.append(viz.callout(verdict["level"], verdict["title"], body))
    blocks.append(viz.section("体检概览", viz.stat_tiles([
        {"label": "数据表", "value": str(len(result["tables"])),
         "note": "、".join(t["name"] for t in result["tables"])},
        {"label": "总行数", "value": viz.fmt_num(sum(t["meta"]["rows_total"] for t in result["tables"])),
         "note": f"{sum(len(t['columns']) for t in result['tables'])} 个字段"},
        {"label": "P0 问题", "value": str(counts.get("P0", 0)), "tone": "bad" if counts.get("P0") else "neutral",
         "delta": "会导致结果算错" if counts.get("P0") else "无"},
        {"label": "P1 / P2 问题", "value": f"{counts.get('P1', 0)} / {counts.get('P2', 0)}", "note": "P1 需在口径中处理"},
    ])))
    status = {"P0": "fail", "P1": "warn", "P2": "info"}
    if issues:
        blocks.append(viz.section("问题清单（按严重程度）", viz.checklist([
            {"status": status[i["severity"]], "title": f"[{i['severity']}] {i['table']}" + (f" · {i['column']}" if i["column"] else "") + f"：{i['title']}",
             "detail": f"影响：{i['impact']}。建议：{i['action']}"} for i in issues[:40]
        ]), lead="P0 会直接导致结果算错；P1 需要在分析口径中处理；P2 了解即可。"))

    for j in result["joins"]:
        blocks.append(viz.section(f"关联检查：{j['join']}", viz.table(
            ["子表行数", "找不到主表的行", "孤儿比例", "主表键唯一", "主表无子记录", "单键最多子记录"],
            [[viz.fmt_num(j["child_rows"]), viz.fmt_num(j["orphan_rows"]), viz.fmt_pct(j["orphan_rate"], 1),
              "是" if j["parent_unique"] else "否", viz.fmt_num(j["parent_without_child"]), viz.fmt_num(j["fanout_max"])]],
            numeric=(0, 1, 2, 4, 5))))

    for t in result["tables"]:
        meta = t["meta"]
        parts = [viz.table(
            ["行数", "字段数", "编码", "分隔符", "主键候选", "重复行", "时间字段"],
            [[viz.fmt_num(meta["rows_total"]), str(len(t["columns"])), meta["encoding"], meta["delimiter"],
              "、".join(t["key_candidates"]) or ("、".join(t["key_check"]["columns"]) + "（指定）" if t["key_check"] else "无"),
              viz.fmt_num(t["duplicate_rows"]), t["time_column"] or "—"]], numeric=(0, 1, 5))]
        trend = t["trend"]
        if trend.get("dates") and len(trend["dates"]) >= 3:
            labels = [d[5:] for d in trend["dates"]]
            parts.append(viz.line_chart(labels, [{"name": "行数", "values": trend["rows"]}], fmt=lambda v: viz.fmt_num(v, 0),
                                        title=f"每日数据量（按 {t['time_column']}）",
                                        caption="断档（0 行）通常是任务失败或分区缺失；突增可能是重复导入、补数或大促。"))
        rows = [[c["name"], TYPE_NAMES.get(c["type"], c["type"]), viz.fmt_pct(c["missing_rate"], 1), viz.fmt_num(c["distinct"]),
                 _field_summary(c)] for c in t["columns"]]
        parts.append(viz.table(["字段", "推断类型", "缺失率", "不同取值", "分布摘要"], rows, numeric=(2, 3)))
        cats = [c for c in t["columns"] if c["type"] in ("category", "boolean") and 1 < c["distinct"] <= 20][:3]
        for c in cats:
            top = c["top_values"][:8]
            parts.append(viz.bar_chart([str(v) for v, _ in top], [n for _, n in top], fmt=lambda v: viz.fmt_num(v, 0),
                                       title=f"{c['name']} 取值分布（Top {len(top)}）"))
        blocks.append(viz.section(f"表 {t['name']}", *parts, lead=meta["path"]))

    blocks.append(viz.section("说明", viz.paragraph(
        "类型由数据实际取值推断，字段含义需要结合业务确认。极端值按 3 倍四分位距判断；数据量突增按中位数绝对偏差（稳健 z > 5）判断；"
        "伪缺失包括 NULL、\\N、-、未知 等占位值。体检只说明“数据长什么样”，不代表业务结论。")))
    return viz.html_report("数据体检报告", blocks, subtitle="、".join(t["name"] for t in result["tables"]), brand="拾穗数据 · 数据体检")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _round(obj):
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    return obj


def _pairs(specs: list[str], what: str) -> dict:
    out = {}
    for spec in specs:
        name, _, value = spec.partition("=")
        if not value:
            raise SystemExit(f"{what} 格式应为 表名=值，收到：{spec}")
        out[name] = value
    return out


def cmd_profile(args: argparse.Namespace) -> int:
    paths = _pairs(args.table, "--table")
    if not paths:
        raise SystemExit("至少需要一个 --table 表名=路径")
    keys = {k: v.split("+") for k, v in _pairs(args.key, "--key").items()}
    time_cols = _pairs(args.time_col, "--time-col")
    sheets = _pairs(args.sheet, "--sheet")
    TIME.configure(args.tz)
    tables = {name: profile_table(name, path, keys.get(name), time_cols.get(name), args.max_rows, sheets.get(name)) for name, path in paths.items()}
    joins = [check_join(spec, tables) for spec in args.join]
    issues = build_issues(tables, joins)
    result = {"tables": list(tables.values()), "joins": joins, "issues": issues, "verdict": build_verdict(issues)}
    for t in result["tables"]:
        t["trend"] = {k: v for k, v in t["trend"].items() if k != "dates" or len(v) <= 400}
    if args.html:
        viz.save(args.html, render_html(result))
    output = _round(result)
    if args.html:
        output["html_report"] = os.path.abspath(args.html)
    text = json.dumps(output, ensure_ascii=False, indent=2, default=str)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="数据体检（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("profile", help="对一张或多张表做体检")
    p.add_argument("--table", action="append", default=[], help="表名=CSV、TSV 或 xlsx 路径，可重复")
    p.add_argument("--sheet", action="append", default=[], help="表名=工作表名，只对 xlsx 有效，默认第一个工作表")
    p.add_argument("--tz", default="+08:00", help="业务时区，带时区的时间会换算到这里，默认 +08:00")
    p.add_argument("--key", action="append", default=[], help="表名=主键列，组合主键用 + 连接，如 orders=order_id 或 events=user_id+event_time")
    p.add_argument("--join", action="append", default=[], help="关联检查：子表.列=主表.列，如 orders.user_id=users.user_id")
    p.add_argument("--time-col", action="append", default=[], help="表名=时间列，用于趋势和分区一致性检查；默认自动选择")
    p.add_argument("--max-rows", type=int, help="每张表最多体检的行数，在全表上随机抽样（结果会注明）")
    p.add_argument("--html", help="输出 HTML 报告路径")
    p.add_argument("--json", help="同时把 JSON 写入文件")
    p.set_defaults(func=cmd_profile)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(sio.run_cli(main))
