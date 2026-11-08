#!/usr/bin/env python3
"""拾穗脚本共用的输入工具：编码识别、CSV / xlsx 读取、时间解析、取值解析、CLI 友好报错（仅依赖 Python 标准库）。

唯一源文件是 skills/data-viz-kit/scripts/sskit_io.py。其他 Skill 保存副本，让单个 Skill 目录复制出去也能运行，
修改后要同步到这些副本。
"""

from __future__ import annotations

import codecs
import csv
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterator

_CHUNK = 1 << 20
_NULL_TEXT = {"", "null", "none", "nan", "n/a", "na", "\\n", "#n/a"}
_TRUE = {"1", "1.0", "true", "t", "yes", "y", "是", "对"}
_FALSE = {"0", "0.0", "false", "f", "no", "n", "否", "错"}


# ---------------------------------------------------------------------------
# 编码与 CSV
# ---------------------------------------------------------------------------

def _decodes(path: str, encoding: str) -> bool:
    decoder = codecs.getincrementaldecoder(encoding)()
    try:
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(_CHUNK)
                if not chunk:
                    decoder.decode(b"", final=True)
                    return True
                decoder.decode(chunk)
    except UnicodeDecodeError:
        return False


def detect_encoding(path: str) -> str:
    """按 BOM、UTF-8、GB18030 的顺序识别，只扫描不载入内存。GB18030 兼容 GBK 和 GB2312。"""
    with open(path, "rb") as handle:
        head = handle.read(4)
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if _decodes(path, "utf-8"):
        return "utf-8-sig"
    if _decodes(path, "gb18030"):
        return "gb18030"
    raise SystemExit(f"{path} 既不是 UTF-8 也不是 GBK/GB18030，请先转成 UTF-8 再运行")


def encoding_label(encoding: str) -> str:
    return {"utf-8-sig": "UTF-8", "gb18030": "GBK/GB18030", "utf-16": "UTF-16"}.get(encoding, encoding)


def guess_delimiter(first_line: str) -> str:
    return max(",\t;|", key=first_line.count) if first_line.strip() else ","


@contextmanager
def open_csv(path: str) -> Iterator[csv.DictReader]:
    """打开 CSV / TSV：自动识别编码和分隔符，去掉表头两端空白，逐行读取。"""
    encoding = detect_encoding(path)
    with open(path, encoding=encoding, newline="") as handle:
        first = handle.readline()
        handle.seek(0)
        reader = csv.DictReader(handle, delimiter=guess_delimiter(first))
        if not reader.fieldnames:
            raise SystemExit(f"{path} 是空文件")
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        yield reader


def read_csv(path: str) -> list[dict]:
    with open_csv(path) as reader:
        return list(reader)


# ---------------------------------------------------------------------------
# xlsx（标准库解析，不依赖 openpyxl）
# ---------------------------------------------------------------------------

_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_BUILTIN_DATE_IDS = set(range(14, 23)) | set(range(27, 37)) | {45, 46, 47} | set(range(50, 59))


def _column_index(ref: str) -> int:
    index = 0
    for ch in ref:
        if not ch.isalpha():
            break
        index = index * 26 + ord(ch.upper()) - 64
    return index - 1


