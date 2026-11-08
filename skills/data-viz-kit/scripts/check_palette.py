#!/usr/bin/env python3
"""拾穗图表配色校验器（仅依赖 Python 标准库）。

配色是可以计算的，所以不要靠肉眼判断。这个脚本检查：

1. 明度带：OKLCH L 落在当前模式的可读区间内
2. 彩度下限：OKLCH C 不低于下限，否则读起来像灰色
3. 色觉障碍区分度：模拟红色盲 / 绿色盲后，相邻色的 OKLab ΔE(×100)
4. 正常视觉区分度：未模拟时相邻色的 OKLab ΔE(×100)
5. 对比度：每个颜色相对图表底色的 WCAG 对比度

用法：
  python3 check_palette.py                      # 校验 sskit_viz.py 内置的拾穗配色（亮/暗两套）
  python3 check_palette.py "#2f6bb3,#c99a3d" --mode light --surface "#fdfbf7"
  python3 check_palette.py "#..." --pairs all    # 散点、地图等所有颜色两两相邻的图形

退出码：任何 FAIL 返回 1；WARN 不影响退出码，但要求图表提供直接标签或表格视图。
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

BAND = {"light": (0.43, 0.78), "dark": (0.48, 0.80)}
CHROMA_FLOOR = 0.08
CVD_TARGET = 8.0
CVD_FLOOR = 6.0
NORMAL_FLOOR = 15.0
CONTRAST_TARGET = 3.0
CONTRAST_FLOOR = 2.0

# Machado, Oliveira & Fernandes (2009)，严重度 1.0，作用于线性 sRGB
CVD_MATRICES = {
    "protan": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deutan": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
}


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError(f"无法解析颜色：#{value}")
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))


def to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def linear_rgb(value: str) -> tuple[float, float, float]:
    return tuple(to_linear(c) for c in hex_to_rgb(value))


def oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = rgb
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (max(x, 0.0) ** (1 / 3) for x in (l, m, s))
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def simulate(rgb: tuple[float, float, float], kind: str) -> tuple[float, float, float]:
    matrix = CVD_MATRICES[kind]
    return tuple(min(max(sum(row[i] * rgb[i] for i in range(3)), 0.0), 1.0) for row in matrix)


def delta_e(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return 100 * sum((x - y) ** 2 for x, y in zip(oklab(a), oklab(b))) ** 0.5


def luminance(value: str) -> float:
    r, g, b = linear_rgb(value)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    hi, lo = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def validate(colors: list[str], mode: str, surface: str, pairs: str = "adjacent") -> dict:
    rows = []
    failures = []
    warnings = []
    low, high = BAND[mode]

    for index, color in enumerate(colors, start=1):
        L, a, b = oklab(linear_rgb(color))
        chroma = (a * a + b * b) ** 0.5
        ratio = contrast(color, surface)
        row = {"slot": index, "color": color, "L": round(L, 3), "C": round(chroma, 3), "contrast": round(ratio, 2)}
        rows.append(row)
        if not low <= L <= high:
            failures.append(f"slot {index} {color} 明度 L={L:.3f} 不在 {mode} 区间 [{low}, {high}]")
        if chroma < CHROMA_FLOOR:
            failures.append(f"slot {index} {color} 彩度 C={chroma:.3f} 低于 {CHROMA_FLOOR}，会读成灰色")
        if ratio < CONTRAST_FLOOR:
            failures.append(f"slot {index} {color} 对比度 {ratio:.2f} 低于 {CONTRAST_FLOOR}")
        elif ratio < CONTRAST_TARGET:
            warnings.append(f"slot {index} {color} 对比度 {ratio:.2f} 低于 {CONTRAST_TARGET}：必须配直接标签或表格视图")

    if pairs == "all":
        pair_list = list(itertools.combinations(range(len(colors)), 2))
    else:
        pair_list = [(i, i + 1) for i in range(len(colors) - 1)]

    pair_rows = []
    for i, j in pair_list:
        a, b = linear_rgb(colors[i]), linear_rgb(colors[j])
        normal = delta_e(a, b)
        cvd = min(delta_e(simulate(a, kind), simulate(b, kind)) for kind in CVD_MATRICES)
        pair_rows.append({"pair": f"{i + 1}-{j + 1}", "normal": round(normal, 1), "cvd": round(cvd, 1)})
        if normal < NORMAL_FLOOR:
            failures.append(f"slot {i + 1}/{j + 1} 正常视觉 ΔE={normal:.1f} 低于 {NORMAL_FLOOR}")
        if cvd < CVD_FLOOR:
            failures.append(f"slot {i + 1}/{j + 1} 色觉障碍 ΔE={cvd:.1f} 低于 {CVD_FLOOR}")
        elif cvd < CVD_TARGET:
            warnings.append(f"slot {i + 1}/{j + 1} 色觉障碍 ΔE={cvd:.1f} 低于 {CVD_TARGET}：必须配图例 + 直接标签")

    return {
        "mode": mode,
        "surface": surface,
        "pairs": pairs,
        "colors": rows,
        "pair_checks": pair_rows,
        "failures": failures,
        "warnings": warnings,
        "passed": not failures,
    }


def print_report(report: dict) -> None:
    print(f"\n[{report['mode']}] surface={report['surface']} pairs={report['pairs']}")
    for row in report["colors"]:
        print(f"  slot {row['slot']}  {row['color']}  L={row['L']:.3f}  C={row['C']:.3f}  contrast={row['contrast']:.2f}")
    for row in report["pair_checks"]:
        print(f"  pair {row['pair']:>5}  normal ΔE={row['normal']:>5.1f}  cvd ΔE={row['cvd']:>5.1f}")
    for message in report["warnings"]:
        print(f"  WARN  {message}")
    for message in report["failures"]:
        print(f"  FAIL  {message}")
    print("  RESULT: " + ("PASS" if report["passed"] else "FAIL"))


def builtin_reports(pairs: str) -> list[dict]:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from sskit_viz import THEMES  # noqa: E402

    reports = []
    for mode, theme in THEMES.items():
        reports.append(validate(theme["series"], mode, theme["surface"], pairs))
        reports.append(validate(theme["series"][:3], mode, theme["surface"], "all"))  # 散点 / 地图的 3 色上限
        reports.append(validate(theme["status_marks"], mode, theme["surface"], "all"))
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description="校验图表配色是否可读、可区分、色觉障碍友好")
    parser.add_argument("colors", nargs="?", help="逗号分隔的 hex 颜色；省略时校验内置拾穗配色")
    parser.add_argument("--mode", choices=["light", "dark"], default="light")
    parser.add_argument("--surface", help="图表底色，默认取内置主题")
    parser.add_argument("--pairs", choices=["adjacent", "all"], default="adjacent")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    if args.colors:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from sskit_viz import THEMES  # noqa: E402

        surface = args.surface or THEMES[args.mode]["surface"]
        colors = [c if c.startswith("#") else f"#{c}" for c in args.colors.split(",") if c.strip()]
        reports = [validate(colors, args.mode, surface, args.pairs)]
    else:
        reports = builtin_reports(args.pairs)

    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    else:
        for report in reports:
            print_report(report)

    return 0 if all(r["passed"] for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
