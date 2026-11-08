#!/usr/bin/env python3
"""分析报告组装器：把分析脚本的 JSON 结果和报告规格（spec）拼成一份数字可溯源的报告（仅依赖 Python 标准库）。

核心约定：报告里的数字不手写，而是用 {{来源:路径|格式}} 引用来源 JSON，由脚本取值、格式化并记录出处。

  python3 report.py refs --source funnel=funnel.json --grep overall      # 列出可引用的数字
  python3 report.py skeleton --source funnel=funnel.json > spec.json      # 生成已绑定关键数字的规格草稿
  python3 report.py build --spec spec.json --html report.html --md report.md
  python3 report.py lint --text report.md --source funnel=funnel.json      # 检查手写报告里的数字能否溯源

来源 JSON 可以来自 ab_test.py、funnel.py、retention.py、eda.py 的 --json 输出，也可以是任意 JSON。
规格格式见 ../references/spec-schema.md。
"""

from __future__ import annotations

import argparse
import ast
import json
import operator
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sskit_viz as viz  # noqa: E402
import sskit_io as sio  # noqa: E402

esc = viz.esc

SOURCE_TYPES = {
    "ab": "ab-test-analysis",
    "funnel": "funnel-analysis",
    "retention": "retention-cohort-analysis",
    "eda": "exploratory-data-analysis",
    "generic": "其他 JSON",
}
# 列表元素优先用这些字段做选择器，比下标更稳定也更好读
ID_KEYS = ("transition", "segment", "metric", "cohort", "period", "name", "id", "group", "label")

REF_RE = re.compile(r"\{\{\s*([^{}|]+?)\s*(?:\|\s*([^{}]+?))?\s*\}\}")
PATH_RE = re.compile(r"\[([^\]]*)\]|([^.\[\]]+)")
TODO_MARK = "【待补充"

# 数字扫描：日期、时间、版本号等先抹掉，再找数字
DATE_RES = [
    re.compile(r"\d{4}\s?[-/.年]\s?\d{1,2}(?:\s?[-/.月]\s?\d{1,2}\s?[日号]?)?"),
    re.compile(r"\d{1,2}\s?月(?:\s?\d{1,2}\s?[日号])?"),
    re.compile(r"\d{1,2}\s?[日号](?![均内])"),
    re.compile(r"\d{1,2}/\d{1,2}"),
    re.compile(r"\d{1,2}:\d{2}"),
]
NUM_RE = re.compile(r"(?<![A-Za-z\d.,])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?(%|pp|个百分点|万|亿|倍|ms|s)?(?![A-Za-z\d])")
TIME_WORDS = ("天", "日", "周", "个月", "小时", "分钟", "年", "季度", "步", "层", "级")
UNIT_SCALE = {"%": 100, "pp": 100, "个百分点": 100, "万": 1e-4, "亿": 1e-8}

CAUSAL_RE = re.compile(r"导致|造成|使得|致使|归因于|归功于|因为|由于|引起|引发|源于|根本原因|直接原因|决定了|带来了|驱动了|拉动了|推动了")
VAGUE_RE = re.compile(r"持续关注|密切关注|加强关注|进一步关注|保持关注|重点关注|持续跟进|持续观察|加强监控|加强沟通|加强管理|"
                      r"持续优化|进一步优化|优化体验|提升效率|完善机制|持续改进|持续推进|持续提升|加大投入")
_CN = "一二两三四五六七八九十百千几"
# 用汉字写的数字无法和来源比对，必须改成阿拉伯数字并引用来源
CN_NUM_RE = re.compile(
    rf"[{_CN}]+成(?![不功本员为绩品就长立])|[{_CN}]+倍|翻了?[{_CN}]*[番倍]|近半|过半|大半|一半|"
    rf"[{_CN}]+个百分点|[{_CN}]+分之[{_CN}]+|[{_CN}半]+[万亿](?![不别要])"
)


class RefError(Exception):
    pass


# ---------------------------------------------------------------------------
# 来源与引用
# ---------------------------------------------------------------------------

def detect_type(data) -> str:
    if not isinstance(data, dict):
        return "generic"
    if "srm" in data and "comparisons" in data:
        return "ab"
    if "funnel" in data and "periods" in data:
        return "funnel"
    if "retention" in data and "matrix" in data:
        return "retention"
    if "tables" in data and "issues" in data:
        return "eda"
    return "generic"


def load_sources(pairs: list[str], spec: dict | None = None, spec_dir: str = ".") -> dict:
    """来源 = spec.sources（相对 spec 所在目录）+ 命令行 --source（同名时命令行优先）。"""
    paths = {}
    for name, path in ((spec or {}).get("sources") or {}).items():
        paths[name] = path if os.path.isabs(path) else os.path.join(spec_dir, path)
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--source 格式应为 名称=路径：{pair}")
        name, path = pair.split("=", 1)
        paths[name.strip()] = path.strip()
    sources = {}
    for name, path in paths.items():
        if name == "facts":
            raise SystemExit("来源名称 facts 已保留给 spec.facts")
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            raise SystemExit(f"找不到来源文件：{name}={path}")
        except json.JSONDecodeError as exc:
            raise SystemExit(f"来源不是合法 JSON：{name}={path}（{exc}）")
        sources[name] = {"path": path, "type": detect_type(data), "data": data}
    return sources


def walk(data, path: str):
    """按路径取值：a.b[0].c、steps[transition=注册 → 加购].rate。"""
    current = data
    trail = []
    for bracket, key in PATH_RE.findall(path):
        token = bracket if bracket else key
        where = ".".join(trail) or "根"
        if bracket:
            if not isinstance(current, list):
                raise RefError(f"{where} 不是列表，不能用 [{token}]")
            if "=" in token:
                field, value = (part.strip() for part in token.split("=", 1))
                hit = next((item for item in current if isinstance(item, dict) and str(item.get(field)) == value), None)
                if hit is None:
                    options = [str(item.get(field)) for item in current if isinstance(item, dict) and field in item]
                    raise RefError(f"{where} 中没有 {field}={value}，可选：{', '.join(options[:12]) or '（该字段不存在）'}")
                current = hit
            else:
                try:
                    current = current[int(token)]
                except (ValueError, IndexError):
                    raise RefError(f"{where} 共 {len(current)} 项，[{token}] 越界或不是数字")
        else:
            key = key.strip()
            if isinstance(current, dict):
                if key not in current:
                    raise RefError(f"{where} 中没有键「{key}」，可用：{', '.join(list(current)[:16])}")
                current = current[key]
            elif isinstance(current, list) and key.isdigit():
                current = current[int(key)]
            else:
                raise RefError(f"{where} 不是对象，不能取「{key}」")
        trail.append(token if not bracket else f"[{token}]")
    return current


def _p(value: float, digits: int | None) -> str:
    return "p<0.001" if value < 0.001 else f"p={value:.{digits or 3}f}"


FORMATS = {
    "pct": lambda v, d: viz.fmt_pct(v, 1 if d is None else d),
    "pp": lambda v, d: viz.fmt_pp(v, 1 if d is None else d),
    "spct": lambda v, d: viz.fmt_signed_pct(v, 1 if d is None else d),
    "num": lambda v, d: viz.fmt_num(v, 2 if d is None else d),
    "snum": lambda v, d: viz.fmt_signed(v, 2 if d is None else d),
    "int": lambda v, d: f"{round(v):,}",
    "fixed": lambda v, d: f"{v:.{1 if d is None else d}f}",
    "times": lambda v, d: f"{v:.{1 if d is None else d}f} 倍",
    "p": _p,
}


def apply_format(value, spec: str | None) -> str:
    """格式管道：abs / neg / len 先变换，最后一个名字决定显示格式，如 abs|pp.2。"""
    fmt = None
    for part in [p.strip() for p in (spec or "").split("|") if p.strip()]:
        if part == "abs":
            value = abs(value)
        elif part == "neg":
            value = -value
        elif part == "len":
            value = len(value)
        else:
            fmt = part
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
            return "[" + ", ".join(apply_format(v, fmt) for v in value) + "]"
        return "、".join(apply_format(v, fmt) for v in value)
    if isinstance(value, dict):
        raise RefError("引用指向的是对象，请继续写到具体字段")
    name, _, digits = (fmt or "").partition(".")
    if not name:
        return f"{value:,}" if isinstance(value, int) else viz.fmt_num(value, 2)
    if name not in FORMATS:
        raise RefError(f"未知格式「{name}」，可用：{', '.join(FORMATS)}，以及 abs / neg / len")
    return FORMATS[name](value, int(digits) if digits else None)


def _short(value) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 80 else text[:77] + "…"


SAFE_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.USub: operator.neg, ast.UAdd: operator.pos}
SAFE_CALLS = {"abs": abs, "min": min, "max": max}


def _eval(node, names: dict):
    if isinstance(node, ast.Expression):
        return _eval(node.body, names)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPS:
        return SAFE_OPS[type(node.op)](_eval(node.left, names), _eval(node.right, names))
    if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPS:
        return SAFE_OPS[type(node.op)](_eval(node.operand, names))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in SAFE_CALLS:
        return SAFE_CALLS[node.func.id](*(_eval(a, names) for a in node.args))
    raise RefError("表达式只支持 + - * / 、括号、数字、abs/min/max 和 {来源:路径} 引用")