def _shared_strings(book: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in book.namelist():
        return []
    out = []
    root = ET.fromstring(book.read("xl/sharedStrings.xml"))
    for item in root.findall(f"{_M}si"):
        # 忽略拼音注音 rPh，只拼接正文
        parts = [t.text or "" for t in item.findall(f"{_M}t")]
        parts += [t.text or "" for run in item.findall(f"{_M}r") for t in run.findall(f"{_M}t")]
        out.append("".join(parts))
    return out


def _date_styles(book: zipfile.ZipFile) -> set[int]:
    if "xl/styles.xml" not in book.namelist():
        return set()
    root = ET.fromstring(book.read("xl/styles.xml"))
    custom = set()
    formats = root.find(f"{_M}numFmts")
    if formats is not None:
        for fmt in formats.findall(f"{_M}numFmt"):
            code = re.sub(r'"[^"]*"|\\.|\[[^\]]*\]', "", fmt.get("formatCode", ""))
            if re.search(r"[ymdhs]", code, re.I):
                custom.add(int(fmt.get("numFmtId", "0")))
    styles = root.find(f"{_M}cellXfs")
    if styles is None:
        return set()
    return {i for i, xf in enumerate(styles.findall(f"{_M}xf"))
            if int(xf.get("numFmtId", "0")) in _BUILTIN_DATE_IDS | custom}


def _sheet_path(book: zipfile.ZipFile, sheet: str | None) -> tuple[str, str, bool]:
    workbook = ET.fromstring(book.read("xl/workbook.xml"))
    rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target", "") for rel in rels.findall(f"{_REL}Relationship")}
    sheets = workbook.find(f"{_M}sheets")
    entries = [(s.get("name", ""), s.get(f"{_R}id", "")) for s in (sheets if sheets is not None else [])]
    if not entries:
        raise SystemExit("xlsx 文件里没有工作表")
    chosen = next((e for e in entries if e[0] == sheet), None) if sheet else entries[0]
    if chosen is None:
        raise SystemExit(f"找不到工作表 {sheet}（现有：{[e[0] for e in entries]}）")
    target = targets[chosen[1]].lstrip("/")
    props = workbook.find(f"{_M}workbookPr")
    uses_1904 = props is not None and props.get("date1904") in ("1", "true")
    return (target if target.startswith("xl/") else f"xl/{target}"), chosen[0], uses_1904


def _serial_to_text(value: float, uses_1904: bool) -> str:
    base = datetime(1904, 1, 1) if uses_1904 else datetime(1899, 12, 30)
    moment = base + timedelta(days=value)
    return moment.strftime("%Y-%m-%d") if value == int(value) else moment.strftime("%Y-%m-%d %H:%M:%S")


def read_xlsx(path: str, sheet: str | None = None) -> tuple[list[str], list[list[str]], str]:
    """读取一个工作表，返回表头、数据行（全部为字符串）和工作表名。"""
    try:
        book = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise SystemExit(f"{path} 不是有效的 xlsx 文件；.xls 旧格式请先另存为 .xlsx 或 CSV") from None
    with book:
        shared = _shared_strings(book)
        date_styles = _date_styles(book)
        target, sheet_name, uses_1904 = _sheet_path(book, sheet)
        rows: list[list[str]] = []
        with book.open(target) as stream:
            for _, element in ET.iterparse(stream, events=("end",)):
                if element.tag != f"{_M}row":
                    continue
                cells: dict[int, str] = {}
                position = 0
                for cell in element.findall(f"{_M}c"):
                    ref = cell.get("r")
                    column = _column_index(ref) if ref else position
                    position = column + 1
                    kind, raw = cell.get("t", "n"), cell.find(f"{_M}v")
                    text = raw.text if raw is not None and raw.text is not None else ""
                    if kind == "s" and text:
                        text = shared[int(text)]
                    elif kind == "inlineStr":
                        text = "".join(t.text or "" for t in cell.iter(f"{_M}t"))
                    elif kind == "b":
                        text = "TRUE" if text == "1" else "FALSE"
                    elif kind == "n" and text and int(cell.get("s", "0")) in date_styles:
                        text = _serial_to_text(float(text), uses_1904)
                    cells[column] = text
                width = max(cells) + 1 if cells else 0
                rows.append([cells.get(i, "") for i in range(width)])
                element.clear()
    rows = [r for r in rows if any(v.strip() for v in r)]
    if not rows:
        raise SystemExit(f"{path} 的工作表 {sheet_name} 是空的")
    header = [h.strip() for h in rows[0]]
    return header, [(r + [""] * len(header))[: max(len(header), len(r))] for r in rows[1:]], sheet_name


# ---------------------------------------------------------------------------
# 时间
# ---------------------------------------------------------------------------

_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S.%f", "%Y/%m/%d %H:%M", "%Y/%m/%d", "%Y%m%d", "%Y.%m.%d", "%Y年%m月%d日")
_OFFSET_RE = re.compile(r"^(.*\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)\s*(Z|UTC|[+-]\d{2}(?::?\d{2})?)$", re.I)
_LONG_FRACTION_RE = re.compile(r"(\.\d{6})\d+")


def parse_offset(text: str) -> timezone:
    value = text.strip().upper()
    if value in ("Z", "UTC"):
        return timezone.utc
    match = re.match(r"^([+-])(\d{2})(?::?(\d{2}))?$", value)
    if not match:
        raise SystemExit(f"时区格式应为 +08:00、-05:00 或 UTC，收到：{text}")
    sign = 1 if match.group(1) == "+" else -1
    return timezone(sign * timedelta(hours=int(match.group(2)), minutes=int(match.group(3) or 0)))


class TimeParser:
    """把各种时间写法解析成“业务时区下的无时区时间”。

    带时区的时间（Z、+08:00、Unix 时间戳）换算到业务时区；不带时区的时间视为已经是业务时区。
    分析脚本里所有时间因此都是无时区的，可以直接比较，自然日和批次也按业务时区划分。
    """

    def __init__(self, tz: str = "+08:00") -> None:
        self.configure(tz)

    def configure(self, tz: str) -> None:
        self.label = tz
        self.target = parse_offset(tz)
        self.aware = self.naive = self.blank = 0

    def _plain(self, value: str) -> datetime | None:
        value = _LONG_FRACTION_RE.sub(r"\1", value.replace("T", " "))
        for fmt in _FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None

    def try_parse(self, text: str | None) -> datetime | None:
        """解析失败返回 None。空值计入 blank。"""
        raw = (text or "").strip()
        if not raw:
            self.blank += 1
            return None
        if len(raw) == 19 and raw[4] == "-" and raw[7] == "-" and raw[10] in " T" and raw[13] == ":" and raw[16] == ":":
            try:
                value = datetime(int(raw[:4]), int(raw[5:7]), int(raw[8:10]), int(raw[11:13]), int(raw[14:16]), int(raw[17:19]))
                self.naive += 1
                return value
            except ValueError:
                pass
        if raw.isdigit() and len(raw) in (10, 13):
            seconds = int(raw) / (1000 if len(raw) == 13 else 1)
            self.aware += 1
            return datetime.fromtimestamp(seconds, timezone.utc).astimezone(self.target).replace(tzinfo=None)
        match = _OFFSET_RE.match(raw)
        if match:
            plain = self._plain(match.group(1).strip())
            if plain is None:
                return None
            self.aware += 1
            return plain.replace(tzinfo=parse_offset(match.group(2))).astimezone(self.target).replace(tzinfo=None)
        plain = self._plain(raw)
        if plain is not None:
            self.naive += 1
        return plain

    def __call__(self, text: str | None) -> datetime | None:
        """空值返回 None，由调用方跳过；非空但解析不了时退出并给出原值。"""
        raw = (text or "").strip()
        value = self.try_parse(raw)
        if value is None and raw:
            raise SystemExit(f"无法解析时间：{raw}（支持 YYYY-MM-DD HH:MM:SS、ISO 8601 带时区、YYYY/MM/DD、YYYYMMDD、Unix 时间戳）")
        return value

    def summary(self) -> dict:
        return {"timezone": self.label, "aware_converted": self.aware, "naive_assumed": self.naive, "blank": self.blank,
                "mixed": self.aware > 0 and self.naive > 0}

    def check(self) -> dict | None:
        """返回一条给报告用的质量检查；时间写法没有需要提醒的地方时返回 None。"""
        if self.aware and self.naive:
            return {"id": "timezone", "status": "warn", "title": f"同一份数据里既有带时区（{self.aware} 行）也有不带时区（{self.naive} 行）的时间",
                    "detail": f"带时区的已换算到 {self.label}，不带时区的按 {self.label} 处理。请确认后者确实是这个时区，否则按天和按批次的结果会错位"}
        if self.blank:
            return {"id": "blank_time", "status": "warn", "title": f"{self.blank} 行时间为空，已跳过", "detail": "空时间较多时先排查埋点或导出"}
        if self.aware:
            return {"id": "timezone", "status": "info", "title": f"{self.aware} 行带时区的时间已换算到 {self.label}",
                    "detail": "自然日和批次按这个时区划分；业务时区不同时用 --tz 指定"}
        return None


# ---------------------------------------------------------------------------
# 取值
# ---------------------------------------------------------------------------

def is_null(value: str | None) -> bool:
    return value is None or value.strip().lower() in _NULL_TEXT


def parse_flag(value: str | None, column: str = "") -> float | None:
    """解析 0/1 型取值，兼容 true/false、yes/no、Y/N、是/否、对/错。空值返回 None。"""
    if is_null(value):
        return None
    lowered = value.strip().lower()
    if lowered in _TRUE:
        return 1.0
    if lowered in _FALSE:
        return 0.0
    raise SystemExit(f"比例指标 {column} 只能是 0/1、true/false、yes/no、Y/N 或 是/否，收到：{value}")


def parse_number(value: str | None, column: str = "") -> float | None:
    """解析数值，兼容千分位和货币符号。空值返回 None，无法解析时退出并给出原值。"""
    if is_null(value):
        return None
    text = re.sub(r"[¥￥$,\s]", "", value)
    try:
        number = float(text)
    except ValueError:
        raise SystemExit(f"字段 {column} 有无法解析的数值：{value}") from None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_cli(main: Callable[[], int]) -> int:
    """把常见的输入错误转成一句话提示，避免把 traceback 留给使用者。"""
    try:
        return main()
    except FileNotFoundError as exc:
        raise SystemExit(f"找不到文件：{exc.filename}") from None
    except IsADirectoryError as exc:
        raise SystemExit(f"这是目录，不是文件：{exc.filename}") from None
    except PermissionError as exc:
        raise SystemExit(f"没有读取权限：{exc.filename}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON 格式错误（第 {exc.lineno} 行第 {exc.colno} 列）：{exc.msg}") from None
