#!/usr/bin/env python3
"""血缘影响计算器：从边表、dbt manifest 或 SQL 文件算下游闭包，按变更类型分级（仅依赖 Python 标准库）。

  python3 lineage.py edges --sql a.sql --sql b.sql --out edges.csv
  python3 lineage.py impact --edges edges.csv --assets assets.csv --target dwd_order_detail_d --change drop_column
  python3 lineage.py impact --manifest target/manifest.json --target fct_orders --change semantic_change

结论只覆盖已知血缘。没出现在结果里不代表没有下游，临时 SQL、Excel 和外部系统通常不在血缘里。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict, deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_io as sio  # noqa: E402

CHANGES = {
    "drop_column": ("breaking", "字段下线"), "rename_column": ("breaking", "字段改名"), "type_change": ("breaking", "字段类型变更"),
    "drop_table": ("breaking", "表下线"), "migrate_table": ("breaking", "表迁移"), "semantic_change": ("semantic", "口径调整"),
    "add_column": ("additive", "新增字段"), "delay": ("delay", "产出延迟或调度调整"),
}
BUSINESS_FACING = {"dashboard", "report", "api", "model", "exposure", "metric", "看板", "报表", "接口", "模型", "指标"}
REMEDIATION = {
    "breaking": ["先提供兼容字段或视图，保留双跑窗口", "通知所有 P0、P1 对象的负责人并确认迁移时间", "下线前用查询日志确认已无读取", "准备回滚脚本和触发条件"],
    "semantic": ["新旧口径并行展示一段时间", "明确历史数据是否回填", "同步所有下游的报表说明和对外口径", "在数据文档里记录生效日期"],
    "additive": ["确认下游没有 SELECT * 或按列序号读取", "补字段文档"],
    "delay": ["评估下游 SLA 是否受影响", "同步受影响的看板和报表的更新时间"],
}


def _level(kind: str, asset: dict, depth: int) -> tuple[str, str]:
    facing = asset.get("type", "").lower() in BUSINESS_FACING
    core = asset.get("importance", "").lower() in ("core", "high", "p0", "核心")
    if kind == "breaking":
        if depth == 1:
            return "P0", "直接读取，变更会让它立刻报错或空值"
        return ("P1", "间接依赖，上游失败后会传导到业务可见的结果") if facing or core else ("P2", "间接依赖，随上游一起验证")
    if kind == "semantic":
        return ("P0", "核心业务对象的数字含义会变") if core else ("P1", "数字含义会变，需要同步口径")
    if kind == "delay":
        return ("P1", "业务可见结果的更新时间受影响") if facing or core else ("P2", "可能受影响，需要确认 SLA")
    return "P3", "新增内容，通常无直接影响"


def _read_edges(path: str) -> list[dict]:
    rows = sio.read_csv(path)
    if not rows:
        raise SystemExit("边表为空")
    pick = lambda row, *names: next((row[n].strip() for n in names if row.get(n)), "")  # noqa: E731
    edges = []
    for row in rows:
        up, down = pick(row, "upstream", "source", "src", "from"), pick(row, "downstream", "target", "dst", "to")
        if not up or not down:
            raise SystemExit("边表需要 upstream 和 downstream 两列（也接受 source/target、src/dst、from/to）")
        edges.append({"upstream": up, "downstream": down, "column": pick(row, "upstream_column", "column")})
    return edges


def _read_manifest(path: str) -> tuple[list[dict], dict]:
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    child_map = manifest.get("child_map")
    if not child_map:
        raise SystemExit("manifest 缺少 child_map，请使用 dbt 生成的 target/manifest.json")
    short = lambda uid: uid.split(".")[-1]  # noqa: E731
    edges = [{"upstream": short(u), "downstream": short(d), "column": ""} for u, children in child_map.items() for d in children if not d.startswith("test.")]
    assets = {}
    for section, default in (("nodes", ""), ("sources", "source"), ("exposures", "exposure"), ("metrics", "metric")):
        for uid, node in (manifest.get(section) or {}).items():
            meta = node.get("meta") or (node.get("config") or {}).get("meta") or {}
            owner = meta.get("owner") or ((node.get("owner") or {}).get("name") if isinstance(node.get("owner"), dict) else "")
            assets[short(uid)] = {"type": default or node.get("resource_type", ""), "owner": owner or "", "importance": str(meta.get("importance", ""))}
    return edges, assets


def cmd_impact(args: argparse.Namespace) -> int:
    if bool(args.edges) == bool(args.manifest):
        raise SystemExit("--edges 与 --manifest 二选一")
    edges, assets = _read_edges(args.edges) if args.edges else _read_manifest(args.manifest)[0], {}
    if args.manifest:
        assets = _read_manifest(args.manifest)[1]
    for row in sio.read_csv(args.assets) if args.assets else []:
        assets[row["name"].strip()] = {"type": (row.get("type") or "").strip(), "owner": (row.get("owner") or "").strip(), "importance": (row.get("importance") or "").strip()}
    children = defaultdict(list)
    for edge in edges:
        children[edge["upstream"]].append(edge)
    table, _, column = args.target.partition(":")
    if table not in children and table not in {e["downstream"] for e in edges}:
        names = sorted({e["upstream"] for e in edges} | {e["downstream"] for e in edges})
        close = [n for n in names if table.lower() in n.lower() or n.lower() in table.lower()][:8]
        raise SystemExit(f"血缘里找不到 {table}。相近名称：{close or names[:8]}")
    kind, label = CHANGES[args.change]
    seen: dict[str, dict] = {}
    cycles = set()
    queue = deque([(table, [table], 0)])
    while queue:
        node, path, depth = queue.popleft()
        for edge in children.get(node, []):
            if depth == 0 and column and edge["column"] and edge["column"] != column:
                continue
            child = edge["downstream"]
            if child in path:
                cycles.add(" → ".join(path + [child]))
                continue
            if args.max_depth and depth + 1 > args.max_depth:
                continue
            if child not in seen:
                asset = assets.get(child, {})
                level, reason = _level(kind, asset, depth + 1)
                seen[child] = {"object": child, "type": asset.get("type") or "未知", "owner": asset.get("owner") or "待确认", "importance": asset.get("importance") or "未知",
                               "depth": depth + 1, "path": " → ".join(path + [child]), "level": level, "reason": reason}
                queue.append((child, path + [child], depth + 1))
    impacted = sorted(seen.values(), key=lambda x: (x["level"], x["depth"], x["object"]))
    owners = defaultdict(list)
    for item in impacted:
        owners[item["owner"]].append(item["object"])
    checks = []
    if not impacted:
        checks.append({"id": "no_downstream", "status": "warn", "title": "已知血缘里没有下游", "detail": "这不代表真的没有下游。下线前用查询日志核对最近 30 天的读取记录"})
    unknown = [i["object"] for i in impacted if i["type"] == "未知"]
    if unknown:
        checks.append({"id": "unknown_assets", "status": "warn", "title": f"{len(unknown)} 个下游缺少类型信息，分级可能偏低", "detail": "、".join(unknown[:10])})
    if "待确认" in owners:
        checks.append({"id": "unknown_owner", "status": "warn", "title": f"{len(owners['待确认'])} 个下游没有负责人", "detail": "通知清单不完整，补充资产负责人后重新运行"})
    if cycles:
        checks.append({"id": "cycle", "status": "fail", "title": f"血缘存在 {len(cycles)} 个环", "detail": "；".join(sorted(cycles)[:3])})
    if column and not any(e["column"] for e in children.get(table, [])):
        checks.append({"id": "column_lineage", "status": "warn", "title": "边表没有字段级信息，结果按表级血缘计算", "detail": "实际影响可能小于列表，用 upstream_column 列补充字段级血缘"})
    counts = {lv: sum(1 for i in impacted if i["level"] == lv) for lv in ("P0", "P1", "P2", "P3")}
    verdict = ({"level": "bad", "title": f"{label}会直接影响 {counts['P0']} 个关键对象，必须先做兼容方案"} if counts["P0"]
               else ({"level": "warning", "title": f"{label}影响 {counts['P1']} 个对象，需要协调后再上线"} if counts["P1"]
                     else {"level": "info", "title": f"{label}的已知影响较小；未知下游仍需用查询日志确认"}))
    result = {"target": args.target, "change": args.change, "change_label": label, "summary": counts, "impacted": impacted,
              "notify": [{"owner": o, "objects": sorted(v)} for o, v in sorted(owners.items())], "recommended_actions": REMEDIATION[kind], "checks": checks, "verdict": verdict,
              "limits": ["只覆盖已知血缘", "没出现在结果里不代表没有下游", "临时 SQL、Excel 和外部系统需要查询日志补充"]}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            handle.write(text)
    print(text)
    return 0


_COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
_TARGET = re.compile(r"\binsert\s+(?:overwrite|into)\s+(?:table\s+)?([\w.`\"]+)|\bcreate\s+(?:or\s+replace\s+)?(?:temporary\s+|temp\s+|materialized\s+)?(?:table|view)\s+(?:if\s+not\s+exists\s+)?([\w.`\"]+)", re.I)
_SOURCE = re.compile(r"\b(?:from|join)\s+([A-Za-z_][\w.`\"]*)", re.I)
_CTE = re.compile(r"\b([A-Za-z_]\w*)\s+as\s*\(\s*(?:select|with)\b", re.I)


def edges_from_sql(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    clean = _COMMENT.sub(" ", text)
    out, notes = [], []
    for statement in re.split(r";\s*(?:\n|$)", clean):
        target = _TARGET.search(statement)
        if not target:
            if statement.strip() and _SOURCE.search(statement):
                notes.append("有查询语句没有写入目标（INSERT 或 CREATE），已跳过")
            continue
        name = (target.group(1) or target.group(2)).strip('`"')
        ctes = {m.group(1).lower() for m in _CTE.finditer(statement)}
        for match in _SOURCE.finditer(statement):
            source = match.group(1).strip('`"')
            if source.lower() not in ctes and source.lower() != name.lower() and source.lower() not in ("select", "lateral", "unnest"):
                out.append((source, name))
    return sorted(set(out)), sorted(set(notes))


def cmd_edges(args: argparse.Namespace) -> int:
    pairs, notes = set(), set()
    for path in args.sql:
        with open(path, encoding=sio.detect_encoding(path)) as handle:
            found, note = edges_from_sql(handle.read())
        pairs |= set(found)
        notes |= set(note)
    ordered = sorted(pairs)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["upstream", "downstream"])
            writer.writerows(ordered)
    print(json.dumps({"edges": [{"upstream": u, "downstream": d} for u, d in ordered], "count": len(ordered), "notes": sorted(notes),
                      "limits": ["用正则提取，动态 SQL 和存储过程提取不到", "结果是表级血缘，不含字段级"]}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="血缘影响计算器（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)
    i = sub.add_parser("impact", help="计算某个对象变更的下游影响")
    i.add_argument("--edges", help="边表 CSV：upstream, downstream，可选 upstream_column")
    i.add_argument("--manifest", help="dbt 的 target/manifest.json")
    i.add_argument("--assets", help="资产 CSV：name, type, owner, importance")
    i.add_argument("--target", required=True, help="变更对象：表名，字段级写成 表名:字段名")
    i.add_argument("--change", required=True, choices=sorted(CHANGES), help="变更类型")
    i.add_argument("--max-depth", type=int, help="最多追溯的层数，默认不限")
    i.add_argument("--json", help="同时把 JSON 写入文件")
    i.set_defaults(func=cmd_impact)
    e = sub.add_parser("edges", help="从 SQL 文件提取表级血缘")
    e.add_argument("--sql", action="append", required=True, help="SQL 文件路径，可重复")
    e.add_argument("--out", help="输出边表 CSV")
    e.set_defaults(func=cmd_edges)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(sio.run_cli(main))
