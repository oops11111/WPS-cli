"""PDF to DOCX, XLSX or PPTX (P13-014, P13-015, P13-016).

``analyse_pdf`` reads the text layer with pdfplumber (the ``pdf`` extra): words with their font size and weight are
grouped into lines and paragraphs; a line clearly larger than the body text is a heading (the largest size is
level 1); ruled tables are found with pdfplumber's table finder; text repeated at the top or bottom of most pages
is a running header or footer and is dropped, as are bare page numbers. Pictures are cropped from the rendered page.

A page without a text layer is scanned. Without ``ocr=True`` a PDF whose pages are all scanned is refused with
PDF_NEEDS_OCR (decision 5); with it, RapidOCR (the ``ocr`` extra) reads the rendered page.

The result is clean HTML handed to html-editable, so DOCX output gets Writer headings, lists and native tables,
XLSX output gets one worksheet per table, and PPTX output gets one slide per page (titled with the page's first
heading; slide positions follow the reading order, not the page coordinates).
"""

from __future__ import annotations

import base64
import html
import io
import re
import statistics
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .conversion_paths import check_paths, missing_dependency

_BULLET = re.compile(r"^\s*([•·▪◦●○■□\-–*\uf0b7\uf0a7\uf0d8\uf076]|\(?\d{1,2}[.)、）]|（\d{1,2}）|[a-zA-Z][.)])\s*")
_CJK = re.compile(r"[⺀-鿿＀-￯]")
MAX_PAGES = 300


@dataclass
class Line:
    text: str
    size: float
    bold: bool
    top: float
    bottom: float
    x0: float
    x1: float


@dataclass
class Item:
    kind: str  # heading, paragraph, list, table, image
    text: str = ""
    level: int = 0
    rows: list[list[str]] = field(default_factory=list)
    image: bytes | None = None
    width: float = 0.0
    bold: bool = False
    top: float = 0.0
    size: float = 0.0
    columns: list[float] = field(default_factory=list)  # table column widths in points
    ruled: bool = True  # a table drawn with lines (else its columns were found from the text alignment)
    bottom: float = 0.0
    pitches: list[float] = field(default_factory=list)  # distances between the tops of its lines
    row_heights: list[float] = field(default_factory=list)  # table rows, in points
    padding: float | None = None  # a table cell's left inset, in points
    header_bold: bool | None = None  # whether the table's first row is set in bold


@dataclass
class Page:
    number: int
    width: float
    height: float
    items: list[Item] = field(default_factory=list)
    scanned: bool = False
    ocr: bool = False


@dataclass
class Analysis:
    pages: list[Page]
    body_size: float
    headers: list[str]
    footers: list[str]
    warnings: list[str]
    margins: tuple[float, float, float, float] | None = None  # top, right, bottom, left in points


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _key(text: str) -> str:
    """Running headers and footers differ only by their page number."""
    return re.sub(r"\d+", "#", _norm(text))


def _join(previous: str, line: str) -> str:
    if not previous:
        return line
    if previous.endswith("-") and line[:1].islower():
        return previous[:-1] + line
    if _CJK.search(previous[-1:]) or _CJK.search(line[:1]):
        return previous + line
    return previous + " " + line