class Context:
    """持有来源数据，负责解析引用、记录溯源、扫描未溯源数字。"""

    def __init__(self, sources: dict, facts: dict | None = None):
        self.sources = sources
        self.data = {name: src["data"] for name, src in sources.items()}
        self.facts_meta: dict[str, dict] = {}
        self.data["facts"] = {}
        self.trace: dict[tuple, dict] = {}
        self.errors: list[str] = []
        self.numbers: list[dict] = []
        self.cn_numbers: list[dict] = []
        self._index: list[tuple[str, float]] | None = None
        self._load_facts(facts or {})

    def _load_facts(self, facts: dict) -> None:
        pending = dict(facts)
        for _ in range(len(pending) + 1):
            progressed = False
            for name, item in list(pending.items()):
                meta = item if isinstance(item, dict) else {"value": item}
                try:
                    value = self._eval_expr(meta["expr"]) if "expr" in meta else meta.get("value")
                except RefError as exc:
                    if "facts:" in str(meta.get("expr", "")) and any(f"facts:{k}" in meta["expr"] for k in pending):
                        continue  # 依赖的派生事实还没算出来，下一轮再试
                    self.errors.append(f"facts.{name}：{exc}")
                    value = None
                self.data["facts"][name] = value
                self.facts_meta[name] = meta
                del pending[name]
                progressed = True
            if not pending or not progressed:
                break
        for name in pending:
            self.errors.append(f"facts.{name}：表达式存在循环依赖")

    def _eval_expr(self, expr: str) -> float:
        names = {}

        def swap(match: re.Match) -> str:
            key = f"v{len(names)}"
            value = self.resolve(match.group(1))
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise RefError(f"表达式里的 {match.group(1)} 不是数字")
            names[key] = value
            return key

        body = re.sub(r"\{([^{}]+)\}", swap, expr)
        try:
            return _eval(ast.parse(body, mode="eval"), names)
        except SyntaxError:
            raise RefError(f"表达式语法错误：{expr}")
        except ZeroDivisionError:
            raise RefError(f"表达式除以 0：{expr}")

    def split(self, body: str) -> tuple[str, str]:
        if ":" in body:
            name, path = body.split(":", 1)
            return name.strip(), path.strip()
        return "facts", body.strip()

    def resolve(self, body: str):
        name, path = self.split(body)
        if name not in self.data:
            raise RefError(f"没有名为「{name}」的来源，已加载：{', '.join(self.data)}")
        return walk(self.data[name], path)

    def label(self, body: str) -> str:
        name, path = self.split(body)
        if name == "facts":
            meta = self.facts_meta.get(path.split(".")[0].split("[")[0], {})
            origin = meta.get("source") or ("派生计算：" + meta["expr"] if "expr" in meta else "")
            return f"facts:{path}" + (f"（{origin}）" if origin else "")
        return f"{name}:{path}"

    def ref(self, body: str, fmt: str | None, where: str):
        try:
            raw = self.resolve(body)
            shown = apply_format(raw, fmt)
        except RefError as exc:
            self.errors.append(f"{where}：{{{{{body}}}}} {exc}")
            return None, "⟦引用错误⟧"
        key = (body, fmt or "")
        if key not in self.trace:
            self.trace[key] = {"shown": shown, "ref": self.label(body), "raw": _short(raw), "where": where}
        return raw, shown

    # -- 叙述文本 ----------------------------------------------------------

    def text(self, value, where: str, html_mode: bool = True) -> str:
        """渲染一段叙述：引用替换成数字，HTML 下带出处提示；同时扫描手写数字。"""
        if value is None:
            return ""
        text = str(value)
        self.scan(REF_RE.sub(" ", text), where)
        out, pos = [], 0
        for match in REF_RE.finditer(text):
            out.append(_prose(text[pos:match.start()], html_mode))
            raw, shown = self.ref(match.group(1).strip(), match.group(2), where)
            if html_mode:
                tip = f"来源 {self.label(match.group(1).strip())} = {_short(raw)}"
                out.append(f'<span class="ref" title="{esc(tip)}">{esc(shown)}</span>')
            else:
                out.append(shown)
            pos = match.end()
        out.append(_prose(text[pos:], html_mode))
        return "".join(out)

    def value(self, item, where: str):
        """图表数据：整段是一个引用时返回原始值，否则按字面量处理并参与溯源检查。"""
        if isinstance(item, str):
            match = REF_RE.fullmatch(item.strip())
            if match:
                raw, _ = self.ref(match.group(1).strip(), match.group(2), where)
                return raw
            return item
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            self.scan(f"{item}", where)
        return item

    # -- 数字溯源检查 ------------------------------------------------------

    def index(self) -> list[tuple[str, float]]:
        if self._index is None:
            self._index = []
            for name, data in self.data.items():
                for path, value in flatten(data):
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        self._index.append((f"{name}:{path}" if name != "facts" else path, float(value)))
        return self._index

    def match(self, number: float, decimals: int, unit: str | None) -> str | None:
        scale = UNIT_SCALE.get(unit or "", 1)
        target = f"{abs(number):.{decimals}f}"
        hits = []
        for ref, value in self.index():
            if f"{abs(value) * scale:.{decimals}f}" == target:
                hits.append(ref)
            # facts 里的百分数可能直接写成 8.2（单位 %），按原值也算命中
            elif scale == 100 and ":" not in ref and f"{abs(value):.{decimals}f}" == target:
                hits.append(ref)
        # 多个候选时优先推荐“正经”的字段：不是区间端点、路径更短
        return min(hits, key=lambda r: (bool(re.search(r"ci\[\d\]|_ci", r)), len(r)), default=None)

    def scan(self, text: str, where: str) -> None:
        for match in CN_NUM_RE.finditer(text):
            self.cn_numbers.append({"where": where, "text": match.group(0)})
        for pattern in DATE_RES:
            text = pattern.sub(" ", text)
        for match in NUM_RE.finditer(text):
            whole, frac, unit = match.group(1), match.group(2), match.group(3)
            number = float(whole.replace(",", "") + (frac or ""))
            decimals = len(frac) - 1 if frac else 0
            tail = text[match.end():].lstrip()
            if not frac and not unit:
                if number <= 12 or (1900 <= number <= 2100 and len(whole) == 4):
                    continue  # 序号、计数、年份
                if tail.startswith(TIME_WORDS):
                    continue  # “30 天窗口”这类口径参数
            if unit == "%" and tail.startswith(("区间", "置信", "CI", "的置信", "分位")):
                continue  # 95% 区间、90% 分位这类方法参数
            token = match.group(0).strip()
            ref = self.match(number, decimals, unit)
            self.numbers.append({"where": where, "text": token, "status": "matched" if ref else "unmatched",
                                 "suggest": ref})


def _prose(text: str, html_mode: bool) -> str:
    if not html_mode:
        return text
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(text))


def flatten(data, prefix: str = ""):
    """展开成 (路径, 值)。列表里的对象优先用 ID_KEYS 生成选择器；短数字列表（区间）整体也算一个叶子。"""
    if isinstance(data, dict):
        for key, value in data.items():
            if str(key).startswith("_"):
                continue
            yield from flatten(value, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(data, list):
        if data and len(data) <= 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in data):
            yield prefix, data
        used = set()
        for i, item in enumerate(data):
            selector = f"[{i}]"
            if isinstance(item, dict):
                for key in ID_KEYS:
                    value = item.get(key)
                    if isinstance(value, (str, int)) and not isinstance(value, bool) and (key, value) not in used:
                        if sum(1 for other in data if isinstance(other, dict) and other.get(key) == value) == 1:
                            selector = f"[{key}={value}]"
                            used.add((key, value))
                            break
            yield from flatten(item, prefix + selector)
    else:
        yield prefix, data


# ---------------------------------------------------------------------------
# 图表预设：每种来源一组，返回 (HTML, Markdown 表格)
# ---------------------------------------------------------------------------

def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    line = lambda cells: "| " + " | ".join(str(c).replace("|", "\\|") for c in cells) + " |"  # noqa: E731
    return "\n".join([line(headers), line(["---"] * len(headers))] + [line(r) for r in rows])


def _fmt_callable(spec: str | None):
    return lambda v: apply_format(v, spec)


