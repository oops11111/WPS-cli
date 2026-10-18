"""Computed CSS styles applied to python-docx objects (P13-004).

html_editable builds the document's structure; the functions here give each paragraph, run, table, cell, image
and section the look the browser (or the built-in cascade) computed for the HTML element it came from: fonts,
sizes, colours, weight, slant, decoration, letter spacing, alignment, line height, spacing before and after,
indents, shading, borders, page breaks, column widths, cell padding and alignment, image sizes, and the page
size and margins of @page. In appearance mode (decision 9), absolutely positioned elements keep their position
as framed paragraphs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .html_styles import StyledDocument, color, first_font, is_bold, px

EMU_PER_PX = 9525
_TRANSPARENT_PARENTS = {"html", "body", "main", "document"}
PRINT_MARGIN_MM = 10
_PAGE_SIZES = {"a4": (210, 297), "a3": (297, 420), "a5": (148, 210), "letter": (215.9, 279.4), "legal": (215.9, 355.6)}


@dataclass
class Context:
    styled: StyledDocument | None
    appearance: bool = False
    last_space_after: float = 0.0
    applied: set[str] = field(default_factory=set)


def _qn(tag: str):
    from docx.oxml.ns import qn

    return qn(tag)


def _element(tag: str, **attrs: str):
    from docx.oxml import OxmlElement

    element = OxmlElement(tag)
    for key, value in attrs.items():
        element.set(_qn(key), value)
    return element


def run_props(context: Context, node) -> dict[str, Any]:
    if context.styled is None or node is None:
        return {}
    style = context.styled.style(node)
    size = px(style.get("font-size")) or 16.0
    props: dict[str, Any] = {
        "font": first_font(style.get("font-family")),
        "size": round(size * 0.75, 1),
        "color": color(style.get("color")),
        "bold": is_bold(style),
        "italic": style.get("font-style") in {"italic", "oblique"},
    }
    # Decorations, script position and an inline background are not inherited, but show on the text inside:
    # take them from the inline elements around the text too.
    chain = context.styled.inline_ancestors(node)
    inline = [n for n in chain if context.styled.style(n).get("display", "inline") == "inline"]
    decoration = " ".join(context.styled.style(n).get("text-decoration-line", "") for n in chain)
    if "underline" in decoration:
        props["underline"] = True
    if "line-through" in decoration:
        props["strike"] = True
    for element in inline:
        shade = color(context.styled.style(element).get("background-color"))
        if shade:
            props["shade"] = shade
            break
    spacing = px(style.get("letter-spacing"), size)
    if spacing:
        props["spacing"] = spacing * 0.75
    vertical = next(
        (v for v in (context.styled.style(n).get("vertical-align") for n in inline) if v in {"sub", "super"}), None
    )
    if vertical in {"sub", "super"}:
        props["subscript" if vertical == "sub" else "superscript"] = True
    context.applied.add("character")
    return props


def _style_turns_on(run, name: str) -> bool:
    from .office_html import _inherited

    try:
        return bool(_inherited(run, run._parent, name))
    except AttributeError:
        return False


def apply_run(run, props: dict[str, Any]) -> None:
    from docx.shared import Pt, RGBColor

    if not props:
        return
    font = run.font
    if props.get("font"):
        font.name = props["font"]
        fonts = run._r.get_or_add_rPr().find(_qn("w:rFonts"))
        if fonts is None:
            fonts = _element("w:rFonts")
            run._r.get_or_add_rPr().insert(0, fonts)
        for key in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            fonts.set(_qn(key), props["font"])
    if props.get("size"):
        font.size = Pt(props["size"])
    if props.get("color"):
        font.color.rgb = RGBColor.from_string(props["color"])
    for name in ("bold", "italic"):
        if props.get(name):
            setattr(font, name, True)
        elif name in props and _style_turns_on(run, name):
            # The paragraph style (Quote, Caption, a heading) would add it; the HTML did not ask for it.
            setattr(font, name, False)
    if props.get("underline"):
        font.underline = True
    if props.get("strike"):
        font.strike = True
    if props.get("subscript"):
        font.subscript = True
    if props.get("superscript"):
        font.superscript = True
    if props.get("shade"):
        run._r.get_or_add_rPr().append(
            _element("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": props["shade"]})
        )
    if props.get("spacing"):
        run._r.get_or_add_rPr().append(_element("w:spacing", **{"w:val": str(int(props["spacing"] * 20))}))


def _container_with(context: Context, node, ancestors, name: str):
    """The nearest enclosing block (not the page body) whose computed style has a visible value for name."""
    for ancestor in reversed(ancestors):
        if ancestor.tag in _TRANSPARENT_PARENTS:
            return None
        style = context.styled.style(ancestor)
        if name == "background-color" and color(style.get(name)):
            return ancestor
        if name == "border" and any(_border(style, side) for side in ("top", "right", "bottom", "left")):
            return ancestor
    return None


def _border(style: dict[str, str], side: str) -> tuple[float, str, str] | None:
    kind = style.get(f"border-{side}-style", "none")
    width = px(style.get(f"border-{side}-width")) or 0
    if kind in {"none", "hidden", ""} or width <= 0:
        return None
    word = {"dashed": "dashed", "dotted": "dotted", "double": "double"}.get(kind, "single")
    return width, word, color(style.get(f"border-{side}-color")) or "000000"


def _borders_xml(tag: str, borders: dict[str, tuple[float, str, str]]):
    container = _element(tag)
    for side in ("top", "left", "bottom", "right"):
        if side in borders:
            width, kind, hue = borders[side]
            container.append(
                _element(
                    f"w:{side}",
                    **{"w:val": kind, "w:sz": str(max(2, int(width * 0.75 * 8))), "w:space": "1", "w:color": hue},
                )
            )
    return container


def _left_offset(context: Context, node, ancestors) -> float | None:
    """How far the element starts right of the page's content edge, in CSS px."""
    styled = context.styled
    box = styled.box(node)
    if box is not None:
        body = next((a for a in ancestors if a.tag == "body"), None)
        body_box = styled.box(body) if body is not None else None
        base = body_box["x"] + (px(styled.style(body).get("padding-left")) or 0) if body_box else 8.0
        return max(0.0, box["x"] - base)
    total = 0.0
    for element in [*ancestors, node]:
        if element.tag in {"html", "body", "document", "ul", "ol"}:
            continue
        style = styled.style(element)
        total += (px(style.get("margin-left")) or 0) + (px(style.get("padding-left")) or 0)
        if element is not node:
            total += (_border(style, "left") or (0, "", ""))[0]
    return total