def _word_lines(
    page, exclude: list[tuple[float, float, float, float]], words: list[dict] | None = None
) -> list[list[dict]]:
    """The page's words grouped into lines by vertical overlap (a subscript stays on its line), top to bottom."""
    if words is None:
        words = page.extract_words(extra_attrs=["size", "fontname"], keep_blank_chars=False)
    kept = []
    for word in words:
        middle = (word["top"] + word["bottom"]) / 2
        if any(x0 - 1 <= word["x0"] <= x1 + 1 and top - 1 <= middle <= bottom + 1 for x0, top, x1, bottom in exclude):
            continue
        kept.append(word)
    kept.sort(key=lambda w: (w["top"], w["x0"]))
    lines: list[list[dict]] = []
    spans: list[list[float]] = []  # top, bottom of each line's main text
    for word in kept:
        height = max(word["bottom"] - word["top"], 0.1)
        for index in range(len(lines) - 1, max(-1, len(lines) - 4), -1):
            top, bottom = spans[index]
            overlap = min(bottom, word["bottom"]) - max(top, word["top"])
            if overlap >= min(height, bottom - top) * 0.4:
                lines[index].append(word)
                if word["size"] >= max(w["size"] for w in lines[index]) * 0.9:
                    spans[index] = [min(top, word["top"]), max(bottom, word["bottom"])]
                break
        else:
            lines.append([word])
            spans.append([word["top"], word["bottom"]])
    for words_in_line in lines:
        words_in_line.sort(key=lambda w: w["x0"])
    return lines


def _segments(words: list[dict]) -> list[list[dict]]:
    """A line's words split where the gap is wide enough to separate table cells."""
    segments: list[list[dict]] = []
    for word in words:
        if segments and word["x0"] - segments[-1][-1]["x1"] < max(word["size"] * 1.5, 9.0):
            segments[-1].append(word)
        else:
            segments.append([word])
    return segments


def _text_of(words: list[dict]) -> str:
    text = ""
    last = None
    for word in words:
        if (
            text
            and (word["x0"] - last["x1"] > word["size"] * 0.2)
            and not (_CJK.search(text[-1]) and _CJK.search(word["text"][0]))
        ):
            text += " "
        text += word["text"]
        last = word
    return _norm(text)


def _match_columns(boxes: list[list[float]], columns: list[list[float]]) -> list[int | None]:
    """For each cell box, the column whose slot holds its centre. Slots meet halfway between the column centres,
    so that centred headers match left- or right-aligned columns."""
    order = sorted(range(len(columns)), key=lambda c: columns[c][0])
    centres = [(columns[c][0] + columns[c][1]) / 2 for c in order]
    bounds = [(a + b) / 2 for a, b in zip(centres, centres[1:], strict=False)]
    matched: list[int | None] = []
    for box in boxes:
        centre = (box[0] + box[1]) / 2
        position = sum(centre > bound for bound in bounds)
        column = order[position]
        # A box must reach its column's side of the neighbouring columns.
        inside = (position == 0 or box[1] > columns[order[position - 1]][1]) and (
            position + 1 == len(order) or box[0] < columns[order[position + 1]][0]
        )
        matched.append(column if inside else None)
    return matched