def preset_funnel(data: dict, name: str, chart: dict, ctx: Context) -> tuple[str, str]:
    meta = data["funnel"]
    cur, base = meta.get("current"), meta.get("baseline")
    transitions = meta["transitions"]
    kind = chart["preset"]
    caption = chart.get("caption") or f"来源：{name}（funnel-analysis）"
    pct = lambda v: viz.fmt_pct(v, 1)  # noqa: E731
    if kind == "steps":
        current = [row["step_rate"] for row in data["periods"][cur]["table"][1:]]
        if base and base in data["periods"]:
            baseline = [row["step_rate"] for row in data["periods"][base]["table"][1:]]
            html = viz.paired_bar_chart(transitions, current, baseline, names=(cur, base), fmt=pct,
                                        title=chart.get("title", "各步转化率"), caption=caption)
            md = _md_table(["步骤", base, cur], [[t, pct(b), pct(c)] for t, c, b in zip(transitions, current, baseline)])
        else:
            html = viz.bar_chart(transitions, current, fmt=pct, title=chart.get("title", "各步转化率"), caption=caption)
            md = _md_table(["步骤", cur], [[t, pct(c)] for t, c in zip(transitions, current)])
        return html, md
    if kind == "counts":
        counts = data["periods"][cur]["counts"]
        html = viz.bar_chart(meta["steps"], counts, title=chart.get("title", f"{cur} 各步人数"), caption=caption)
        return html, _md_table(["步骤", "人数"], [[s, f"{c:,}"] for s, c in zip(meta["steps"], counts)])
    comparison = data.get("comparison")
    if not comparison:
        raise RefError(f"{name} 没有两期对比，不能用 {kind} 预设")
    if kind == "contribution":
        steps = comparison["steps"]
        values = [s.get("contribution_pp") or 0.0 for s in steps]
        tones = [viz.delta_tone(v, True, (s.get("test") or {}).get("p_value", 1) < 0.05) for v, s in zip(values, steps)]
        pp = lambda v: viz.fmt_pp(v, 1)  # noqa: E731
        html = viz.diverging_bar_chart([s["transition"] for s in steps], values, fmt=pp, tones=tones,
                                       title=chart.get("title", "各步对整体变化的贡献"), caption=caption)
        return html, _md_table(["步骤", "贡献"], [[s["transition"], pp(v)] for s, v in zip(steps, values)])
    if kind == "segments":
        dims = comparison.get("segments") or {}
        dim = chart.get("dim") or next(iter(dims), None)
        if dim not in dims:
            raise RefError(f"{name} 没有分群维度 {dim}")
        headers = ["分群", f"占比 {base}→{cur}", f"转化 {base}→{cur}", "结构效应", "转化效应"]
        rows = [[r["segment"], f"{pct(r['share_baseline'])} → {pct(r['share_current'])}",
                 f"{pct(r['conv_baseline'])} → {pct(r['conv_current'])}",
                 viz.fmt_pp(r["mix_effect"], 1), viz.fmt_pp(r["rate_effect"], 1)] for r in dims[dim]["rows"]]
        return _figure_table(chart.get("title", f"{_by(dim)}拆解"), headers, rows, caption), _md_table(headers, rows)
    raise RefError(f"funnel 没有预设 {kind}，可用：steps / counts / contribution / segments")


def preset_ab(data: dict, name: str, chart: dict, ctx: Context) -> tuple[str, str]:
    if chart["preset"] != "effects":
        raise RefError("ab 只有 effects 预设")
    role_name = {"primary": "主指标", "secondary": "次要指标", "guardrail": "护栏指标"}
    rows, md_rows = [], []
    multi = len({c["treatment"] for c in data["comparisons"]}) > 1
    for c in data["comparisons"]:
        if c.get("ci_rel") is None:
            continue
        label = c["metric"] + (f"（{c['treatment']}）" if multi else "")
        rows.append({"label": label, "estimate": c["rel_lift"], "low": c["ci_rel"][0], "high": c["ci_rel"][1],
                     "tone": viz.delta_tone(c["rel_lift"], c.get("higher_is_better", True), c.get("significant", False)),
                     "sub": f"{role_name.get(c.get('role'), c.get('role', ''))} · {_p(c['p_value'], 3)}"})
        md_rows.append([label, viz.fmt_signed_pct(c["rel_lift"]),
                        f"[{viz.fmt_signed_pct(c['ci_rel'][0])}, {viz.fmt_signed_pct(c['ci_rel'][1])}]", _p(c["p_value"], 3)])
    html = viz.interval_chart(rows, title=chart.get("title", "相对提升与 95% 区间"),
                              caption=chart.get("caption") or f"来源：{name}（ab-test-analysis）；区间跨过 0 表示不显著")
    return html, _md_table(["指标", "相对提升", "95% 区间", "显著性"], md_rows)


def preset_retention(data: dict, name: str, chart: dict, ctx: Context) -> tuple[str, str]:
    meta = data["retention"]
    labels = dict(zip(meta["periods"], meta["labels"]))
    caption = chart.get("caption") or f"来源：{name}（retention-cohort-analysis）"
    pct = lambda v: viz.fmt_pct(v, 1)  # noqa: E731
    kind = chart["preset"]
    if kind == "curve":
        points = [p for p in data["curve"] if p.get("rate") is not None]
        periods = [p["period"] for p in points]
        series = [{"name": "全部", "values": [p["rate"] for p in points]}]
        dims = data.get("segment_curves") or {}
        dim = chart.get("dim") or next(iter(dims), None)
        if dim in dims and chart.get("segments", True):
            for seg, curve in dims[dim].items():
                by_period = {p["period"]: p.get("rate") for p in curve}
                series.append({"name": seg, "values": [by_period.get(k) for k in periods]})
        x = [labels.get(k, str(k)) for k in periods]
        html = viz.line_chart(x, series, fmt=lambda v: viz.fmt_pct(v, 0), title=chart.get("title", "留存曲线（固定批次）"),
                              caption=caption)
        md = _md_table(["周期"] + [s["name"] for s in series],
                       [[x[i]] + [pct(s["values"][i]) if s["values"][i] is not None else "—" for s in series] for i in range(len(x))])
        return html, md
    if kind == "matrix":
        cohorts = [m["cohort"] for m in data["matrix"]]
        html = viz.heatmap_table(cohorts, meta["labels"], [m["rates"] for m in data["matrix"]],
                                 row_notes=[f"{m['size']:,}" for m in data["matrix"]], note_header="人数", corner="批次",
                                 title=chart.get("title", "留存矩阵"), caption=caption + "；斜纹为尚未观察完整")
        md = _md_table(["批次", "人数"] + meta["labels"],
                       [[m["cohort"], f"{m['size']:,}"] + [pct(v) if v is not None else "—" for v in m["rates"]] for m in data["matrix"]])
        return html, md
    if kind == "segments":
        comparison = data.get("comparison") or {}
        dims = comparison.get("segments") or {}
        dim = chart.get("dim") or next(iter(dims), None)
        if dim not in dims:
            raise RefError(f"{name} 没有批次对比的分群拆解")
        cur, base = comparison["current"], comparison["baseline"]
        headers = ["分群", f"占比 {base}→{cur}", f"留存 {base}→{cur}", "结构效应", "留存效应"]
        rows = [[r["segment"], f"{pct(r['share_baseline'])} → {pct(r['share_current'])}",
                 f"{pct(r['rate_baseline'])} → {pct(r['rate_current'])}",
                 viz.fmt_pp(r["mix_effect"], 1), viz.fmt_pp(r["rate_effect"], 1)] for r in dims[dim]["rows"]]
        return _figure_table(chart.get("title", f"{_by(dim)}拆解"), headers, rows, caption), _md_table(headers, rows)
    raise RefError("retention 可用预设：curve / matrix / segments")


def preset_eda(data: dict, name: str, chart: dict, ctx: Context) -> tuple[str, str]:
    if chart["preset"] != "issues":
        raise RefError("eda 只有 issues 预设")
    levels = chart.get("levels", ["P0", "P1"])
    issues = [i for i in data["issues"] if i["severity"] in levels]
    limit = chart.get("limit", 10)
    headers = ["级别", "位置", "问题", "处理方式"]
    rows = [[i["severity"], _where(i), i["title"], i["action"]]
            for i in issues[:limit]]
    note = f"；另有 {len(issues) - limit} 条见体检报告" if len(issues) > limit else ""
    caption = (chart.get("caption") or f"来源：{name}（exploratory-data-analysis）") + note
    return _figure_table(chart.get("title", "数据问题清单"), headers, rows, caption), _md_table(headers, rows)


PRESETS = {"funnel": preset_funnel, "ab": preset_ab, "retention": preset_retention, "eda": preset_eda}


def _by(dim: str) -> str:
    """“按渠道拆” / “按 channel_id 拆”：英文维度名两侧留空格。"""
    return f"按 {dim} " if dim.isascii() else f"按{dim}"


def _figure_table(title: str, headers: list[str], rows: list[list[str]], caption: str) -> str:
    return (f'<figure class="chart"><figcaption class="fig-title">{esc(title)}</figcaption>'
            f'{viz.table(headers, rows)}<p class="fig-note">{esc(caption)}</p></figure>')


