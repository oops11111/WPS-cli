"""Conversion fidelity: one check for every conversion direction (P13-001, P13-002).

`fidelity_check(source, target)` reads both files into the same simple model (blocks of text with their kind,
level and run formatting; tables; images; slides; animations; sheets) and scores six aspects from 0 to 1:

- text: how much of the source's text appears in the target, in order;
- structure: headings by level, list items by level, tables and their shape, images, slides or pages;
- formatting: for each formatted source run (bold, italic, underline, strike, colour, size), whether the target
  has the same run with the same formatting;
- animations: entrance, exit and emphasis effects, their kind, target text and delay;
- data: table and sheet cell values;
- layout: both sides rendered to page images (HTML with Chromium, Office through WPS or LibreOffice as PDF, PDF
  directly) and compared page by page with the structural similarity index (SSIM).

Aspects that do not apply to a pair are reported as such. The thresholds of docs/PHASE13_PLAN.md depend on the
conversion group (`thresholds_for`), and the verdict uses them.
"""

from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

HTML = {".html", ".htm"}
OFFICE = {".docx", ".xlsx", ".pptx"}
WPS_FAMILY = {".doc", ".xls", ".ppt", ".wps", ".et", ".dps", ".odt", ".ods", ".odp"}
ASPECTS = ("text", "structure", "formatting", "animations", "data", "layout")


@dataclass
class Run:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    color: str | None = None
    size: float | None = None


