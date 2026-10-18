"""Convert local semantic HTML into an editable spreadsheet (xlsx) or presentation (pptx).

These converters run offline. They do not use WPS. Each outermost <table> becomes a worksheet, and the
nearest preceding heading names it; rowspan and colspan become merged cells, numbers written with
thousands separators, percent signs, currency symbols or exponents become numbers with a matching number
format, ISO-like dates become dates, and <br> becomes a line break in the cell. Local images are placed
below the table before them. The presentation converter is in html_slides. Anything that cannot be mapped
(cell formulas, nested tables) is reported as a warning rather than dropped silently.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .html_editable import validate_office_paths
from .html_text import decode_html_bytes

_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_NUMBER = re.compile(r"-?(0|[1-9]\d*)(\.\d+)?")
MAX_SHEETS = 50
MAX_ROWS_PER_SHEET = 10_000
MAX_SLIDES = 200
_SHEET_TITLE_LIMIT = 31  # Excel's limit


def _normalise(text: str) -> str:
    return " ".join(text.split())


def _read_html(source: Path) -> tuple[str, str | None]:
    text, _encoding, decode_warning = decode_html_bytes(source.read_bytes())
    return text, decode_warning


_THOUSANDS = re.compile(r"[-+]?\d{1,3}(,\d{3})+(\.\d+)?")
_PERCENT = re.compile(r"[-+]?\d+(\.\d+)?%")
_SCIENTIFIC = re.compile(r"[-+]?\d+(\.\d+)?[eE][-+]?\d+")
_DATE = re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})")
_CURRENCIES = {"¥": "¥", "￥": "¥", "$": "$", "€": "€", "£": "£"}


def _decimals(text: str) -> int:
    return len(text.split(".", 1)[1].rstrip("%")) if "." in text else 0


def _cell_value(text: str) -> tuple[Any, bool, str | None]:
    """Return (value, is_formula_like, number_format) for a cell's text.

    Plain, thousands-separated, signed, percent, currency and scientific numbers become numbers, and ISO-like
    dates become dates, each with a number format that shows them as written. Leading zeros stay text (an id,
    not a number), and text starting with '=' stays text (a formula is never evaluated from HTML).
    """
    import datetime as dt

    if text.startswith("="):
        return text, True, None
    stripped = text.strip()
    plain = stripped.lstrip("+")
    if _NUMBER.fullmatch(plain):
        return (float(plain) if "." in plain else int(plain)), False, None
    if _THOUSANDS.fullmatch(stripped):
        number = stripped.lstrip("+").replace(",", "")
        decimals = _decimals(number)
        value = float(number) if decimals else int(number)
        return value, False, "#,##0" + ("." + "0" * decimals if decimals else "")
    if _PERCENT.fullmatch(stripped):
        number = stripped.lstrip("+")[:-1]
        decimals = _decimals(number)
        return round(float(number) / 100, decimals + 2), False, "0" + ("." + "0" * decimals if decimals else "") + "%"
    if stripped[:1] in _CURRENCIES:
        value, _formula, number_format = _cell_value(stripped[1:].strip())
        if isinstance(value, (int, float)) and not isinstance(value, bool) and "%" not in (number_format or ""):
            symbol = _CURRENCIES[stripped[0]]
            decimals = number_format.split(".", 1)[1] if number_format and "." in number_format else ""
            return value, False, f'"{symbol}"#,##0' + (f".{decimals}" if decimals else "")
    if _SCIENTIFIC.fullmatch(stripped):
        return float(stripped), False, "0.00E+00"
    match = _DATE.fullmatch(stripped)
    if match:
        try:
            return dt.date(*(int(part) for part in match.groups())), False, "yyyy-mm-dd"
        except ValueError:
            pass
    return text, False, None


def _unique_sheet_name(base: str, used: set[str]) -> str:
    cleaned = re.sub(r"[\[\]:*?/\\]", " ", base).strip() or "Table"
    cleaned = cleaned[:_SHEET_TITLE_LIMIT]
    name, counter = cleaned, 2
    while name.casefold() in used:
        suffix = f" {counter}"
        name = cleaned[: _SHEET_TITLE_LIMIT - len(suffix)] + suffix
        counter += 1
    used.add(name.casefold())
    return name


def _parse_tree(source: Path):
    from .html_editable import _TreeParser

    text, decode_warning = _read_html(source)
    parser = _TreeParser()
    parser.feed(text)
    parser.close()
    return parser, decode_warning


def _outer_tables(root) -> list[tuple[str | None, Any]]:
    """The outermost tables in document order, each with the text of the nearest heading before it."""
    from .html_editable import _Node, _text

    found: list[tuple[str | None, Any]] = []
    last_heading: list[str | None] = [None]

    def visit(node) -> None:
        for child in node.children:
            if not isinstance(child, _Node):
                continue
            if child.tag in _HEADINGS:
                last_heading[0] = _normalise(_text(child)) or last_heading[0]
            elif child.tag == "table":
                found.append((last_heading[0], child))
            else:
                visit(child)

    visit(root)
    return found


def convert_html_to_xlsx(
    input_path: str | Path, output_path: str | Path
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    source, destination, path_errors = validate_office_paths(input_path, output_path, ".xlsx")
    if path_errors:
        return False, {}, path_errors
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
    except ImportError:
        return False, {}, [{"code": "CONVERTER_UNAVAILABLE", "message": "openpyxl is required for xlsx output."}]
    from .html_editable import _safe_link_target, _walk, cell_text, has_nested_table, local_image, table_grid

    parser, decode_warning = _parse_tree(source)
    tables = _outer_tables(parser.root)
    if not tables:
        return (
            False,
            {},
            [{"code": "NO_CONTENT", "message": "The HTML contains no <table> elements to convert to a worksheet."}],
        )
    warnings: list[str] = [decode_warning] if decode_warning else []
    if len(tables) > MAX_SHEETS:
        warnings.append(f"Only the first {MAX_SHEETS} tables were converted.")
        tables = tables[:MAX_SHEETS]
    workbook = Workbook()
    workbook.remove(workbook.active)
    used: set[str] = set()
    sheets = []
    formula_like = 0
    total_rows = 0
    nested = 0
    table_sheets: dict[int, Any] = {}
    for index, (title, table) in enumerate(tables, start=1):
        grid, merges = table_grid(table)
        if len(grid) > MAX_ROWS_PER_SHEET:
            warnings.append(f"Table {index} was cut to {MAX_ROWS_PER_SHEET} rows.")
            grid = grid[:MAX_ROWS_PER_SHEET]
            merges = [merge for merge in merges if merge[2] < MAX_ROWS_PER_SHEET]
        sheet = workbook.create_sheet(_unique_sheet_name(title or f"Table {index}", used))
        table_sheets[id(table)] = sheet
        for row_index, row in enumerate(grid, start=1):
            for column_index, node in enumerate(row, start=1):
                if node is None:
                    continue
                text = cell_text(node)
                if has_nested_table(node):
                    nested += 1
                    inner = [
                        " | ".join(
                            cell_text(item) for item in row_node.children if getattr(item, "tag", "") in {"td", "th"}
                        )
                        for item_table in _walk(node)
                        if item_table is not node and item_table.tag == "table"
                        for row_node in item_table.children
                        if getattr(row_node, "tag", "") == "tr"
                    ]
                    text = "\n".join(part for part in [text, *inner] if part)
                if not text:
                    continue
                value, is_formula, number_format = _cell_value(text)
                cell = sheet.cell(row=row_index, column=column_index)
                cell.value = value
                if is_formula:
                    cell.data_type = "s"
                    formula_like += 1
                if number_format:
                    cell.number_format = number_format
                if node.tag == "th":
                    cell.font = Font(bold=True)
                if "\n" in text:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                links = [link for link in _walk(node) if link.tag == "a" and link.attrs.get("href")]
                if len(links) == 1 and _safe_link_target(links[0].attrs["href"]):
                    cell.hyperlink = links[0].attrs["href"].strip()
                    cell.style = "Hyperlink"
        for first_row, first_column, last_row, last_column in merges:
            sheet.merge_cells(
                start_row=first_row + 1, start_column=first_column + 1, end_row=last_row + 1, end_column=last_column + 1
            )
            if grid[first_row][first_column].tag == "th":
                sheet.cell(row=first_row + 1, column=first_column + 1).alignment = Alignment(
                    horizontal="center", vertical="center"
                )
        total_rows += len(grid)
        sheets.append({"name": sheet.title, "rows": len(grid), "merged_ranges": len(merges)})
    # Each image goes on the sheet of the nearest table before it, below that table.
    images = 0
    current_sheet = None
    for node in _walk(parser.root):
        if id(node) in table_sheets:
            current_sheet = table_sheets[id(node)]
        if node.tag != "img":
            continue
        path, warning = local_image(source, node.attrs.get("src", ""))
        if warning:
            warnings.append(warning)
            continue
        try:
            from openpyxl.drawing.image import Image as SheetImage

            picture = SheetImage(str(path))
        except Exception:  # noqa: BLE001 - Pillow missing or not an image
            warnings.append(f"Image could not be read and was omitted: {node.attrs.get('src', '')}")
            continue
        sheet = current_sheet or workbook.worksheets[0]
        picture.anchor = f"A{sheet.max_row + 2}"
        sheet.add_image(picture)
        images += 1
    if formula_like:
        warnings.append(f"{formula_like} cell(s) starting with '=' were written as text, not formulas.")
    if nested:
        warnings.append(f"{nested} table(s) nested in a cell were written into that cell as text, one row per line.")
    workbook.save(destination)
    return (
        True,
        {
            "input_path": str(source),
            "output_path": str(destination),
            "format": "xlsx",
            "sheets": sheets,
            "rows": total_rows,
            "images": images,
            "warnings": warnings,
        },
        [],
    )


def convert_html_to_pptx(
    input_path: str | Path, output_path: str | Path
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    from .html_slides import convert_html_to_pptx as convert

    return convert(input_path, output_path)


OUTPUT_FORMATS = ("docx", "xlsx", "pptx")
BACKENDS = {"docx": "python-docx", "xlsx": "openpyxl", "pptx": "python-pptx"}


def convert_html_to_office(
    input_path: str | Path,
    output_path: str | Path,
    output_format: str = "docx",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    """Dispatch to the converter for one output format. docx keeps the existing Writer mapping."""
    if output_format == "docx":
        from .html_editable import convert_html_editable

        return convert_html_editable(input_path, output_path)
    if output_format == "xlsx":
        return convert_html_to_xlsx(input_path, output_path)
    if output_format == "pptx":
        return convert_html_to_pptx(input_path, output_path)
    return (
        False,
        {},
        [
            {
                "code": "INVALID_ARGUMENT",
                "message": f"Unsupported output format: {output_format}. Use docx, xlsx or pptx.",
            }
        ],
    )
