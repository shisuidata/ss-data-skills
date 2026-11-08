#!/usr/bin/env python3
"""数据文档草稿生成：从 DDL、SQL 和 eda.py 体检结果生成字段字典骨架，输出 Markdown、YAML 或 dbt schema.yml（仅依赖 Python 标准库）。

  python3 doc_gen.py draft --ddl table.sql --sql job.sql --eda eda.json --eda-table orders --format md --out doc.md

脚本只整理能从材料里确定的信息，业务含义和使用边界写成【待补充】，由人或 Agent 结合上下文填写，绝不猜测。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_io as sio  # noqa: E402

TODO = "【待补充】"


def _read(path: str) -> str:
    with open(path, encoding=sio.detect_encoding(path)) as handle:
        return handle.read()


def _split_columns(body: str) -> list[str]:
    parts, depth, start, quote = [], 0, 0, None
    for i, ch in enumerate(body):
        if quote:
            if ch == quote and body[i - 1] != "\\":
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch in "(<":
            depth += 1
        elif ch in ")>":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(body[start:i])
            start = i + 1
    parts.append(body[start:])
    return [p.strip() for p in parts if p.strip()]


def _matching(text: str, start: int) -> int:
    depth = 0
    quote = None
    for i in range(start, len(text)):
        ch = text[i]
        if quote:
            if ch == quote and text[i - 1] != "\\":
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    raise SystemExit("DDL 括号不匹配")


COL_RE = re.compile(r"^[`\"]?([\w一-鿿]+)[`\"]?\s+([A-Za-z_]+(?:\s*[(<][^)>]*[)>])?)(.*)$", re.S)
COMMENT_RE = re.compile(r"\bcomment\s+'((?:[^'\\]|\\.|'')*)'", re.I)
CONSTRAINT = ("primary", "key", "unique", "index", "constraint", "foreign", "check", "watermark", "period", "distribute", "partition")


def parse_ddl(text: str) -> dict:
    clean = re.sub(r"--[^\n]*|/\*.*?\*/", " ", text, flags=re.S)
    head = re.search(r"\bcreate\s+(?:external\s+|temporary\s+|temp\s+)?table\s+(?:if\s+not\s+exists\s+)?([\w.`\"]+)", clean, re.I)
    if not head:
        raise SystemExit("没有找到 CREATE TABLE 语句")
    table = head.group(1).replace("`", "").replace('"', "")
    open_paren = clean.find("(", head.end())
    close_paren = _matching(clean, open_paren)
    columns, primary = [], []
    for part in _split_columns(clean[open_paren + 1:close_paren]):
        first = part.split()[0].strip('`"').lower()
        if first in CONSTRAINT:
            match = re.search(r"primary\s+key\s*\(([^)]*)\)", part, re.I)
            if match:
                primary = [c.strip(' `"') for c in match.group(1).split(",")]
            continue
        match = COL_RE.match(part)
        if not match:
            continue
        comment = COMMENT_RE.search(match.group(3))
        columns.append({"name": match.group(1), "type": match.group(2).strip(), "comment": comment.group(1) if comment else "",
                        "nullable": not re.search(r"\bnot\s+null\b", match.group(3), re.I)})
        if re.search(r"\bprimary\s+key\b", match.group(3), re.I):
            primary.append(match.group(1))
    tail = clean[close_paren + 1:]
    partition_cols = []
    match = re.search(r"partitioned\s+by\s*\(", tail, re.I) or re.search(r"\bpartition\s+by\s*\(", tail, re.I)
    if match:
        start = match.end() - 1
        inner = tail[start + 1:_matching(tail, start)]
        for part in _split_columns(inner):
            col = COL_RE.match(part)
            name = col.group(1) if col else re.sub(r".*\(([\w]+)\).*", r"\1", part).strip(' `"')
            partition_cols.append(name)
            if col:
                comment = COMMENT_RE.search(col.group(3))
                columns.append({"name": name, "type": col.group(2).strip(), "comment": comment.group(1) if comment else "", "nullable": False, "partition": True})
    for col in columns:
        if col["name"] in partition_cols:
            col["partition"] = True
    table_comment = COMMENT_RE.search(tail)
    order = re.search(r"\border\s+by\s*\(?([^)\n]+)\)?", tail, re.I)
    if not primary and order and re.search(r"engine\s*=", tail, re.I):
        primary = [c.strip(' `"') for c in order.group(1).split(",")]
    return {"table": table, "comment": table_comment.group(1) if table_comment else "", "columns": columns, "primary_key": primary, "partition": partition_cols}


def upstream_tables(sql: str) -> list[str]:
    clean = re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql, flags=re.S)
    ctes = {m.group(1).lower() for m in re.finditer(r"\b([A-Za-z_]\w*)\s+as\s*\(\s*(?:select|with)\b", clean, re.I)}
    found = [m.group(1).strip('`"') for m in re.finditer(r"\b(?:from|join)\s+([A-Za-z_][\w.`\"]*)", clean, re.I)]
    return sorted({t for t in found if t.lower() not in ctes and t.lower() not in ("select", "lateral", "unnest")})


def merge_eda(doc: dict, path: str, table_name: str | None) -> None:
    with open(path, encoding="utf-8") as handle:
        eda = json.load(handle)
    tables = eda.get("tables") or []
    table = next((t for t in tables if t["name"] == table_name), None) if table_name else (tables[0] if len(tables) == 1 else None)
    if table is None:
        raise SystemExit(f"请用 --eda-table 指定表，可选：{[t['name'] for t in tables]}")
    by_name = {c["name"]: c for c in table["columns"]}
    if not doc["columns"]:
        doc["table"] = doc["table"] or table["name"]
        doc["columns"] = [{"name": c["name"], "type": c.get("type", ""), "comment": "", "nullable": c.get("missing_rate", 0) > 0} for c in table["columns"]]
    for col in doc["columns"]:
        profile = by_name.get(col["name"])
        if not profile:
            continue
        notes = []
        if profile.get("missing_rate"):
            notes.append(f"缺失率 {profile['missing_rate']:.1%}")
        if profile.get("type") == "category" and profile.get("distinct", 99) <= 8:
            notes.append("取值：" + "、".join(str(v) for v, _ in profile.get("top_values", [])))
        if (profile.get("stats") or {}).get("max") is not None:
            notes.append(f"范围 {profile['stats']['min']} 到 {profile['stats']['max']}")
        if profile.get("range"):
            notes.append(f"时间范围 {profile['range'][0][:10]} 到 {profile['range'][1][:10]}")
        col["profile"] = "；".join(notes)
    doc["rows_profiled"] = (table.get("meta") or {}).get("rows_total")
    key = table.get("key_check") or {}
    if key.get("columns") and not doc["primary_key"]:
        doc["primary_key"] = key["columns"]
        doc["primary_key_note"] = "由体检确认" if not key.get("duplicate_keys") else f"体检发现 {key['duplicate_keys']} 个重复键，粒度待确认"
    doc["quality_notes"] = [f"[{i['severity']}] {i.get('column') or '整表'}：{i['title']}" for i in eda.get("issues", []) if i.get("table") == table["name"]]


def to_md(doc: dict) -> str:
    def show(value) -> str:
        return (", ".join(value) if isinstance(value, list) else value) or TODO
    lines = [f"# 数据文档：{doc['table'] or TODO}", "", "## 1. 基本信息", "", "| 项目 | 内容 |", "| --- | --- |",
             f"| 表名 | {doc['table'] or TODO} |", f"| 表说明 | {doc['comment'] or TODO} |",
             f"| 主键 / 粒度 | {show(doc['primary_key'])}{'（' + doc['primary_key_note'] + '）' if doc.get('primary_key_note') else ''} |",
             f"| 分区字段 | {show(doc['partition'])} |", f"| 更新频率 | {TODO} |", f"| 负责人 | {TODO} |", "",
             "## 2. 业务用途", "", TODO, "", "## 3. 数据粒度与更新策略", "", f"一行代表：{TODO}", "", "## 4. 字段字典", "",
             "| 字段 | 类型 | 含义 | 可空 | 数据画像 |", "| --- | --- | --- | --- | --- |"]
    for c in doc["columns"]:
        tag = "（分区）" if c.get("partition") else ""
        lines.append(f"| {c['name']}{tag} | {c['type']} | {c['comment'] or TODO} | {'是' if c['nullable'] else '否'} | {c.get('profile', '') or '—'} |")
    lines += ["", "## 5. 生产逻辑", "", TODO, "", "## 6. 上下游关系", "", "上游：" + (show(doc["upstream"]) if doc["upstream"] else TODO), "", f"下游：{TODO}", "",
              "## 7. 使用示例", "", TODO, "", "## 8. 质量规则与 SLA", ""]
    lines += [f"- {n}" for n in doc.get("quality_notes", [])] or [TODO]
    missing = sum(1 for c in doc["columns"] if not c["comment"])
    lines += ["", "## 9. 常见误用与风险", "", TODO, "", "## 10. 待补充信息", "", f"- {missing} 个字段缺少业务含义", "- 更新频率、负责人、下游、使用边界", ""]
    return "\n".join(lines)


def _yaml_text(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def to_yaml(doc: dict) -> str:
    lines = [f"table: {_yaml_text(doc['table'])}", f"description: {_yaml_text(doc['comment'] or TODO)}", f"grain: {json.dumps(doc['primary_key'], ensure_ascii=False)}",
             f"partition: {json.dumps(doc['partition'], ensure_ascii=False)}", f"upstream: {json.dumps(doc['upstream'], ensure_ascii=False)}", "columns:"]
    for c in doc["columns"]:
        lines += [f"  - name: {_yaml_text(c['name'])}", f"    type: {_yaml_text(c['type'])}", f"    description: {_yaml_text(c['comment'] or TODO)}", f"    nullable: {'true' if c['nullable'] else 'false'}"]
        if c.get("profile"):
            lines.append(f"    profile: {_yaml_text(c['profile'])}")
    return "\n".join(lines) + "\n"


def to_dbt(doc: dict) -> str:
    name = (doc["table"] or "model").split(".")[-1]
    lines = ["version: 2", "", "models:", f"  - name: {name}", f"    description: {_yaml_text(doc['comment'] or TODO)}", "    columns:"]
    for c in doc["columns"]:
        lines += [f"      - name: {c['name']}", f"        description: {_yaml_text(c['comment'] or TODO)}"]
        if not c["nullable"]:
            lines += ["        data_tests:", "          - not_null"]
    return "\n".join(lines) + "\n"


def cmd_draft(args: argparse.Namespace) -> int:
    if not (args.ddl or args.eda):
        raise SystemExit("至少需要 --ddl 或 --eda")
    doc = parse_ddl(_read(args.ddl)) if args.ddl else {"table": "", "comment": "", "columns": [], "primary_key": [], "partition": []}
    doc["upstream"] = upstream_tables(_read(args.sql)) if args.sql else []
    if args.eda:
        merge_eda(doc, args.eda, args.eda_table)
    if not doc["columns"]:
        raise SystemExit("没有解析到任何字段，请检查 DDL 格式")
    content = {"md": to_md, "yaml": to_yaml, "dbt": to_dbt}[args.format](doc)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(content)
    missing = [c["name"] for c in doc["columns"] if not c["comment"]]
    print(json.dumps({"table": doc["table"], "columns": len(doc["columns"]), "primary_key": doc["primary_key"], "partition": doc["partition"], "upstream": doc["upstream"],
                      "columns_missing_description": missing, "format": args.format, "output": os.path.abspath(args.out) if args.out else None, "content": None if args.out else content,
                      "note": "【待补充】处需要结合业务上下文填写，脚本不会猜测业务含义"}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="数据文档草稿生成（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("draft", help="生成文档草稿")
    d.add_argument("--ddl", help="CREATE TABLE 语句文件")
    d.add_argument("--sql", help="生产这张表的 SQL 文件，用于提取上游")
    d.add_argument("--eda", help="eda.py 的 JSON 输出")
    d.add_argument("--eda-table", help="--eda 中要使用的表名")
    d.add_argument("--format", choices=["md", "yaml", "dbt"], default="md", help="输出格式")
    d.add_argument("--out", help="输出文件路径")
    d.set_defaults(func=cmd_draft)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(sio.run_cli(main))