@dataclass
class Block:
    kind: str  # heading, paragraph, list, table, image, title
    text: str = ""
    level: int = 0
    runs: list[Run] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class Model:
    kind: str
    blocks: list[Block] = field(default_factory=list)
    slides: int | None = None
    pages: int | None = None
    animations: list[tuple[str, str, str, int]] = field(default_factory=list)  # (class, effect, text, delay ms)
    sheets: dict[str, list[list[str]]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u200b", "")).strip()


def _plain(text: str) -> str:
    return re.sub(r"\s+", "", text)


# ---------------------------------------------------------------------------------------------- readers


def read_model(path: str | Path, *, use_browser: bool = True) -> Model:
    path = Path(path)
    suffix = path.suffix.casefold()
    if suffix in HTML:
        return _read_html(path, use_browser)
    if suffix == ".docx":
        return _read_docx(path)
    if suffix == ".pptx":
        return _read_pptx(path)
    if suffix == ".xlsx":
        return _read_xlsx(path)
    if suffix in {".csv", ".tsv"}:
        from .tabular import read_delimited

        rows, _meta = read_delimited(path)
        return Model("csv", [Block("table", rows=rows)], sheets={path.stem: rows})
    if suffix in {".md", ".markdown"}:
        from .markdown_convert import markdown_to_html_text

        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "page.html"
            html_path.write_text(markdown_to_html_text(path.read_text(encoding="utf-8")), encoding="utf-8")
            model = _read_html(html_path, use_browser=False)
        model.kind = "md"
        return model
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix in {".txt"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        return Model("text", [Block("paragraph", _norm(line)) for line in text.splitlines() if _norm(line)])
    raise ValueError(f"fidelity-check cannot read {suffix} files")


def _html_run(styled, node, text: str) -> Run:
    from .docx_styling import Context, run_props

    props = run_props(Context(styled), node)
    return Run(
        text,
        bool(props.get("bold")),
        bool(props.get("italic")),
        bool(props.get("underline")),
        bool(props.get("strike")),
        props.get("color"),
        props.get("size"),
    )


def _read_html(path: Path, use_browser: bool) -> Model:
    from .html_editable import _HEADINGS, _Node, _text, table_grid
    from .html_editable import cell_text as html_cell_text
    from .html_styles import load

    styled = load(path, use_browser=use_browser)
    model = Model("html")
    skip = {"script", "style", "head", "title", "svg"}

    def runs_of(node, original=None) -> list[Run]:
        """The node's text runs; ``original`` is the parsed element a synthetic copy stands for."""
        runs: list[Run] = []

        def collect(element):
            for child in element.children:
                if isinstance(child, str):
                    if _norm(child):
                        owner = original if element is node and original is not None else element
                        runs.append(_html_run(styled, owner, _norm(child)))
                elif child.tag not in {"ul", "ol", "table"} | skip:
                    collect(child)

        collect(node)
        return runs

    def visit(node, list_level: int = 0) -> None:
        for child in node.children:
            if isinstance(child, str):
                if _norm(child) and node.tag not in skip:
                    model.blocks.append(Block("paragraph", _norm(child), runs=[_html_run(styled, node, _norm(child))]))
                continue
            tag = child.tag
            if tag in skip or child.attrs.get("class", "").split().count("notes"):
                if "notes" in child.attrs.get("class", "").split():
                    model.notes.append(_norm(_text(child)))
                continue
            if tag in _HEADINGS:
                if _norm(_text(child)):
                    model.blocks.append(Block("heading", _norm(_text(child)), _HEADINGS[tag], runs_of(child)))
            elif tag in {"ul", "ol"}:
                for item in child.children:
                    if isinstance(item, _Node) and item.tag == "li":
                        own = _Node(
                            "li",
                            item.attrs,
                            [c for c in item.children if not (isinstance(c, _Node) and c.tag in {"ul", "ol"})],
                        )
                        if _norm(_text(own)):
                            model.blocks.append(Block("list", _norm(_text(own)), list_level + 1, runs_of(own, item)))
                        for nested in item.children:
                            if isinstance(nested, _Node) and nested.tag in {"ul", "ol"}:
                                visit(_Node("div", children=[nested]), list_level + 1)
            elif tag == "table":
                grid, _merges = table_grid(child)
                rows = [[html_cell_text(c) if c is not None else "" for c in row] for row in grid]
                model.blocks.append(Block("table", rows=rows))
                for row in grid:
                    for cell in row:
                        if cell is not None and _norm(_text(cell)):
                            model.blocks.append(Block("cell-run", _norm(_text(cell)), runs=runs_of(cell)))
            elif tag == "img":
                model.blocks.append(Block("image", child.attrs.get("alt", "")))
            elif tag == "section":
                model.slides = (model.slides or 0) + 1
                visit(child, list_level)
            elif tag in {"p", "blockquote", "pre", "figcaption", "caption", "dt", "dd", "summary", "address"}:
                inner_images = [n for n in _walk_nodes(child) if n.tag == "img"]
                if _norm(_text(child)):
                    model.blocks.append(Block("paragraph", _norm(_text_without_alt(child)), runs=runs_of(child)))
                for image in inner_images:
                    model.blocks.append(Block("image", image.attrs.get("alt", "")))
            else:
                visit(child, list_level)

    visit(styled.root)
    model.blocks = [b for b in model.blocks if b.kind in {"table", "image"} or b.text]
    # Animations, as html_slides reads them.
    from .html_slides import _animation_of, parse_css

    css = parse_css(styled.css_text and f"<style>{styled.css_text}</style>")
    # Start times as a slide plays them: an "after" effect starts when the previous one ends (html_slides).
    previous: tuple[int, int] | None = None  # start, duration
    for node in _walk_nodes(styled.root):
        if node.tag == "section":
            previous = None
        animation = _animation_of(node, css)
        if animation and _norm(_text(node)):
            if animation.trigger == "click":
                previous = None
            start = animation.delay
            if animation.trigger == "after" and previous is not None:
                start = previous[0] + max(1, previous[1]) + animation.delay
            previous = (start, animation.duration)
            model.animations.append((animation.kind, animation.effect, _norm(_text(node))[:40], start))
    return model


def _walk_nodes(node):
    from .html_editable import _walk

    return list(_walk(node))


def _text_without_alt(node) -> str:
    from .html_editable import _Node

    parts: list[str] = []

    def collect(element):
        for child in element.children:
            if isinstance(child, str):
                parts.append(child)
            elif isinstance(child, _Node) and child.tag == "br":
                parts.append(" ")
            elif isinstance(child, _Node) and child.tag != "img":
                collect(child)

    collect(node)
    return "".join(parts)


def _docx_run(run) -> Run:
    """A run's effective formatting: its own, else its character style's, else its paragraph style's."""
    from .office_html import _inherited

    paragraph = run._parent
    hue = None
    try:
        if run.font.color is not None and run.font.color.type is not None and run.font.color.rgb is not None:
            hue = str(run.font.color.rgb)
    except (AttributeError, ValueError):
        hue = None
    size = _inherited(run, paragraph, "size")
    return Run(
        run.text,
        bool(_inherited(run, paragraph, "bold")),
        bool(_inherited(run, paragraph, "italic")),
        bool(_inherited(run, paragraph, "underline")),
        bool(_inherited(run, paragraph, "strike")),
        hue,
        size.pt if size else None,
    )


def _read_docx(path: Path) -> Model:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(path)
    model = Model("docx")
    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph = Paragraph(child, document)
            text = _norm(paragraph.text)
            style = paragraph.style.name if paragraph.style is not None else ""
            images = len(child.findall(".//" + qn("w:drawing")))
            runs = [_docx_run(r) for r in paragraph.runs if r.text]
            if text:
                match = re.match(r"Heading (\d)", style)
                if match:
                    model.blocks.append(Block("heading", text, int(match.group(1)), runs))
                elif style.startswith("List"):
                    level = re.search(r"(\d)$", style)
                    model.blocks.append(Block("list", text, int(level.group(1)) if level else 1, runs))
                elif style == "Title":
                    model.blocks.append(Block("heading", text, 1, runs))
                else:
                    model.blocks.append(Block("paragraph", text, 0, runs))
            for _ in range(images):
                model.blocks.append(Block("image"))
        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            rows = []
            seen: set[int] = set()
            unique = []
            for row in table.rows:
                cells = []
                for cell in row.cells:
                    # Merged cells repeat across the rows and columns they cover: count each once.
                    key = id(cell._tc)
                    cells.append("" if key in seen else _norm(cell.text))
                    if key not in seen:
                        unique.append(cell)
                    seen.add(key)
                rows.append(cells)
            model.blocks.append(Block("table", rows=rows))
            for cell in unique:
                runs = [_docx_run(r) for p in cell.paragraphs for r in p.runs if r.text.strip()]
                if runs:
                    model.blocks.append(Block("cell-run", _norm(cell.text), runs=runs))
    # Page header and footer text is content too (html-editable puts data-page="header"/"footer" there).
    for section in document.sections[:1]:
        for part in (section.header, section.footer):
            if part.is_linked_to_previous:
                continue
            for paragraph in part.paragraphs:
                if _norm(paragraph.text):
                    model.blocks.append(
                        Block("paragraph", _norm(paragraph.text), 0, [_docx_run(r) for r in paragraph.runs if r.text])
                    )
    model.pages = None
    return model


_PRESETS = {
    ("entr", "10"): "fade",
    ("entr", "2"): "fly",
    ("entr", "53"): "zoom",
    ("exit", "10"): "fade",
    ("exit", "2"): "fly",
    ("exit", "53"): "zoom",
    ("emph", "6"): "pulse",
    ("emph", "8"): "spin",
}


def _read_pptx(path: Path) -> Model:
    from pptx import Presentation

    presentation = Presentation(path)
    model = Model("pptx", slides=len(presentation.slides))
    p = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    for slide in presentation.slides:
        texts: dict[int, list[str]] = {}
        title_id = slide.shapes.title.shape_id if slide.shapes.title is not None else None
        for shape in slide.shapes:
            if shape.has_text_frame:
                paragraphs = [_norm("".join(r.text for r in para.runs)) for para in shape.text_frame.paragraphs]
                texts[shape.shape_id] = paragraphs
                for para in shape.text_frame.paragraphs:
                    text = _norm("".join(r.text for r in para.runs))
                    if not text:
                        continue
                    runs = [_docx_like_run(r) for r in para.runs if r.text]
                    if shape.shape_id == title_id or shape.name.startswith("Title"):
                        model.blocks.append(Block("heading", text, 1, runs))
                    elif _bulleted(shape, para):
                        model.blocks.append(Block("list", text, para.level + 1, runs))
                    else:
                        model.blocks.append(Block("paragraph", text, 0, runs))
            elif shape.has_table:
                texts[shape.shape_id] = [" ".join(_norm(c.text) for row in shape.table.rows for c in row.cells)]
                rows = []
                for row in shape.table.rows:
                    rows.append([_norm(cell.text) if not cell.is_spanned else "" for cell in row.cells])
                model.blocks.append(Block("table", rows=rows))
                for row in shape.table.rows:
                    for cell in row.cells:
                        runs = [_docx_like_run(r) for p in cell.text_frame.paragraphs for r in p.runs if r.text.strip()]
                        if runs and not cell.is_spanned:
                            model.blocks.append(Block("cell-run", _norm(cell.text), runs=runs))
            elif shape.shape_type == 13:
                model.blocks.append(Block("image"))
        if slide.has_notes_slide and _norm(slide.notes_slide.notes_text_frame.text):
            model.notes.append(_norm(slide.notes_slide.notes_text_frame.text))
        timing = slide._element.find(f"{p}timing")
        if timing is None:
            continue
        for node in timing.iter(f"{p}cTn"):
            preset_class = node.get("presetClass")
            if not preset_class:
                continue
            target = node.find(f".//{p}spTgt")
            if target is None:
                continue
            spid = int(target.get("spid"))
            paragraph = target.find(f".//{p}pRg")
            lines = texts.get(spid, [])
            if paragraph is not None and int(paragraph.get("st")) < len(lines):
                text = lines[int(paragraph.get("st"))]
            else:
                text = " ".join(t for t in lines if t)
            delay = node.find(f"{p}stCondLst/{p}cond")
            kind = {"entr": "entrance", "exit": "exit", "emph": "emphasis"}.get(preset_class, preset_class)
            effect = _PRESETS.get((preset_class, node.get("presetID")), node.get("presetID"))
            model.animations.append((kind, effect, text[:40], int(delay.get("delay", "0")) if delay is not None else 0))
    return model


def _bulleted(shape, paragraph) -> bool:
    props = paragraph._p.pPr
    a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    if props is not None and props.find(f"{a}buChar") is not None:
        return True
    if props is not None and props.find(f"{a}buNone") is not None:
        return False
    if paragraph.level:
        return True
    try:
        return shape.is_placeholder and shape.placeholder_format.idx == 1
    except Exception:  # noqa: BLE001
        return False


def _docx_like_run(run) -> Run:
    font = run.font
    hue = None
    try:
        if font.color is not None and font.color.type is not None:
            hue = str(font.color.rgb)
    except AttributeError:
        hue = None
    return Run(
        run.text,
        bool(font.bold),
        bool(font.italic),
        bool(font.underline),
        False,
        hue,
        font.size.pt if font.size else None,
    )


def _read_xlsx(path: Path) -> Model:
    from openpyxl import load_workbook

    workbook = load_workbook(path, data_only=False)
    model = Model("xlsx")
    for sheet in workbook.worksheets:
        rows = []
        for row in sheet.iter_rows():
            rows.append([_cell_display(c) for c in row])
        while rows and not any(rows[-1]):
            rows.pop()
        model.sheets[sheet.title] = rows
        model.blocks.append(Block("heading", sheet.title, 2))
        model.blocks.append(Block("table", rows=rows))
        model.blocks += [Block("image") for _ in getattr(sheet, "_images", [])]
    return model


def _cell_display(cell) -> str:
    value = cell.value
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        pattern = (cell.number_format or "").casefold()
        if re.fullmatch(r"yyyy([/.-])m{1,2}\1d{1,2}", pattern):
            separator = re.search(r"[/.-]", pattern).group(0)
            return value.strftime(f"%Y{separator}%m{separator}%d")
        return value.strftime("%Y-%m-%d")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, (int, float)) and cell.number_format and "%" in cell.number_format:
        decimals = len(cell.number_format.split(".")[1].rstrip("%")) if "." in cell.number_format else 0
        return f"{value * 100:.{decimals}f}%"
    fixed = re.fullmatch(r"0\.(0+)", cell.number_format or "")
    if isinstance(value, (int, float)) and fixed:
        return f"{value:.{len(fixed.group(1))}f}"
    if isinstance(value, (int, float)) and cell.number_format and "#,##0" in cell.number_format:
        decimals = len(cell.number_format.split(".")[1]) if "." in cell.number_format else 0
        text = f"{value:,.{decimals}f}"
        symbol = re.match(r'"(.)"', cell.number_format)
        return (symbol.group(1) if symbol else "") + text
    return str(value)


def _read_pdf(path: Path) -> Model:
    model = Model("pdf")
    try:
        import pdfplumber
    except ImportError:
        pdfplumber = None
    if pdfplumber is not None:
        # As pdf_convert reads it: running headers, footers and page numbers are not content.
        from .pdf_convert import analyse_pdf

        analysis = analyse_pdf(path, images=True)
        model.pages = len(analysis.pages)
        for page in analysis.pages:
            for item in page.items:
                if item.kind == "table":
                    model.blocks.append(Block("table", rows=item.rows))
                elif item.kind == "image":
                    model.blocks.append(Block("image"))
                elif item.kind == "list":
                    model.blocks.append(Block("list", _norm(item.text), 1))
                else:
                    model.blocks.append(Block(item.kind, _norm(item.text), item.level))
        return model
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(path))
    model.pages = len(document)
    for page in document:
        for line in page.get_textpage().get_text_range().splitlines():
            if _norm(line):
                model.blocks.append(Block("paragraph", _norm(line)))
    return model


