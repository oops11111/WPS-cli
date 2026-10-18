"""Convert a semantic HTML slide deck into an editable presentation (pptx), with its animations.

Each <section>, and each <h1>/<h2> outside a section, starts a slide. The first h1/h2 is the slide's title;
paragraphs, list items (with their nesting level) and h3 to h6 become the body, keeping bold, italic,
underline, strike-through and colour. Tables become slide tables (with merged cells), local images become
pictures and local video or audio becomes media; they share the space below the title. <aside class="notes">
becomes the speaker notes.

CSS animations become entrance effects. An element whose class (or style attribute) gives it an
`animation` with a known @keyframes is animated: keyframes that move it (translateX/translateY) fly in from
that side, keyframes that scale it zoom in, anything else fades in. Every effect starts with the slide, after
its CSS animation-delay, as the browser would play it. A slide's transition comes from data-transition (fade,
push, wipe, cover, split, dissolve, zoom, cut) or, without one, from a CSS `transition` on the section (fade).
What cannot be represented (hover effects, SVG, scripts, unavailable media) is reported in the warnings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .html_editable import (
    INLINE_FORMATS,
    _Node,
    _text,
    _TreeParser,
    _walk,
    cell_text,
    local_image,
    style_formats,
    table_grid,
    validate_office_paths,
)
from .html_text import decode_html_bytes

MAX_SLIDES = 200
_TEXT_BLOCKS = {"p", "li", "h3", "h4", "h5", "h6", "blockquote", "pre", "dt", "dd", "figcaption"}
_MEDIA = {"video": "video/mp4", "audio": "audio/mpeg"}
_MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".wmv": "video/x-ms-wmv",
    ".avi": "video/x-msvideo",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
}
_TRANSITIONS = {
    "fade": '<p:fade xmlns:p="{p}"/>',
    "push": '<p:push xmlns:p="{p}" dir="u"/>',
    "wipe": '<p:wipe xmlns:p="{p}"/>',
    "cover": '<p:cover xmlns:p="{p}"/>',
    "slide": '<p:cover xmlns:p="{p}"/>',
    "split": '<p:split xmlns:p="{p}"/>',
    "dissolve": '<p:dissolve xmlns:p="{p}"/>',
    "zoom": '<p:zoom xmlns:p="{p}"/>',
    "cut": '<p:cut xmlns:p="{p}"/>',
}
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_TIME = re.compile(r"(\d+(?:\.\d+)?)(ms|s)\b")


def _normalise(text: str) -> str:
    return " ".join(text.split())


def _ms(token: str) -> int | None:
    match = _TIME.fullmatch(token.strip())
    if not match:
        return None
    value = float(match.group(1))
    return int(value if match.group(2) == "ms" else value * 1000)


# ---------------------------------------------------------------------------------------------------- CSS


@dataclass
class Animation:
    effect: str  # fade, fly or zoom
    direction: str = ""  # for fly: left, right, top or bottom
    duration: int = 500
    delay: int = 0


@dataclass
class _Css:
    keyframes: dict[str, tuple[str, str]] = field(default_factory=dict)
    # class name -> declarations
    classes: dict[str, dict[str, str]] = field(default_factory=dict)
    hover: bool = False


def _declarations(body: str) -> dict[str, str]:
    result = {}
    for declaration in body.split(";"):
        name, _, value = declaration.partition(":")
        if name.strip() and value.strip():
            result[name.strip().casefold()] = value.strip()
    return result


def _keyframes_effect(body: str) -> tuple[str, str]:
    """What a @keyframes block does, as an entrance effect: (effect, direction)."""
    start = re.search(r"(?:from|0%)\s*\{([^}]*)\}", body)
    text = (start.group(1) if start else body).casefold()
    move = re.search(r"translate([xy])?\(\s*(-?)\s*\d", text)
    if move:
        axis = (move.group(1) or "x").casefold()
        negative = move.group(2) == "-"
        if axis == "x":
            return "fly", "left" if negative else "right"
        return "fly", "top" if negative else "bottom"
    if "scale" in text:
        return "zoom", ""
    return "fade", ""


def parse_css(html: str) -> _Css:
    css = _Css()
    for style in re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.S | re.I):
        style = re.sub(r"/\*.*?\*/", "", style, flags=re.S)
        # @keyframes name { from {...} to {...} }: two levels of braces.
        for name, body in re.findall(r"@(?:-webkit-)?keyframes\s+([\w-]+)\s*\{((?:[^{}]*\{[^{}]*\})*[^{}]*)\}", style):
            css.keyframes[name] = _keyframes_effect(body)
        flat = re.sub(r"@(?:-webkit-)?keyframes\s+[\w-]+\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", style)
        for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", flat):
            declarations = _declarations(body)
            for selector in selectors.split(","):
                selector = selector.strip()
                if ":hover" in selector or ":focus" in selector:
                    css.hover = True
                    continue
                match = re.fullmatch(r"[\w-]*\.([\w-]+)", selector)
                if match:
                    css.classes.setdefault(match.group(1), {}).update(declarations)
    return css


def _animation_of(node: _Node, css: _Css) -> Animation | None:
    declarations: dict[str, str] = {}
    for name in node.attrs.get("class", "").split():
        declarations.update(css.classes.get(name, {}))
    if node.attrs.get("style"):
        declarations.update(_declarations(node.attrs["style"]))
    name = declarations.get("animation-name")
    duration = _ms(declarations.get("animation-duration", "")) if declarations.get("animation-duration") else None
    delay = _ms(declarations.get("animation-delay", "")) if declarations.get("animation-delay") else None
    if "animation" in declarations:
        times = []
        for token in declarations["animation"].replace(",", " ").split():
            if token in css.keyframes and not name:
                name = token
            elif _ms(token) is not None:
                times.append(_ms(token))
        duration = duration if duration is not None else (times[0] if times else None)
        if delay is None and len(times) > 1:
            delay = times[1]
    if not name or name == "none":
        return None
    effect, direction = css.keyframes.get(name, ("fade", ""))
    return Animation(effect, direction, duration or 500, delay or 0)


def _transition_of(section: _Node | None, css: _Css) -> tuple[str | None, str]:
    """The slide transition and its speed (fast, med or slow), or None."""
    if section is None:
        return None, "med"
    named = section.attrs.get("data-transition", "").strip().casefold()
    declarations: dict[str, str] = {}
    for name in section.attrs.get("class", "").split():
        declarations.update(css.classes.get(name, {}))
    if section.attrs.get("style"):
        declarations.update(_declarations(section.attrs["style"]))
    duration = None
    transition = declarations.get("transition", "")
    for token in transition.replace(",", " ").split():
        if _ms(token) is not None:
            duration = _ms(token)
            break
    speed = "med" if duration is None else ("fast" if duration <= 500 else "med" if duration <= 1000 else "slow")
    if named:
        return named, speed
    if transition and transition.casefold() != "none":
        return "fade", speed
    return None, speed


# ---------------------------------------------------------------------------------------------------- slides


@dataclass
class _Line:
    node: _Node
    level: int = 0
    heading: bool = False


@dataclass
class _Slide:
    section: _Node | None = None
    title: _Node | None = None
    lines: list[_Line] = field(default_factory=list)
    tables: list[_Node] = field(default_factory=list)
    images: list[_Node] = field(default_factory=list)
    media: list[_Node] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def empty(self) -> bool:
        return not (self.title or self.lines or self.tables or self.images or self.media or self.notes)


def _is_notes(node: _Node) -> bool:
    classes = node.attrs.get("class", "").split()
    return "notes" in classes or node.attrs.get("role") == "note" and node.tag == "aside"


def collect_slides(root: _Node) -> list[_Slide]:
    slides = [_Slide()]

    def start(section: _Node | None = None) -> None:
        if slides[-1].empty():
            slides[-1].section = section
        else:
            slides.append(_Slide(section=section))

    def visit(node: _Node, level: int = 0) -> None:
        for child in node.children:
            if not isinstance(child, _Node):
                if _normalise(child):
                    slides[-1].lines.append(_Line(_Node("p", children=[child])))
                continue
            tag = child.tag
            if tag in {"head", "title", "meta", "link"}:
                continue
            if tag == "section":
                start(child)
                visit(child)
                start()
            elif tag in {"h1", "h2"}:
                current = slides[-1]
                if current.title is not None or current.lines or current.tables or current.images or current.media:
                    start()
                slides[-1].title = child
            elif _is_notes(child):
                text = _normalise(_text(child))
                if text:
                    slides[-1].notes.append(text)
            elif tag == "table":
                slides[-1].tables.append(child)
            elif tag == "img":
                slides[-1].images.append(child)
            elif tag in _MEDIA:
                slides[-1].media.append(child)
            elif tag in {"ul", "ol"}:
                for item in child.children:
                    if isinstance(item, _Node) and item.tag == "li":
                        nested = [c for c in item.children if isinstance(c, _Node) and c.tag in {"ul", "ol"}]
                        own = _Node("li", item.attrs, [c for c in item.children if c not in nested])
                        if _normalise(_text(own)):
                            slides[-1].lines.append(_Line(own, level))
                        for sub in nested:
                            visit(_Node("div", children=[sub]), level + 1)
            elif tag in _TEXT_BLOCKS:
                inner = [n for n in _walk(child) if n is not child and n.tag in {"img", "table"} | set(_MEDIA)]
                if _normalise(_text(child)):
                    slides[-1].lines.append(_Line(child, level, heading=tag in {"h3", "h4", "h5", "h6"}))
                for item in inner:
                    getattr(slides[-1], {"img": "images", "table": "tables"}.get(item.tag, "media")).append(item)
            else:
                visit(child, level)

    visit(root)
    return [slide for slide in slides if not slide.empty()]


def _runs(node: _Node, formats: dict[str, Any] | None = None) -> list[tuple[str, dict[str, Any]]]:
    formats = formats or {}
    runs: list[tuple[str, dict[str, Any]]] = []
    for child in node.children:
        if isinstance(child, str):
            runs.append((re.sub(r"\s+", " ", child), formats))
        elif child.tag == "br":
            runs.append(("\v", formats))
        elif child.tag in {"ul", "ol", "table", "img", *(_MEDIA)} or _is_notes(child):
            continue
        else:
            inner = dict(formats)
            if child.tag in INLINE_FORMATS:
                inner[INLINE_FORMATS[child.tag]] = True
            if child.attrs.get("style"):
                inner.update(style_formats(child.attrs["style"]))
            runs += _runs(child, inner)
    # Trim the source's whitespace at both ends.
    while runs and not runs[0][0].strip():
        runs.pop(0)
    while runs and not runs[-1][0].strip():
        runs.pop()
    if runs:
        runs[0] = (runs[0][0].lstrip(), runs[0][1])
        runs[-1] = (runs[-1][0].rstrip(), runs[-1][1])
    return runs


def _fill_paragraph(paragraph, runs: list[tuple[str, dict[str, Any]]], heading: bool = False) -> None:
    from pptx.dml.color import RGBColor

    for text, formats in runs:
        run = paragraph.add_run()
        run.text = text
        font = run.font
        if formats.get("bold") or heading:
            font.bold = True
        if formats.get("italic"):
            font.italic = True
        if formats.get("underline"):
            font.underline = True
        if formats.get("code"):
            font.name = "Consolas"
        if formats.get("color"):
            font.color.rgb = RGBColor.from_string(formats["color"])
        if formats.get("strike") or formats.get("subscript") or formats.get("superscript"):
            props = run._r.get_or_add_rPr()
            if formats.get("strike"):
                props.set("strike", "sngStrike")
            if formats.get("subscript"):
                props.set("baseline", "-25000")
            if formats.get("superscript"):
                props.set("baseline", "30000")


# ---------------------------------------------------------------------------------------------------- timing


def _target(spid: int, paragraph: int | None) -> str:
    if paragraph is None:
        return f'<p:spTgt spid="{spid}"/>'
    return f'<p:spTgt spid="{spid}"><p:txEl><p:pRg st="{paragraph}" end="{paragraph}"/></p:txEl></p:spTgt>'


_FLY = {
    "left": (2, 8, "0-#ppt_w/2", "#ppt_y"),
    "right": (2, 2, "1+#ppt_w/2", "#ppt_y"),
    "top": (2, 1, "#ppt_x", "0-#ppt_h/2"),
    "bottom": (2, 4, "#ppt_x", "1+#ppt_h/2"),
}


def _anim(ids, target: str, attribute: str, start: str, end: str, duration: int) -> str:
    return (
        '<p:anim calcmode="lin" valueType="num"><p:cBhvr additive="base">'
        f'<p:cTn id="{next(ids)}" dur="{duration}" fill="hold"/><p:tgtEl>{target}</p:tgtEl>'
        f"<p:attrNameLst><p:attrName>{attribute}</p:attrName></p:attrNameLst></p:cBhvr>"
        f'<p:tavLst><p:tav tm="0"><p:val><p:strVal val="{start}"/></p:val></p:tav>'
        f'<p:tav tm="100000"><p:val><p:strVal val="{end}"/></p:val></p:tav></p:tavLst></p:anim>'
    )


def _effect(ids, spid: int, paragraph: int | None, animation: Animation) -> str:
    target = _target(spid, paragraph)
    duration = max(1, animation.duration)
    show = (
        f'<p:set><p:cBhvr><p:cTn id="{next(ids)}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/>'
        f"</p:stCondLst></p:cTn><p:tgtEl>{target}</p:tgtEl><p:attrNameLst><p:attrName>style.visibility"
        '</p:attrName></p:attrNameLst></p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>'
    )
    if animation.effect == "fly":
        preset, subtype, x, y = _FLY.get(animation.direction, _FLY["left"])
        behaviours = show + _anim(ids, target, "ppt_x", x, "#ppt_x", duration)
        behaviours += _anim(ids, target, "ppt_y", y, "#ppt_y", duration)
    elif animation.effect == "zoom":
        preset, subtype = 53, 16
        behaviours = show + _anim(ids, target, "ppt_w", "0", "#ppt_w", duration)
        behaviours += _anim(ids, target, "ppt_h", "0", "#ppt_h", duration)
        behaviours += (
            f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{next(ids)}" dur="{duration}"/>'
            f"<p:tgtEl>{target}</p:tgtEl></p:cBhvr></p:animEffect>"
        )
    else:
        preset, subtype = 10, 0
        behaviours = show + (
            f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{next(ids)}" dur="{duration}"/>'
            f"<p:tgtEl>{target}</p:tgtEl></p:cBhvr></p:animEffect>"
        )
    return (
        f'<p:par><p:cTn id="{next(ids)}" presetID="{preset}" presetClass="entr" presetSubtype="{subtype}" '
        f'fill="hold" grpId="0" nodeType="withEffect"><p:stCondLst><p:cond delay="{animation.delay}"/>'
        f"</p:stCondLst><p:childTnLst>{behaviours}</p:childTnLst></p:cTn></p:par>"
    )


def timing_xml(effects: list[tuple[int, int | None, Animation, str]], base: int = 0) -> str:
    """The slide's <p:timing>: every effect starts with the slide, after its delay. effects are
    (shape id, paragraph index or None, animation, shape kind: text, picture or table). Time node ids start
    after base, so that they do not collide with a timing the slide already has (a video's)."""

    def counter():
        number = base + 5
        while True:
            yield number
            number += 1

    ids = counter()
    ordered = sorted(effects, key=lambda item: item[2].delay)
    # Effects are numbered before the containers that wrap them, which take ids 1 to 4.
    pars = "".join(_effect(ids, spid, paragraph, animation) for spid, paragraph, animation, _kind in ordered)
    builds = []
    seen: set[int] = set()
    for spid, _paragraph, _animation, kind in ordered:
        if spid in seen:
            continue
        seen.add(spid)
        if kind == "table":
            builds.append(f'<p:bldGraphic spid="{spid}" grpId="0"><p:bldAsOne/></p:bldGraphic>')
        elif kind == "text":
            by_paragraph = any(s == spid and p is not None for s, p, _a, _k in ordered)
            builds.append(f'<p:bldP spid="{spid}" grpId="0"' + (' build="p"/>' if by_paragraph else "/>"))
    build_list = f"<p:bldLst>{''.join(builds)}</p:bldLst>" if builds else ""
    return (
        f'<p:timing xmlns:p="{_P}"><p:tnLst><p:par><p:cTn id="{base + 1}" dur="indefinite" restart="never" '
        f'nodeType="tmRoot"><p:childTnLst><p:seq concurrent="1" nextAc="seek"><p:cTn id="{base + 2}" '
        f'dur="indefinite" nodeType="mainSeq"><p:childTnLst><p:par><p:cTn id="{base + 3}" fill="hold">'
        f'<p:stCondLst><p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="{base + 2}"/>'
        f'</p:cond></p:stCondLst><p:childTnLst><p:par><p:cTn id="{base + 4}" fill="hold"><p:stCondLst>'
        '<p:cond delay="0"/></p:stCondLst>'
        f"<p:childTnLst>{pars}</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst>"
        '</p:cTn><p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond>'
        '</p:prevCondLst><p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl>'
        f"</p:cond></p:nextCondLst></p:seq></p:childTnLst></p:cTn></p:par></p:tnLst>{build_list}</p:timing>"
    )


def _existing_timing(slide):
    return slide._element.find(f"{{{_P}}}timing")


def _max_time_node_id(timing) -> int:
    ids = [int(node.get("id")) for node in timing.iter(f"{{{_P}}}cTn") if (node.get("id") or "").isdigit()]
    return max(ids, default=0)


def _add_after_clrmap(slide, xml: str) -> None:
    """Add a <p:transition> or <p:timing> in schema order (cSld, clrMapOvr, transition, timing). A timing the
    slide already has, such as the one python-pptx writes for a video, receives the main sequence instead."""
    from lxml import etree

    element = etree.fromstring(xml)
    sld = slide._element
    if element.tag == f"{{{_P}}}timing":
        existing = _existing_timing(slide)
        if existing is not None:
            root = existing.find(f"{{{_P}}}tnLst/{{{_P}}}par/{{{_P}}}cTn/{{{_P}}}childTnLst")
            sequence = element.find(f"{{{_P}}}tnLst/{{{_P}}}par/{{{_P}}}cTn/{{{_P}}}childTnLst/{{{_P}}}seq")
            root.insert(0, sequence)
            builds = element.find(f"{{{_P}}}bldLst")
            if builds is not None:
                old = existing.find(f"{{{_P}}}bldLst")
                if old is None:
                    existing.append(builds)
                else:
                    old.extend(list(builds))
            return
        transition = sld.find(f"{{{_P}}}transition")
        if transition is not None:
            transition.addnext(element)
            return
    anchor = sld.find(f"{{{_P}}}clrMapOvr")
    if anchor is None:
        anchor = sld.find(f"{{{_P}}}cSld")
    anchor.addnext(element)


# ---------------------------------------------------------------------------------------------------- convert


def convert_html_to_pptx(
    input_path: str | Path, output_path: str | Path
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    source, destination, path_errors = validate_office_paths(input_path, output_path, ".pptx")
    if path_errors:
        return False, {}, path_errors
    try:
        from pptx import Presentation
        from pptx.util import Emu, Inches, Pt
    except ImportError:
        return (
            False,
            {},
            [{"code": "CONVERTER_UNAVAILABLE", "message": "Install the html optional dependency: python-pptx."}],
        )
    html, _encoding, decode_warning = decode_html_bytes(source.read_bytes())
    parser = _TreeParser()
    parser.feed(html)
    parser.close()
    css = parse_css(html)
    slides = collect_slides(parser.root)
    if not slides:
        return (
            False,
            {},
            [
                {
                    "code": "NO_CONTENT",
                    "message": "The HTML contains no headings, paragraphs or list items to convert to slides.",
                }
            ],
        )
    warnings: list[str] = [decode_warning] if decode_warning else []
    if len(slides) > MAX_SLIDES:
        warnings.append(f"Only the first {MAX_SLIDES} slides were converted.")
        slides = slides[:MAX_SLIDES]
    if parser.warnings:
        warnings += sorted(parser.warnings)
    for tag in sorted(parser.unsupported_elements):
        warnings.append(f"<{tag}> elements cannot be converted and were omitted.")
    if css.hover:
        warnings.append("Hover effects (:hover, :focus) cannot be represented in a presentation and were omitted.")

    presentation = Presentation()
    layout = presentation.slide_layouts[1]  # title and content
    width, height = presentation.slide_width, presentation.slide_height
    margin = Inches(0.5)
    counts = {"tables": 0, "images": 0, "media": 0, "notes": 0, "animations": 0, "transitions": 0}
    partial_animations = 0
    unknown_transitions: set[str] = set()
    for data in slides:
        slide = presentation.slides.add_slide(layout)
        effects: list[tuple[int, int | None, Animation, str]] = []
        title_shape = slide.shapes.title
        if data.title is not None:
            _fill_paragraph(title_shape.text_frame.paragraphs[0], _runs(data.title))
            animation = _animation_of(data.title, css)
            if animation:
                effects.append((title_shape.shape_id, None, animation, "text"))
        body_shape = slide.placeholders[1]
        top = body_shape.top
        region = height - top - margin
        items: list[tuple[str, Any]] = [("body", None)] if data.lines else []
        items += [("table", node) for node in data.tables]
        items += [("image", node) for node in data.images]
        items += [("media", node) for node in data.media]
        slot = int(region / max(1, len(items)))
        position = top
        if not data.lines:
            body_shape._element.getparent().remove(body_shape._element)
        for kind, node in items:
            if kind == "body":
                # Setting part of an inherited placeholder's position zeroes the rest, so set all four.
                left, body_width = body_shape.left, body_shape.width
                body_shape.left, body_shape.width = left, body_width
                body_shape.top, body_shape.height = position, slot
                frame = body_shape.text_frame
                for index, line in enumerate(data.lines):
                    paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
                    paragraph.level = min(line.level, 4)
                    _fill_paragraph(paragraph, _runs(line.node), heading=line.heading)
                    animated = _animation_of(line.node, css)
                    if animated is None:
                        inner = [n for n in _walk(line.node) if n is not line.node and _animation_of(n, css)]
                        if inner:
                            animated = _animation_of(inner[0], css)
                            partial_animations += 1
                    if animated:
                        effects.append((body_shape.shape_id, index, animated, "text"))
            elif kind == "table":
                grid, merges = table_grid(node)
                columns = len(grid[0]) if grid else 0
                if not grid or not columns:
                    continue
                table_height = min(slot, Inches(0.45) * len(grid))
                frame = slide.shapes.add_table(len(grid), columns, margin, position, width - 2 * margin, table_height)
                table = frame.table
                for r, row in enumerate(grid):
                    for c, cell_node in enumerate(row):
                        if cell_node is None:
                            continue
                        cell = table.cell(r, c)
                        cell.text = cell_text(cell_node)
                        for paragraph in cell.text_frame.paragraphs:
                            for run in paragraph.runs:
                                run.font.size = Pt(14)
                                if cell_node.tag == "th":
                                    run.font.bold = True
                for first_row, first_column, last_row, last_column in merges:
                    table.cell(first_row, first_column).merge(table.cell(last_row, last_column))
                counts["tables"] += 1
                animation = _animation_of(node, css)
                if animation:
                    effects.append((frame.shape_id, None, animation, "table"))
            elif kind == "image":
                path, warning = local_image(source, node.attrs.get("src", ""))
                if warning:
                    warnings.append(warning)
                    continue
                try:
                    picture = slide.shapes.add_picture(str(path), margin, position)
                except Exception:  # noqa: BLE001 - not an image python-pptx can read
                    warnings.append(f"Image could not be read and was omitted: {node.attrs.get('src', '')}")
                    continue
                scale = min((width - 2 * margin) / picture.width, slot / picture.height, 1.0)
                picture.width, picture.height = Emu(int(picture.width * scale)), Emu(int(picture.height * scale))
                picture.left = int((width - picture.width) / 2)
                counts["images"] += 1
                animation = _animation_of(node, css)
                if animation:
                    effects.append((picture.shape_id, None, animation, "picture"))
            else:
                raw = node.attrs.get("src") or next(
                    (c.attrs.get("src", "") for c in node.children if isinstance(c, _Node) and c.tag == "source"),
                    "",
                )
                path, warning = local_image(source, raw)
                mime = _MEDIA_TYPES.get(path.suffix.casefold()) if path else None
                if path is None or mime is None:
                    warnings.append(
                        f"<{node.tag}> {raw or '(no source)'} was not converted: "
                        + (
                            "the file is unavailable or outside the input folder."
                            if path is None
                            else "unsupported type."
                        )
                    )
                    continue
                movie = slide.shapes.add_movie(str(path), margin, position, width - 2 * margin, slot, mime_type=mime)
                counts["media"] += 1
                del movie
            position += slot
        if data.notes:
            slide.notes_slide.notes_text_frame.text = "\n".join(data.notes)
            counts["notes"] += 1
        transition, speed = _transition_of(data.section, css)
        if transition:
            if transition in _TRANSITIONS:
                inner = _TRANSITIONS[transition].format(p=_P)
                _add_after_clrmap(slide, f'<p:transition xmlns:p="{_P}" spd="{speed}">{inner}</p:transition>')
                counts["transitions"] += 1
            elif transition != "none":
                unknown_transitions.add(transition)
        if effects:
            existing = _existing_timing(slide)
            base = _max_time_node_id(existing) if existing is not None else 0
            _add_after_clrmap(slide, timing_xml(effects, base))
            counts["animations"] += len(effects)
    if partial_animations:
        warnings.append(
            f"{partial_animations} animation(s) on part of a paragraph were applied to the whole paragraph."
        )
    for name in sorted(unknown_transitions):
        warnings.append(f"Unknown slide transition {name!r} was omitted.")
    presentation.save(destination)
    return (
        True,
        {
            "input_path": str(source),
            "output_path": str(destination),
            "format": "pptx",
            "slides": len(slides),
            "mapped_objects": counts,
            "warnings": warnings,
        },
        [],
    )