def custom_chart(chart: dict, ctx: Context, where: str) -> tuple[str, str]:
    """自定义图表：数据用引用或数字给出，例如 {"type": "bar", "categories": [...], "values": ["{{facts:a}}", ...]}。"""
    kind = chart.get("type")
    fmt = _fmt_callable(chart.get("fmt"))
    title, caption = chart.get("title"), chart.get("caption")
    cats = [str(ctx.value(c, where)) for c in chart.get("categories", [])]

    def nums(key: str) -> list:
        values = [ctx.value(v, where) for v in chart.get(key, [])]
        if len(values) != len(cats):
            raise RefError(f"{key} 有 {len(values)} 个值，categories 有 {len(cats)} 个")
        return values

    if kind == "bar":
        values = nums("values")
        return viz.bar_chart(cats, values, fmt=fmt, title=title, caption=caption), _md_table(["", "值"], [[c, fmt(v)] for c, v in zip(cats, values)])
    if kind == "diverging":
        values = nums("values")
        return (viz.diverging_bar_chart(cats, values, fmt=fmt, tones=chart.get("tones"), title=title, caption=caption),
                _md_table(["", "变化"], [[c, fmt(v)] for c, v in zip(cats, values)]))
    if kind == "paired":
        cur, base = nums("current"), nums("baseline")
        names = tuple(chart.get("names", ["本期", "上期"]))
        return (viz.paired_bar_chart(cats, cur, base, names=names, fmt=fmt, title=title, caption=caption),
                _md_table(["", names[1], names[0]], [[c, fmt(b), fmt(a)] for c, a, b in zip(cats, cur, base)]))
    if kind == "line":
        series = []
        for s in chart.get("series", []):
            values = [ctx.value(v, where) for v in s.get("values", [])]
            series.append({"name": s.get("name", ""), "values": values})
        return (viz.line_chart(cats, series, fmt=fmt, title=title, caption=caption),
                _md_table([""] + [s["name"] for s in series], [[c] + [fmt(s["values"][i]) for s in series] for i, c in enumerate(cats)]))
    raise RefError("自定义图表 type 可用：bar / diverging / paired / line；或用 preset 引用来源的标准图")


def render_chart(chart: dict, ctx: Context, where: str) -> tuple[str, str]:
    try:
        if "preset" in chart:
            name = chart.get("source") or next(iter(ctx.sources), None)
            if name not in ctx.sources:
                raise RefError(f"图表来源「{name}」未加载")
            src = ctx.sources[name]
            builder = PRESETS.get(src["type"])
            if not builder:
                raise RefError(f"{name} 是通用 JSON，没有预设图，请改用自定义图表")
            return builder(src["data"], name, chart, ctx)
        return custom_chart(chart, ctx, where)
    except RefError as exc:
        ctx.errors.append(f"{where}·图表：{exc}")
        return "", ""
    except (KeyError, IndexError, TypeError) as exc:
        ctx.errors.append(f"{where}·图表：来源结构不符合预设（{exc!r}）")
        return "", ""


# ---------------------------------------------------------------------------
# 来源可信度
# ---------------------------------------------------------------------------

# 会让数字本身不可信的检查：样本分配失衡、漏斗 / 留存人数不单调。其余 fail（如缺护栏指标）影响结论，不影响数字
BLOCKING_CHECKS = {"ab": {"srm"}, "funnel": {"monotonic"}, "retention": {"monotonic"}}


def _where(issue: dict) -> str:
    column = issue.get("column") or ""
    if "=" in column or "." in column:
        return column
    return issue["table"] + (f".{column}" if column else "")


def source_health(name: str, src: dict) -> dict:
    """汇总一个来源的结论和非通过检查；阻断问题会在报告顶部醒目提示。"""
    data, kind = src["data"], src["type"]
    verdict = data.get("verdict") if isinstance(data, dict) else None
    items, blocking = [], []
    if kind == "eda":
        for issue in data.get("issues", []):
            if issue["severity"] in ("P0", "P1"):
                where = _where(issue)
                items.append({"status": "fail" if issue["severity"] == "P0" else "warn",
                              "title": f"{issue['severity']} · {where}：{issue['title']}", "detail": issue.get("impact", "")})
                if issue["severity"] == "P0":
                    blocking.append(f"{where}：{issue['title']}")
    elif isinstance(data, dict):
        for check in data.get("checks") or []:
            if check.get("status") in ("warn", "fail"):
                items.append({"status": check["status"], "title": check["title"], "detail": check.get("detail", "")})
                if check["status"] == "fail" and check.get("id") in BLOCKING_CHECKS.get(kind, {check.get("id")}):
                    blocking.append(check["title"])
    return {"name": name, "type": kind, "path": src["path"], "verdict": verdict, "items": items,
            "blocking": list(dict.fromkeys(blocking))}


# ---------------------------------------------------------------------------
# 规格检查
# ---------------------------------------------------------------------------

def collect_text(spec: dict):
    """遍历规格里所有叙述文本：(位置, 文本)。"""
    yield "标题", spec.get("title")
    yield "一句话结论", spec.get("headline")
    yield "需要的决策", spec.get("decision")
    for i, line in enumerate(spec.get("summary") or [], 1):
        yield f"摘要{i}", line
    for i, f in enumerate(spec.get("findings") or [], 1):
        yield f"发现{i}·标题", f.get("title")
        for j, line in enumerate(f.get("evidence") or [], 1):
            yield f"发现{i}·证据{j}", line
        yield f"发现{i}·解释", f.get("interpretation")
        yield f"发现{i}·影响", f.get("impact")
    for i, h in enumerate(spec.get("hypotheses") or [], 1):
        for key in ("hypothesis", "evidence", "verify"):
            yield f"假设{i}", h.get(key)
    for i, a in enumerate(spec.get("actions") or [], 1):
        for key in ("action", "expected", "cost", "owner"):
            yield f"建议{i}", a.get(key)
    for i, line in enumerate(spec.get("limitations") or [], 1):
        yield f"限制{i}", line
    for i, line in enumerate(spec.get("next_steps") or [], 1):
        yield f"下一步{i}", line


def review_spec(spec: dict) -> list[str]:
    warnings = []
    if not spec.get("headline"):
        warnings.append("缺少 headline（一句话结论）：读者只看一句话时应该看到什么")
    elif not REF_RE.search(spec["headline"]):
        warnings.append("headline 没有引用任何数字：结论应该带上最关键的那个数")
    for i, f in enumerate(spec.get("findings") or [], 1):
        if not any(REF_RE.search(str(line)) for line in f.get("evidence") or []):
            warnings.append(f"发现{i}「{f.get('title', '')}」没有可溯源的数据证据，报告中会标为“证据不足”")
    for where, text in [("一句话结论", spec.get("headline"))] + [(f"摘要{i}", s) for i, s in enumerate(spec.get("summary") or [], 1)] + \
            [(f"发现{i}·标题", f.get("title")) for i, f in enumerate(spec.get("findings") or [], 1)]:
        hit = CAUSAL_RE.search(str(text or ""))
        if hit:
            warnings.append(f"{where} 使用了因果措辞「{hit.group(0)}」：只有实验或已验证的机制才能这样写，否则改成“与…同时发生 / 主要集中在”")
    for i, a in enumerate(spec.get("actions") or [], 1):
        hit = VAGUE_RE.search(str(a.get("action", "")))
        if hit:
            warnings.append(f"建议{i}「{hit.group(0)}」不是可执行动作：写清楚做什么、谁做、何时看结果")
        if not a.get("owner"):
            warnings.append(f"建议{i} 没有负责人")
    if not spec.get("actions"):
        warnings.append("没有建议动作：报告要推动决策")
    if not spec.get("limitations"):
        warnings.append("没有写风险与限制")
    todo = sum(str(text or "").count(TODO_MARK) for _, text in collect_text(spec))
    if todo:
        warnings.append(f"还有 {todo} 处「{TODO_MARK}…】」没有填写")
    return warnings


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

EXTRA_CSS = """
.ref{border-bottom:1px dotted var(--accent);cursor:help;font-variant-numeric:tabular-nums}
.headline{font-size:19px;font-weight:650;line-height:1.5}
.decision{margin-top:10px;padding:10px 14px;border-radius:10px;background:var(--wash);color:var(--ink)}
.decision b{color:var(--accent-text);font-weight:650;margin-right:6px}
ol.summary{margin:0;padding-left:22px}
ol.summary li{margin:6px 0}
.finding{border-top:1px solid var(--grid);padding:20px 0 6px}
.finding:first-of-type{border-top:0;padding-top:2px}
.finding-head{display:flex;gap:10px;align-items:baseline}
.finding-no{color:var(--accent-text);font-weight:650;font-variant-numeric:tabular-nums}
.finding h3{font-size:16px;margin:0;line-height:1.5;font-weight:650}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 6px}
.tag{font-size:12px;border:1px solid var(--border);border-radius:6px;padding:1px 8px;color:var(--ink-2)}
.tag-warn{color:var(--warning-text);border-color:currentColor}
ul.evidence{margin:6px 0 10px;padding-left:20px}
ul.evidence li{margin:4px 0}
dl.explain{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;margin:6px 0 0}
dl.explain dt{color:var(--ink-2);font-size:13px;padding-top:2px}
dl.explain dd{margin:0}
ul.plain{margin:0;padding-left:20px}
ul.plain li{margin:4px 0}
details summary{cursor:pointer;color:var(--ink-2)}
.prose-sm{color:var(--ink-2);font-size:14px;margin:6px 0}
td .ref{border-bottom-color:var(--axis)}
@media (max-width:560px){dl.explain{grid-template-columns:1fr}dl.explain dt{padding-top:6px}}
@media print{details{display:block}details>*{display:block}}
"""

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "高": 0, "中": 1, "低": 2}
CONFIDENCE = {"high": "置信度 高", "medium": "置信度 中", "low": "置信度 低"}
KIND = {"fact": "事实", "inference": "推断", "experiment": "实验结论"}
STATUS = {"pending": "待验证", "supported": "有证据支持", "rejected": "已排除"}


