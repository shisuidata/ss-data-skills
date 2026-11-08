#!/usr/bin/env python3
"""拾穗图表套件：生成自包含 HTML 数据报告（仅依赖 Python 标准库）。

设计取舍：
- 图表输出为内联 SVG，文字由浏览器渲染，彻底绕开 matplotlib 中文字体变方块的问题
- 颜色全部走 CSS 变量，亮色 / 暗色模式各有一套经过 check_palette.py 校验的取值
- 数字格式遵循中文业务习惯：万 / 亿、百分点（pp）、带符号的涨跌
- 涨跌颜色有两种约定：goodbad（好坏色，默认）和 market（红涨绿跌），且永远配 ▲▼ 符号

这个文件是 data-viz-kit 的规范实现。其他 Skill 的 scripts/ 里会保存一份完全相同的副本，
保证每个 Skill 单独复制出去也能运行；修改后请运行仓库根目录的 `node scripts/sync-viz-kit.mjs`。
"""

from __future__ import annotations

import html
import math
from datetime import datetime
from typing import Callable, Iterable, Sequence

__version__ = "0.2.0"

THEMES = {
    "light": {
        "page": "#f6f2ea",
        "surface": "#fdfbf7",
        "ink": "#2b2822",
        "ink_2": "#615c52",
        "muted": "#8c8578",
        "grid": "#ebe5d8",
        "axis": "#cfc7b6",
        "border": "rgba(43, 40, 34, 0.10)",
        "accent": "#c99a3d",
        "accent_text": "#86621d",
        "series": ["#2f6bb3", "#c99a3d", "#2a9d8f", "#c8553d", "#7b61b8", "#5b8c3a", "#d0739a"],
        "status_marks": ["#1b7f79", "#d9a21b", "#d1453b"],
        "good_text": "#13655f",
        "warning_text": "#8a6100",
        "bad_text": "#b23a31",
        "wash": "rgba(201, 154, 61, 0.10)",
    },
    "dark": {
        "page": "#14130f",
        "surface": "#1d1b17",
        "ink": "#f1ede2",
        "ink_2": "#c9c2b2",
        "muted": "#8c8578",
        "grid": "#2e2b25",
        "axis": "#454037",
        "border": "rgba(255, 255, 255, 0.10)",
        "accent": "#deba6a",
        "accent_text": "#deba6a",
        "series": ["#5b8fd6", "#d4ad5a", "#38b49a", "#e07a62", "#9d86de", "#7fb15a", "#e592b4"],
        "status_marks": ["#1b7f79", "#d9a21b", "#d1453b"],
        "good_text": "#4fc2b6",
        "warning_text": "#e9bd4f",
        "bad_text": "#f07a70",
        "wash": "rgba(222, 186, 106, 0.10)",
    },
}

FONT_STACK = (
    '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", '
    '"Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", system-ui, sans-serif'
)

TONES = ("good", "bad", "warning", "neutral")
ICONS = {"good": "✓", "pass": "✓", "bad": "✕", "fail": "✕", "warning": "!", "warn": "!", "neutral": "–", "info": "i"}

esc = html.escape


# ---------------------------------------------------------------------------
# 数字格式
# ---------------------------------------------------------------------------

def _trim(text: str) -> str:
    return text.rstrip("0").rstrip(".") if "." in text else text


def fmt_num(value: float | int | None, digits: int = 2) -> str:
    """按中文习惯压缩大数：12,345 → 1.23万；123,456,789 → 1.23亿。"""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    if magnitude >= 1e8:
        return f"{sign}{_trim(f'{magnitude / 1e8:.{digits}f}')}亿"
    if magnitude >= 1e4:
        return f"{sign}{_trim(f'{magnitude / 1e4:.{digits}f}')}万"
    if float(magnitude).is_integer():
        return f"{sign}{int(magnitude):,}"
    return f"{sign}{_trim(f'{magnitude:,.{digits}f}')}"


def fmt_pct(value: float | None, digits: int = 2) -> str:
    """比例 → 百分数：0.0777 → 7.77%。"""
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"


def fmt_signed_pct(value: float | None, digits: int = 1) -> str:
    """相对变化：0.1099 → +11.0%。负号使用真正的减号，避免与连字符混淆。"""
    if value is None:
        return "—"
    if round(value * 100, digits) == 0:
        return "0%"
    text = f"{abs(value) * 100:.{digits}f}%"
    return ("+" if value > 0 else "−") + text


def fmt_pp(value: float | None, digits: int = 2) -> str:
    """比例差 → 百分点：0.0077 → +0.77pp。"""
    if value is None:
        return "—"
    if round(value * 100, digits) == 0:
        return "0pp"
    text = f"{abs(value) * 100:.{digits}f}pp"
    return ("+" if value > 0 else "−") + text