def apply_paragraph(paragraph, node, ancestors, context: Context, *, list_item: bool = False) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
    from docx.shared import Pt

    if context.styled is None or node is None:
        return
    style = context.styled.style(node)
    size = px(style.get("font-size")) or 16.0
    form = paragraph.paragraph_format
    align = {
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "end": WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "start": WD_ALIGN_PARAGRAPH.LEFT,
    }.get(style.get("text-align", "start"))
    if align is not None:
        form.alignment = align
    line = px(style.get("line-height"), size, size)
    if line:
        form.line_spacing_rule = WD_LINE_SPACING.AT_LEAST
        form.line_spacing = Pt(line * 0.75)
    else:
        # CSS "normal" is about 1.2 times the font size.
        form.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        form.line_spacing = 1.0
    top = (px(style.get("margin-top"), size) or 0) * 0.75
    bottom = (px(style.get("margin-bottom"), size) or 0) * 0.75
    # Adjacent vertical margins collapse in CSS: the larger one wins.
    form.space_before = Pt(max(0.0, top - context.last_space_after))
    form.space_after = Pt(bottom)
    context.last_space_after = bottom
    if not list_item:
        offset = _left_offset(context, node, ancestors)
        if offset:
            form.left_indent = Pt(offset * 0.75)
    indent = px(style.get("text-indent"), size)
    if indent:
        form.first_line_indent = Pt(indent * 0.75)
    if style.get("break-before") in {"page", "always", "left", "right"} or style.get("page-break-before") == "always":
        form.page_break_before = True
    props = paragraph._p.get_or_add_pPr()
    fill = color(style.get("background-color"))
    holder = node if fill else _container_with(context, node, ancestors, "background-color")
    if holder is not None:
        fill = color(context.styled.style(holder).get("background-color"))
        props.append(_element("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": fill}))
        context.applied.add("shading")
    border_holder = (
        node
        if any(_border(style, s) for s in ("top", "right", "bottom", "left"))
        else (_container_with(context, node, ancestors, "border"))
    )
    if border_holder is not None:
        holder_style = context.styled.style(border_holder)
        borders = {side: b for side in ("top", "left", "bottom", "right") if (b := _border(holder_style, side))}
        props.append(_borders_xml("w:pBdr", borders))
        context.applied.add("border")
    if context.appearance and style.get("position") in {"absolute", "fixed"}:
        box = context.styled.box(node)
        if box is not None:
            props.append(
                _element(
                    "w:framePr",
                    **{
                        "w:w": str(int(box["width"] * 15)),
                        "w:x": str(int(box["x"] * 15)),
                        "w:y": str(int(box["y"] * 15)),
                        "w:hAnchor": "page",
                        "w:vAnchor": "page",
                        "w:wrap": "around",
                    },
                )
            )
            context.applied.add("position")
    context.applied.add("paragraph")