def _text_tables(lines: list[list[dict]]) -> tuple[list[tuple[float, float, list[list[str]], list[float]]], set[int]]:
    """Tables without ruling lines: three or more lines whose cells line up in two or more columns."""
    tables: list[tuple[float, float, list[list[str]], list[float]]] = []
    used: set[int] = set()
    segmented = [_segments(words) for words in lines]
    index = 0
    while index < len(lines):
        if len(segmented[index]) < 2:
            index += 1
            continue
        run = [index]
        columns = [[min(w["x0"] for w in seg), max(w["x1"] for w in seg)] for seg in segmented[index]]
        cursor = index + 1
        while cursor < len(lines):
            segments = segmented[cursor]
            previous = lines[run[-1]]
            gap = min(w["top"] for w in lines[cursor]) - max(w["bottom"] for w in previous)
            if gap > max(w["size"] for w in previous) * 2.2:
                break
            boxes = [[min(w["x0"] for w in seg), max(w["x1"] for w in seg)] for seg in segments]
            matched = _match_columns(boxes, columns)
            fits = len(set(matched)) == len(boxes) and None not in matched
            if (len(segments) >= 2 and fits) or (len(segments) == 1 and fits and boxes[0][0] > columns[0][1]):
                run.append(cursor)
                for box, column in zip(boxes, matched, strict=True):
                    columns[column][0] = min(columns[column][0], box[0])
                    columns[column][1] = max(columns[column][1], box[1])
                cursor += 1
            else:
                break
        multi = sum(len(segmented[i]) >= 2 for i in run)
        if len(run) >= 3 and multi >= 3:
            columns.sort()
            merged: list[list[float]] = []
            for column in columns:
                if merged and column[0] <= merged[-1][1] + 2:
                    merged[-1][1] = max(merged[-1][1], column[1])
                else:
                    merged.append(list(column))
            raw_rows = []
            for line_index in run:
                row = [""] * len(merged)
                for segment in segmented[line_index]:
                    x0, x1 = min(w["x0"] for w in segment), max(w["x1"] for w in segment)
                    best = max(range(len(merged)), key=lambda c: min(x1, merged[c][1]) - max(x0, merged[c][0]))
                    row[best] = _norm(row[best] + " " + _text_of(segment))
                middle = (min(w["top"] for w in lines[line_index]) + max(w["bottom"] for w in lines[line_index])) / 2
                raw_rows.append((middle, row))
            # A cell that wraps puts lines with an empty first column above or below its row: each such line
            # belongs to the nearest line that has a first column.
            anchors = [i for i, (_m, row) in enumerate(raw_rows) if row[0]]
            if anchors and anchors[0] == 0:
                pieces: dict[int, list[tuple[float, list[str]]]] = {i: [raw_rows[i]] for i in anchors}
                for i, (middle, row) in enumerate(raw_rows):
                    if i not in pieces:
                        nearest = min(anchors, key=lambda a: abs(raw_rows[a][0] - middle))
                        pieces[nearest].append((middle, row))
                rows = []
                for anchor in anchors:
                    parts = sorted(pieces[anchor], key=lambda item: item[0])
                    rows.append(
                        [_norm(_join_all([part[1][c] for part in parts if part[1][c]])) for c in range(len(merged))]
                    )
            else:
                rows = [row for _m, row in raw_rows]
            if len(merged) >= 2:
                top = min(w["top"] for w in lines[run[0]])
                bottom = max(w["bottom"] for w in lines[run[-1]])
                # Each column reaches to the next one's start.
                widths = [merged[c + 1][0] - merged[c][0] for c in range(len(merged) - 1)]
                widths.append(merged[-1][1] - merged[-1][0] + 6)
                tables.append((top, bottom, rows, widths))
                used.update(run)
                index = run[-1] + 1
                continue
        index += 1
    return tables, used


def _make_line(words: list[dict]) -> Line:
    main = max(w["size"] for w in words)
    body_words = [w for w in words if w["size"] >= main * 0.85]
    return Line(
        text=_text_of(words),
        size=statistics.median([round(w["size"], 1) for w in body_words]),
        bold=all(re.search(r"bold|black|heavy|semibold", w["fontname"], re.I) for w in body_words),
        top=min(w["top"] for w in body_words),
        bottom=max(w["bottom"] for w in body_words),
        x0=min(w["x0"] for w in words),
        x1=max(w["x1"] for w in words),
    )


def _join_all(parts: list[str]) -> str:
    text = ""
    for part in parts:
        text = _join(text, part)
    return text


def _lines_of(page, exclude: list[tuple[float, float, float, float]], tables_out: list, words=None) -> list[Line]:
    word_lines = _word_lines(page, exclude, words)
    tables, used = _text_tables(word_lines)
    tables_out.extend(tables)
    return [_make_line(words) for i, words in enumerate(word_lines) if i not in used and _text_of(words)]