# ---------------------------------------------------------------------------------------------- comparisons


def _texts(model: Model) -> list[str]:
    values = []
    for block in model.blocks:
        if block.kind == "table":
            values += [c for row in block.rows for c in row if c]
        elif block.kind not in {"image", "cell-run"} and block.text:
            values.append(block.text)
    return values


def score_text(source: Model, target: Model) -> tuple[float, list[str]]:
    target_text = _plain(" ".join(_texts(target)))
    total = found = 0
    missing = []
    for piece in _texts(source):
        plain = _plain(piece)
        if not plain:
            continue
        total += len(plain)
        if plain in target_text:
            found += len(plain)
            continue
        matcher = SequenceMatcher(None, plain, target_text, autojunk=False)
        size = sum(block.size for block in matcher.get_matching_blocks())
        found += size
        if size < len(plain):
            missing.append(piece[:60])
    return (found / total if total else 1.0), missing[:10]


def _structure(model: Model) -> dict[str, int]:
    counts: dict[str, int] = {}
    for block in model.blocks:
        if block.kind == "heading":
            key = f"heading {block.level}"
        elif block.kind == "list":
            key = f"list item level {block.level}"
        elif block.kind == "table":
            key = f"table {len(block.rows)}x{max((len(r) for r in block.rows), default=0)}"
        elif block.kind == "image":
            key = "image"
        else:
            continue
        counts[key] = counts.get(key, 0) + 1
    if model.slides:
        counts["slides"] = model.slides
    return counts