def apply_table(table, node, grid, rows, context: Context, page_width_px: float) -> None:
    """Column widths, table width, cell shading, borders, padding and vertical alignment."""
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.shared import Emu

    # <thead> rows repeat at the top of each page, and say which rows are the header when read back.
    header_rows = sum(
        1
        for part in node.children
        if getattr(part, "tag", "") == "thead"
        for row in part.children
        if getattr(row, "tag", "") == "tr"
    )
    for row in table.rows[: min(header_rows, len(table.rows) - 1)]:
        row._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    if context.styled is None:
        table.style = "Table Grid"
        return
    styled = context.styled
    table_style = styled.style(node)
    widths = _column_widths(styled, node, grid, page_width_px)
    if widths:
        table.autofit = False
        total = sum(widths)
        scale = min(1.0, page_width_px / total) if total else 1.0
        for row in table.rows:
            for index, cell in enumerate(row.cells[: len(widths)]):
                cell.width = Emu(int(widths[index] * scale * EMU_PER_PX))
        for index, column in enumerate(table.columns):
            if index < len(widths):
                column.width = Emu(int(widths[index] * scale * EMU_PER_PX))
        context.applied.add("column widths")
    if table_style.get("margin-left") == "auto" or node.attrs.get("align") == "center":
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
    has_borders = node.attrs.get("border") not in {None, "", "0"}
    for row_index, row in enumerate(grid):
        for column_index, cell_node in enumerate(row):
            if cell_node is None:
                continue
            cell = table.cell(row_index, column_index)
            style = styled.style(cell_node)
            row_node = rows[row_index] if row_index < len(rows) else None
            fill = color(style.get("background-color")) or (
                color(styled.style(row_node).get("background-color")) if row_node is not None else None
            )
            props = cell._tc.get_or_add_tcPr()
            if fill:
                props.append(_element("w:shd", **{"w:val": "clear", "w:color": "auto", "w:fill": fill}))
                context.applied.add("cell shading")
            borders = {side: b for side in ("top", "left", "bottom", "right") if (b := _border(style, side))}
            if not borders and has_borders:
                borders = {side: (1.0, "single", "808080") for side in ("top", "left", "bottom", "right")}
            if borders:
                props.append(_borders_xml("w:tcBorders", borders))
                context.applied.add("cell borders")
            margins = _element("w:tcMar")
            for side, name in (("top", "top"), ("left", "left"), ("bottom", "bottom"), ("right", "right")):
                value = px(style.get(f"padding-{side}"))
                if value is not None:
                    margins.append(_element(f"w:{name}", **{"w:w": str(int(value * 15)), "w:type": "dxa"}))
            if len(margins):
                props.append(margins)
            vertical = {
                "middle": WD_CELL_VERTICAL_ALIGNMENT.CENTER,
                "bottom": WD_CELL_VERTICAL_ALIGNMENT.BOTTOM,
                "top": WD_CELL_VERTICAL_ALIGNMENT.TOP,
            }.get(style.get("vertical-align", ""))
            if vertical is not None:
                cell.vertical_alignment = vertical
    # Borders come from the CSS on each cell (or the border attribute): without them the browser draws no
    # grid lines, so the table has no table style either.
    table.style = None