def _html_table(headers: list[str], rows: list[list[str]], nowrap: tuple = ()) -> str:
    """单元格内容已是 HTML（含引用标记）；长文本列允许换行，nowrap 列保持一行。"""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f'<td style="white-space:{"nowrap" if i in nowrap else "normal"}">{c}</td>'
                                    for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def build(spec: dict, ctx: Context) -> dict:
    """渲染 HTML 与 Markdown；两份共享同一套引用解析结果。"""
    health = [source_health(name, src) for name, src in ctx.sources.items()]
    blocking = [(h["name"], b) for h in health for b in h["blocking"]]
    H, M = [], []  # HTML 块、Markdown 行
    t = lambda value, where: ctx.text(value, where, True)  # noqa: E731
    m = lambda value, where: ctx.text(value, where, False)  # noqa: E731
    # 叙述只扫描一次：Markdown 渲染时临时关闭扫描与溯源记录
    md_ctx = _Silent(ctx)

    title = spec.get("title") or "数据分析报告"
    M.append(f"# {md_ctx.text(title)}")
    if spec.get("subtitle"):
        M.append(f"\n{md_ctx.text(spec['subtitle'])}")

    if blocking:
        body = "；".join(f"{name}：{text}" for name, text in blocking[:4])
        H.append(viz.callout("bad", "数据可信度存疑：来源中有阻断问题，结论需谨慎使用", body))
        M.append(f"\n> ✕ **数据可信度存疑**：{body}")

    level = spec.get("level", "info")
    decision = spec.get("decision")
    head_html = f'<div class="headline">{t(spec.get("headline"), "一句话结论")}</div>'
    if decision:
        head_html += f'<div class="decision"><b>需要的决策</b>{t(decision, "需要的决策")}</div>'
    H.append(f'<div class="callout callout-{level if level in ("good", "warning", "bad", "info") else "info"}">'
             f'<span class="icon" aria-hidden="true">{viz.ICONS.get(level, "i")}</span><div>{head_html}</div></div>')
    M.append(f"\n> **{md_ctx.text(spec.get('headline'))}**")
    if decision:
        M.append(f">\n> 需要的决策：{md_ctx.text(decision)}")

    tiles = []
    for i, k in enumerate(spec.get("kpis") or [], 1):
        tiles.append({key: ctx.text(k.get(key), f"指标卡{i}", False) for key in ("label", "value", "delta", "note") if k.get(key)}
                     | {"tone": k.get("tone", "neutral")})
    if tiles:
        H.append(viz.stat_tiles(tiles))
        M.append("\n" + _md_table([x["label"] for x in tiles], [[x["value"] + (f"（{x['delta']}）" if x.get("delta") else "") for x in tiles]]))

    summary = spec.get("summary") or []
    if summary:
        items = "".join(f"<li>{t(s, f'摘要{i}')}</li>" for i, s in enumerate(summary, 1))
        H.append(viz.section("执行摘要", f'<ol class="summary">{items}</ol>'))
        M.append("\n## 执行摘要\n\n" + "\n".join(f"{i}. {md_ctx.text(s)}" for i, s in enumerate(summary, 1)))

    scope = spec.get("scope") or {}
    scope_rows = list(scope.items()) if isinstance(scope, dict) else [tuple(r) for r in scope]
    bg_blocks, bg_md = [], []
    for key, label in (("background", "背景"), ("question", "要回答的问题")):
        if spec.get(key):
            bg_blocks.append(f'<p class="prose"><strong>{label}：</strong>{t(spec[key], label)}</p>')
            bg_md.append(f"**{label}**：{md_ctx.text(spec[key])}")
    if scope_rows:
        bg_blocks.append(_html_table(["项目", "口径"], [[esc(str(k)), t(v, f"口径·{k}")] for k, v in scope_rows], nowrap=(0,)))
        bg_md.append(_md_table(["项目", "口径"], [[k, md_ctx.text(v)] for k, v in scope_rows]))
    if bg_blocks:
        H.append(viz.section("背景与口径", *bg_blocks))
        M.append("\n## 背景与口径\n\n" + "\n\n".join(bg_md))

    findings = spec.get("findings") or []
    if findings:
        cards, md_cards = [], []
        for i, f in enumerate(findings, 1):
            evidence = f.get("evidence") or []
            has_evidence = any(REF_RE.search(str(e)) for e in evidence)
            tags = [KIND.get(f.get("type", "fact"), f.get("type", ""))]
            if f.get("confidence") in CONFIDENCE:
                tags.append(CONFIDENCE[f["confidence"]])
            tag_html = "".join(f'<span class="tag">{esc(x)}</span>' for x in tags if x)
            if not has_evidence:
                tag_html += '<span class="tag tag-warn">! 证据不足</span>'
            ev_html = "".join(f"<li>{t(e, f'发现{i}·证据{j}')}</li>" for j, e in enumerate(evidence, 1))
            chart_html, chart_md = render_chart(f["chart"], ctx, f"发现{i}") if f.get("chart") else ("", "")
            explain = ""
            for key, label in (("interpretation", "解释"), ("impact", "影响")):
                if f.get(key):
                    explain += f"<dt>{label}</dt><dd>{t(f[key], f'发现{i}·{label}')}</dd>"
            cards.append(
                f'<article class="finding"><div class="finding-head"><span class="finding-no">{i:02d}</span>'
                f'<h3>{t(f.get("title"), f"发现{i}·标题")}</h3></div><div class="tags">{tag_html}</div>'
                + (f'<ul class="evidence">{ev_html}</ul>' if ev_html else "") + chart_html
                + (f'<dl class="explain">{explain}</dl>' if explain else "") + "</article>"
            )
            md = [f"### 发现 {i}：{md_ctx.text(f.get('title'))}", "",
                  f"*{' · '.join(x for x in tags if x)}{' · 证据不足' if not has_evidence else ''}*", ""]
            md += [f"- 数据证据：{md_ctx.text(e)}" for e in evidence]
            if chart_md:
                md += ["", chart_md, ""]
            for key, label in (("interpretation", "解释判断"), ("impact", "业务影响")):
                if f.get(key):
                    md.append(f"- {label}：{md_ctx.text(f[key])}")
            md_cards.append("\n".join(md))
        H.append(viz.section("核心发现", "".join(cards)))
        M.append("\n## 核心发现\n\n" + "\n\n".join(md_cards))

    hypotheses = spec.get("hypotheses") or []
    if hypotheses:
        headers = ["假设", "支持证据", "如何验证", "状态"]
        rows = [[t(h.get("hypothesis"), f"假设{i}"), t(h.get("evidence"), f"假设{i}"), t(h.get("verify"), f"假设{i}"),
                 esc(STATUS.get(h.get("status", "pending"), h.get("status", "")))] for i, h in enumerate(hypotheses, 1)]
        H.append(viz.section("原因假设", _html_table(headers, rows, nowrap=(3,)), lead="以下是待验证的推断，不是已确认的原因"))
        M.append("\n## 原因假设\n\n" + _md_table(headers, [[md_ctx.text(h.get(k)) for k in ("hypothesis", "evidence", "verify")]
                                                      + [STATUS.get(h.get("status", "pending"), h.get("status", ""))] for h in hypotheses]))

    actions = sorted(spec.get("actions") or [], key=lambda a: PRIORITY_ORDER.get(str(a.get("priority")), 9))
    if actions:
        headers = ["优先级", "建议", "预期收益", "成本 / 风险", "负责人", "时间"]
        keys = ("action", "expected", "cost", "owner", "due")
        rows = [[esc(str(a.get("priority", "")))] + [t(a.get(k), f"建议{i}") for k in keys] for i, a in enumerate(actions, 1)]
        H.append(viz.section("建议动作", _html_table(headers, rows, nowrap=(0, 4, 5))))
        M.append("\n## 建议动作\n\n" + _md_table(headers, [[str(a.get("priority", ""))] + [md_ctx.text(a.get(k)) for k in keys] for a in actions]))

    risk_blocks, risk_md = [], []
    limitations = spec.get("limitations") or []
    if limitations:
        risk_blocks.append('<ul class="plain">' + "".join(f"<li>{t(x, f'限制{i}')}</li>" for i, x in enumerate(limitations, 1)) + "</ul>")
        risk_md += [f"- {md_ctx.text(x)}" for x in limitations]
    src_rows, check_items = [], []
    for h in health:
        verdict = (h["verdict"] or {}).get("title", "—")
        src_rows.append([h["name"], SOURCE_TYPES[h["type"]], verdict, os.path.basename(h["path"])])
        check_items += [dict(item, title=f"{h['name']} · {item['title']}") for item in h["items"]]
    if src_rows:
        risk_blocks.append('<p class="prose-sm">数据来源与脚本结论：</p>' + viz.table(["来源", "类型", "脚本结论", "文件"], src_rows))
        if check_items:
            risk_blocks.append('<p class="prose-sm">脚本标记的口径与质量问题：</p>' + viz.checklist(check_items[:12]))
        risk_md += ["", "数据来源：", "", _md_table(["来源", "类型", "脚本结论", "文件"], src_rows)]
        risk_md += [f"- {'✕' if c['status'] == 'fail' else '!'} {c['title']}" for c in check_items[:12]]
    if risk_blocks:
        H.append(viz.section("风险与限制", *risk_blocks))
        M.append("\n## 风险与限制\n\n" + "\n".join(risk_md))

    next_steps = spec.get("next_steps") or []
    if next_steps:
        H.append(viz.section("下一步", '<ul class="plain">' + "".join(f"<li>{t(x, f'下一步{i}')}</li>" for i, x in enumerate(next_steps, 1)) + "</ul>"))
        M.append("\n## 下一步\n\n" + "\n".join(f"- {md_ctx.text(x)}" for x in next_steps))

    trace = list(ctx.trace.values())
    unmatched = [n for n in ctx.numbers if n["status"] == "unmatched"]
    note = f"报告引用了 {len(trace)} 个来源数值，悬停数字可看出处"
    note += f"；另有 {len(unmatched)} 个手写数字未能在来源中找到" if unmatched else "；正文没有未溯源的手写数字"
    rows = [[x["shown"], x["ref"], x["raw"]] for x in trace]
    H.append(viz.section("附录：数字溯源", f'<details><summary>{esc(note)}</summary>'
                         f'{viz.table(["报告中的写法", "来源路径", "原始值"], rows)}</details>'))
    M.append(f"\n---\n\n附录：{note}。")

    meta_parts = [f"读者：{spec['audience']}" if spec.get("audience") else "", spec.get("date", ""),
                  f"生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    page = viz.html_report(md_ctx.text(title), H, subtitle=md_ctx.text(spec.get("subtitle")) or None,
                           meta=" · ".join(p for p in meta_parts if p), brand="拾穗数据 · 分析报告", extra_css=EXTRA_CSS)
    return {"html": page, "markdown": "\n".join(M) + "\n", "health": health, "blocking": blocking}