def score_structure(source: Model, target: Model, *, levels: bool = True) -> tuple[float, dict[str, Any]]:
    want, have = _structure(source), _structure(target)
    slides = target.slides or source.slides
    if slides:
        # A slide has one title: heading levels collapse, and further headings on a slide are body text.
        for counts in (want, have):
            headings = sum(v for k, v in list(counts.items()) if k.startswith("heading ") and counts.pop(k))
            if headings:
                counts["heading"] = min(headings, slides)
    if not levels:
        want = {re.sub(r" \d+$| level \d+$", "", k): v for k, v in want.items()}
        have = {re.sub(r" \d+$| level \d+$", "", k): v for k, v in have.items()}
    total = sum(want.values())
    matched = sum(min(count, have.get(key, 0)) for key, count in want.items())
    differences = {
        k: {"source": want.get(k, 0), "target": have.get(k, 0)}
        for k in set(want) | set(have)
        if want.get(k, 0) != have.get(k, 0)
    }
    return (matched / total if total else 1.0), differences


def _char_props(model: Model, cells: bool) -> tuple[str, list[Run | None]]:
    """The text of the model's table cells (cells=True) or of everything else, with each character's run."""
    text, props = [], []
    for block in model.blocks:
        if (block.kind == "cell-run") != cells:
            continue
        for run in block.runs:
            plain = _plain(run.text)
            text.append(plain)
            props += [run] * len(plain)
    return "".join(text), props