def _column_widths(styled: StyledDocument, node, grid, page_width_px: float) -> list[float]:
    columns = len(grid[0]) if grid else 0
    widths: list[float | None] = [None] * columns
    for row in grid:
        for index, cell in enumerate(row):
            if cell is None or widths[index] is not None:
                continue
            if int(cell.attrs.get("colspan", "1") or "1") != 1:
                continue
            box = styled.box(cell)
            if box is not None:
                # Word's cell margins and borders take a little more room than the browser's cell box.
                widths[index] = box["width"] + 6
                continue
            declared = cell.attrs.get("width") or styled.style(cell).get("width")
            if declared:
                parent = px(styled.style(node).get("width")) or page_width_px
                value = px(declared if not declared.isdigit() else f"{declared}px", 16, parent)
                if value:
                    widths[index] = value
    # <col style="width:..."> gives the widths of columns no single cell sized.
    cols = [
        col
        for group in node.children
        if getattr(group, "tag", "") == "colgroup"
        for col in group.children
        if getattr(col, "tag", "") == "col"
    ]
    for index, col in enumerate(cols[:columns]):
        if widths[index] is None:
            declared = col.attrs.get("width") or styled.style(col).get("width")
            value = px(declared if declared and not declared.isdigit() else f"{declared}px", 16) if declared else None
            if value:
                widths[index] = value
    if all(width is None for width in widths):
        return []
    known = [w for w in widths if w is not None]
    fallback = (sum(known) / len(known)) if known else 100.0
    return [w if w is not None else fallback for w in widths]


def image_size(context: Context, node) -> tuple[int | None, int | None]:
    """The image's width and height in EMU, from the browser box, the attributes or the style."""
    if context.styled is not None:
        box = context.styled.box(node)
        if box is not None and box["width"] > 0:
            return int(box["width"] * EMU_PER_PX), int(box["height"] * EMU_PER_PX)
        style = context.styled.style(node)
    else:
        style = {}
    width = px(node.attrs.get("width") + "px" if (node.attrs.get("width") or "").isdigit() else style.get("width"))
    height = px(node.attrs.get("height") + "px" if (node.attrs.get("height") or "").isdigit() else style.get("height"))
    return (int(width * EMU_PER_PX) if width else None, int(height * EMU_PER_PX) if height else None)


def apply_page(document, styled: StyledDocument | None) -> float:
    """@page size and margins on the first section; returns the text width in CSS px."""
    from docx.shared import Mm

    section = document.sections[0]
    page = styled.page if styled is not None else {}
    size = page.get("size", "").casefold().split()
    if size:
        named = next((_PAGE_SIZES[token] for token in size if token in _PAGE_SIZES), None)
        lengths = [px(token) for token in size if px(token)]
        if named:
            width, height = named
            if "landscape" in size:
                width, height = height, width
            section.page_width, section.page_height = Mm(width), Mm(height)
        elif len(lengths) == 2:
            section.page_width, section.page_height = Mm(lengths[0] * 25.4 / 96), Mm(lengths[1] * 25.4 / 96)
    # Without @page margins, the browser prints with 10 mm margins (and html-render uses the same), not Word's
    # 1 inch; the document follows the browser.
    sides = {k: page.get(f"margin-{k}") for k in ("top", "right", "bottom", "left")}
    for side in ("top", "right", "bottom", "left"):
        value = px(sides.get(side)) if sides.get(side) else None
        setattr(section, f"{side}_margin", Mm(value * 25.4 / 96) if value is not None else Mm(PRINT_MARGIN_MM))
    width_emu = section.page_width - section.left_margin - section.right_margin
    return width_emu / EMU_PER_PX


def page_role(node) -> str | None:
    """'header' or 'footer' for elements marked as the page header or footer."""
    role = node.attrs.get("data-page", "").casefold()
    if role in {"header", "footer"}:
        return role
    classes = node.attrs.get("class", "").split()
    if "page-header" in classes:
        return "header"
    if "page-footer" in classes:
        return "footer"
    return None


def css_coverage(styled: StyledDocument | None) -> list[str]:
    """CSS the conversion cannot reproduce, for unsupported_css."""
    if styled is None:
        return []
    notes = set()
    text = styled.css_text
    if re.search(r"display\s*:\s*(flex|grid|inline-flex|inline-grid)", text):
        notes.add("flex and grid layout (paragraphs follow document order)")
    if re.search(r"position\s*:\s*(absolute|fixed)", text):
        notes.add("absolute positioning (kept only with --fidelity appearance)")
    if re.search(r"(box-shadow|border-radius|transform|filter|linear-gradient|radial-gradient)", text):
        notes.add("shadows, rounded corners, transforms, filters and gradients")
    if styled.mode == "cascade":
        notes.update(w.split(":", 1)[0] for w in styled.warnings if "Selectors" in w)
    return sorted(notes)