class _Silent:
    """Markdown 渲染用：只替换引用，不重复扫描、不重复记错误。"""

    def __init__(self, ctx: Context):
        self.ctx = ctx

    def text(self, value) -> str:
        if value is None:
            return ""

        def swap(match: re.Match) -> str:
            try:
                return apply_format(self.ctx.resolve(match.group(1).strip()), match.group(2))
            except RefError:
                return "⟦引用错误⟧"
        return REF_RE.sub(swap, str(value))


# ---------------------------------------------------------------------------
# 规格草稿
# ---------------------------------------------------------------------------

def R(name: str, path: str, fmt: str = "") -> str:
    return "{{" + f"{name}:{path}" + (f"|{fmt}" if fmt else "") + "}}"


def _sel(items: list, key: str, value, index: int) -> str:
    unique = sum(1 for x in items if x.get(key) == value) == 1
    return f"[{key}={value}]" if unique else f"[{index}]"


def skeleton_funnel(name: str, d: dict) -> dict:
    meta = d["funnel"]
    cur, base = meta["current"], meta.get("baseline")
    comp = d.get("comparison")
    out = {"kpis": [], "findings": [], "scope": [["漏斗", " → ".join(meta["steps"])], ["来源", f"{name}（funnel-analysis）"]],
           "limitations": [], "actions": []}
    if not (base and comp):
        out["headline"] = f"{meta['name']}：整体转化 {R(name, f'periods.{cur}.overall', 'pct')}，{TODO_MARK}：一句话结论】"
        out["kpis"].append({"label": "整体转化", "value": R(name, f"periods.{cur}.overall", "pct")})
        out["findings"].append({"title": f"流失最多的一步是 {d['drop_points']['largest_loss']['transition']}", "type": "fact",
                                "evidence": [f"这一步流失 {R(name, 'drop_points.largest_loss.lost', 'int')} 人",
                                             f"转化率最低的一步：{R(name, 'drop_points.lowest_step_rate.transition')}，"
                                             f"{R(name, 'drop_points.lowest_step_rate.step_rate', 'pct')}"],
                                "chart": {"preset": "steps", "source": name},
                                "interpretation": f"{TODO_MARK}：这一步的产品形态和用户动机】", "impact": f"{TODO_MARK}】"})
        return out
    out["scope"].insert(0, ["对比", f"{cur} vs {base}"])
    sig = comp["overall"].get("p_value", 1) < 0.05
    out["headline"] = (f"{meta['name']}：整体转化 {R(name, f'periods.{base}.overall', 'pct')} → "
                       f"{R(name, f'periods.{cur}.overall', 'pct')}（{R(name, 'comparison.overall.diff', 'pp')}），{TODO_MARK}：主要原因一句话】")
    out["level"] = {"good": "good", "bad": "bad"}.get(viz.delta_tone(comp["overall"]["diff"], True, sig), "info")
    out["kpis"] = [
        {"label": f"整体转化（{cur}）", "value": R(name, f"periods.{cur}.overall", "pct"),
         "delta": R(name, "comparison.overall.diff", "pp"), "tone": viz.delta_tone(comp["overall"]["diff"], True, sig),
         "note": f"{base} " + R(name, f"periods.{base}.overall", "pct") + "，" + R(name, "comparison.overall.p_value", "p")},
        {"label": f"入口人数（{cur}）", "value": R(name, f"periods.{cur}.counts[0]", "int"),
         "note": f"{base} " + R(name, f"periods.{base}.counts[0]", "int")},
    ]
    steps = comp["steps"]
    top_i = max(range(len(steps)), key=lambda i: abs(steps[i].get("contribution_pp") or 0))
    top = steps[top_i]
    sel = f"comparison.steps{_sel(steps, 'transition', top['transition'], top_i)}"
    out["findings"].append({
        "title": f"变化最大的来源是「{top['transition']}」这一步", "type": "fact", "confidence": "high",
        "evidence": [f"单步转化 {R(name, sel + '.rate_baseline', 'pct')} → {R(name, sel + '.rate_current', 'pct')}"
                     f"（{R(name, sel + '.test.diff', 'pp')}，{R(name, sel + '.test.p_value', 'p')}）",
                     f"贡献整体变化的 {R(name, sel + '.share_of_change', 'pct.0')}；若这一步恢复到{base}水平，"
                     f"整体转化可回到 {R(name, sel + '.counterfactual_overall', 'pct')}"],
        "chart": {"preset": "steps", "source": name},
        "interpretation": f"{TODO_MARK}：这一步在{cur}发生了什么（改版、性能、价格、埋点）】",
        "impact": f"{TODO_MARK}：换算成业务结果，例如少了多少付费用户】"})
    out["kpis"].append({"label": "最大变化步骤", "value": R(name, sel + ".rate_current", "pct"),
                        "delta": R(name, sel + ".test.diff", "pp"),
                        "tone": viz.delta_tone(top["test"]["diff"], True, top["test"]["p_value"] < 0.05), "note": top["transition"]})
    for dim, seg in (comp.get("segments") or {}).items():
        rows = seg["rows"]
        mix_major = abs(seg["mix_effect"]) > abs(seg["rate_effect"])
        key = "mix_effect" if mix_major else "rate_effect"
        ri = max(range(len(rows)), key=lambda i: abs(rows[i][key]))
        rp = f"comparison.segments.{dim}.rows{_sel(rows, 'segment', rows[ri]['segment'], ri)}"
        out["findings"].append({
            "title": f"{_by(dim)}拆：{'用户构成变化' if mix_major else '同类用户转化变差'}是更大的部分", "type": "fact", "confidence": "medium",
            "evidence": [f"结构效应 {R(name, f'comparison.segments.{dim}.mix_effect', 'pp')}，"
                         f"分群自身转化效应 {R(name, f'comparison.segments.{dim}.rate_effect', 'pp')}",
                         f"{rows[ri]['segment']}：占比 {R(name, rp + '.share_baseline', 'pct')} → {R(name, rp + '.share_current', 'pct')}，"
                         f"自身转化 {R(name, rp + '.conv_baseline', 'pct')} → {R(name, rp + '.conv_current', 'pct')}"],
            "chart": {"preset": "segments", "source": name, "dim": dim},
            "interpretation": f"{TODO_MARK}：构成为什么变了 / 该分群体验为什么变差】"})
        break
    out["limitations"] = [R(name, f"checks[id={c['id']}].title") + "：" + R(name, f"checks[id={c['id']}].detail")
                          for c in d.get("checks", []) if c.get("status") in ("warn", "info")]
    out["actions"] = [{"priority": "P0" if i == 0 else "P1", "action": R(name, f"verdict.next_steps[{i}]"),
                       "expected": f"{TODO_MARK}】", "owner": f"{TODO_MARK}】"} for i in range(len(d["verdict"].get("next_steps", [])))]
    return out