def score_formatting(source: Model, target: Model) -> tuple[float, list[str]]:
    streams = {flag: _char_props(target, flag) for flag in (False, True)}
    positions = {False: 0, True: 0}
    checks = passed = 0
    problems = []
    for block in source.blocks:
        cells = block.kind == "cell-run"
        target_text, target_props = streams[cells]
        for run in block.runs:
            plain = _plain(run.text)
            if not plain:
                continue
            wanted = {
                "bold": run.bold,
                "italic": run.italic,
                "underline": run.underline,
                "strike": run.strike,
            }
            if run.color and run.color not in {"000000"}:
                wanted["color"] = run.color
            if run.size:
                wanted["size"] = run.size
            if (
                not any(v for k, v in wanted.items() if k in {"bold", "italic", "underline", "strike"})
                and "color" not in wanted
            ):
                if "size" not in wanted:
                    continue
            index = target_text.find(plain, positions[cells])
            if index < 0:
                index = target_text.find(plain)
            if index < 0:
                continue
            positions[cells] = index + len(plain)
            got = target_props[index]
            for name, value in wanted.items():
                checks += 1
                actual = getattr(got, name) if got is not None else None
                if name == "size":
                    ok = actual is not None and abs(actual - value) <= 1.0
                elif name == "color":
                    ok = (actual or "000000").upper() == value.upper()
                else:
                    ok = bool(actual) == bool(value)
                passed += ok
                if not ok and len(problems) < 10:
                    problems.append(f"{plain[:20]}: {name} {value!r} -> {actual!r}")
    return (passed / checks if checks else 1.0), problems


