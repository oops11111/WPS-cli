"""Convert local semantic HTML into an editable spreadsheet (xlsx) or presentation (pptx).

These converters run offline. They do not use WPS. Each <table> becomes a worksheet, and the nearest
preceding heading names it. Each <section>, and each <h1>/<h2>, starts a slide, and the text of its
headings, paragraphs and list items becomes the slide's title and body. Anything that cannot be mapped
(images, nested tables, cell formulas) is reported as a warning rather than dropped silently.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .html_editable import validate_office_paths
from .html_text import decode_html_bytes

_SKIP = {"script", "style", "noscript", "template", "svg", "iframe", "object", "canvas"}
_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_NUMBER = re.compile(r"-?(0|[1-9]\d*)(\.\d+)?")
MAX_SHEETS = 50
MAX_ROWS_PER_SHEET = 10_000
MAX_SLIDES = 200
_SHEET_TITLE_LIMIT = 31  # Excel's limit


def _normalise(text: str) -> str:
    return " ".join(text.split())


class _TableCollector(HTMLParser):
    """Collects outermost <table> elements as rows of cell text, titled by the nearest preceding heading."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[dict[str, Any]] = []
        self.images = 0
        self._skip = 0
        self._table_depth = 0
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._heading: str | None = None
        self._heading_text: list[str] = []
        self._last_heading: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "img":
            self.images += 1
        elif tag in _HEADINGS and self._heading is None:
            self._heading = tag
            self._heading_text = []
        elif tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self.tables.append({"title": self._last_heading, "rows": []})
        elif self._table_depth == 1 and tag == "tr":
            self._row = []
        elif self._table_depth == 1 and tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag == self._heading:
            self._last_heading = _normalise("".join(self._heading_text)) or None
            self._heading = None
        elif tag == "table":
            self._table_depth = max(0, self._table_depth - 1)
        elif self._table_depth == 1 and tag in {"td", "th"} and self._cell is not None:
            self._row.append(_normalise("".join(self._cell)))
            self._cell = None
        elif self._table_depth == 1 and tag == "tr" and self._row is not None:
            if any(self._row):
                self.tables[-1]["rows"].append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._skip:
            return
        if self._heading is not None:
            self._heading_text.append(data)
        if self._cell is not None:
            self._cell.append(data)


