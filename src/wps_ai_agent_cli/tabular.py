"""CSV/TSV <-> XLSX (P13-011).

Reading detects the encoding (BOM, UTF-8, then GB18030, which covers GBK) and the delimiter. Writing an XLSX keeps
every cell's text: numbers become numbers only when their displayed form comes back unchanged (``3.50`` gets the
``0.00`` format, ``007`` and long digit strings stay text).
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

from .conversion_paths import check_paths, missing_dependency

DELIMITED = {".csv", ".tsv", ".txt"}
_NUMBER = re.compile(r"-?(?:0|[1-9]\d{0,14})(?:\.(\d{1,10}))?")
_PERCENT = re.compile(r"(-?(?:0|[1-9]\d{0,12})(?:\.(\d{1,8}))?)%")
_THOUSANDS = re.compile(r"-?[1-9]\d{0,2}(?:,\d{3})+(?:\.(\d{1,10}))?")


def decode_text(data: bytes, encoding: str | None = None) -> tuple[str, str]:
    """The text and the encoding it was read with."""
    if encoding:
        return data.decode(encoding), encoding
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), "utf-8-sig"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16"), "utf-16"
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("gb18030"), "gb18030"


def sniff_delimiter(text: str, suffix: str = ".csv") -> str:
    if suffix == ".tsv":
        return "\t"
    sample = "\n".join(text.splitlines()[:50])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return "\t" if sample.count("\t") > sample.count(",") else ","


def read_delimited(
    path: str | Path, encoding: str | None = None, delimiter: str | None = None
) -> tuple[list[list[str]], dict[str, Any]]:
    path = Path(path)
    text, used = decode_text(path.read_bytes(), encoding)
    delimiter = delimiter or sniff_delimiter(text, path.suffix.casefold())
    rows = [row for row in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)]
    while rows and not any(cell.strip() for cell in rows[-1]):
        rows.pop()
    width = max((len(r) for r in rows), default=0)
    rows = [r + [""] * (width - len(r)) for r in rows]
    return rows, {"encoding": used, "delimiter": delimiter, "rows": len(rows), "columns": width}


def typed_value(text: str) -> tuple[Any, str | None]:
    """A number and its number format when ``text`` is a number that displays the same way; else the text."""
    stripped = text.strip()
    if stripped != text or not stripped:
        return text, None
    match = _NUMBER.fullmatch(stripped)
    if match:
        if re.match(r"-?0\d", stripped):
            return text, None
        decimals = match.group(1)
        if decimals is None:
            return int(stripped), None
        return float(stripped), "0." + "0" * len(decimals)
    match = _PERCENT.fullmatch(stripped)
    if match:
        decimals = match.group(2)
        return float(match.group(1)) / 100, "0" + ("." + "0" * len(decimals) if decimals else "") + "%"
    match = _THOUSANDS.fullmatch(stripped)
    if match:
        decimals = match.group(1)
        number = float(stripped.replace(",", ""))
        return (number if decimals else int(number)), "#,##0" + ("." + "0" * len(decimals) if decimals else "")
    return text, None


def _looks_like_header(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return False
    first = [c for c in rows[0] if c.strip()]
    return bool(first) and all(typed_value(c)[1] is None and isinstance(typed_value(c)[0], str) for c in first)


def _width(text: str) -> float:
    return sum(2 if ord(ch) > 0x2E7F else 1 for ch in text)


def csv_to_xlsx(
    input_path: str | Path,
    output_path: str | Path,
    encoding: str | None = None,
    delimiter: str | None = None,
    sheet_name: str | None = None,
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    source, destination, errors = check_paths(input_path, output_path, DELIMITED, {".xlsx"})
    if errors:
        return False, {}, errors
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        return missing_dependency("html", "openpyxl")
    try:
        rows, meta = read_delimited(source, encoding, delimiter)
    except (UnicodeDecodeError, LookupError) as exc:
        return False, {}, [{"code": "INPUT_DECODE_FAILED", "message": f"Could not read the text: {exc}"}]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = (sheet_name or source.stem)[:31] or "Sheet1"
    numbers = 0
    header = _looks_like_header(rows)
    widths: dict[int, float] = {}
    for r, row in enumerate(rows, start=1):
        for c, text in enumerate(row, start=1):
            if text == "":
                continue
            value, number_format = (text, None) if header and r == 1 else typed_value(text)
            cell = sheet.cell(row=r, column=c, value=value)
            if isinstance(value, str):
                cell.number_format = "@"
                if value.startswith("="):
                    cell.data_type = "s"
            else:
                numbers += 1
                if number_format:
                    cell.number_format = number_format
            if header and r == 1:
                cell.font = Font(bold=True)
            widths[c] = max(widths.get(c, 0), _width(text))
    from openpyxl.utils import get_column_letter

    for c, width in widths.items():
        sheet.column_dimensions[get_column_letter(c)].width = min(60, max(8, width + 2))
    if header:
        sheet.freeze_panes = "A2"
    workbook.save(destination)
    return (
        True,
        {
            "input_path": str(source),
            "output_path": str(destination),
            "format": "xlsx",
            "encoding": meta["encoding"],
            "delimiter": meta["delimiter"],
            "rows": meta["rows"],
            "columns": meta["columns"],
            "numbers": numbers,
            "header_row": header,
            "warnings": [],
        },
        [],
    )


def display_text(cell) -> str:
    """A cell as its number format shows it, for the formats csv_to_xlsx writes and the common ones."""
    from .fidelity import _cell_display

    return _cell_display(cell)


def xlsx_to_csv(
    input_path: str | Path,
    output_path: str | Path,
    sheet_name: str | None = None,
    encoding: str = "utf-8-sig",
    delimiter: str | None = None,
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    source, destination, errors = check_paths(input_path, output_path, {".xlsx", ".xlsm"}, {".csv", ".tsv"})
    if errors:
        return False, {}, errors
    try:
        from openpyxl import load_workbook
    except ImportError:
        return missing_dependency("html", "openpyxl")
    workbook = load_workbook(source, data_only=True)
    formulas = load_workbook(source, data_only=False)
    names = workbook.sheetnames
    if sheet_name and sheet_name not in names:
        return False, {}, [{"code": "SHEET_NOT_FOUND", "message": f"No sheet {sheet_name!r}; sheets: {names}"}]
    sheet = workbook[sheet_name or names[0]]
    formula_sheet = formulas[sheet.title]
    warnings = []
    uncached = 0
    rows = []
    for row in sheet.iter_rows():
        values = []
        for cell in row:
            if cell.value is None and isinstance(formula_sheet[cell.coordinate].value, str):
                raw = formula_sheet[cell.coordinate].value
                if raw.startswith("="):
                    uncached += 1
                    values.append(raw)
                    continue
            values.append(display_text(cell))
        rows.append(values)
    while rows and not any(rows[-1]):
        rows.pop()
    width = max((max((i + 1 for i, v in enumerate(r) if v), default=0) for r in rows), default=0)
    rows = [r[:width] for r in rows]
    if uncached:
        warnings.append(
            f"{uncached} formula cell(s) have no saved result (the file was not recalculated by WPS or Excel); "
            "their formulas were written instead."
        )
    if len(names) > 1:
        warnings.append(f"Only sheet {sheet.title!r} was written; the workbook has {len(names)} sheets.")
    delimiter = delimiter or ("\t" if destination.suffix.casefold() == ".tsv" else ",")
    buffer = io.StringIO(newline="")
    csv.writer(buffer, delimiter=delimiter, lineterminator="\r\n").writerows(rows)
    destination.write_bytes(buffer.getvalue().encode(encoding))
    return (
        True,
        {
            "input_path": str(source),
            "output_path": str(destination),
            "format": destination.suffix.casefold().lstrip("."),
            "sheet": sheet.title,
            "rows": len(rows),
            "columns": width,
            "encoding": encoding,
            "warnings": warnings,
        },
        [],
    )