def skeleton_ab(name: str, d: dict) -> dict:
    comps = d["comparisons"]
    exp = d["experiment"]
    pi = next((i for i, c in enumerate(comps) if c.get("role") == "primary"), 0)
    p = f"comparisons[{pi}]"
    fmt = "pct" if comps[pi]["type"] == "proportion" else "num"
    sig = comps[pi].get("significant", False)
    out = {
        "headline": f"{exp['name']}：{comps[pi]['metric']} {R(name, p + '.control_value', fmt)} → {R(name, p + '.treatment_value', fmt)}"
                    f"（相对 {R(name, p + '.rel_lift', 'spct')}，{R(name, p + '.p_value', 'p')}）。{R(name, 'verdict.title')}",
        "level": {"bad": "bad", "warning": "warning", "good": "good"}.get(d["verdict"].get("level"), "info"),
        "scope": [["实验", exp["name"]], ["对照 / 实验组", f"{exp['control']} / {'、'.join(exp['treatments'])}"],
                  ["运行天数", R(name, "experiment.days", "int") + " / 计划 " + R(name, "experiment.planned_days", "int")],
                  ["来源", f"{name}（ab-test-analysis）"]],
        "kpis": [{"label": comps[pi]["metric"], "value": R(name, p + ".treatment_value", fmt), "delta": R(name, p + ".rel_lift", "spct"),
                  "tone": viz.delta_tone(comps[pi]["rel_lift"], comps[pi].get("higher_is_better", True), sig),
                  "note": "对照 " + R(name, p + ".control_value", fmt)},
                 {"label": "p 值", "value": R(name, p + ".p_value", "p"), "note": "显著性阈值 " + R(name, "experiment.alpha")},
                 {"label": "可检测的最小提升", "value": R(name, p + ".mde_rel", "spct.0"), "note": "当前样本量下"}],
        "findings": [{
            "title": f"主指标「{comps[pi]['metric']}」{'显著变化' if sig else '没有显著变化'}", "type": "experiment", "confidence": "high" if sig else "medium",
            "evidence": [f"{exp['control']} {R(name, p + '.control_value', fmt)}，{comps[pi]['treatment']} {R(name, p + '.treatment_value', fmt)}",
                         f"相对提升 {R(name, p + '.rel_lift', 'spct')}，95% 区间 {R(name, p + '.ci_rel', 'spct')}，{R(name, p + '.p_value', 'p')}",
                         f"当前样本量能可靠检测的最小相对提升约 {R(name, p + '.mde_rel', 'spct.0')}"],
            "chart": {"preset": "effects", "source": name},
            "interpretation": f"{TODO_MARK}：结果对决策意味着什么】"}],
        "limitations": [R(name, f"checks[id={c['id']}].title") for c in d.get("checks", []) if c.get("status") in ("warn", "fail")],
        "actions": [{"priority": "P0" if i == 0 else "P1", "action": R(name, f"verdict.next_steps[{i}]"), "owner": f"{TODO_MARK}】"}
                    for i in range(len(d["verdict"].get("next_steps", [])))],
    }
    return out


UNITS = {"day": "按日", "week": "按周", "month": "按月"}
MODES = {"on": "第 N 期当期有回访", "within": "N 期内有过回访"}
BOUNDARIES = {"natural": "自然日 / 自然周 / 自然月", "rolling": "滚动 24 小时"}


def skeleton_retention(name: str, d: dict) -> dict:
    meta = d["retention"]
    key = meta["key_label"]
    comp = d.get("comparison")
    out = {"kpis": [], "findings": [], "limitations": [], "actions": [],
           "scope": [["粒度与周期", f"{UNITS.get(meta['unit'], meta['unit'])}，{'、'.join(meta['labels'])}"],
                     ["留存口径", MODES.get(meta["mode"], meta["mode"])],
                     ["时间边界", BOUNDARIES.get(meta["boundary"], meta["boundary"])],
                     ["来源", f"{name}（retention-cohort-analysis）"]]}
    if comp:
        out["headline"] = (f"{key} 留存 {R(name, 'comparison.rate_baseline', 'pct')} → {R(name, 'comparison.rate_current', 'pct')}"
                           f"（{R(name, 'comparison.test.diff', 'pp')}），{TODO_MARK}：主要原因一句话】")
        out["kpis"].append({"label": f"{key} 留存（{comp['current']}）", "value": R(name, "comparison.rate_current", "pct"),
                            "delta": R(name, "comparison.test.diff", "pp"),
                            "tone": viz.delta_tone(comp["test"]["diff"], True, comp["test"]["p_value"] < 0.05),
                            "note": f"{comp['baseline']} " + R(name, "comparison.rate_baseline", "pct")})
    else:
        out["headline"] = f"{R(name, 'verdict.title')}，{TODO_MARK}：一句话结论】"
    points = [i for i, p in enumerate(d["curve"]) if p.get("rate") is not None]
    if points:
        first, last = points[0], points[-1]
        out["kpis"].append({"label": f"{meta['labels'][last]} 留存（固定批次）", "value": R(name, f"curve[{last}].rate", "pct"),
                            "note": "曲线可观察到的最远周期"})
        out["findings"].append({
            "title": "留存曲线形状", "type": "fact", "confidence": "high",
            "evidence": [f"{meta['labels'][first]} {R(name, f'curve[{first}].rate', 'pct')}，{meta['labels'][last]} "
                         f"{R(name, f'curve[{last}].rate', 'pct')}（固定 {R(name, 'curve_cohorts', 'len')} 个已成熟批次）"],
            "chart": {"preset": "curve", "source": name}, "interpretation": f"{TODO_MARK}：后段是否趋平，意味着什么】"})
    if comp and comp.get("segments"):
        dim, seg = next(iter(comp["segments"].items()))
        rows = seg["rows"]
        ri = max(range(len(rows)), key=lambda i: abs(rows[i]["mix_effect"]))
        rp = f"comparison.segments.{dim}.rows{_sel(rows, 'segment', rows[ri]['segment'], ri)}"
        mix_major = abs(seg["mix_effect"]) > abs(seg["rate_effect"])
        out["findings"].append({
            "title": f"{_by(dim)}拆：{'用户构成变化' if mix_major else '同类用户留存变差'}是更大的部分", "type": "fact", "confidence": "medium",
            "evidence": [f"结构效应 {R(name, f'comparison.segments.{dim}.mix_effect', 'pp')}，留存效应 {R(name, f'comparison.segments.{dim}.rate_effect', 'pp')}",
                         f"{rows[ri]['segment']} 占比 {R(name, rp + '.share_baseline', 'pct.0')} → {R(name, rp + '.share_current', 'pct.0')}"],
            "chart": {"preset": "segments", "source": name, "dim": dim}, "interpretation": f"{TODO_MARK}】"})
    for dim, tests in (d.get("segment_tests") or {}).items():
        sig = [i for i, x in enumerate(tests) if x["vs_rest"]["p_value"] < 0.05 and x["vs_rest"]["diff"] < 0]
        if sig:
            i = min(sig, key=lambda k: tests[k]["vs_rest"]["diff"])
            sp = f"segment_tests.{dim}{_sel(tests, 'segment', tests[i]['segment'], i)}"
            out["findings"].append({
                "title": f"{dim}={tests[i]['segment']} 的留存明显更低", "type": "fact", "confidence": "high",
                "evidence": [f"{key} 留存 {R(name, sp + '.rate', 'pct')}，比其余用户 {R(name, sp + '.vs_rest.diff', 'pp')}"
                             f"（95% 区间 {R(name, sp + '.vs_rest.ci', 'pp')}）"],
                "interpretation": f"{TODO_MARK}】"})
        break
    for i, a in enumerate(d.get("anomalies") or []):
        out["findings"].append({
            "title": f"批次 {a['cohort']} 异常", "type": "fact", "confidence": "medium",
            "evidence": [f"{key} 留存 {R(name, f'anomalies[{i}].rate', 'pct')}，按构成调整后的预期 {R(name, f'anomalies[{i}].expected', 'pct')}"
                         f"（{R(name, f'anomalies[{i}].diff', 'pp')}）"],
            "interpretation": f"{TODO_MARK}：这个批次前后发生了什么】"})
    out["limitations"] = [R(name, f"checks[id={c['id']}].title") for c in d.get("checks", []) if c.get("status") in ("warn", "info")]
    out["actions"] = [{"priority": "P0" if i == 0 else "P1", "action": R(name, f"verdict.next_steps[{i}]"), "owner": f"{TODO_MARK}】"}
                      for i in range(len(d["verdict"].get("next_steps", [])))]
    return out