def score_animations(source: Model, target: Model) -> tuple[float, list[str]]:
    if not source.animations:
        return 1.0, []
    remaining = list(target.animations)
    matched = 0
    problems = []
    for kind, effect, text, delay in source.animations:
        hit = next(
            (
                a
                for a in remaining
                if a[0] == kind and a[1] == effect and _plain(text)[:10] in _plain(a[2]) and abs(a[3] - delay) <= 50
            ),
            None,
        )
        if hit:
            matched += 1
            remaining.remove(hit)
        else:
            problems.append(f"{kind} {effect} on {text[:20]!r} after {delay} ms")
    return matched / len(source.animations), problems[:10]


def _value(text: str) -> str:
    """A cell's value for comparison: numbers by value (1.2e4 = 12000, 3.50 = 3.5), dates as ISO dates."""
    plain = _plain(text)
    number = re.fullmatch(r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?", plain)
    if number:
        return repr(float(plain))
    date = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", plain)
    if date:
        return f"{int(date.group(1)):04d}-{int(date.group(2)):02d}-{int(date.group(3)):02d}"
    return plain


def score_data(source: Model, target: Model) -> tuple[float, list[str]]:
    want = [[c for c in row] for b in source.blocks if b.kind == "table" for row in b.rows]
    raw_cells = [c for b in target.blocks if b.kind == "table" for row in b.rows for c in row if c]
    have_cells = [_value(c) for c in raw_cells]
    # A cell can hold a nested table's rows as further lines: its first line is the cell's own text.
    have_cells += [_value(c.split("\n", 1)[0]) for c in raw_cells if "\n" in c and c.split("\n", 1)[0].strip()]
    if not want:
        return 1.0, []
    pool = {}
    for cell in have_cells:
        pool[cell] = pool.get(cell, 0) + 1
    total = matched = 0
    missing = []
    for row in want:
        for cell in row:
            plain = _value(cell)
            if not plain:
                continue
            total += 1
            if pool.get(plain, 0) > 0:
                pool[plain] -= 1
                matched += 1
            elif len(missing) < 10:
                missing.append(cell[:30])
    return (matched / total if total else 1.0), missing


# ---------------------------------------------------------------------------------------------- layout


def ssim(first, second) -> float:
    """Mean structural similarity of two greyscale images (numpy arrays of the same shape), 7x7 windows."""
    import numpy as np

    a = first.astype(np.float64)
    b = second.astype(np.float64)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    window = 7

    def mean(image):
        padded = np.pad(image, ((1, 0), (1, 0)))
        total = padded.cumsum(0).cumsum(1)
        sums = total[window:, window:] - total[:-window, window:] - total[window:, :-window] + total[:-window, :-window]
        return sums / (window * window)

    mu_a, mu_b = mean(a), mean(b)
    var_a = mean(a * a) - mu_a**2
    var_b = mean(b * b) - mu_b**2
    covariance = mean(a * b) - mu_a * mu_b
    value = ((2 * mu_a * mu_b + c1) * (2 * covariance + c2)) / ((mu_a**2 + mu_b**2 + c1) * (var_a + var_b + c2))
    return float(value.mean())


def _pdf_pages(pdf: Path, width: int) -> list[Any]:
    import pypdfium2 as pdfium

    pages = []
    document = pdfium.PdfDocument(str(pdf))
    try:
        for page in document:
            scale = width / page.get_width()
            pages.append(page.render(scale=scale).to_pil().convert("L"))
            page.close()
    finally:
        document.close()
    return pages


def _office_pdf(path: Path, out_dir: Path, renderer: str) -> tuple[Path | None, str | None]:
    if renderer == "wps":
        from .wps_convert import wps_convert

        output = out_dir / (path.stem + ".pdf")
        ok, _data, errors = wps_convert(path, output)
        return (output, None) if ok else (None, "; ".join(e["message"] for e in errors))
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None, "LibreOffice (soffice) is not installed"
    profile = Path(tempfile.mkdtemp(prefix="wps-lo-profile-"))
    try:
        subprocess.run(
            [
                soffice,
                f"-env:UserInstallation={profile.as_uri()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(path),
            ],
            capture_output=True,
            timeout=240,
            check=False,
        )
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    output = out_dir / (path.stem + ".pdf")
    return (output, None) if output.is_file() else (None, "LibreOffice did not produce a PDF")


def _html_images(path: Path, out_dir: Path, width: int, slides: bool) -> tuple[list[Any] | None, str | None]:
    from PIL import Image

    if slides:
        from .html_styles import load

        shots = out_dir / "sections"
        shots.mkdir(exist_ok=True)
        styled = load(path, screenshots_dir=shots, viewport=(1280, 720))
        if styled.mode != "browser" or not styled.section_screenshots:
            return None, "a Chromium browser is needed to render the HTML slides"
        return [Image.open(s).convert("L") for s in styled.section_screenshots], None
    from .html_render import render_html

    output = out_dir / (path.stem + "-browser.pdf")
    ok, _data, errors = render_html(path, output, "pdf", margin_mm=10)
    if not ok:
        return None, errors[0]["message"] if errors else "the HTML could not be rendered"
    return _pdf_pages(output, width), None


def _images_for(
    path: Path, out_dir: Path, renderer: str, width: int, slides: bool
) -> tuple[list[Any] | None, str | None]:
    suffix = path.suffix.casefold()
    if suffix in HTML:
        return _html_images(path, out_dir, width, slides)
    if suffix == ".pdf":
        return _pdf_pages(path, width), None
    if suffix in OFFICE | WPS_FAMILY:
        pdf, problem = _office_pdf(path, out_dir, renderer)
        return (_pdf_pages(pdf, width), None) if pdf else (None, problem)
    if suffix == ".png":
        from PIL import Image

        return [Image.open(path).convert("L")], None
    return None, f"no renderer for {suffix}"


def score_layout(source: Path, target: Path, renderer: str = "auto") -> dict[str, Any]:
    try:
        import numpy as np
    except ImportError:
        return {
            "status": "unavailable",
            "reason": "install the fidelity optional dependency (numpy) for the layout check",
        }
    if renderer == "auto":
        renderer = (
            "wps"
            if sys.platform == "win32" and os.environ.get("WPS_AGENT_FIDELITY_RENDERER") != "libreoffice"
            else "libreoffice"
        )
    if renderer == "none":
        return {"status": "skipped", "reason": "renderer none"}
    width = 800
    slides = target.suffix.casefold() == ".pptx" or source.suffix.casefold() == ".pptx"
    with tempfile.TemporaryDirectory(prefix="wps-fidelity-") as tmp:
        work = Path(tmp)
        (work / "a").mkdir()
        (work / "b").mkdir()
        first, problem = _images_for(source, work / "a", renderer, width, slides)
        if first is None:
            return {"status": "unavailable", "reason": problem, "renderer": renderer}
        second, problem = _images_for(target, work / "b", renderer, width, slides)
        if second is None:
            return {"status": "unavailable", "reason": problem, "renderer": renderer}
        scores = []
        for a, b in zip(first, second, strict=False):
            b = b.resize(a.size)
            scores.append(round(ssim(np.asarray(a), np.asarray(b)), 4))
        missing = abs(len(first) - len(second))
        mean = sum(scores) / (len(scores) + missing) if scores else 0.0
        return {
            "status": "measured",
            "renderer": renderer,
            "score": round(mean, 4),
            "pages": {"source": len(first), "target": len(second)},
            "page_scores": scores,
            "missing_fonts": missing_fonts(),
        }


def missing_fonts() -> list[str]:
    """The test fonts (decision 5) that are not installed, as far as fc-list or the Windows font folder tells."""
    wanted = {"Microsoft YaHei": ["msyh"], "Noto Sans CJK SC": ["notosanscjk"]}
    if sys.platform == "win32":
        folder = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        names = " ".join(p.name.casefold() for p in folder.glob("*")) if folder.is_dir() else ""
        return [font for font, keys in wanted.items() if not any(k in names for k in keys)]
    if shutil.which("fc-list"):
        listing = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, check=False).stdout
        return [font for font in wanted if font not in listing]
    return list(wanted)