def _measure_table(page, table, item: Item) -> None:
    """Row heights, the cells' left inset and the header weight of a ruled table, as the PDF draws them."""
    item.row_heights = [row.bbox[3] - row.bbox[1] for row in table.rows if row.bbox]
    try:
        words = page.within_bbox(table.bbox).extract_words(extra_attrs=["fontname"])
    except ValueError:
        return
    insets = []
    first_row = table.rows[0].bbox if table.rows else None
    header_fonts = []
    for cell in table.cells:
        inside = [w for w in words if cell[0] - 1 <= w["x0"] <= cell[2] and cell[1] - 1 <= w["top"] <= cell[3]]
        if inside:
            insets.append(min(w["x0"] for w in inside) - cell[0])
            if first_row and abs(cell[1] - first_row[1]) < 1:
                header_fonts += [w["fontname"] for w in inside]
    # Centred header cells sit further in: the smaller half of the insets is the padding.
    body = sorted(i for i in insets if i >= 0)
    if body:
        item.padding = statistics.median(body[: max(1, len(body) // 2)]) or None
    if header_fonts:
        item.header_bold = all(re.search(r"bold|black|heavy|semibold", f, re.I) for f in header_fonts)


def _ocr_words(page_image, engine, scale: float) -> list[dict]:
    """RapidOCR's text boxes as words in PDF points, with a font size estimated from the box height."""
    import numpy as np

    result, _elapsed = engine(np.asarray(page_image.convert("RGB")))
    words = []
    for box, text, _score in result or []:
        xs = [point[0] * scale for point in box]
        ys = [point[1] * scale for point in box]
        if not _norm(text):
            continue
        height = max(ys) - min(ys)
        words.append(
            {
                "text": _norm(text),
                "x0": min(xs),
                "x1": max(xs),
                "top": min(ys),
                "bottom": max(ys),
                # A text box is about 1.35 times the font size; sizes are rounded to whole points.
                "size": float(round(height / 1.35)),
                "fontname": "",
            }
        )
    return words


def _ocr_engine():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return None
    return RapidOCR()


def analyse_pdf(path: str | Path, ocr: bool = False, images: bool = True) -> Analysis:
    import pdfplumber

    warnings: list[str] = []
    pages: list[Page] = []
    raw: list[tuple[Page, list[Line]]] = []
    engine = None
    bounds: list = []
    with pdfplumber.open(str(path)) as pdf:
        if len(pdf.pages) > MAX_PAGES:
            warnings.append(f"Only the first {MAX_PAGES} pages were converted.")
        for number, plumber_page in enumerate(pdf.pages[:MAX_PAGES], start=1):
            page = Page(number, float(plumber_page.width), float(plumber_page.height))
            tables = plumber_page.find_tables()
            boxes = [table.bbox for table in tables]
            text_tables: list = []
            lines = _lines_of(plumber_page, boxes, text_tables)
            for table in tables:
                rows = [[_norm(cell or "") for cell in row] for row in table.extract()]
                if rows and any(any(row) for row in rows):
                    edges = sorted({round(cell[0], 1) for cell in table.cells} | {round(table.bbox[2], 1)})
                    widths = [b - a for a, b in zip(edges, edges[1:], strict=False)]
                    item = Item("table", rows=rows, top=table.bbox[1], columns=widths, bottom=table.bbox[3])
                    _measure_table(plumber_page, table, item)
                    page.items.append(item)
            for top, bottom, rows, widths in text_tables:
                page.items.append(Item("table", rows=rows, top=top, columns=widths, ruled=False, bottom=bottom))
            bounds.append((page, lines, [t.bbox for t in tables] + [(0, t[0], 0, t[1]) for t in text_tables]))
            if not plumber_page.chars:
                page.scanned = True
                if ocr:
                    engine = engine or _ocr_engine()
                    if engine is None:
                        raise ModuleNotFoundError("rapidocr_onnxruntime", name="rapidocr_onnxruntime")
                    rendered = plumber_page.to_image(resolution=300).original
                    words = _ocr_words(rendered, engine, page.width / rendered.width)
                    text_tables = []
                    lines = _lines_of(plumber_page, [], text_tables, words)
                    for top, bottom, rows, widths in text_tables:
                        page.items.append(Item("table", rows=rows, top=top, columns=widths, ruled=False, bottom=bottom))
                    page.ocr = True
            if images and not page.scanned:
                for picture in plumber_page.images:
                    bbox = (
                        max(0, picture["x0"]),
                        max(0, picture["top"]),
                        min(page.width, picture["x1"]),
                        min(page.height, picture["bottom"]),
                    )
                    if bbox[2] - bbox[0] < 16 or bbox[3] - bbox[1] < 16:
                        continue
                    try:
                        crop = plumber_page.crop(bbox).to_image(resolution=150).original
                    except Exception:  # noqa: BLE001 - a picture pdfplumber cannot render
                        continue
                    buffer = io.BytesIO()
                    crop.save(buffer, format="PNG")
                    page.items.append(
                        Item("image", image=buffer.getvalue(), width=bbox[2] - bbox[0], top=bbox[1], bottom=bbox[3])
                    )
            raw.append((page, lines))
            pages.append(page)
    sizes = [line.size for _page, lines in raw for line in lines for _ in range(max(1, len(line.text)))]
    body = statistics.mode([round(s) for s in sizes]) if sizes else 12.0
    # Running headers and footers: the same text (page numbers aside) near the top or bottom of most pages.
    headers, footers = set(), set()
    if len(raw) >= 2:
        top_counts: dict[str, int] = {}
        bottom_counts: dict[str, int] = {}
        for page, lines in raw:
            for line in lines:
                if line.top < page.height * 0.09:
                    top_counts[_key(line.text)] = top_counts.get(_key(line.text), 0) + 1
                elif line.bottom > page.height * 0.91:
                    bottom_counts[_key(line.text)] = bottom_counts.get(_key(line.text), 0) + 1
        need = max(2, (len(raw) + 1) // 2)
        headers = {k for k, v in top_counts.items() if v >= need}
        footers = {k for k, v in bottom_counts.items() if v >= need}
    # OCR sizes come from box heights and wobble by a point or two: they need a wider margin.
    ocr_pages = any(page.ocr for page in pages)
    factor = 1.2 if ocr_pages else 1.15
    tolerance = 2.1 if ocr_pages else 0.6
    heading_sizes = sorted(
        {round(line.size) for _p, lines in raw for line in lines if line.size >= body * factor}, reverse=True
    )
    # Sizes within a step of each other are one heading level (OCR sizes vary by a point or two).
    step = 1.6 if ocr_pages else 0.5
    levels: dict[int, int] = {}
    level = 0
    for index, size in enumerate(heading_sizes):
        if index == 0 or heading_sizes[index - 1] - size > step:
            level += 1
        levels[size] = min(level, 6)
    body_lines: list[tuple[Page, Line]] = []
    for page, lines in raw:
        current: Item | None = None
        previous: Line | None = None
        for line in lines:
            key = _key(line.text)
            near_edge = line.top < page.height * 0.09 or line.bottom > page.height * 0.91
            if near_edge and (
                key in headers
                or key in footers
                or re.fullmatch(r"[-–—\s]*#[-–—\s]*|第#页.*|#\s*/\s*#|Page # of #", key, re.I)
            ):
                previous = None
                continue
            level = levels.get(round(line.size))
            bullet = _BULLET.match(line.text) if len(line.text) > 2 else None
            if level:
                if (
                    current is not None
                    and current.kind == "heading"
                    and current.level == level
                    and previous is not None
                    and line.top - previous.bottom < line.size * 0.8
                ):
                    current.text = _join(current.text, line.text)
                    current.pitches.append(line.top - previous.top)
                    current.bottom = line.bottom
                else:
                    current = Item(
                        "heading", line.text, level, top=line.top, size=line.size, bottom=line.bottom, bold=line.bold
                    )
                    page.items.append(current)
            elif bullet is not None:
                text = (
                    line.text[bullet.end() :] if bullet.group(1) in "•·▪◦●○■□-–*\uf0b7\uf0a7\uf0d8\uf076" else line.text
                )
                current = Item(
                    "list",
                    text,
                    1 if line.x0 - (previous.x0 if previous else line.x0) < 12 else 2,
                    top=line.top,
                    size=line.size,
                    bottom=line.bottom,
                )
                current.bold = line.bold
                page.items.append(current)
            else:
                gap = line.top - previous.bottom if previous is not None else None
                continues = (
                    current is not None
                    and current.kind in {"paragraph", "list"}
                    and previous is not None
                    and gap is not None
                    and gap < line.size * 0.9
                    and abs(previous.size - line.size) < tolerance
                    and not (previous.x1 < page.width * 0.6 and current.kind == "paragraph" and line.x0 <= previous.x0)
                )
                if continues and current is not None:
                    current.text = _join(current.text, line.text)
                    current.bold = current.bold and line.bold
                    current.pitches.append(line.top - previous.top)
                    current.bottom = line.bottom
                else:
                    current = Item(
                        "paragraph", line.text, top=line.top, bold=line.bold, size=line.size, bottom=line.bottom
                    )
                    page.items.append(current)
            previous = line
            body_lines.append((page, line))
        page.items.sort(key=lambda item: item.top)
    if any(page.scanned for page in pages) and not ocr:
        scanned = [str(page.number) for page in pages if page.scanned]
        warnings.append(f"Pages without a text layer were not read (scanned): {', '.join(scanned[:20])}.")
    margins = None
    if body_lines:
        first = pages[0]
        top = min(line.top for _p, line in body_lines)
        left = min(line.x0 for _p, line in body_lines)
        right = first.width - max(line.x1 for _p, line in body_lines)
        bottom = first.height - max(line.bottom for _p, line in body_lines)
        margins = (max(18.0, top - 4), max(18.0, min(right, left)), max(18.0, bottom - 4), max(18.0, left))
    return Analysis(pages, float(body), sorted(headers), sorted(footers), warnings, margins)


def _display(key: str) -> str:
    """A running header's text; page numbers (kept as # in the key) are left out."""
    return _norm(re.sub(r"#", "", key))


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _table_html(
    rows: list[list[str]], widths: list[float] | None = None, ruled: bool = True, item: Item | None = None
) -> str:
    width = max(len(row) for row in rows)
    cols = ""
    if widths and len(widths) == width:
        cols = "<colgroup>" + "".join(f'<col style="width:{w:.0f}pt">' for w in widths) + "</colgroup>"
    heights = item.row_heights if item is not None and len(item.row_heights) == len(rows) else []
    cell_style = ""
    if item is not None and item.padding is not None:
        cell_style = f' style="padding:0 {item.padding:.1f}pt;vertical-align:middle"'
    head_style = cell_style
    if item is not None and item.header_bold is False:
        head_style = cell_style[:-1] + ';font-weight:normal"' if cell_style else ' style="font-weight:normal"'

    def tr(index: int) -> str:
        return f'<tr style="height:{heights[index]:.1f}pt">' if heights else "<tr>"

    head = "".join(f"<th{head_style}>{_escape(cell)}</th>" for cell in rows[0] + [""] * (width - len(rows[0])))
    body = "".join(
        tr(index)
        + "".join(f"<td{cell_style}>{_escape(cell)}</td>" for cell in row + [""] * (width - len(row)))
        + "</tr>"
        for index, row in enumerate(rows[1:], start=1)
    )
    border = ' border="1"' if ruled else ""
    return f"<table{border}>{cols}<thead>{tr(0)}{head}</tr></thead><tbody>{body}</tbody></table>"


def _size_style(
    item: Item, body: float, extra: str = "", spacing: tuple[float, float] | None = None, bold: bool | None = None
) -> str:
    """The item's style: its size when it differs from the body text and, for a document, the space above it
    and its line pitch as measured on the page (spacing), so that lines fall where the PDF has them."""
    parts = [extra] if extra else []
    if item.size and (item.kind == "heading" or abs(item.size - body) > 0.4):
        parts.append(f"font-size:{item.size:g}pt")
    if bold is False:
        parts.append("font-weight:normal")  # a heading in the PDF's regular weight stays regular
    if spacing is not None:
        before, pitch = spacing
        parts.append(f"margin:{before:.1f}pt 0 0 0")
        parts.append(f"line-height:{pitch:.1f}pt")
    return f' style="{";".join(parts)}"' if parts else ""


def _items_html(items: list[Item], body: float = 12.0, page_break: bool = False, top: float | None = None) -> str:
    """The page's items as HTML. With ``top`` (the page's top margin, for DOCX output) each block keeps the gap
    above it and its line pitch from the page, marked data-line-rule="exact" for html-editable."""
    out: list[str] = []
    in_list = False
    # Where the document's text cursor is, in page points: each block's first line box starts where the PDF
    # has its glyphs (less half the box padding), and the space before it is what is left above that.
    cursor = top
    for index, item in enumerate(items):
        extra = "break-before:page" if page_break and index == 0 else ""
        spacing = None
        exact = ""
        if cursor is not None and item.kind in {"heading", "paragraph", "list"}:
            glyphs = item.size or max(item.bottom - item.top, 0.0) or body
            pitch = statistics.median(item.pitches) if item.pitches else glyphs * 1.3
            pitch = max(pitch, glyphs * 1.05)
            start = item.top - (pitch - glyphs) / 2
            spacing = (min(max(0.0, start - cursor), 144.0), pitch)
            exact = ' data-line-rule="exact"'
            cursor = max(cursor, start) + pitch * (len(item.pitches) + 1)
        elif cursor is not None and item.bottom:
            gap = item.top - cursor
            if item.kind == "table" and gap > 1 and not extra and out:
                # A table has no space before it: the gap becomes the space after the block above.
                out[-1] = re.sub(
                    r"margin:([\d.]+)pt 0 0 0", rf"margin:\1pt 0 {min(gap, 144.0):.1f}pt 0", out[-1], count=1
                )
            cursor = item.bottom
        if item.kind == "list":
            if not in_list:
                out.append("<ul>")
                in_list = True
            text = _escape(item.text)
            out.append(
                f"<li{_size_style(item, body, extra, spacing)}{exact}>"
                f"{f'<strong>{text}</strong>' if item.bold else text}</li>"
            )
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if item.kind == "heading":
            out.append(
                f"<h{item.level}{_size_style(item, body, extra, spacing, item.bold)}{exact}>"
                f"{_escape(item.text)}</h{item.level}>"
            )
        elif item.kind == "paragraph":
            text = _escape(item.text)
            out.append(
                f"<p{_size_style(item, body, extra, spacing)}{exact}>"
                f"{f'<strong>{text}</strong>' if item.bold else text}</p>"
            )
        elif item.kind == "table":
            if extra:
                out.append(f'<p style="{extra};font-size:1pt"> </p>')
            out.append(_table_html(item.rows, item.columns, item.ruled, item))
        elif item.kind == "image" and item.image:
            width = round(item.width / 72 * 96)
            data = base64.b64encode(item.image).decode("ascii")
            style = f"width:{width}px" + (f";{extra}" if extra else "")
            out.append(f'<p><img src="data:image/png;base64,{data}" alt="" style="{style}"></p>')
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def pdf_to_office(
    input_path: str | Path, output_path: str | Path, ocr: bool = False
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    source, destination, errors = check_paths(input_path, output_path, {".pdf"}, {".docx", ".xlsx", ".pptx"})
    if errors:
        return False, {}, errors
    try:
        import pdfplumber  # noqa: F401
    except ImportError:
        return missing_dependency("pdf", "pdfplumber")
    try:
        analysis = analyse_pdf(source, ocr=ocr, images=destination.suffix.casefold() != ".xlsx")
    except ModuleNotFoundError:
        return missing_dependency("ocr", "rapidocr_onnxruntime")
    except Exception as exc:  # noqa: BLE001 - encrypted or damaged PDF
        code = (
            "PDF_ENCRYPTED"
            if "password" in str(exc).casefold() or "encrypt" in str(exc).casefold()
            else "INPUT_READ_FAILED"
        )
        return False, {}, [{"code": code, "message": f"Could not read {source.name}: {exc}"}]
    pages = analysis.pages
    if pages and all(page.scanned for page in pages) and not ocr:
        return (
            False,
            {"pages": len(pages), "scanned_pages": len(pages)},
            [
                {
                    "code": "PDF_NEEDS_OCR",
                    "message": "The PDF has no text layer (it is scanned). Install the ocr optional dependency "
                    "(pip install wps-ai-agent-cli[ocr]) and convert with --ocr.",
                }
            ],
        )
    suffix = destination.suffix.casefold()
    title = _escape(source.stem)
    if suffix == ".pptx":
        sections = []
        for page in pages:
            heading = next((i for i in page.items if i.kind == "heading"), None)
            # One slide per page: the page's other headings become bold paragraphs on it.
            rest = [
                Item("paragraph", i.text, top=i.top, bold=True, size=i.size) if i.kind == "heading" else i
                for i in page.items
                if i is not heading
            ]
            name = _escape(heading.text) if heading else f"第 {page.number} 页"
            sections.append(f"<section><h1>{name}</h1>\n{_items_html(rest, analysis.body_size)}\n</section>")
        body = "\n".join(sections)
    elif suffix == ".xlsx":
        tables = [(page, item) for page in pages for item in page.items if item.kind == "table"]
        if not tables:
            return (
                False,
                {"pages": len(pages)},
                [{"code": "NO_TABLES", "message": "The PDF has no ruled tables to put in a workbook."}],
            )
        body = "\n".join(
            f"<h2>第{page.number}页 表{index}</h2>\n{_table_html(item.rows, item.columns)}"
            for index, (page, item) in enumerate(tables, start=1)
        )
    else:
        parts = []
        if analysis.headers:
            parts.append(f'<div data-page="header">{_escape(_display(analysis.headers[0]))}</div>')
        if analysis.footers:
            parts.append(f'<div data-page="footer">{_escape(_display(analysis.footers[0]))}</div>')
        margin_top = analysis.margins[0] if analysis.margins else None
        parts += [_items_html(page.items, analysis.body_size, page.number > 1, margin_top) for page in pages]
        body = "\n".join(parts)
    css = ""
    if pages and suffix == ".docx":
        first = pages[0]
        css = f"@page{{size:{first.width:g}pt {first.height:g}pt"
        if analysis.margins:
            top, right, bottom, left = analysis.margins
            css += f";margin:{top:.0f}pt {right:.0f}pt {bottom:.0f}pt {left:.0f}pt"
        css += f"}}\nbody{{font-size:{analysis.body_size:g}pt}}\n"
    from .html_office import convert_html_to_office
    from .office_html import _page

    with tempfile.TemporaryDirectory() as tmp:
        page_file = Path(tmp) / f"{source.stem}.html"
        page_file.write_text(_page(title, body, css), encoding="utf-8")
        ok, data, errors = convert_html_to_office(page_file, destination, suffix.lstrip("."), use_browser=False)
    if not ok:
        return ok, data, errors
    counts = {"headings": 0, "paragraphs": 0, "list": 0, "table": 0, "image": 0}
    for page in pages:
        for item in page.items:
            key = {"heading": "headings", "paragraph": "paragraphs"}.get(item.kind, item.kind)
            counts[key] = counts.get(key, 0) + 1
    data.update(
        {
            "input_path": str(source),
            "pages": len(pages),
            "scanned_pages": sum(page.scanned for page in pages),
            "ocr_pages": sum(page.ocr for page in pages),
            "body_font_size": analysis.body_size,
            "running_headers": analysis.headers,
            "running_footers": analysis.footers,
            "recognised": counts,
            "warnings": analysis.warnings + [w for w in data.get("warnings", []) if "Unsupported element" not in w],
        }
    )
    return True, data, []
