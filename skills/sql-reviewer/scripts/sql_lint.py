#!/usr/bin/env python3
"""SQL 静态检查：找出会导致算错、漏算、全表扫描的典型写法（仅依赖 Python 标准库）。

  python3 sql_lint.py check --sql query.sql --dialect spark --partition-col dt

不连接数据库，不判断业务口径。结果给 Agent 做第一轮筛查：确定的错误标 confidence=high，
依赖表结构才能确认的问题标 confidence=low，必须结合表结构和口径人工判断。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_io as sio  # noqa: E402

DIALECTS = ("hive", "spark", "flink", "clickhouse", "mysql", "postgres", "trino", "doris", "starrocks", "generic")
INTEGER_DIVISION = {"postgres", "trino"}
DIVIDE_BY_ZERO_SENSITIVE = {"postgres", "trino", "clickhouse", "mysql"}
PARTITION_NAMES = {"dt", "ds", "pt", "p_date", "partition_date", "stat_date", "biz_date"}
JOIN_WORDS = {"left", "right", "full", "inner", "cross", "semi", "anti", "outer", "join", "natural", "global", "any", "asof"}
CLAUSES = {"where", "group", "having", "order", "limit", "qualify", "window", "union", "except", "intersect",
           "cluster", "distribute", "sort", "settings", "offset", "fetch"}
NOT_ALIAS = JOIN_WORDS | CLAUSES | {"on", "using", "lateral", "final", "as", "tablesample", "for"}
SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
TIME_NAME = re.compile(r"time|_at$|timestamp", re.I)
DATE_LITERAL = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WINDOW_NEEDS_ORDER = {"row_number", "rank", "dense_rank", "lag", "lead", "first_value", "last_value", "ntile", "percent_rank", "cume_dist"}
NOT_FUNCTIONS = {"in", "exists", "and", "or", "not", "on", "values", "over", "when", "then", "else", "case", "between", "any", "all"}


class Token:
    __slots__ = ("kind", "text", "low", "line")

    def __init__(self, kind: str, text: str, line: int) -> None:
        self.kind, self.text, self.low, self.line = kind, text, text.lower(), line


def preprocess(sql: str) -> str:
    """把 dbt 的 ref / source 换成表名，其余模板语法换成占位，行号保持不变。"""
    sql = re.sub(r"\{\{\s*ref\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}", r"\1", sql)
    sql = re.sub(r"\{\{\s*source\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}", r"\1.\2", sql)
    sql = re.sub(r"\{%.*?%\}", lambda m: "\n" * m.group(0).count("\n"), sql, flags=re.S)
    return re.sub(r"\{\{.*?\}\}", lambda m: "'__param__'" + "\n" * m.group(0).count("\n"), sql, flags=re.S)


def tokenize(sql: str) -> list[Token]:
    tokens, i, line, n = [], 0, 1, len(sql)
    word = re.compile(r"[A-Za-z_一-鿿][\w$一-鿿]*(?:\.(?:\*|[A-Za-z_一-鿿`\"][\w$一-鿿`\"]*))*")
    number = re.compile(r"\d+(?:\.\d+)?")
    while i < n:
        ch = sql[i]
        if ch == "\n":
            line += 1
            i += 1
        elif ch.isspace():
            i += 1
        elif sql.startswith("--", i):
            end = sql.find("\n", i)
            i = n if end < 0 else end
        elif sql.startswith("/*", i):
            end = sql.find("*/", i)
            end = n if end < 0 else end + 2
            line += sql.count("\n", i, end)
            i = end
        elif sql.startswith("${", i):
            end = sql.find("}", i)
            end = n if end < 0 else end + 1
            tokens.append(Token("param", sql[i:end], line))
            i = end
        elif ch == "'":
            j = i + 1
            while j < n and not (sql[j] == "'" and sql[j + 1:j + 2] != "'" and sql[j - 1] != "\\"):
                j += 2 if sql[j] == "'" else 1
            tokens.append(Token("str", sql[i + 1:j], line))
            line += sql.count("\n", i, j)
            i = j + 1
        elif ch in '`"':
            end = sql.find(ch, i + 1)
            end = n if end < 0 else end
            rest = word.match(sql, end + 1) if sql[end + 1:end + 2] == "." else None
            tokens.append(Token("word", sql[i + 1:end], line))
            i = end + 1
            if rest is None:
                continue
        else:
            match = word.match(sql, i)
            if match:
                tokens.append(Token("word", match.group(0).replace("`", "").replace('"', ""), line))
                i = match.end()
                continue
            match = number.match(sql, i)
            if match:
                tokens.append(Token("num", match.group(0), line))
                i = match.end()
                continue
            two = sql[i:i + 2]
            if two in ("<>", "!=", "<=", ">=", "==", "||", "::"):
                tokens.append(Token("op", two, line))
                i += 2
            else:
                tokens.append(Token("op", ch, line))
                i += 1
    return tokens


class Analyzer:
    def __init__(self, sql: str, dialect: str, partition_cols: set[str] | None) -> None:
        self.lines = sql.splitlines()
        self.tok = tokenize(preprocess(sql))
        self.dialect = dialect
        self.partition_given = partition_cols or None
        self.partition_cols = partition_cols or PARTITION_NAMES
        self.findings: list[dict] = []
        self.seen: set[tuple] = set()
        self.depth, self.match = self._parens()
        self.ctes = self._ctes()
        self.scopes = self._scopes()
        self.tables: Counter = Counter()

    def _parens(self) -> tuple[list[int], dict[int, int]]:
        depth, match, stack, level = [], {}, [], 0
        for i, t in enumerate(self.tok):
            if t.text == ")" and t.kind == "op":
                level = max(level - 1, 0)
                if stack:
                    match[stack.pop()] = i
            depth.append(level)
            if t.text == "(" and t.kind == "op":
                stack.append(i)
                level += 1
        for i in stack:
            match[i] = len(self.tok) - 1
        return depth, match

    def _ctes(self) -> set[str]:
        names = set()
        for i in range(len(self.tok) - 3):
            a, b, c, d = self.tok[i:i + 4]
            if a.kind == "word" and b.low == "as" and c.text == "(" and d.low in ("select", "with"):
                names.add(a.low)
        return names

    def _scopes(self) -> list[dict]:
        scopes = []
        for i, t in enumerate(self.tok):
            if t.low != "select" or t.kind != "word":
                continue
            d, end = self.depth[i], len(self.tok)
            for j in range(i + 1, len(self.tok)):
                if self.depth[j] < d or (self.depth[j] == d and self.tok[j].low in (";", "union", "except", "intersect")):
                    end = j
                    break
            scopes.append(self._parse_scope(i, end, d))
        return scopes

    def _top(self, start: int, end: int, d: int):
        for i in range(start, end):
            if self.depth[i] == d:
                yield i

    def _parse_scope(self, start: int, end: int, d: int) -> dict:
        clauses: dict[str, int] = {}
        for i in self._top(start + 1, end, d):
            low = self.tok[i].low
            if low == "from" and "from" not in clauses:
                clauses["from"] = i
            elif low in CLAUSES and "from" in clauses and low not in clauses:
                clauses[low] = i
        stops = sorted(v for k, v in clauses.items() if k != "from") + [end]
        scope = {"start": start, "end": end, "depth": d, "clauses": clauses, "sources": [], "where": None}
        if "from" in clauses:
            from_end = next(s for s in stops if s > clauses["from"])
            scope["sources"] = self._parse_sources(clauses["from"] + 1, from_end, d)
        if "where" in clauses:
            where_end = next((s for s in stops if s > clauses["where"]), end)
            scope["where"] = (clauses["where"] + 1, where_end)
        return scope

    def _read_source(self, i: int, end: int) -> tuple[dict, int]:
        source = {"table": None, "alias": None, "line": self.tok[i].line if i < end else 0, "subquery": False}
        if i < end and self.tok[i].text == "(":
            source["subquery"] = True
            i = self.match[i] + 1
        elif i < end:
            source["table"] = self.tok[i].text
            i += 1
            if i < end and self.tok[i].text == "(":
                source["subquery"] = True
                i = self.match[i] + 1
        if i < end and self.tok[i].low == "as":
            i += 1
        if i < end and self.tok[i].kind == "word" and self.tok[i].low not in NOT_ALIAS:
            source["alias"] = self.tok[i].text
            i += 1
        if i < end and self.tok[i].low == "final":
            i += 1
        source["alias"] = source["alias"] or (source["table"].split(".")[-1] if source["table"] else None)
        return source, i

    def _parse_sources(self, start: int, end: int, d: int) -> list[dict]:
        sources, i = [], start
        first, i = self._read_source(i, end)
        first.update(join="base", on=None)
        sources.append(first)
        while i < end:
            t = self.tok[i]
            if self.depth[i] != d:
                i += 1
                continue
            if t.text == ",":
                kind, i = "comma", i + 1
            elif t.low in JOIN_WORDS:
                words = []
                while i < end and self.tok[i].low in JOIN_WORDS:
                    words.append(self.tok[i].low)
                    i += 1
                kind = " ".join(w for w in words if w not in ("join", "outer", "global")) or "inner"
            else:
                i += 1
                continue
            source, i = self._read_source(i, end)
            source.update(join=kind, on=None)
            if i < end and self.tok[i].low in ("on", "using"):
                source["using"] = self.tok[i].low == "using"
                on_start = i + 1
                i += 1
                while i < end and not (self.depth[i] == d and (self.tok[i].low in JOIN_WORDS or self.tok[i].text == ",")):
                    i += 1
                source["on"] = (on_start, i)
            sources.append(source)
        return sources

    def add(self, rule: str, severity: str, line: int, message: str, fix: str, confidence: str = "high") -> None:
        key = (rule, line, message)
        if key in self.seen:
            return
        self.seen.add(key)
        snippet = self.lines[line - 1].strip() if 0 < line <= len(self.lines) else ""
        self.findings.append({"rule": rule, "severity": severity, "confidence": confidence, "line": line,
                              "snippet": snippet[:160], "message": message, "fix": fix})

    def _predicates(self, start: int, end: int) -> list[tuple[int, int]]:
        out, cur, i, between = [], start, start, 0
        while i < end:
            t = self.tok[i]
            if t.text == "(" and t.kind == "op":
                i = self.match[i] + 1
                continue
            if t.low == "between":
                between += 1
            elif t.low == "and":
                if between:
                    between -= 1
                else:
                    out.append((cur, i))
                    cur = i + 1
            i += 1
        out.append((cur, end))
        return [p for p in out if p[0] < p[1]]

    def _refs(self, start: int, end: int, alias: str) -> bool:
        prefix = alias.lower() + "."
        return any(self.tok[i].kind == "word" and self.tok[i].low.startswith(prefix) for i in range(start, end))

    def _partition_hit(self, start: int, end: int, source: dict, single: bool) -> bool:
        for i in range(start, end):
            t = self.tok[i]
            if t.kind != "word":
                continue
            if "." in t.low:
                head, _, col = t.low.rpartition(".")
                if col in self.partition_cols and head.split(".")[-1] == (source["alias"] or "").lower():
                    return True
            elif t.low in self.partition_cols and (single or source["join"] == "base"):
                return True
        return False

    def run(self) -> None:
        self._global_rules()
        all_sources = [s for scope in self.scopes for s in scope["sources"]]
        physical = [s for s in all_sources if s["table"] and not s["subquery"] and s["table"].lower() not in self.ctes]
        self.tables = Counter(s["table"] for s in physical)
        any_filtered = False
        for scope in self.scopes:
            for source in scope["sources"]:
                if self._source_filtered(scope, source):
                    any_filtered = True
        for scope in self.scopes:
            self._join_rules(scope)
            self._where_rules(scope)
            self._partition_rules(scope, any_filtered)
            self._fanout_rule(scope)
        self.findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["line"]))

    def _source_filtered(self, scope: dict, source: dict) -> bool:
        single = len(scope["sources"]) == 1
        where_hit = scope["where"] and self._partition_hit(*scope["where"], source, single)
        on_hit = source.get("on") and self._partition_hit(*source["on"], source, single)
        return bool(where_hit or on_hit)

    def _global_rules(self) -> None:
        tok = self.tok
        for i, t in enumerate(tok):
            nxt = tok[i + 1] if i + 1 < len(tok) else None
            prev = tok[i - 1] if i else None
            if t.text in ("=", "!=", "<>", "==") and t.kind == "op" and nxt is not None and nxt.low == "null":
                self.add("null_comparison", "P0", t.line, "用 = 或 <> 比较 NULL，结果永远不为真，条件形同虚设", "改成 IS NULL 或 IS NOT NULL")
            if t.low == "not" and nxt is not None and nxt.low == "in" and i + 3 < len(tok) and tok[i + 2].text == "(" and tok[i + 3].low == "select":
                self.add("not_in_subquery", "P1", t.line, "NOT IN 子查询只要返回一个 NULL，整个条件就不会命中任何行", "改成 NOT EXISTS 或 LEFT JOIN … IS NULL，或确保子查询字段非空", "low")
            if t.low == "union" and (nxt is None or nxt.low != "all"):
                self.add("union_distinct", "P2", t.line, "UNION 会去重并排序，开销大且可能吞掉合法的重复行", "确认不需要去重时改成 UNION ALL")
            if t.low == "group" and nxt is not None and nxt.low == "by" and i + 2 < len(tok) and tok[i + 2].kind == "num":
                self.add("group_by_ordinal", "P2", t.line, "GROUP BY 用列序号，调整 SELECT 顺序时容易悄悄算错", "写出字段名")
            if t.low == "select" and nxt is not None and (nxt.text == "*" or nxt.low.endswith(".*")) and self.depth[i] == 0:
                self.add("select_star", "P2", t.line, "最终结果 SELECT *，上游加字段会直接影响下游", "列出需要的字段")
            if t.low == "over" and nxt is not None and nxt.text == "(" and prev is not None and prev.text == ")":
                open_paren = next((j for j in range(i - 1, -1, -1) if self.match.get(j) == i - 1), None)
                func = tok[open_paren - 1].low if open_paren else ""
                body = range(i + 2, self.match[i + 1])
                if func in WINDOW_NEEDS_ORDER and not any(tok[j].low == "order" for j in body):
                    self.add("window_without_order", "P1", t.line, f"{func}() 的窗口没有 ORDER BY，取到哪一行不确定，每次运行可能不同", "补 ORDER BY，并加能打破平局的字段")
            if t.text == "/" and t.kind == "op" and nxt is not None:
                self._division(i)

    def _division(self, i: int) -> None:
        tok, t = self.tok, self.tok[i]
        nxt = tok[i + 1]
        guarded = nxt.low == "nullif"
        counts_denominator = nxt.low == "count"
        counts_numerator = tok[i - 1].text == ")" and any(
            self.match.get(j) == i - 1 and j > 0 and tok[j - 1].low == "count" for j in range(max(0, i - 40), i))
        if self.dialect in INTEGER_DIVISION and counts_denominator and counts_numerator:
            self.add("integer_division", "P0", t.line, f"{self.dialect} 中两个 COUNT 相除是整数除法，转化率会被截断成 0", "分子乘 1.0 或 CAST 成 DECIMAL")
        if self.dialect in DIVIDE_BY_ZERO_SENSITIVE and counts_denominator and not guarded:
            self.add("divide_by_zero", "P2", t.line, "分母可能为 0", "用 NULLIF(分母, 0) 保护", "low")

    def _join_rules(self, scope: dict) -> None:
        sources = scope["sources"]
        where = scope["where"]
        for source in sources[1:]:
            kind, line = source["join"], source["line"]
            if kind == "comma":
                alias = source["alias"] or ""
                linked = where and any(self._refs(a, b, alias) and any(self.tok[k].text == "=" for k in range(a, b))
                                       for a, b in self._predicates(*where))
                if not linked:
                    self.add("cartesian_join", "P0", line, f"逗号连接 {source['table'] or '子查询'} 没有关联条件，会产生笛卡尔积", "改成 JOIN … ON 并写清关联键")
            elif "cross" in kind:
                self.add("cross_join", "P2", line, "CROSS JOIN 会产生笛卡尔积，确认这是有意的", "数据量大时先限制两侧行数", "low")
            elif source.get("on") is None and "natural" not in kind:
                self.add("join_without_condition", "P0", line, f"JOIN {source['table'] or '子查询'} 没有 ON 条件", "补上关联键")
            elif source.get("on") and not source.get("using"):
                start, end = source["on"]
                texts = [self.tok[k].text for k in range(start, end)]
                if len(texts) == 3 and texts[1] == "=" and texts[0] == texts[2]:
                    self.add("always_true_join", "P0", line, "ON 条件恒为真，等同笛卡尔积", "写出真实的关联键")
                if any(self.tok[k].low == "or" and self.depth[k] == self.depth[start] for k in range(start, end)):
                    self.add("or_in_join", "P2", line, "JOIN 条件里有 OR，多数引擎无法走等值连接，容易退化成嵌套循环", "拆成两段 UNION ALL，或先规范化关联键", "low")
            if where and kind.startswith("left") and source["alias"]:
                self._left_join_filter(source, where)

    def _left_join_filter(self, source: dict, where: tuple[int, int]) -> None:
        alias = source["alias"]
        for a, b in self._predicates(*where):
            if not self._refs(a, b, alias):
                continue
            words = [self.tok[k].low for k in range(a, b)]
            if any(w in ("coalesce", "nvl", "ifnull") for w in words) or "or" in words:
                continue
            if "is" in words and "null" in words:
                if "not" in words:
                    self.add("left_join_not_null", "P1", self.tok[a].line, f"WHERE 中 {alias} 的 IS NOT NULL 让 LEFT JOIN 退化成 INNER JOIN", "如果就是要内连接，改写成 INNER JOIN 更清楚")
                continue
            self.add("left_join_right_filter", "P0", self.tok[a].line,
                     f"LEFT JOIN 的右表 {alias} 在 WHERE 中被过滤，没匹配上的行会被丢弃，分母被悄悄缩小",
                     "把这个条件移到 ON 里，或先在子查询里过滤右表")

    def _where_rules(self, scope: dict) -> None:
        if not scope["where"]:
            return
        for a, b in self._predicates(*scope["where"]):
            words = [self.tok[k] for k in range(a, b)]
            for k, t in enumerate(words):
                column = t.low.split(".")[-1]
                if t.kind == "word" and TIME_NAME.search(column) and column not in self.partition_cols and k + 1 < len(words):
                    nxt = words[k + 1]
                    if nxt.low == "between" and k + 4 < len(words) and words[k + 4].kind == "str" and DATE_LITERAL.match(words[k + 4].text):
                        self.add("between_day_end", "P1", t.line, f"{t.text} 是时间字段，BETWEEN 的结束日期只包含当天 00:00:00，最后一天几乎全部漏掉", "改成 >= 开始日期 AND < 结束日期次日")
                    if nxt.text == "<=" and k + 2 < len(words) and words[k + 2].kind == "str" and DATE_LITERAL.match(words[k + 2].text):
                        self.add("between_day_end", "P1", t.line, f"{t.text} <= 日期只包含当天 00:00:00，当天数据几乎全部漏掉", "改成 < 次日")
                if t.kind == "word" and t.low.split(".")[-1] in self.partition_cols and k + 2 < len(words) and words[k + 1].text == "=" and words[k + 2].kind == "num":
                    self.add("partition_type_mismatch", "P1", t.line, f"分区字段 {t.text} 用数字比较，字符串分区会发生隐式转换，分区裁剪可能失效", "用字符串字面量比较")
            for k in range(a, b - 1):
                t = self.tok[k]
                if t.kind == "word" and self.tok[k + 1].text == "(" and t.low not in NOT_FUNCTIONS:
                    inner = range(k + 2, self.match[k + 1])
                    if any(self.tok[j].kind == "word" and self.tok[j].low.split(".")[-1] in self.partition_cols for j in inner):
                        self.add("function_on_partition", "P1", t.line, f"分区字段被 {t.text}() 包住，分区裁剪会失效，可能全表扫描", "直接比较分区字段，把函数放到比较值一侧")

    def _partition_rules(self, scope: dict, any_filtered: bool) -> None:
        if not (self.partition_given or any_filtered):
            return
        for source in scope["sources"]:
            table = source["table"]
            if not table or source["subquery"] or table.lower() in self.ctes:
                continue
            if self._source_filtered(scope, source):
                continue
            if table.lower().startswith(("dim_", "dim.")):
                continue
            confidence = "high" if self.partition_given else "low"
            self.add("missing_partition_filter", "P1", source["line"], f"表 {table} 没有分区过滤，可能全表扫描，也可能把历史数据算进来", "在 WHERE 或 ON 中加上分区条件", confidence)

    def _fanout_rule(self, scope: dict) -> None:
        joined = [s for s in scope["sources"][1:] if s["table"] and not s["subquery"] and s["table"].lower() not in self.ctes
                  and "semi" not in s["join"] and "anti" not in s["join"] and not s["table"].lower().startswith("dim_")]
        base = scope["sources"][0]["alias"] if scope["sources"] else None
        if not joined or not base:
            return
        end = scope["clauses"].get("from", scope["end"])
        for i in range(scope["start"], end - 2):
            t = self.tok[i]
            if t.low in ("sum", "avg", "count") and self.tok[i + 1].text == "(":
                first = self.tok[i + 2]
                if first.low != "distinct" and first.low.startswith(base.lower() + "."):
                    self.add("join_fanout", "P1", t.line, f"{t.text}({first.text}) 在 JOIN {joined[0]['table']} 之后聚合，如果右表对关联键不唯一，结果会被放大",
                             "确认右表在关联键上唯一，或先聚合到关联键粒度再 JOIN", "low")


def verdict(findings: list[dict]) -> dict:
    counts = Counter(f["severity"] for f in findings)
    if counts["P0"]:
        return {"level": "bad", "title": f"{counts['P0']} 个 P0 问题会导致结果算错，修复前不要上线"}
    if counts["P1"]:
        return {"level": "warning", "title": f"{counts['P1']} 个 P1 问题需要结合表结构和数据分布确认"}
    return {"level": "good", "title": "没有发现典型错误写法；这不代表口径正确，还需要人工审查业务逻辑"}


def cmd_check(args: argparse.Namespace) -> int:
    files, all_findings, tables, ctes, statements = [], [], Counter(), set(), 0
    partition = {c.strip().lower() for c in args.partition_col} or None
    for path in args.sql:
        with open(path, encoding=sio.detect_encoding(path)) as handle:
            text = handle.read()
        analyzer = Analyzer(text, args.dialect, partition)
        analyzer.run()
        for finding in analyzer.findings:
            all_findings.append({"file": path, **finding})
        tables.update(analyzer.tables)
        ctes |= analyzer.ctes
        statements += sum(1 for part in re.split(r";\s*(?:\n|$)", text) if part.strip())
        files.append(path)
    result = {
        "files": files, "dialect": args.dialect, "statements": statements,
        "tables": sorted(tables), "ctes": sorted(ctes),
        "summary": {s: sum(1 for f in all_findings if f["severity"] == s) for s in ("P0", "P1", "P2")},
        "findings": all_findings, "verdict": verdict(all_findings),
        "limits": ["静态检查只看写法，不知道表结构、唯一性和数据分布", "confidence=low 的结论必须结合表结构确认", "业务口径是否正确需要人工审查"],
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    if args.fail_on and any(SEVERITY_ORDER[f["severity"]] <= SEVERITY_ORDER[args.fail_on] for f in all_findings):
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="SQL 静态检查（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="检查一个或多个 SQL 文件")
    c.add_argument("--sql", action="append", required=True, help="SQL 文件路径，可重复")
    c.add_argument("--dialect", choices=DIALECTS, default="generic", help="执行引擎，影响整数除法等规则")
    c.add_argument("--partition-col", action="append", default=[], help="分区字段，可重复；不填时只在 SQL 已使用常见分区字段时检查")
    c.add_argument("--fail-on", choices=["P0", "P1", "P2"], help="存在该级别及以上问题时返回非 0，便于接入 CI")
    c.add_argument("--json", help="同时把 JSON 写入文件")
    c.set_defaults(func=cmd_check)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(sio.run_cli(main))
