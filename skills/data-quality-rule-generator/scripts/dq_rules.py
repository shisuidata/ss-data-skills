#!/usr/bin/env python3
"""数据质量规则生成器：从表结构 JSON 或 eda.py 体检结果生成规则，输出 SQL、dbt、Great Expectations（仅依赖 Python 标准库）。

  python3 dq_rules.py generate --schema table.json --sql rules.sql --dbt schema.yml --ge suite.json
  python3 dq_rules.py generate --eda eda.json --table orders --partition dt --sql rules.sql

所有 SQL 都返回 invalid_count，0 表示通过。阈值如果不是用户给的，会标 assumption=true，上线前必须确认。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_io as sio  # noqa: E402

BLOCK, ALERT, OBSERVE = "阻断", "告警", "观察"
ACTIONS = {BLOCK: "任务失败或禁止发布", ALERT: "通知负责人处理", OBSERVE: "记录趋势，暂不拦截"}
MONEY_RE = re.compile(r"amount|price|gmv|fee|cost|金额|价格", re.I)
RATE_RE = re.compile(r"rate|ratio|pct|percent|率|占比", re.I)


def quote(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


class Builder:
    def __init__(self, schema: dict, biz_date: str) -> None:
        self.schema = schema
        self.table = schema["table"]
        self.partition = schema.get("partition")
        self.biz_date = biz_date
        self.rules: list[dict] = []

    def where(self, extra: str = "") -> str:
        parts = ([f"{self.partition} = {self.biz_date}"] if self.partition else []) + ([extra] if extra else [])
        return "\nwhere " + "\n  and ".join(parts) if parts else ""

    def add(self, kind: str, target: str, description: str, severity: str, sql: str, assumption: bool | str = False, spec: dict | None = None) -> None:
        number = len(self.rules) + 1
        self.rules.append({"id": f"dq_{number:03d}_{kind}", "type": kind, "object": target, "description": description, "severity": severity,
                           "action": ACTIONS[severity], "assumption": assumption, "sql": sql, "spec": spec or {}})

    def build(self) -> list[dict]:
        schema, table = self.schema, self.table
        if self.partition:
            freshness = schema.get("freshness") or {}
            deadline = freshness.get("deadline")
            self.add("freshness", self.partition, f"{self.partition} 当天分区按时产出" + (f"（{deadline} 前）" if deadline else ""), BLOCK,
                     f"select case when count(*) = 0 then 1 else 0 end as invalid_count\nfrom {table}{self.where()}",
                     False if deadline else "产出时限未提供，调度时间需要确认")
        floor = (schema.get("row_count") or {}).get("min", 1)
        self.add("row_count", table, f"分区行数不少于 {floor}", BLOCK,
                 f"select case when count(*) < {floor} then 1 else 0 end as invalid_count\nfrom {table}{self.where()}",
                 False if schema.get("row_count") else "最小行数按 1 处理")
        grain = schema.get("grain") or []
        if grain:
            cols = ", ".join(grain)
            self.add("unique", cols, f"表粒度 {cols} 唯一", BLOCK,
                     f"select count(*) as invalid_count\nfrom (\n  select {cols}\n  from {table}{self.where()}\n  group by {cols}\n  having count(*) > 1\n) t",
                     schema.get("grain_assumption", False), {"columns": grain})
        for col in schema.get("columns") or []:
            self._column(col)
        for logic in schema.get("logic") or []:
            self.add("logic", logic["name"], logic["name"], logic.get("severity", ALERT),
                     f"select count(*) as invalid_count\nfrom {table}{self.where('not (' + logic['expr'] + ')')}")
        for metric in schema.get("metrics") or []:
            self._fluctuation(metric)
        for rec in schema.get("reconcile") or []:
            self._reconcile(rec)
        return self.rules

    def _column(self, col: dict) -> None:
        name, table = col["name"], self.table
        assumption = col.get("assumption", False)
        if col.get("nullable") is False:
            severity = BLOCK if name in (self.schema.get("grain") or []) else ALERT
            self.add("not_null", name, f"{name} 不为空", severity, f"select count(*) as invalid_count\nfrom {table}{self.where(f'{name} is null')}", assumption)
        if col.get("enum"):
            values = ", ".join(quote(v) for v in col["enum"])
            self.add("enum", name, f"{name} 在合法取值内", ALERT, f"select count(*) as invalid_count\nfrom {table}{self.where(f'{name} not in ({values})')}",
                     col.get("enum_assumption", assumption), {"values": col["enum"]})
        if col.get("min") is not None or col.get("max") is not None:
            conds = ([f"{name} < {col['min']}"] if col.get("min") is not None else []) + ([f"{name} > {col['max']}"] if col.get("max") is not None else [])
            joined = " or ".join(conds)
            self.add("range", name, f"{name} 在 [{col.get('min', '-∞')}, {col.get('max', '+∞')}] 内", ALERT,
                     f"select count(*) as invalid_count\nfrom {table}{self.where(f'({joined})')}", col.get("range_assumption", assumption),
                     {"min": col.get("min"), "max": col.get("max")})
        if col.get("numerator") and col.get("denominator"):
            a, b = col["numerator"], col["denominator"]
            self.add("logic", name, f"{a} 不大于 {b}", ALERT, f"select count(*) as invalid_count\nfrom {table}{self.where(f'{a} > {b}')}",
                     f"{b} 为 0 时 {name} 应为空还是 0，需要确认")
        if col.get("ref"):
            parent, _, parent_col = col["ref"].rpartition(".")
            self.add("reference", name, f"{name} 能关联到 {col['ref']}", ALERT,
                     f"select count(*) as invalid_count\nfrom {table} t\nleft join {parent} p\n  on t.{name} = p.{parent_col}\nwhere p.{parent_col} is null\n  and t.{name} is not null"
                     + (f"\n  and t.{self.partition} = {self.biz_date}" if self.partition else ""), assumption, {"ref": col["ref"]})

    def _fluctuation(self, metric: dict) -> None:
        name, expr = metric["name"], metric["expr"]
        window, threshold = metric.get("window_days", 7), metric.get("threshold_pct")
        assumed = threshold is None
        threshold = 0.3 if assumed else threshold
        table, p = self.table, self.partition or "dt"
        sql = (f"with today as (\n  select {expr} as v from {table} where {p} = {self.biz_date}\n),\n"
               f"history as (\n  select avg(v) as v\n  from (\n    select {p}, {expr} as v\n    from {table}\n"
               f"    where {p} >= date_sub({self.biz_date}, {window}) and {p} < {self.biz_date}\n    group by {p}\n  ) d\n)\n"
               f"select case when h.v is null or h.v = 0 then 0\n            when abs(t.v - h.v) / abs(h.v) > {threshold} then 1 else 0 end as invalid_count\n"
               "from today t cross join history h")
        self.add("fluctuation", name, f"{name} 与近 {window} 天均值偏差不超过 {threshold:.0%}", metric.get("severity", ALERT), sql,
                 "波动阈值未基于历史数据，上线前用历史分布校准" if assumed else False, {"expr": expr, "window_days": window, "threshold_pct": threshold})

    def _reconcile(self, rec: dict) -> None:
        tolerance = rec.get("tolerance_pct", 0.001)
        target = f"select {rec['target_expr']} as v from {self.table}" + (f" where {self.partition} = {self.biz_date}" if self.partition else "")
        source = f"select {rec['source_expr']} as v from {rec['source']}" + (f" where {rec['source_filter']}" if rec.get("source_filter") else "")
        sql = (f"select case when s.v is null or t.v is null then 1\n            when abs(t.v - s.v) > {tolerance} * greatest(abs(s.v), 1) then 1 else 0 end as invalid_count\n"
               f"from ({target}) t\ncross join ({source}) s")
        self.add("reconcile", rec["name"], f"{rec['name']}（容差 {tolerance:.2%}）", rec.get("severity", BLOCK), sql, "容差未提供" if "tolerance_pct" not in rec else False)


def from_eda(eda: dict, table_name: str | None, partition: str | None) -> dict:
    tables = eda.get("tables") or []
    table = next((t for t in tables if t["name"] == table_name), None) if table_name else (tables[0] if len(tables) == 1 else None)
    if table is None:
        raise SystemExit(f"请用 --table 指定表，可选：{[t['name'] for t in tables]}")
    columns, assumed = [], "基于样本体检推断，上线前确认"
    for c in table["columns"]:
        col: dict = {"name": c["name"], "assumption": assumed}
        if c.get("type") == "empty":
            continue
        if c.get("missing_rate") == 0:
            col["nullable"] = False
        if c.get("type") == "category" and 1 < c.get("distinct", 0) <= 20:
            col["enum"] = [v for v, _ in c.get("top_values", [])] if c["distinct"] <= 8 else None
        stats = c.get("stats") or {}
        if c.get("type") in ("integer", "number") and stats:
            if (MONEY_RE.search(c["name"]) or stats.get("min", -1) >= 0) and not c.get("negatives"):
                col["min"] = 0
            if RATE_RE.search(c["name"]) and stats.get("max", 2) <= 1:
                col["max"] = 1
        if len(col) > 2:
            columns.append(col)
    key = table.get("key_check") or {}
    grain = key.get("columns") or (table.get("key_candidates") or [])[:1]
    prefix = table["name"] + "."
    for join in eda.get("joins") or []:
        left, _, right = join["join"].partition("=")
        if left.startswith(prefix):
            name = left[len(prefix):]
            col = next((x for x in columns if x["name"] == name), None)
            if col is None:
                col = {"name": name, "assumption": assumed}
                columns.append(col)
            col["ref"] = right
    return {"table": table["name"], "partition": partition, "grain": grain, "grain_assumption": False if key.get("columns") else "表粒度由体检推断", "columns": columns}


def to_dbt(schema: dict, rules: list[dict], legacy: bool = False) -> str:
    """默认使用 dbt 1.10.5 起的 arguments 写法（dbt v2 必须如此）；legacy 输出旧版本的平铺写法。"""
    nest = [] if legacy else ["              arguments:"]
    pad = "              " if legacy else "                "
    lines = ["version: 2", "", "models:", f"  - name: {schema['table']}", "    columns:"]
    names = {c["name"]: c for c in schema.get("columns") or []}
    grain = schema.get("grain") or []
    for name in list(dict.fromkeys(list(names) + grain)):
        col = names.get(name, {})
        tests = []
        if col.get("nullable") is False or name in grain:
            tests.append("not_null")
        if len(grain) == 1 and name == grain[0]:
            tests.append("unique")
        if col.get("enum"):
            tests.append({"accepted_values": col["enum"]})
        if col.get("ref"):
            tests.append({"relationships": col["ref"]})
        lines.append(f"      - name: {name}")
        if tests:
            lines.append("        data_tests:")
            for test in tests:
                if test in ("not_null", "unique"):
                    lines.append(f"          - {test}")
                elif "accepted_values" in test:
                    lines.append("          - accepted_values:")
                    lines += nest
                    lines.append(pad + "values: [" + ", ".join(json.dumps(v, ensure_ascii=False) for v in test["accepted_values"]) + "]")
                else:
                    parent, _, field = test["relationships"].rpartition(".")
                    lines.append("          - relationships:")
                    lines += nest
                    lines.append(pad + f"to: ref('{parent}')")
                    lines.append(pad + f"field: {field}")
    if len(grain) > 1:
        lines += ["    data_tests:", "      - dbt_utils.unique_combination_of_columns:"]
        lines += [] if legacy else ["          arguments:"]
        lines.append(("          " if legacy else "            ") + "combination_of_columns: [" + ", ".join(grain) + "]")
    others = [r for r in rules if r["type"] in ("range", "logic", "fluctuation", "reconcile", "freshness")]
    if others:
        lines += ["", "# 下面这些规则没有内置 dbt test，建议写成 singular test，SQL 见 --sql 的输出：", *[f"#   {r['id']}: {r['description']}" for r in others]]
    return "\n".join(lines) + "\n"


def to_ge(schema: dict, rules: list[dict]) -> dict:
    expectations = []
    for r in rules:
        spec = r["spec"]
        kwargs, kind = None, None
        if r["type"] == "not_null":
            kind, kwargs = "expect_column_values_to_not_be_null", {"column": r["object"]}
        elif r["type"] == "unique":
            cols = spec["columns"]
            kind, kwargs = ("expect_column_values_to_be_unique", {"column": cols[0]}) if len(cols) == 1 else ("expect_compound_columns_to_be_unique", {"column_list": cols})
        elif r["type"] == "enum":
            kind, kwargs = "expect_column_values_to_be_in_set", {"column": r["object"], "value_set": spec["values"]}
        elif r["type"] == "range":
            kind, kwargs = "expect_column_values_to_be_between", {"column": r["object"], "min_value": spec.get("min"), "max_value": spec.get("max")}
        if kind:
            expectations.append({"type": kind, "kwargs": kwargs, "meta": {"rule_id": r["id"], "severity": r["severity"]}})
    return {"name": f"{schema['table']}_suite", "expectations": expectations,
            "meta": {"note": "只包含 Great Expectations 有内置表达的规则；波动、对账等规则请使用 SQL 输出"}}


def to_sql(rules: list[dict]) -> str:
    blocks = []
    for r in rules:
        head = f"-- {r['id']} [{r['severity']}] {r['description']}"
        if r["assumption"]:
            head += f"\n-- 待确认：{r['assumption'] if isinstance(r['assumption'], str) else '依据是假设'}"
        blocks.append(f"{head}\n{r['sql']};")
    return "\n\n".join(blocks) + "\n"


def cmd_generate(args: argparse.Namespace) -> int:
    if bool(args.schema) == bool(args.eda):
        raise SystemExit("--schema 与 --eda 二选一")
    if args.schema:
        with open(args.schema, encoding=sio.detect_encoding(args.schema)) as handle:
            schema = json.load(handle)
        if "table" not in schema:
            raise SystemExit("表结构 JSON 缺少字段：table")
    else:
        with open(args.eda, encoding="utf-8") as handle:
            schema = from_eda(json.load(handle), args.table, args.partition)
    rules = Builder(schema, args.biz_date).build()
    outputs = {}
    for path, content in ((args.sql, to_sql(rules)), (args.dbt, to_dbt(schema, rules, args.dbt_legacy) if args.dbt else None),
                          (args.ge, json.dumps(to_ge(schema, rules), ensure_ascii=False, indent=2) + "\n" if args.ge else None)):
        if path:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
            outputs[os.path.basename(path)] = os.path.abspath(path)
    summary = {"table": schema["table"], "rule_count": len(rules), "by_severity": {s: sum(1 for r in rules if r["severity"] == s) for s in (BLOCK, ALERT, OBSERVE)},
               "assumptions": [{"id": r["id"], "note": r["assumption"] if isinstance(r["assumption"], str) else "依据是假设"} for r in rules if r["assumption"]],
               "rules": rules, "outputs": outputs}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="数据质量规则生成器（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate", help="生成质量规则")
    g.add_argument("--schema", help="表结构 JSON，见 references/schema-format.md")
    g.add_argument("--eda", help="eda.py 的 JSON 输出，按体检结果推断规则")
    g.add_argument("--table", help="--eda 模式下要处理的表名")
    g.add_argument("--partition", help="--eda 模式下的分区字段")
    g.add_argument("--biz-date", default=":biz_date", help="业务日期表达式，如 '${bizdate}'，默认 :biz_date")
    g.add_argument("--sql", help="输出 SQL 校验文件")
    g.add_argument("--dbt", help="输出 dbt schema.yml（dbt 1.10.5 及以上的 arguments 写法）")
    g.add_argument("--dbt-legacy", action="store_true", help="改用 dbt 1.10.5 以前的平铺写法")
    g.add_argument("--ge", help="输出 Great Expectations 1.x 规则集 JSON")
    g.set_defaults(func=cmd_generate)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(sio.run_cli(main))