# ---------------------------------------------------------------------------------------------- verdict


def group_of(source: Path, target: Path) -> str:
    a, b = source.suffix.casefold(), target.suffix.casefold()
    if a in HTML or b in HTML:
        if (a in OFFICE and b in HTML) or (a in HTML and b in OFFICE):
            return "A"
    if a in WPS_FAMILY or b in WPS_FAMILY or b in {".png"}:
        return "B"
    if a in {".csv", ".tsv", ".md", ".markdown"} or b in {".csv", ".tsv", ".md", ".markdown"}:
        return "C"
    if a == ".pdf":
        return "E"
    if a in OFFICE and b in OFFICE and a != b:
        return "D"
    return "A" if a in HTML or b in HTML else "B"


THRESHOLDS = {
    "A": {"text": 1.0, "structure": 1.0, "formatting": 1.0, "animations": 1.0, "data": 1.0, "layout": 0.90},
    "B": {"text": 1.0, "structure": 1.0, "layout": 0.95},
    "C": {"text": 1.0, "structure": 1.0, "data": 1.0},
    "D": {"text": 1.0, "data": 1.0},
    "E": {"text": 1.0, "data": 0.98, "layout": 0.85},
}


def thresholds_for(source: Path, target: Path) -> dict[str, float]:
    return dict(THRESHOLDS[group_of(source, target)])


