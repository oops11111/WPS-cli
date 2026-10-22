"""One entry point for every format pair (P13-017): ``convert(input, output, ...)`` picks the converter.

Routes, by source and target extension:

=====================================  ===========================================================
HTML -> DOCX, XLSX, PPTX               html-editable mapping (computed CSS; ``fidelity`` editable or appearance)
HTML -> PDF, PNG                       the browser (html-render)
DOCX, PPTX, XLSX -> HTML               clean HTML with inline styles (office_html)
HTML, DOCX, PPTX, XLSX -> Markdown     markdown_convert
Markdown -> HTML, DOCX, PPTX           markdown_convert
CSV, TSV, TXT <-> XLSX                 tabular (encoding and delimiter detected)
DOCX <-> PPTX, XLSX -> DOCX/PPTX       cross_type (``sheet`` and ``cell_range`` for a worksheet range)
PDF -> DOCX, XLSX, PPTX                pdf_convert (``ocr`` for scanned pages)
WPS, legacy Office and ODF formats     WPS itself through COM (wps_convert), on Windows
=====================================  ===========================================================

A pair with no direct route goes through one intermediate file (a .doc to Markdown is .doc -> .docx with WPS, then
.docx -> .md); the result lists each step in ``route``.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .conversion_paths import check_paths

HTML = {".html", ".htm"}
MARKDOWN = {".md", ".markdown"}
DELIMITED = {".csv", ".tsv", ".txt"}
OOXML = {".docx", ".xlsx", ".pptx"}
Result = tuple[bool, dict[str, Any], list[dict[str, str]]]


def _html_office(source: Path, target: Path, options: dict[str, Any]) -> Result:
    from .html_office import convert_html_to_office

    return convert_html_to_office(
        source,
        target,
        target.suffix.casefold().lstrip("."),
        fidelity=options.get("fidelity", "editable"),
        use_browser=options.get("use_browser", True),
    )


def _html_render(source: Path, target: Path, options: dict[str, Any]) -> Result:
    from .html_render import render_html

    return render_html(source, target, target.suffix.casefold().lstrip("."))


def _office_html(source: Path, target: Path, options: dict[str, Any]) -> Result:
    from .office_html import office_to_html

    return office_to_html(source, target, images=options.get("images", "embed"))


def _to_markdown(source: Path, target: Path, options: dict[str, Any]) -> Result:
    from .markdown_convert import to_markdown

    return to_markdown(source, target)


def _md_html(source: Path, target: Path, options: dict[str, Any]) -> Result:
    from .markdown_convert import md_to_html

    return md_to_html(source, target)


def _md_office(source: Path, target: Path, options: dict[str, Any]) -> Result:
    from .markdown_convert import md_to_office

    return md_to_office(source, target, use_browser=options.get("use_browser", True))


def _csv_xlsx(source: Path, target: Path, options: dict[str, Any]) -> Result:
    from .tabular import csv_to_xlsx

    return csv_to_xlsx(source, target, options.get("encoding"), options.get("delimiter"), options.get("sheet"))


def _xlsx_csv(source: Path, target: Path, options: dict[str, Any]) -> Result:
    from .tabular import xlsx_to_csv

    return xlsx_to_csv(
        source, target, options.get("sheet"), options.get("encoding") or "utf-8-sig", options.get("delimiter")
    )


def _docx_pptx(source: Path, target: Path, options: dict[str, Any]) -> Result:
    from .cross_type import docx_to_pptx

    return docx_to_pptx(source, target)


def _pptx_docx(source: Path, target: Path, options: dict[str, Any]) -> Result:
    from .cross_type import pptx_to_docx

    return pptx_to_docx(source, target)


def _xlsx_table(source: Path, target: Path, options: dict[str, Any]) -> Result:
    from .cross_type import xlsx_range_to_table

    return xlsx_range_to_table(source, target, options.get("sheet"), options.get("cell_range"))


def _pdf_office(source: Path, target: Path, options: dict[str, Any]) -> Result:
    from .pdf_convert import pdf_to_office

    return pdf_to_office(source, target, ocr=options.get("ocr", False))


def _wps(source: Path, target: Path, options: dict[str, Any]) -> Result:
    from .wps_convert import wps_convert

    return wps_convert(source, target, dpi=options.get("dpi", 150))


def _direct(source: str, target: str) -> tuple[str, Callable[[Path, Path, dict[str, Any]], Result]] | None:
    from .wps_convert import FAMILIES, family_of

    if source in HTML and target in OOXML:
        return "html-editable", _html_office
    if source in HTML and target in {".pdf", ".png"}:
        return "html-render", _html_render
    if source in OOXML and target in HTML:
        return "office-to-html", _office_html
    if source in HTML | OOXML and target in MARKDOWN:
        return "to-markdown", _to_markdown
    if source in MARKDOWN and target in HTML:
        return "markdown-to-html", _md_html
    if source in MARKDOWN and target in OOXML:
        return "markdown-to-office", _md_office
    if source in DELIMITED and target == ".xlsx":
        return "csv-to-xlsx", _csv_xlsx
    if source in {".xlsx", ".xlsm"} and target in {".csv", ".tsv"}:
        return "xlsx-to-csv", _xlsx_csv
    if source == ".docx" and target == ".pptx":
        return "docx-to-pptx", _docx_pptx
    if source == ".pptx" and target == ".docx":
        return "pptx-to-docx", _pptx_docx
    if source in {".xlsx", ".xlsm"} and target in {".docx", ".pptx"}:
        return "xlsx-range-to-table", _xlsx_table
    if source == ".pdf" and target in OOXML:
        return "pdf-to-office", _pdf_office
    component = family_of(Path("x" + source))
    if component is not None and (target in FAMILIES[component]["outputs"] or target in {".pdf", ".png"}):
        return "wps", _wps
    return None


def routes(source: str, target: str) -> list[tuple[str, str]]:
    """The steps from one extension to another: [(step name, extension written)], or [] when there is no route."""
    source, target = source.casefold(), target.casefold()
    direct = _direct(source, target)
    if direct:
        return [(direct[0], target)]
    for middle in (".docx", ".xlsx", ".pptx", ".html", ".pdf"):
        first, second = _direct(source, middle), _direct(middle, target)
        if first and second and middle not in {source, target}:
            return [(first[0], middle), (second[0], target)]
    return []


def describe_output(path: Path) -> dict[str, Any]:
    """What the converted file holds, so a caller need not open it to check: slide titles, headings, sheets."""
    suffix = path.suffix.casefold()
    try:
        if suffix == ".pptx":
            from pptx import Presentation

            slides = Presentation(path).slides
            titles = [s.shapes.title.text_frame.text if s.shapes.title is not None else "" for s in slides]
            return {"slides": len(titles), "slide_titles": titles[:50]}
        if suffix == ".docx":
            from docx import Document

            document = Document(path)
            headings = [
                p.text for p in document.paragraphs if p.style is not None and p.style.name.startswith("Heading")
            ]
            return {"headings": headings[:50], "paragraphs": len(document.paragraphs), "tables": len(document.tables)}
        if suffix in {".xlsx", ".xlsm"}:
            from openpyxl import load_workbook

            workbook = load_workbook(path, read_only=True)
            try:
                return {"sheets": [{"name": ws.title, "dimensions": ws.calculate_dimension()} for ws in workbook]}
            finally:
                workbook.close()
    except Exception:  # noqa: BLE001 - the summary is a convenience; the conversion already succeeded
        return {}
    return {}


def convert(input_path: str | Path, output_path: str | Path, **options: Any) -> Result:
    """Convert ``input_path`` to ``output_path``; options: fidelity, use_browser, images, ocr, sheet, cell_range,
    encoding, delimiter, dpi."""
    source = Path(input_path).expanduser().resolve()
    destination = Path(output_path).expanduser().resolve()
    steps = routes(source.suffix, destination.suffix)
    if not steps:
        from .wps_convert import FORMAT_NOT_SUPPORTED_BY_WPS, family_of

        code = FORMAT_NOT_SUPPORTED_BY_WPS if family_of(source) else "UNSUPPORTED_CONVERSION"
        return (
            False,
            {},
            [
                {
                    "code": code,
                    "message": f"No conversion from {source.suffix or '(no extension)'} to "
                    f"{destination.suffix or '(no extension)'}; see docs/CONVERSION_MATRIX.md.",
                }
            ],
        )
    if len(steps) == 1:
        _name, function = _direct(source.suffix.casefold(), destination.suffix.casefold())
        ok, data, errors = function(source, destination, options)
        if ok:
            data["route"] = [steps[0][0]]
            data["output_summary"] = describe_output(destination)
        return ok, data, errors
    # Two steps: the intermediate file lives in a temporary folder and is removed.
    _source_dir, _target_dir, path_errors = check_paths(
        source, destination, {source.suffix.casefold()}, {destination.suffix.casefold()}
    )
    if path_errors:
        return False, {}, path_errors
    warnings: list[str] = []
    with tempfile.TemporaryDirectory(prefix="wps-convert-") as tmp:
        middle = Path(tmp) / f"{source.stem}{steps[0][1]}"
        first = _direct(source.suffix.casefold(), steps[0][1])
        ok, data, errors = first[1](source, middle, options)
        if not ok:
            return ok, data, errors
        warnings += data.get("warnings", [])
        second = _direct(steps[0][1], destination.suffix.casefold())
        ok, data, errors = second[1](middle, destination, options)
        if not ok:
            return ok, data, errors
    data["input_path"] = str(source)
    data["route"] = [steps[0][0], steps[1][0]]
    data["output_summary"] = describe_output(destination)
    data["warnings"] = warnings + data.get("warnings", [])
    return True, data, []