def skeleton_eda(name: str, d: dict) -> dict:
    counts = d["verdict"].get("counts", {})
    p0 = [i for i, x in enumerate(d["issues"]) if x["severity"] == "P0"]
    out = {"headline": R(name, "verdict.title"), "level": d["verdict"].get("level", "info"),
           "kpis": [{"label": f"{lvl} 问题", "value": R(name, f"verdict.counts.{lvl}", "int")} for lvl in ("P0", "P1", "P2") if lvl in counts],
           "scope": [["数据", "、".join(f"{t['name']}（{t['meta'].get('rows', '?')} 行）" for t in d["tables"])],
                     ["来源", f"{name}（exploratory-data-analysis）"]],
           "findings": [], "limitations": [],
           "actions": [{"priority": "P0", "action": R(name, f"issues[{i}].action"), "owner": f"{TODO_MARK}】"} for i in p0]}
    if p0:
        out["findings"].append({"title": "数据有必须先处理的问题", "type": "fact", "confidence": "high",
                                "evidence": [R(name, f"issues[{i}].table") + "：" + R(name, f"issues[{i}].title") for i in p0],
                                "chart": {"preset": "issues", "source": name}, "impact": f"{TODO_MARK}：不处理会让哪个结论算错】"})
    return out


SKELETONS = {"funnel": skeleton_funnel, "ab": skeleton_ab, "retention": skeleton_retention, "eda": skeleton_eda}


def make_skeleton(sources: dict, source_args: list[str]) -> dict:
    spec = {"title": f"{TODO_MARK}：报告标题】", "audience": f"{TODO_MARK}：读者，例如 业务负责人、产品经理】",
            "question": f"{TODO_MARK}：这份报告要回答的业务问题】", "decision": f"{TODO_MARK}：希望读者做出的决策】",
            "sources": {pair.split("=", 1)[0]: pair.split("=", 1)[1] for pair in source_args},
            "facts": {}, "headline": "", "level": "info", "kpis": [], "summary": [], "scope": [], "findings": [],
            "hypotheses": [{"hypothesis": f"{TODO_MARK}】", "evidence": "", "verify": "", "status": "pending"}],
            "actions": [], "limitations": [], "next_steps": []}
    for name, src in sources.items():
        builder = SKELETONS.get(src["type"])
        if not builder:
            continue
        part = builder(name, src["data"])
        if not spec["headline"]:
            spec["headline"] = part.get("headline", "")
            spec["level"] = part.get("level", "info")
        spec["kpis"] += part.get("kpis", [])
        spec["scope"] += part.get("scope", [])
        spec["findings"] += part.get("findings", [])
        spec["limitations"] += part.get("limitations", [])
        spec["actions"] += part.get("actions", [])
    spec["kpis"] = spec["kpis"][:4]
    spec["summary"] = [f"{TODO_MARK}：三条以内，每条一个结论 + 一个关键数字】"]
    spec["limitations"].append(f"{TODO_MARK}：样本、口径、归因上的限制】")
    return spec


# ---------------------------------------------------------------------------
# 命令
# ---------------------------------------------------------------------------

def suggest_format(path: str, value) -> str:
    key = re.split(r"[.\]]", path)[-1].lower() if path else ""
    if isinstance(value, list):
        if key == "ci_rel":
            return "spct"
        if key in ("ci", "ci_abs"):
            return "pp"
        return "pct" if key.endswith("ci") and all(0 <= v <= 1 for v in value) else "num"
    if isinstance(value, int):
        return "int"
    if "p_value" in key or key == "p_adjusted":
        return "p"
    if any(k in key for k in ("rel", "lift")):
        return "spct"
    if abs(value) <= 1 and any(k in key for k in ("diff", "effect", "contribution", "mde_abs")):
        return "pp"
    if abs(value) <= 1 and any(k in key for k in ("rate", "share", "overall", "value", "conv", "expected", "ratio", "pct")):
        return "pct"
    return "num"


def cmd_refs(args: argparse.Namespace) -> int:
    sources = load_sources(args.source)
    count = 0
    for name, src in sources.items():
        print(f"# {name}（{SOURCE_TYPES[src['type']]}）")
        for path, value in flatten(src["data"]):
            if isinstance(value, bool) or value is None:
                continue
            if isinstance(value, str) and not args.strings:
                continue
            if isinstance(value, list) and not all(isinstance(v, (int, float)) for v in value):
                continue
            if re.search(r"ci\[\d+\]$", path):
                continue  # 区间端点随区间整体给出
            ref = f"{name}:{path}"
            if args.grep and args.grep not in ref:
                continue
            if isinstance(value, str):
                print(f"{{{{{ref}}}}}  → {value[:60]}")
            else:
                fmt = suggest_format(path, value)
                print(f"{{{{{ref}|{fmt}}}}}  → {apply_format(value, fmt)}   （原值 {_short(value)}）")
            count += 1
            if count >= args.limit:
                print(f"…已显示 {args.limit} 条，用 --grep 缩小范围或调大 --limit")
                return 0
    return 0


def cmd_skeleton(args: argparse.Namespace) -> int:
    sources = load_sources(args.source)
    text = json.dumps(make_skeleton(sources, args.source), ensure_ascii=False, indent=2)
    if args.out:
        viz.save(args.out, text + "\n")
    print(text)
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    with open(args.spec, encoding="utf-8") as handle:
        spec = json.load(handle)
    sources = load_sources(args.source, spec, os.path.dirname(os.path.abspath(args.spec)))
    ctx = Context(sources, spec.get("facts"))
    result = build(spec, ctx)
    if args.html:
        viz.save(args.html, result["html"])
    if args.md:
        viz.save(args.md, result["markdown"])
    numbers = ctx.numbers
    report = {
        "html_report": os.path.abspath(args.html) if args.html else None,
        "markdown": os.path.abspath(args.md) if args.md else None,
        "sources": {h["name"]: {"type": h["type"], "verdict": (h["verdict"] or {}).get("title"), "blocking": h["blocking"]}
                    for h in result["health"]},
        "refs": len(ctx.trace),
        "numbers": {"bound": len(ctx.trace),
                    "matched_unbound": [n for n in numbers if n["status"] == "matched"],
                    "unmatched": [n for n in numbers if n["status"] == "unmatched"],
                    "uncheckable": ctx.cn_numbers},
        "errors": ctx.errors,
        "warnings": review_spec(spec) + [f"来源 {name} 有阻断问题：{text}" for name, text in result["blocking"]],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if ctx.errors:
        return 1
    if args.strict and (report["numbers"]["unmatched"] or report["numbers"]["uncheckable"] or report["warnings"]):
        return 1
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    facts = {}
    if args.facts:
        with open(args.facts, encoding="utf-8") as handle:
            facts = json.load(handle)
    ctx = Context(load_sources(args.source), facts)
    with open(args.text, encoding=sio.detect_encoding(args.text)) as handle:
        lines = handle.read().splitlines()
    fenced = False
    wording = []
    for no, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            ctx.scan(REF_RE.sub(" ", line), f"第 {no} 行")
            for kind, pattern in (("因果措辞", CAUSAL_RE), ("空洞建议", VAGUE_RE)):
                wording += [{"where": f"第 {no} 行", "type": kind, "text": m.group(0)} for m in pattern.finditer(line)]
    unmatched = [n for n in ctx.numbers if n["status"] == "unmatched"]
    matched = [n for n in ctx.numbers if n["status"] == "matched"]
    print(json.dumps({"checked": len(ctx.numbers), "matched": matched, "unmatched": unmatched, "uncheckable": ctx.cn_numbers,
                      "wording": wording, "errors": ctx.errors}, ensure_ascii=False, indent=2))
    return 1 if unmatched or ctx.cn_numbers or ctx.errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="分析报告组装器（拾穗数据技能库）")
    sub = parser.add_subparsers(dest="command", required=True)
    source_help = "来源：名称=JSON 路径，可重复；通常是其他分析脚本的 --json 输出"

    r = sub.add_parser("refs", help="列出来源中可引用的数字和建议写法")
    r.add_argument("--source", action="append", default=[], required=True, help=source_help)
    r.add_argument("--grep", help="只显示路径包含该文本的条目")
    r.add_argument("--strings", action="store_true", help="同时列出文本字段")
    r.add_argument("--limit", type=int, default=200)
    r.set_defaults(func=cmd_refs)

    s = sub.add_parser("skeleton", help="根据来源生成报告规格草稿")
    s.add_argument("--source", action="append", default=[], required=True, help=source_help)
    s.add_argument("--out", help="写入文件（同时打印到标准输出）")
    s.set_defaults(func=cmd_skeleton)

    b = sub.add_parser("build", help="规格 → HTML / Markdown 报告，并检查证据与数字溯源")
    b.add_argument("--spec", required=True, help="报告规格 JSON（见 references/spec-schema.md）")
    b.add_argument("--source", action="append", default=[], help=source_help + "；覆盖 spec.sources 中的同名来源")
    b.add_argument("--html", help="输出 HTML 路径")
    b.add_argument("--md", help="输出 Markdown 路径（便于粘贴到文档）")
    b.add_argument("--strict", action="store_true", help="有未溯源数字或规格警告时返回非 0")
    b.set_defaults(func=cmd_build)

    li = sub.add_parser("lint", help="检查手写 Markdown 报告里的数字能否在来源中找到")
    li.add_argument("--text", required=True, help="Markdown 报告路径")
    li.add_argument("--source", action="append", default=[], help=source_help)
    li.add_argument("--facts", help="补充事实 JSON：{名称: 数值 或 {value, source}}")
    li.set_defaults(func=cmd_lint)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(sio.run_cli(main))