def fidelity_check(
    source: str | Path,
    target: str | Path,
    *,
    renderer: str = "auto",
    layout: bool = True,
    baseline: float | None = None,
    use_browser: bool = True,
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    source, target = Path(source), Path(target)
    for path in (source, target):
        if not path.is_file():
            return False, {}, [{"code": "INPUT_FILE_NOT_FOUND", "message": f"File not found: {path}"}]
    try:
        first = read_model(source, use_browser=use_browser)
        second = read_model(target, use_browser=use_browser)
    except ValueError as exc:
        return False, {}, [{"code": "UNSUPPORTED_FORMAT", "message": str(exc)}]
    except ImportError as exc:
        return False, {}, [{"code": "CONVERTER_UNAVAILABLE", "message": f"Missing optional dependency: {exc.name}"}]
    group = group_of(source, target)
    thresholds = THRESHOLDS[group]
    if "pptx" not in {first.kind, second.kind}:
        # Sections are slides only when one side is a presentation.
        first.slides = second.slides = None
    if second.kind == "xlsx" and first.kind != "xlsx":
        # A workbook holds the source's tables (and images); its other text is reported as omitted by the
        # converter, and sheet names are cut to 31 characters: compare the tables only.
        first.blocks = [b for b in first.blocks if b.kind in {"table", "image"}]
        second.blocks = [b for b in second.blocks if b.kind in {"table", "image"}]
    if first.kind == "xlsx" and second.kind in {"docx", "pptx"}:
        # A worksheet range made into a table: compare with the sheet the table came from.
        tables = [b for b in first.blocks if b.kind == "table"]
        if len(tables) > 1:
            best = max(tables, key=lambda t: score_data(Model("xlsx", [t]), second)[0])
            first.blocks = [best]
    if {first.kind, second.kind} == {"csv", "xlsx"}:
        # A delimited file holds one sheet and no sheet name: compare the first sheet's cells only.
        for model in (first, second):
            if model.kind == "xlsx":
                tables = [b for b in model.blocks if b.kind == "table"]
                model.blocks = tables[:1]
    aspects: dict[str, Any] = {}
    text, missing = score_text(first, second)
    aspects["text"] = {"score": round(text, 4), "missing": missing}
    levels = group in {"A", "B", "C"} and not (group == "C" and source.suffix.casefold() in {".csv", ".tsv"})
    structure, differences = score_structure(first, second, levels=levels)
    aspects["structure"] = {"score": round(structure, 4), "differences": differences}
    formatting, problems = score_formatting(first, second)
    aspects["formatting"] = (
        {"score": round(formatting, 4), "problems": problems}
        if group in {"A", "B"} and second.kind != "xlsx"
        else {"status": "not applicable"}
    )
    if first.animations or second.animations:
        animations, problems = score_animations(first, second)
        aspects["animations"] = {"score": round(animations, 4), "missing": problems}
    else:
        aspects["animations"] = {"status": "not applicable"}
    if any(b.kind == "table" for b in first.blocks):
        data, missing_cells = score_data(first, second)
        aspects["data"] = {"score": round(data, 4), "missing": missing_cells}
    else:
        aspects["data"] = {"status": "not applicable"}
    if layout and "layout" in thresholds:
        aspects["layout"] = score_layout(source, target, renderer)
    else:
        aspects["layout"] = {"status": "not applicable" if "layout" not in thresholds else "skipped"}
    verdict: dict[str, Any] = {}
    for name, minimum in thresholds.items():
        aspect = aspects.get(name, {})
        if "score" not in aspect:
            continue
        if name == "layout" and aspect.get("renderer") == "libreoffice":
            # LibreOffice is the regression check, not the official threshold (decision 1).
            if baseline is not None:
                verdict[name] = aspect["score"] >= baseline - 0.02
                aspect["baseline"] = baseline
            continue
        verdict[name] = aspect["score"] >= minimum
    passed = all(verdict.values())
    data = {
        "source": str(source),
        "target": str(target),
        "group": group,
        "thresholds": thresholds,
        "aspects": aspects,
        "verdict": verdict,
        "passed": passed,
    }
    return True, data, []


def table_rows_from_csv_text(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text)))


def zip_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return archive.namelist()