class _SlideCollector(HTMLParser):
    """Splits the document into slides at <section> and at <h1>/<h2>, and collects their text."""

    _TEXT_BLOCKS = {"p", "li", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.slides: list[dict[str, Any]] = []
        self.tables = 0
        self.images = 0
        self._skip = 0
        self._block: str | None = None
        self._buffer: list[str] = []
        self._start_slide()

    def _start_slide(self) -> None:
        current = self.slides[-1] if self.slides else None
        if current is None or current["title"] or current["lines"]:
            self.slides.append({"title": None, "lines": []})

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "img":
            self.images += 1
        elif tag == "table":
            self.tables += 1
        elif tag == "section":
            self._start_slide()
        elif self._block is None and (tag in {"h1", "h2"} or tag in self._TEXT_BLOCKS):
            if tag in {"h1", "h2"}:
                self._start_slide()
            self._block = tag
            self._buffer = []

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip or tag != self._block:
            return
        text = _normalise("".join(self._buffer))
        slide = self.slides[-1]
        if text:
            if tag in {"h1", "h2"} and slide["title"] is None:
                slide["title"] = text
            else:
                slide["lines"].append(text)
        self._block = None

    def handle_data(self, data):
        if self._skip or self._block is None:
            return
        self._buffer.append(data)


def _read_html(source: Path) -> tuple[str, str | None]:
    text, _encoding, decode_warning = decode_html_bytes(source.read_bytes())
    return text, decode_warning


def _cell_value(text: str) -> tuple[Any, bool]:
    """Return (value, is_formula_like). Plain numbers become numbers; leading zeros stay text."""
    if text.startswith("="):
        return text, True
    if _NUMBER.fullmatch(text):
        return (float(text) if "." in text else int(text)), False
    return text, False


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


def convert_html_to_xlsx(input_path: str | Path, output_path: str | Path) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    source, destination, path_errors = validate_office_paths(input_path, output_path, ".xlsx")
    if path_errors:
        return False, {}, path_errors
    try:
        from openpyxl import Workbook
    except ImportError:
        return False, {}, [{"code": "CONVERTER_UNAVAILABLE", "message": "openpyxl is required for xlsx output."}]

    text, decode_warning = _read_html(source)
    collector = _TableCollector()
    collector.feed(text)
    collector.close()
    if not collector.tables:
        return False, {}, [{"code": "NO_CONTENT", "message": "The HTML contains no <table> elements to convert to a worksheet."}]

    warnings: list[str] = [decode_warning] if decode_warning else []
    if collector.images:
        warnings.append(f"{collector.images} image(s) were not converted.")
    tables = collector.tables[:MAX_SHEETS]
    if len(collector.tables) > MAX_SHEETS:
        warnings.append(f"Only the first {MAX_SHEETS} tables were converted.")

    workbook = Workbook()
    workbook.remove(workbook.active)
    used: set[str] = set()
    sheets = []
    formula_like = 0
    total_rows = 0
    for index, table in enumerate(tables, start=1):
        rows = table["rows"][:MAX_ROWS_PER_SHEET]
        if len(table["rows"]) > MAX_ROWS_PER_SHEET:
            warnings.append(f"Table {index} was cut to {MAX_ROWS_PER_SHEET} rows.")
        sheet = workbook.create_sheet(_unique_sheet_name(table["title"] or f"Table {index}", used))
        for row_index, row in enumerate(rows, start=1):
            for column_index, text in enumerate(row, start=1):
                value, is_formula = _cell_value(text)
                cell = sheet.cell(row=row_index, column=column_index)
                cell.value = value
                if is_formula:
                    cell.data_type = "s"
                    formula_like += 1
        total_rows += len(rows)
        sheets.append({"name": sheet.title, "rows": len(rows)})
    if formula_like:
        warnings.append(f"{formula_like} cell(s) starting with '=' were written as text, not formulas.")

    workbook.save(destination)
    return True, {
        "input_path": str(source),
        "output_path": str(destination),
        "format": "xlsx",
        "sheets": sheets,
        "rows": total_rows,
        "warnings": warnings,
    }, []


def convert_html_to_pptx(input_path: str | Path, output_path: str | Path) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    source, destination, path_errors = validate_office_paths(input_path, output_path, ".pptx")
    if path_errors:
        return False, {}, path_errors
    try:
        from pptx import Presentation
    except ImportError:
        return False, {}, [{"code": "CONVERTER_UNAVAILABLE", "message": "Install the html optional dependency: python-pptx."}]

    text, decode_warning = _read_html(source)
    collector = _SlideCollector()
    collector.feed(text)
    collector.close()
    slides = [slide for slide in collector.slides if slide["title"] or slide["lines"]]
    if not slides:
        return False, {}, [{"code": "NO_CONTENT", "message": "The HTML contains no headings, paragraphs or list items to convert to slides."}]

    warnings: list[str] = [decode_warning] if decode_warning else []
    if collector.tables:
        warnings.append(f"{collector.tables} table(s) were not converted; use html-editable with --format xlsx for tables.")
    if collector.images:
        warnings.append(f"{collector.images} image(s) were not converted.")
    if len(slides) > MAX_SLIDES:
        warnings.append(f"Only the first {MAX_SLIDES} slides were converted.")
        slides = slides[:MAX_SLIDES]

    presentation = Presentation()
    layout = presentation.slide_layouts[1]  # title and content
    for slide_data in slides:
        slide = presentation.slides.add_slide(layout)
        slide.shapes.title.text = slide_data["title"] or ""
        body = slide.placeholders[1].text_frame
        lines = slide_data["lines"]
        body.text = lines[0] if lines else ""
        for line in lines[1:]:
            body.add_paragraph().text = line
    presentation.save(destination)
    return True, {
        "input_path": str(source),
        "output_path": str(destination),
        "format": "pptx",
        "slides": len(slides),
        "warnings": warnings,
    }, []


OUTPUT_FORMATS = ("docx", "xlsx", "pptx")
BACKENDS = {"docx": "python-docx", "xlsx": "openpyxl", "pptx": "python-pptx"}


def convert_html_to_office(
    input_path: str | Path, output_path: str | Path, output_format: str = "docx",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    """Dispatch to the converter for one output format. docx keeps the existing Writer mapping."""
    if output_format == "docx":
        from .html_editable import convert_html_editable

        return convert_html_editable(input_path, output_path)
    if output_format == "xlsx":
        return convert_html_to_xlsx(input_path, output_path)
    if output_format == "pptx":
        return convert_html_to_pptx(input_path, output_path)
    return False, {}, [{"code": "INVALID_ARGUMENT", "message": f"Unsupported output format: {output_format}. Use docx, xlsx or pptx."}]