def fmt_signed(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "—"
    if value == 0:
        return "0"
    return ("+" if value > 0 else "−") + fmt_num(abs(value), digits)


def arrow(value: float | None) -> str:
    if value is None or value == 0:
        return "–"
    return "▲" if value > 0 else "▼"


def delta_tone(delta: float | None, higher_is_better: bool = True, significant: bool = True,
               convention: str = "goodbad") -> str:
    """把一个变化映射成颜色语义。

    goodbad：颜色表达“好 / 坏”，下降也可能是好事（例如退款率下降）
    market：颜色表达“涨 / 跌”，红涨绿跌，适合金融、交易类受众
    不显著或无变化一律 neutral：没有被证实的变化不该被上色
    """
    if delta is None or delta == 0 or not significant:
        return "neutral"
    if convention == "market":
        return "bad" if delta > 0 else "good"  # market 约定下 bad=红（涨），good=绿（跌），只借用色值
    improved = delta > 0 if higher_is_better else delta < 0
    return "good" if improved else "bad"


def nice_ticks(low: float, high: float, count: int = 5) -> list[float]:
    if high == low:
        high = low + 1
    span = high - low
    raw = span / max(count - 1, 1)
    power = 10 ** math.floor(math.log10(raw))
    step = min((m * power for m in (1, 2, 2.5, 5, 10) if m * power >= raw), default=10 * power)
    first = math.floor(low / step + 1e-9)
    last = math.ceil(high / step - 1e-9)
    return [round(k * step, 12) for k in range(first, last + 1)]


# ---------------------------------------------------------------------------
# 图表（内联 SVG，颜色引用 CSS 变量）
# ---------------------------------------------------------------------------

def _num(value) -> float | None:
    """图表只接受有限数值；None、NaN、无穷和非数字都按“缺失”处理。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _no_data(title: str | None, caption: str | None) -> str:
    return _figure('<p class="fig-note">暂无数据</p>', title, caption)


def _tone_var(tone: str) -> str:
    return {"good": "var(--good)", "bad": "var(--bad)", "warning": "var(--warning)"}.get(tone, "var(--neutral)")


def _figure(svg: str, title: str | None, caption: str | None, legend: str = "") -> str:
    head = f'<figcaption class="fig-title">{esc(title)}</figcaption>' if title else ""
    foot = f'<p class="fig-note">{esc(caption)}</p>' if caption else ""
    return f'<figure class="chart">{head}{legend}{svg}{foot}</figure>'


def interval_chart(rows: Sequence[dict], *, title: str | None = None, caption: str | None = None,
                   fmt: Callable[[float], str] = fmt_signed_pct, zero: float = 0.0) -> str:
    """区间图（森林图）：每行一个点估计 + 置信区间，跨过零线即不显著。

    rows: [{"label", "estimate", "low", "high", "tone", "sub"?}]
    这是 A/B 实验结果的首选图形：它同时表达方向、幅度和不确定性。
    """
    rows = [r for r in rows if None not in (_num(r.get("estimate")), _num(r.get("low")), _num(r.get("high")))]
    if not rows:
        return _no_data(title, caption)
    width, label_w, value_w, row_h, top, bottom = 720, 176, 172, 46, 8, 30
    x0, x1 = label_w, width - value_w
    height = top + row_h * len(rows) + bottom
    values = [zero] + [r["low"] for r in rows] + [r["high"] for r in rows]
    lo, hi = min(values), max(values)
    pad = (hi - lo) * 0.08 or 0.01
    ticks = nice_ticks(lo - pad, hi + pad, 5)
    d0, d1 = ticks[0], ticks[-1]

    def sx(v: float) -> float:
        return x0 + (v - d0) / (d1 - d0) * (x1 - x0)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title or "区间图")}">']
    axis_y = top + row_h * len(rows)
    for t in ticks:
        x = sx(t)
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{axis_y}" class="grid"/>')
        parts.append(f'<text x="{x:.1f}" y="{axis_y + 20}" class="tick" text-anchor="middle">{esc(fmt(t))}</text>')
    zx = sx(zero)
    parts.append(f'<line x1="{zx:.1f}" y1="{top - 4}" x2="{zx:.1f}" y2="{axis_y}" class="zero"/>')

    for i, row in enumerate(rows):
        cy = top + row_h * i + row_h / 2
        color = _tone_var(row.get("tone", "neutral"))
        label_y = cy - 6 if row.get("sub") else cy
        tip = f'{row["label"]}：{fmt(row["estimate"])}，95% 区间 [{fmt(row["low"])}, {fmt(row["high"])}]'
        parts.append(f'<g class="row"><title>{esc(tip)}</title>')
        parts.append(f'<rect x="0" y="{cy - row_h / 2:.1f}" width="{width}" height="{row_h}" class="hit"/>')
        parts.append(f'<text x="0" y="{label_y:.1f}" class="label" dominant-baseline="middle">{esc(row["label"])}</text>')
        if row.get("sub"):
            parts.append(f'<text x="0" y="{cy + 10:.1f}" class="sub" dominant-baseline="middle">{esc(row["sub"])}</text>')
        parts.append(
            f'<line x1="{sx(row["low"]):.1f}" y1="{cy:.1f}" x2="{sx(row["high"]):.1f}" y2="{cy:.1f}" '
            f'stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        )
        for end in ("low", "high"):
            ex = sx(row[end])
            parts.append(f'<line x1="{ex:.1f}" y1="{cy - 5:.1f}" x2="{ex:.1f}" y2="{cy + 5:.1f}" stroke="{color}" stroke-width="2" stroke-linecap="round"/>')
        parts.append(f'<circle cx="{sx(row["estimate"]):.1f}" cy="{cy:.1f}" r="5.5" fill="{color}" class="ring"/>')
        parts.append(f'<text x="{x1 + 18}" y="{cy - 6:.1f}" class="value" dominant-baseline="middle">{esc(fmt(row["estimate"]))}</text>')
        parts.append(
            f'<text x="{x1 + 18}" y="{cy + 10:.1f}" class="sub" dominant-baseline="middle">'
            f'[{esc(fmt(row["low"]))}, {esc(fmt(row["high"]))}]</text>'
        )
        parts.append("</g>")
    parts.append("</svg>")
    return _figure("".join(parts), title, caption)


def _hbar(x_base: float, x_end: float, y: float, h: float, color: str) -> str:
    """横向条：基线一端是直角，数据一端 4px 圆角；x_end < x_base 时向左画。"""
    w = abs(x_end - x_base)
    r = min(4.0, w, h / 2)
    if w < 0.5:
        return ""
    s = 1 if x_end >= x_base else -1
    tip = x_end - s * r
    return (f'<path d="M{x_base:.1f},{y:.1f} H{tip:.1f} Q{x_end:.1f},{y:.1f} {x_end:.1f},{y + r:.1f} '
            f'V{y + h - r:.1f} Q{x_end:.1f},{y + h:.1f} {tip:.1f},{y + h:.1f} H{x_base:.1f} Z" fill="{color}"/>')


def _legend(names: Sequence[str], colors: Sequence[str]) -> str:
    keys = "".join(f'<span class="key"><i style="background:{c}"></i>{esc(n)}</span>' for n, c in zip(names, colors))
    return f'<div class="legend">{keys}</div>'


def bar_chart(categories: Sequence[str], values: Sequence[float], *, title: str | None = None,
              caption: str | None = None, fmt: Callable[[float], str] = fmt_num,
              errors: Sequence[tuple[float, float]] | None = None,
              colors: Sequence[str] | None = None, labels: Sequence[str] | None = None) -> str:
    """横向条形图：中文类目标签横排更易读。值从 0 开始，误差线可选。

    colors: 每根条的 CSS 颜色，默认 var(--series-1)；对照组建议用 var(--neutral)
    labels: 自定义条末端文字（例如“9 人 · 75.0%”），默认 fmt(value)
    """
    values = [_num(v) for v in values]
    present = [v for v in values if v is not None]
    if not present:
        return _no_data(title, caption)
    width, label_w, value_w, row_h, bar_h, top, bottom = 720, 150, 132, 42, 20, 6, 26
    x0, x1 = label_w, width - value_w
    height = top + row_h * len(values) + bottom
    highs = [e[1] for e in errors] if errors else []
    d1 = nice_ticks(0, max(present + highs), 4)[-1] or 1

    def sx(v: float | None) -> float:
        return x0 + max(v or 0, 0) / d1 * (x1 - x0)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title or "条形图")}">']
    axis_y = top + row_h * len(values)
    for t in nice_ticks(0, d1, 4):
        x = sx(t)
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{axis_y}" class="grid"/>')
        parts.append(f'<text x="{x:.1f}" y="{axis_y + 18}" class="tick" text-anchor="middle">{esc(fmt(t))}</text>')
    parts.append(f'<line x1="{x0}" y1="{top}" x2="{x0}" y2="{axis_y}" class="zero"/>')

    for i, (name, value) in enumerate(zip(categories, values)):
        cy = top + row_h * i + row_h / 2
        color = colors[i] if colors else "var(--series-1)"
        text = labels[i] if labels else ("—" if value is None else fmt(value))
        label_x = sx(value) + 8
        parts.append(f'<g class="row"><title>{esc(f"{name}：{text}")}</title>')
        parts.append(f'<rect x="0" y="{cy - row_h / 2:.1f}" width="{width}" height="{row_h}" class="hit"/>')
        parts.append(f'<text x="{label_w - 14}" y="{cy:.1f}" class="label" text-anchor="end" dominant-baseline="middle">{esc(name)}</text>')
        parts.append(_hbar(x0, sx(value), cy - bar_h / 2, bar_h, color))
        if errors:
            lo, hi = errors[i]
            parts.append(
                f'<path d="M{sx(lo):.1f},{cy - 5:.1f} V{cy + 5:.1f} M{sx(lo):.1f},{cy:.1f} H{sx(hi):.1f} '
                f'M{sx(hi):.1f},{cy - 5:.1f} V{cy + 5:.1f}" class="whisker"/>'
            )
            label_x = max(label_x, sx(hi) + 8)
        parts.append(f'<text x="{label_x:.1f}" y="{cy:.1f}" class="value" dominant-baseline="middle">{esc(text)}</text>')
        parts.append("</g>")
    parts.append("</svg>")
    return _figure("".join(parts), title, caption)


def paired_bar_chart(categories: Sequence[str], current: Sequence[float], baseline: Sequence[float], *,
                     names: tuple[str, str] = ("本期", "上期"), title: str | None = None,
                     caption: str | None = None, fmt: Callable[[float], str] = fmt_num) -> str:
    """成对横向条形图：每个类目一根本期条（主色）+ 一根对比期条（中性灰），适合两期漏斗对比。"""
    current, baseline = [_num(v) for v in current], [_num(v) for v in baseline]
    present = [v for v in current + baseline if v is not None]
    if not present:
        return _no_data(title, caption)
    width, label_w, value_w, row_h, bar_h, gap, top, bottom = 720, 150, 96, 50, 14, 2, 6, 26
    x0, x1 = label_w, width - value_w
    height = top + row_h * len(categories) + bottom
    d1 = nice_ticks(0, max(present), 4)[-1] or 1
    colors = ("var(--series-1)", "var(--neutral)")

    def sx(v: float | None) -> float:
        return x0 + max(v or 0, 0) / d1 * (x1 - x0)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title or "对比条形图")}">']
    axis_y = top + row_h * len(categories)
    for t in nice_ticks(0, d1, 4):
        x = sx(t)
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{axis_y}" class="grid"/>')
        parts.append(f'<text x="{x:.1f}" y="{axis_y + 18}" class="tick" text-anchor="middle">{esc(fmt(t))}</text>')
    parts.append(f'<line x1="{x0}" y1="{top}" x2="{x0}" y2="{axis_y}" class="zero"/>')

    for i, name in enumerate(categories):
        cy = top + row_h * i + row_h / 2
        a, b = current[i], baseline[i]
        shown = lambda v: "—" if v is None else fmt(v)  # noqa: E731
        tip = f"{name}：{names[0]} {shown(a)}，{names[1]} {shown(b)}"
        parts.append(f'<g class="row"><title>{esc(tip)}</title>')
        parts.append(f'<rect x="0" y="{cy - row_h / 2:.1f}" width="{width}" height="{row_h}" class="hit"/>')
        parts.append(f'<text x="{label_w - 14}" y="{cy:.1f}" class="label" text-anchor="end" dominant-baseline="middle">{esc(name)}</text>')
        for k, (value, y) in enumerate(((a, cy - gap / 2 - bar_h), (b, cy + gap / 2))):
            parts.append(_hbar(x0, sx(value), y, bar_h, colors[k]))
            cls = "value" if k == 0 else "sub"
            parts.append(f'<text x="{sx(value) + 8:.1f}" y="{y + bar_h / 2:.1f}" class="{cls}" dominant-baseline="middle">{esc(shown(value))}</text>')
        parts.append("</g>")
    parts.append("</svg>")
    return _figure("".join(parts), title, caption, _legend(names, colors))


def diverging_bar_chart(categories: Sequence[str], values: Sequence[float], *, title: str | None = None,
                        caption: str | None = None, fmt: Callable[[float], str] = fmt_signed,
                        tones: Sequence[str] | None = None) -> str:
    """正负条形图：从零线向两侧画，适合贡献拆解、同比变化分解。

    tones: 每根条的颜色语义 good / bad / neutral；默认正值 series-1、负值 series-4
    """
    keep = [i for i, v in enumerate(values) if _num(v) is not None]
    if not keep:
        return _no_data(title, caption)
    categories, values = [categories[i] for i in keep], [_num(values[i]) for i in keep]
    tones = [tones[i] for i in keep] if tones else None
    width, label_w, value_w, row_h, bar_h, top, bottom = 720, 176, 24, 40, 18, 6, 26
    x0, x1 = label_w, width - value_w
    height = top + row_h * len(values) + bottom
    lo, hi = min(list(values) + [0.0]), max(list(values) + [0.0])
    span = (hi - lo) or 1.0
    ticks = nice_ticks(lo - span * 0.18 if lo < 0 else 0, hi + span * 0.18 if hi > 0 else 0, 5)
    d0, d1 = ticks[0], ticks[-1]

    def sx(v: float) -> float:
        return x0 + (v - d0) / (d1 - d0) * (x1 - x0)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title or "正负条形图")}">']
    axis_y = top + row_h * len(values)
    for t in ticks:
        x = sx(t)
        parts.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{axis_y}" class="grid"/>')
        parts.append(f'<text x="{x:.1f}" y="{axis_y + 18}" class="tick" text-anchor="middle">{esc(fmt(t))}</text>')
    zx = sx(0)
    for i, (name, value) in enumerate(zip(categories, values)):
        cy = top + row_h * i + row_h / 2
        if tones:
            color = _tone_var(tones[i])
        else:
            color = "var(--series-1)" if value >= 0 else "var(--series-4)"
        parts.append(f'<g class="row"><title>{esc(f"{name}：{fmt(value)}")}</title>')
        parts.append(f'<rect x="0" y="{cy - row_h / 2:.1f}" width="{width}" height="{row_h}" class="hit"/>')
        parts.append(f'<text x="0" y="{cy:.1f}" class="label" dominant-baseline="middle">{esc(name)}</text>')
        parts.append(_hbar(zx, sx(value), cy - bar_h / 2, bar_h, color))
        if value >= 0:
            parts.append(f'<text x="{sx(value) + 8:.1f}" y="{cy:.1f}" class="value" dominant-baseline="middle">{esc(fmt(value))}</text>')
        else:
            parts.append(f'<text x="{sx(value) - 8:.1f}" y="{cy:.1f}" class="value" text-anchor="end" dominant-baseline="middle">{esc(fmt(value))}</text>')
        parts.append("</g>")
    parts.append(f'<line x1="{zx:.1f}" y1="{top}" x2="{zx:.1f}" y2="{axis_y}" class="zero"/>')
    parts.append("</svg>")
    return _figure("".join(parts), title, caption)


def heatmap_table(row_labels: Sequence[str], col_labels: Sequence[str], values: Sequence[Sequence[float | None]], *,
                  row_notes: Sequence[str] | None = None, note_header: str = "", corner: str = "",
                  title: str | None = None, caption: str | None = None,
                  fmt: Callable[[float], str] = lambda v: fmt_pct(v, 1), scale: str = "column") -> str:
    """热力表（留存矩阵、Cohort 表）：单色墨蓝深浅，None 表示尚未观察到（不是 0）。

    scale="column"：颜色在同一列内比较（留存矩阵默认如此，否则颜色只反映“越往后越低”这一常识）
    scale="global"：全表统一色阶
    """
    def bounds(cells: list[float]) -> tuple[float, float]:
        return (min(cells), max(cells)) if cells else (0.0, 1.0)

    values = [[_num(v) for v in row] for row in values]
    columns = [[row[j] for row in values if row[j] is not None] for j in range(len(col_labels))]
    everything = [v for col in columns for v in col]
    head = f'<th>{esc(corner)}</th>' + (f'<th class="num">{esc(note_header)}</th>' if row_notes else "")
    head += "".join(f'<th class="num">{esc(c)}</th>' for c in col_labels)
    body = []
    for i, label in enumerate(row_labels):
        cells = [f'<th scope="row">{esc(label)}</th>']
        if row_notes:
            cells.append(f'<td class="num muted">{esc(row_notes[i])}</td>')
        for j, value in enumerate(values[i]):
            if value is None:
                cells.append('<td class="num hm-na" title="尚未观察到">·</td>')
                continue
            lo, hi = bounds(columns[j] if scale == "column" else everything)
            t = 0.5 if hi == lo else (value - lo) / (hi - lo)
            pct = round(8 + t * 72)
            cls = "num hm hm-strong" if pct >= 52 else "num hm"
            tip = f"{label} · {col_labels[j]}：{fmt(value)}"
            cells.append(f'<td class="{cls}" style="--hm:{pct}%" title="{esc(tip)}">{esc(fmt(value))}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    table_html = (f'<div class="table-wrap"><table class="heatmap"><thead><tr>{head}</tr></thead>'
                  f'<tbody>{"".join(body)}</tbody></table></div>')
    return _figure(table_html, title, caption)


def line_chart(x_labels: Sequence[str], series: Sequence[dict], *, title: str | None = None,
               caption: str | None = None, fmt: Callable[[float], str] = fmt_num,
               y_zero: bool = True, reference: float | None = None) -> str:
    """折线图：series = [{"name", "values", "color"?}]。两条及以上自动带图例。

    reference: 可选的参考线（例如相对提升图里的 0 线）
    """
    series = [{**s, "values": [_num(v) for v in s["values"]]} for s in series]
    if not any(v is not None for s in series for v in s["values"]):
        return _no_data(title, caption)
    width, height = 720, 280
    left, right, top, bottom = 60, 136, 16, 34
    x0, x1, y0, y1 = left, width - right, height - bottom, top
    all_values = [v for s in series for v in s["values"] if v is not None]
    if reference is not None:
        all_values.append(reference)
    lo = min(all_values + ([0] if y_zero else []))
    hi = max(all_values)
    ticks = nice_ticks(lo, hi, 5)
    d0, d1 = ticks[0], ticks[-1]
    n = len(x_labels)

    def sx(i: int) -> float:
        return x0 + (x1 - x0) * (i / (n - 1) if n > 1 else 0.5)

    def sy(v: float) -> float:
        return y0 - (v - d0) / (d1 - d0) * (y0 - y1)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title or "折线图")}">']
    for t in ticks:
        y = sy(t)
        parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{x0 - 10}" y="{y:.1f}" class="tick" text-anchor="end" dominant-baseline="middle">{esc(fmt(t))}</text>')
    if reference is not None:
        parts.append(f'<line x1="{x0}" y1="{sy(reference):.1f}" x2="{x1}" y2="{sy(reference):.1f}" class="zero"/>')
    step = max(1, math.ceil(n / 8))
    for i in range(0, n, step):
        parts.append(f'<text x="{sx(i):.1f}" y="{y0 + 22}" class="tick" text-anchor="middle">{esc(x_labels[i])}</text>')

    colors = [s.get("color") or f"var(--series-{k % 7 + 1})" for k, s in enumerate(series)]
    for s, color in zip(series, colors):
        points = [(sx(i), sy(v)) for i, v in enumerate(s["values"]) if v is not None]
        d = " ".join(f"{'M' if k == 0 else 'L'}{x:.1f},{y:.1f}" for k, (x, y) in enumerate(points))
        parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        if points:
            parts.append(f'<circle cx="{points[-1][0]:.1f}" cy="{points[-1][1]:.1f}" r="4" fill="{color}" class="ring"/>')

    # 末端直接标签：互相挤在一起时放弃，交给图例和悬停提示，而不是把标签推离线条
    ends = sorted(
        ((sy(s["values"][-1]), s["name"], s["values"][-1]) for s in series if s["values"] and s["values"][-1] is not None)
    )
    if all(b[0] - a[0] >= 16 for a, b in zip(ends, ends[1:])):
        for y, name, value in ends:
            tag = f'<tspan class="sub" dx="6">{esc(name)}</tspan>' if len(series) > 1 else ""
            parts.append(f'<text x="{x1 + 10}" y="{y:.1f}" class="value" dominant-baseline="middle">{esc(fmt(value))}{tag}</text>')

    band = (x1 - x0) / max(n - 1, 1)
    for i, label in enumerate(x_labels):
        lines = [label] + [f"{s['name']}：{fmt(s['values'][i])}" for s in series if s["values"][i] is not None]
        x = sx(i) - band / 2
        parts.append(f'<rect x="{x:.1f}" y="{y1}" width="{band:.1f}" height="{y0 - y1}" class="hit col"><title>{esc(chr(10).join(lines))}</title></rect>')
    parts.append("</svg>")

    legend = _legend([s["name"] for s in series], colors) if len(series) > 1 else ""
    return _figure("".join(parts), title, caption, legend)


# ---------------------------------------------------------------------------
# 版面组件
# ---------------------------------------------------------------------------

def stat_tiles(tiles: Iterable[dict]) -> str:
    """指标卡：[{"label", "value", "delta"?, "tone"?, "note"?}]。delta 文本需自带符号。"""
    cells = []
    for tile in tiles:
        tone = tile.get("tone", "neutral")
        delta = ""
        if tile.get("delta"):
            delta = f'<div class="delta tone-{tone}">{esc(tile["delta"])}</div>'
        note = f'<div class="tile-note">{esc(tile["note"])}</div>' if tile.get("note") else ""
        cells.append(
            f'<div class="tile"><div class="tile-label">{esc(tile["label"])}</div>'
            f'<div class="tile-value">{esc(tile["value"])}</div>{delta}{note}</div>'
        )
    return f'<div class="tiles">{"".join(cells)}</div>'


def callout(level: str, title: str, body: str = "", *, raw_body: bool = False) -> str:
    """结论横幅。level: good / warning / bad / info。图标 + 文字，颜色不单独承载含义。"""
    level = level if level in ("good", "warning", "bad", "info") else "info"
    content = body if raw_body else esc(body)
    return (
        f'<div class="callout callout-{level}"><span class="icon" aria-hidden="true">{ICONS[level]}</span>'
        f'<div><div class="callout-title">{esc(title)}</div><div class="callout-body">{content}</div></div></div>'
    )


def checklist(items: Iterable[dict]) -> str:
    """检查清单：[{"status": pass|warn|fail|info, "title", "detail"?}]"""
    label = {"pass": "通过", "warn": "注意", "fail": "不通过", "info": "说明"}
    rows = []
    for item in items:
        status = item.get("status", "info")
        detail = f'<div class="check-detail">{esc(item["detail"])}</div>' if item.get("detail") else ""
        rows.append(
            f'<li class="check check-{status}"><span class="badge">{ICONS.get(status, "i")} {label.get(status, "说明")}</span>'
            f'<div><div class="check-title">{esc(item["title"])}</div>{detail}</div></li>'
        )
    return f'<ul class="checklist">{"".join(rows)}</ul>'


def table(headers: Sequence[str], rows: Sequence[Sequence[str]], *, numeric: Sequence[int] = ()) -> str:
    """表格视图：每张图都应有一个能读出全部数值的表格。numeric 为右对齐的列序号。"""
    head = "".join(f'<th class="{"num" if i in numeric else ""}">{esc(h)}</th>' for i, h in enumerate(headers))
    body = "".join(
        "<tr>" + "".join(f'<td class="{"num" if i in numeric else ""}">{esc(str(c))}</td>' for i, c in enumerate(r)) + "</tr>"
        for r in rows
    )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def paragraph(text: str) -> str:
    return f'<p class="prose">{esc(text)}</p>'


def section(title: str, *blocks: str, lead: str | None = None) -> str:
    lead_html = f'<p class="lead">{esc(lead)}</p>' if lead else ""
    return f'<section><h2>{esc(title)}</h2>{lead_html}{"".join(blocks)}</section>'


# ---------------------------------------------------------------------------
# 页面
# ---------------------------------------------------------------------------

def _tokens(theme: dict) -> str:
    series = "".join(f"--series-{i + 1}:{c};" for i, c in enumerate(theme["series"]))
    good, warning, bad = theme["status_marks"]
    return (
        f"--page:{theme['page']};--surface:{theme['surface']};--ink:{theme['ink']};--ink-2:{theme['ink_2']};"
        f"--muted:{theme['muted']};--grid:{theme['grid']};--axis:{theme['axis']};--border:{theme['border']};"
        f"--accent:{theme['accent']};--accent-text:{theme['accent_text']};--wash:{theme['wash']};{series}"
        f"--good:{good};--warning:{warning};--bad:{bad};--neutral:{theme['muted']};"
        f"--good-text:{theme['good_text']};--warning-text:{theme['warning_text']};--bad-text:{theme['bad_text']};"
    )


CSS = """
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font-family:%(font)s;font-size:15px;line-height:1.65;-webkit-font-smoothing:antialiased}
.page{max-width:880px;margin:0 auto;padding:40px 16px 64px}
header.top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:28px}
.brand{display:flex;align-items:center;gap:8px;color:var(--accent-text);font-size:13px;letter-spacing:.08em}
.brand::before{content:"";width:18px;height:2px;background:var(--accent);border-radius:2px}
h1{font-size:28px;line-height:1.3;margin:10px 0 6px;font-weight:650;letter-spacing:-.01em}
.subtitle{color:var(--ink-2);margin:0}
.meta{color:var(--muted);font-size:12px;margin-top:8px}
.theme-toggle{flex:none;border:1px solid var(--border);background:var(--surface);color:var(--ink-2);border-radius:999px;padding:6px 12px;font:inherit;font-size:12px;cursor:pointer}
.theme-toggle:hover{color:var(--ink)}
section{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:22px 24px;margin:16px 0}
h2{font-size:17px;margin:0 0 12px;font-weight:650}
.lead{color:var(--ink-2);margin:-6px 0 14px}
.prose{margin:8px 0;color:var(--ink)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:4px 0 8px}
.tile{border:1px solid var(--border);border-radius:12px;padding:14px 16px;background:var(--page)}
.tile-label{color:var(--ink-2);font-size:13px}
.tile-value{font-size:28px;font-weight:650;line-height:1.25;margin-top:4px}
.delta{font-size:13px;font-weight:600;margin-top:2px}
.tile-note{color:var(--muted);font-size:12px;margin-top:4px}
.tone-good{color:var(--good-text)}.tone-bad{color:var(--bad-text)}.tone-warning{color:var(--warning-text)}.tone-neutral{color:var(--ink-2)}
.callout{display:flex;gap:14px;align-items:flex-start;border-radius:14px;padding:18px 20px;margin:16px 0;border:1px solid var(--border);background:var(--surface)}
.callout .icon{flex:none;width:28px;height:28px;border-radius:50%%;display:grid;place-items:center;font-weight:700;font-size:15px;color:#fff}
.callout-good .icon{background:var(--good)}.callout-warning .icon{background:var(--warning);color:#2b2822}.callout-bad .icon{background:var(--bad)}.callout-info .icon{background:var(--accent);color:#2b2822}
.callout-good{box-shadow:inset 4px 0 0 var(--good)}.callout-warning{box-shadow:inset 4px 0 0 var(--warning)}.callout-bad{box-shadow:inset 4px 0 0 var(--bad)}.callout-info{box-shadow:inset 4px 0 0 var(--accent)}
.callout-title{font-size:18px;font-weight:650;line-height:1.4}
.callout-body{color:var(--ink-2);margin-top:4px}
.checklist{list-style:none;margin:0;padding:0}
.check{display:flex;gap:12px;padding:10px 0;border-top:1px solid var(--grid)}
.check:first-child{border-top:0}
.badge{flex:none;font-size:12px;font-weight:600;border-radius:6px;padding:2px 8px;height:fit-content;white-space:nowrap;border:1px solid currentColor}
.check-pass .badge{color:var(--good-text)}.check-warn .badge{color:var(--warning-text)}.check-fail .badge{color:var(--bad-text)}.check-info .badge{color:var(--ink-2)}
.check-title{font-weight:600}
.check-detail{color:var(--ink-2);font-size:14px}
figure.chart{margin:8px 0 16px;overflow-x:auto}
.fig-title{font-weight:600;margin-bottom:6px}
.fig-note{color:var(--muted);font-size:12px;margin:4px 0 0}
figure svg{display:block;width:100%%;min-width:540px;height:auto;overflow:visible}
svg text{font-family:%(font)s;fill:var(--ink)}
svg .tick{fill:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}
svg .label{font-size:14px}
svg .sub{fill:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}
svg .value{font-size:14px;font-weight:600;font-variant-numeric:tabular-nums}
svg .grid{stroke:var(--grid);stroke-width:1}
svg .zero{stroke:var(--axis);stroke-width:1.5}
svg .ring{stroke:var(--surface);stroke-width:2}
svg .whisker{stroke:var(--ink-2);stroke-width:1.5;fill:none;stroke-linecap:round}
svg .hit{fill:transparent}
svg .row:hover .hit{fill:var(--wash)}
svg .col:hover{fill:var(--wash)}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--ink-2);margin-bottom:6px}
.legend .key{display:inline-flex;align-items:center;gap:6px}
.legend i{width:14px;height:3px;border-radius:2px;display:inline-block}
.table-wrap{overflow-x:auto;margin:8px 0}
table{border-collapse:collapse;width:100%%;font-size:14px}
th,td{padding:8px 10px;border-bottom:1px solid var(--grid);text-align:left;white-space:nowrap}
th{color:var(--ink-2);font-weight:600;font-size:13px}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
footer{color:var(--muted);font-size:12px;margin-top:24px;text-align:center}
table.heatmap th[scope=row]{font-weight:500;color:var(--ink);font-variant-numeric:tabular-nums}
table.heatmap td.hm{background:color-mix(in oklab,var(--series-1) var(--hm),var(--surface));border-bottom:2px solid var(--surface)}
table.heatmap td.hm-strong{color:#fff;font-weight:600}
table.heatmap td.hm-na{color:var(--muted);background:repeating-linear-gradient(135deg,transparent 0 4px,var(--grid) 4px 5px)}
table.heatmap td.muted{color:var(--ink-2)}
table.heatmap td,table.heatmap th{padding:7px 10px}
@media (max-width:560px){section{padding:18px 16px}h1{font-size:23px}.tile-value{font-size:24px}}
@media print{.theme-toggle{display:none}body{background:#fff}}
""" % {"font": FONT_STACK}

THEME_SCRIPT = """
(function(){var k='sskit-theme',r=document.documentElement,s=null;
try{s=localStorage.getItem(k)}catch(e){}if(s)r.setAttribute('data-theme',s);
var b=document.querySelector('.theme-toggle');if(!b)return;
b.addEventListener('click',function(){var cur=r.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
var next=cur==='dark'?'light':'dark';r.setAttribute('data-theme',next);try{localStorage.setItem(k,next)}catch(e){}});})();
"""


def html_report(title: str, body_blocks: Sequence[str], *, subtitle: str | None = None,
                meta: str | None = None, brand: str = "拾穗数据 · 数据报告", extra_css: str = "") -> str:
    """把版面组件拼成一个自包含 HTML 文件（无外部依赖，可离线打开、可直接发送）。

    extra_css: 调用方追加的样式，只能引用上面定义的 CSS 变量，不要写死颜色
    """
    light, dark = _tokens(THEMES["light"]), _tokens(THEMES["dark"])
    stamp = meta or f"生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    sub = f'<p class="subtitle">{esc(subtitle)}</p>' if subtitle else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
:root{{color-scheme:light;{light}}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{color-scheme:dark;{dark}}}}}
:root[data-theme="dark"]{{color-scheme:dark;{dark}}}
{CSS}{extra_css}
</style>
</head>
<body>
<main class="page">
<header class="top"><div><div class="brand">{esc(brand)}</div><h1>{esc(title)}</h1>{sub}<div class="meta">{esc(stamp)}</div></div>
<button class="theme-toggle" type="button" aria-label="切换深浅色">◐ 深浅色</button></header>
{"".join(body_blocks)}
<footer>由拾穗数据技能库生成 · sskit_viz {__version__}</footer>
</main>
<script>{THEME_SCRIPT}</script>
</body>
</html>
"""


def save(path: str, content: str) -> str:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path
