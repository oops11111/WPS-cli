"""Convert a semantic HTML slide deck into an editable presentation (pptx), with its animations.

Each slide container (a <section>, or an element with the class "slide" such as <div class="slide">) is one
slide, and outside containers each <h1>/<h2> starts one. A container's first h1/h2 is the slide's title;
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
    HTML_SPACE,
    INLINE_FORMATS,
    _Node,
    _text,
    _walk,
    cell_text,
    collapse_space,
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
    return collapse_space(text).strip(HTML_SPACE)


def _ms(token: str) -> int | None:
    match = _TIME.fullmatch(token.strip())
    if not match:
        return None
    value = float(match.group(1))
    return int(value if match.group(2) == "ms" else value * 1000)


# ---------------------------------------------------------------------------------------------------- CSS


@dataclass
class Animation:
    effect: str  # entrance and exit: fade, fly or zoom; emphasis: pulse or spin
    direction: str = ""  # for fly: left, right, top or bottom
    duration: int = 500
    delay: int = 0
    kind: str = "entrance"  # entrance, exit or emphasis
    trigger: str = "with"  # with (the previous effect), after (it) or click


@dataclass
class _Css:
    keyframes: dict[str, tuple[str, str, str]] = field(default_factory=dict)  # name -> (kind, effect, direction)
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


def _hidden(frame: str) -> bool:
    """Whether a keyframe leaves the element out of sight: transparent, moved away or scaled to nothing."""
    return bool(
        re.search(r"opacity\s*:\s*0(\.0*)?\s*(;|$)", frame)
        or re.search(r"translate[xy]?\(\s*-?\s*(\d{3,}|100)", frame)
        or re.search(r"scale\(\s*0(\.0*)?\s*\)", frame)
    )


def _motion(frame: str) -> tuple[str, str]:
    move = re.search(r"translate([xy])?\(\s*(-?)\s*\d", frame)
    if move:
        axis = (move.group(1) or "x").casefold()
        negative = move.group(2) == "-"
        if axis == "x":
            return "fly", "left" if negative else "right"
        return "fly", "top" if negative else "bottom"
    if "scale" in frame:
        return "zoom", ""
    return "fade", ""


def _keyframes_effect(body: str) -> tuple[str, str, str]:
    """What a @keyframes block does, as (kind, effect, direction).

    It is an entrance when the first frame hides the element, an exit when the last one does, and otherwise an
    emphasis: a pulse when it scales, a spin when it rotates.
    """
    start = re.search(r"(?:from|0%)\s*\{([^}]*)\}", body)
    end = re.search(r"(?:to|100%)\s*\{([^}]*)\}", body)
    first = (start.group(1) if start else "").casefold()
    last = (end.group(1) if end else "").casefold()
    if _hidden(last) and not _hidden(first):
        effect, direction = _motion(last)
        return "exit", effect, direction
    if first or not last:
        if _hidden(first) or not end:
            effect, direction = _motion(first or body.casefold())
            return "entrance", effect, direction
    whole = body.casefold()
    if "rotate" in whole:
        return "emphasis", "spin", ""
    if "scale" in whole:
        return "emphasis", "pulse", ""
    effect, direction = _motion(first or whole)
    return "entrance", effect, direction


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
    kind, effect, direction = css.keyframes.get(name, ("entrance", "fade", ""))
    trigger = node.attrs.get("data-trigger", "with").strip().casefold()
    return Animation(
        effect,
        direction,
        duration or 500,
        delay or 0,
        kind,
        trigger if trigger in {"with", "after", "click"} else "with",
    )


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


_BLOCK_LEVEL = {
    "div", "p", "section", "article", "aside", "header", "footer", "main", "nav", "ul", "ol", "table", "figure",
    "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "img", "video", "audio", "form", "details", "dl",
    "address", "hr", "figcaption",
}  # fmt: skip


def _is_slide_container(node: _Node) -> bool:
    """A <section>, or an element whose class names it a slide (<div class="slide">, a common way to write decks)."""
    return node.tag == "section" or "slide" in node.attrs.get("class", "").split()


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
            if _is_slide_container(child) and slides[-1].section is None:
                start(child)
                visit(child)
                start()
            elif tag in {"h1", "h2"}:
                current = slides[-1]
                if current.section is not None:
                    # Inside a slide container the slide is the container: its first h1/h2 is the title, and
                    # content before it (a badge, a kicker) stays on the same slide.
                    if current.title is None:
                        current.title = child
                    else:
                        current.lines.append(_Line(child, level, heading=True))
                    continue
                if current.title is not None or current.tables or current.images or current.media:
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
            elif (
                tag not in {"html", "body", "head"}
                and _normalise(_text(child))
                and not any(isinstance(c, _Node) and (c.tag in _BLOCK_LEVEL or _is_notes(c)) for c in child.children)
            ):
                # A <div> (or any container) holding only text and inline elements is one paragraph.
                slides[-1].lines.append(_Line(child, level))
            else:
                visit(child, level)

    visit(root)
    return [slide for slide in slides if not slide.empty()]


def _runs(node: _Node, formats: dict[str, Any] | None = None, styled=None) -> list[tuple[str, dict[str, Any]]]:
    """The text runs of a node. With the browser's styles (styled), an inline element keeps its own colour and
    weight, as in "执行<span style="color: blue">步骤</span>"."""
    formats = formats or {}
    runs: list[tuple[str, dict[str, Any]]] = []
    for child in node.children:
        if isinstance(child, str):
            runs.append((collapse_space(child), formats))
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
            if styled is not None:
                from .html_styles import color, is_bold

                child_style = styled.style(child)
                hue = color(child_style.get("-webkit-text-fill-color")) or color(child_style.get("color"))
                if hue:
                    inner["color"] = hue
                if is_bold(child_style):
                    inner["bold"] = True
            runs += _runs(child, inner, styled)
    # Trim the source's whitespace at both ends.
    while runs and not runs[0][0].strip(HTML_SPACE):
        runs.pop(0)
    while runs and not runs[-1][0].strip(HTML_SPACE + "\v"):  # a <br> at the end shows no line in a browser
        runs.pop()
    if runs:
        runs[0] = (runs[0][0].lstrip(HTML_SPACE), runs[0][1])
        runs[-1] = (runs[-1][0].rstrip(HTML_SPACE), runs[-1][1])
    return runs


def _fill_paragraph(paragraph, runs: list[tuple[str, dict[str, Any]]], heading: bool = False) -> None:
    from pptx.dml.color import RGBColor

    for text, formats in runs:
        if text == "\v":
            # A <br>: python-pptx would store a vertical tab in a run as the literal text "_x000B_".
            paragraph.add_line_break()
            continue
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
        if formats.get("size"):
            from pptx.util import Pt

            font.size = Pt(round(formats["size"], 1))
        if formats.get("font"):
            font.name = formats["font"]
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


def _effect(ids, spid: int, paragraph: int | None, animation: Animation, delay: int, node_type: str) -> str:
    target = _target(spid, paragraph)
    duration = max(1, animation.duration)

    def visibility(value: str, at: int) -> str:
        return (
            f'<p:set><p:cBhvr><p:cTn id="{next(ids)}" dur="1" fill="hold"><p:stCondLst><p:cond delay="{at}"/>'
            f"</p:stCondLst></p:cTn><p:tgtEl>{target}</p:tgtEl><p:attrNameLst><p:attrName>style.visibility"
            f'</p:attrName></p:attrNameLst></p:cBhvr><p:to><p:strVal val="{value}"/></p:to></p:set>'
        )

    def fade(direction: str) -> str:
        return (
            f'<p:animEffect transition="{direction}" filter="fade"><p:cBhvr><p:cTn id="{next(ids)}" '
            f'dur="{duration}"/><p:tgtEl>{target}</p:tgtEl></p:cBhvr></p:animEffect>'
        )

    if animation.kind == "emphasis":
        preset_class = "emph"
        if animation.effect == "spin":
            preset, subtype = 8, 0
            behaviours = (
                f'<p:animRot by="21600000"><p:cBhvr><p:cTn id="{next(ids)}" dur="{duration}" fill="hold"/>'
                f"<p:tgtEl>{target}</p:tgtEl><p:attrNameLst><p:attrName>r</p:attrName></p:attrNameLst></p:cBhvr>"
                "</p:animRot>"
            )
        else:
            preset, subtype = 6, 0
            behaviours = (
                f'<p:animScale><p:cBhvr><p:cTn id="{next(ids)}" dur="{duration}" autoRev="1" fill="hold"/>'
                f'<p:tgtEl>{target}</p:tgtEl></p:cBhvr><p:by x="115000" y="115000"/></p:animScale>'
            )
    elif animation.kind == "exit":
        preset_class = "exit"
        if animation.effect == "fly":
            preset, subtype, x, y = _FLY.get(animation.direction, _FLY["left"])
            behaviours = _anim(ids, target, "ppt_x", "#ppt_x", x, duration)
            behaviours += _anim(ids, target, "ppt_y", "#ppt_y", y, duration)
        elif animation.effect == "zoom":
            preset, subtype = 53, 16
            behaviours = _anim(ids, target, "ppt_w", "#ppt_w", "0", duration)
            behaviours += _anim(ids, target, "ppt_h", "#ppt_h", "0", duration) + fade("out")
        else:
            preset, subtype = 10, 0
            behaviours = fade("out")
        behaviours += visibility("hidden", duration - 1)
    else:
        preset_class = "entr"
        show = visibility("visible", 0)
        if animation.effect == "fly":
            preset, subtype, x, y = _FLY.get(animation.direction, _FLY["left"])
            behaviours = show + _anim(ids, target, "ppt_x", x, "#ppt_x", duration)
            behaviours += _anim(ids, target, "ppt_y", y, "#ppt_y", duration)
        elif animation.effect == "zoom":
            preset, subtype = 53, 16
            behaviours = show + _anim(ids, target, "ppt_w", "0", "#ppt_w", duration)
            behaviours += _anim(ids, target, "ppt_h", "0", "#ppt_h", duration) + fade("in")
        else:
            preset, subtype = 10, 0
            behaviours = show + fade("in")
    return (
        f'<p:par><p:cTn id="{next(ids)}" presetID="{preset}" presetClass="{preset_class}" presetSubtype="{subtype}" '
        f'fill="hold" grpId="0" nodeType="{node_type}"><p:stCondLst><p:cond delay="{delay}"/>'
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
    # Effects in document order. A click starts a new group; the first group starts with the slide. Within a
    # group, "with" effects start after their CSS delay and "after" effects when the previous one ends.
    groups: list[list[tuple[int, int | None, Animation, str, int]]] = [[]]
    for spid, paragraph, animation, kind in effects:
        if animation.trigger == "click" and groups[-1]:
            groups.append([])
        group = groups[-1]
        start = animation.delay
        if animation.trigger == "after" and group:
            previous = group[-1]
            start = previous[4] + max(1, previous[2].duration) + animation.delay
        group.append((spid, paragraph, animation, kind, start))
    clicked = bool(effects) and effects[0][2].trigger == "click"
    pars = []
    for index, group in enumerate(groups):
        inner = "".join(
            _effect(
                ids, spid, paragraph, animation, start, "clickEffect" if n == 0 and (index or clicked) else "withEffect"
            )
            for n, (spid, paragraph, animation, _kind, start) in enumerate(sorted(group, key=lambda e: e[4]))
        )
        if index == 0 and not clicked:
            condition = f'<p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="{base + 2}"/></p:cond>'
        else:
            condition = '<p:cond delay="indefinite"/>'
        pars.append(
            f'<p:par><p:cTn id="{next(ids)}" fill="hold"><p:stCondLst>{condition}</p:stCondLst><p:childTnLst>'
            f'<p:par><p:cTn id="{next(ids)}" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst>'
            f"<p:childTnLst>{inner}</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>"
        )
    ordered = [(s, p, a, k) for group in groups for (s, p, a, k, _start) in group]
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
        f'dur="indefinite" nodeType="mainSeq"><p:childTnLst>{"".join(pars)}</p:childTnLst>'
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


def _bullets(paragraph, on: bool) -> None:
    from lxml import etree

    props = paragraph._p.get_or_add_pPr()
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    for old in props.findall(f"{{{a}}}buNone") + props.findall(f"{{{a}}}buChar"):
        props.remove(old)
    if on:
        props.set("marL", str(285750 * (paragraph.level + 1)))
        props.set("indent", "-285750")
        etree.SubElement(props, f"{{{a}}}buChar", char="•")
    else:
        etree.SubElement(props, f"{{{a}}}buNone")


def _style_runs(paragraph, styled, node, factor: float, left: bool = False) -> None:
    """Font, size and colour from the computed style, scaled from CSS pixels to the slide."""
    from pptx.dml.color import RGBColor
    from pptx.util import Pt

    from .html_styles import color, first_font, is_bold, px

    style = styled.style(node)
    size = (px(style.get("font-size")) or 16.0) * 0.75 * factor
    hue = color(style.get("color"))
    family = first_font(style.get("font-family"))
    for run in paragraph.runs:
        font = run.font
        if font.size is None:
            font.size = Pt(round(size, 1))
        if hue and font.color.type is None:
            font.color.rgb = RGBColor.from_string(hue)
        if family:
            font.name = family
            props = run._r.get_or_add_rPr()
            east = props.find("{http://schemas.openxmlformats.org/drawingml/2006/main}ea")
            if east is None:
                from lxml import etree

                east = etree.SubElement(props, "{http://schemas.openxmlformats.org/drawingml/2006/main}ea")
            east.set("typeface", family)
        if is_bold(style) and font.bold is None:
            font.bold = True
    align = {"center": 2, "right": 3, "end": 3, "justify": 4}.get(style.get("text-align", ""))
    if align or left:
        from pptx.enum.text import PP_ALIGN

        # A placed title keeps the browser's alignment; the slide layout's own would centre it.
        paragraph.alignment = {2: PP_ALIGN.CENTER, 3: PP_ALIGN.RIGHT, 4: PP_ALIGN.JUSTIFY}.get(align, PP_ALIGN.LEFT)


def _set_slide_background(slide, styled, node: _Node | None) -> None:
    """Paint the slide with the node's background, or the nearest ancestor's that has one (often the body's)."""
    from . import slide_appearance as look

    if node is None:
        return
    parents = {id(c): n for n in _walk(styled.root) for c in n.children if isinstance(c, _Node)}
    holder: _Node | None = node
    while holder is not None:
        background_fill = look.fill_of(styled.style(holder))
        if background_fill is not None:
            look.set_background(slide, background_fill)
            return
        holder = parents.get(id(holder))


def _background_start(data: _Slide) -> _Node | None:
    """The node whose background chain paints a slide: its section, else its first content."""
    if data.section is not None:
        return data.section
    if data.title is not None:
        return data.title
    if data.lines:
        return data.lines[0].node
    return None


def _positioned_slide(slide, data: _Slide, styled, css: _Css, source: Path, appearance: bool, counts, warnings):
    """Place the slide's elements where the browser put them (P13-006); returns the animation effects."""
    from pptx.util import Emu, Pt

    from .html_styles import px

    section_box = styled.box(data.section)
    width, height = slide.part.package.presentation_part.presentation.slide_width, None
    factor = width / Emu(int(section_box["width"] * 9525)) if section_box["width"] else 1.0
    height = slide.part.package.presentation_part.presentation.slide_height

    def place(node):
        box = styled.box(node)
        if box is None:
            return None
        left = int((box["x"] - section_box["x"]) * 9525 * factor)
        top = int((box["y"] - section_box["y"]) * 9525 * factor)
        return (
            Emu(max(0, left)),
            Emu(max(0, top)),
            Emu(max(1, int(box["width"] * 9525 * factor))),
            Emu(max(1, int(box["height"] * 9525 * factor))),
        )

    section_style = styled.style(data.section)
    _set_slide_background(slide, styled, data.section)
    image = re.search(r"url\([\"']?([^\"')]+)", section_style.get("background-image", "") or "")
    if image:
        path, warning = local_image(
            source, image.group(1).split("/")[-1] if image.group(1).startswith("file:") else image.group(1)
        )
        if path is not None:
            picture = slide.shapes.add_picture(str(path), 0, 0, width, height)
            slide.shapes._spTree.remove(picture._element)
            slide.shapes._spTree.insert(2, picture._element)
        elif warning:
            warnings.append(warning)
    if appearance:
        # Every element with a background, a border or a shadow becomes a shape behind the text, in document order
        # so that inner boxes lie on outer ones; tables draw their own cells.
        in_tables = {id(n) for table in _walk(data.section) if table.tag == "table" for n in _walk(table)}
        # The slide's own ::before/::after (a glow over its background) come first, behind everything.
        for decoration in styled.pseudo_elements(data.section):
            _draw_decoration(slide, place, data.section, styled, decoration, factor, counts)
        for node in _walk(data.section):
            if node is data.section or id(node) in in_tables or node.tag in {"br", "img", *(_MEDIA)}:
                continue
            spot = place(node)
            box = styled.box(node)
            if spot is None or not box or box["width"] <= 0 or box["height"] <= 0:
                continue
            _draw_box(slide, spot, box, styled.style(node), factor, counts)
            for decoration in styled.pseudo_elements(node):
                _draw_decoration(slide, place, node, styled, decoration, factor, counts)
    effects: list[tuple[int, int | None, Animation, str]] = []
    title_shape = slide.shapes.title
    if data.title is not None and title_shape is not None:
        spot = place(data.title)
        if spot:
            title_shape.left, title_shape.top, title_shape.width, title_shape.height = spot
        # Drawn last of all so far: the boxes added above must not cover it.
        title_shape._element.getparent().append(title_shape._element)
        frame = title_shape.text_frame
        frame.word_wrap = True
        _fill_paragraph(frame.paragraphs[0], _runs(data.title, styled=styled))
        _style_runs(frame.paragraphs[0], styled, data.title, factor, left=True)
        _text_box_like(frame, styled, data.title, factor, width)
        animation = _animation_of(data.title, css)
        if animation:
            effects.append((title_shape.shape_id, None, animation, "text"))
    elif title_shape is not None:
        title_shape._element.getparent().remove(title_shape._element)
    # Lines that share a list become paragraphs of one text box at the list's place.
    groups: list[tuple[Any, list[_Line]]] = []
    parents = {id(c): n for n in _walk(data.section) for c in n.children if isinstance(c, _Node)}
    for line in data.lines:
        holder = line.node
        while id(holder) in parents and holder.tag not in {"ul", "ol"} and holder.tag == "li":
            holder = parents[id(holder)]
        if line.node.tag == "li":
            original = next(
                (n for n in _walk(data.section) if n.attrs.get("data-wps-i") == line.node.attrs.get("data-wps-i")), None
            )
            outer = original
            while outer is not None and id(outer) in parents:
                outer = parents[id(outer)]
                if outer.tag in {"ul", "ol"} and not any(p.tag in {"ul", "ol"} for p in _ancestors(outer, parents)):
                    break
            key = outer if outer is not None else line.node
        else:
            key = line.node
        if groups and groups[-1][0] is key:
            groups[-1][1].append(line)
        else:
            groups.append((key, [line]))
    for key, lines in groups:
        spot = place(key) or place(lines[0].node)
        if spot is None:
            continue
        box = slide.shapes.add_textbox(*spot)
        frame = box.text_frame
        frame.word_wrap = True
        _no_insets(frame)
        for index, line in enumerate(lines):
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            paragraph.level = min(line.level, 4)
            original = next(
                (n for n in _walk(data.section) if n.attrs.get("data-wps-i") == line.node.attrs.get("data-wps-i")),
                line.node,
            )
            _fill_paragraph(paragraph, _runs(line.node, styled=styled), heading=False)
            _style_runs(paragraph, styled, original, factor)
            if len(lines) == 1:
                _text_box_like(frame, styled, original, factor, width)
            _bullets(paragraph, line.node.tag == "li")
            animated = _animation_of(original, css) or _animation_of(line.node, css)
            if animated is None:
                inner = [n for n in _walk(original) if n is not original and _animation_of(n, css)]
                if inner:
                    animated = _animation_of(inner[0], css)
                    counts["partial_animations"] = counts.get("partial_animations", 0) + 1
            if animated:
                effects.append((box.shape_id, index if len(lines) > 1 else None, animated, "text"))
    for node in data.tables:
        grid, merges = table_grid(node)
        spot = place(node)
        if not grid or spot is None:
            continue
        frame = slide.shapes.add_table(len(grid), len(grid[0]), *spot)
        table = frame.table
        _table_like_html(table, grid, styled, factor)
        for r, row in enumerate(grid):
            for c, cell_node in enumerate(row):
                if cell_node is None:
                    continue
                cell = table.cell(r, c)
                cell.text = cell_text(cell_node)
                for paragraph in cell.text_frame.paragraphs:
                    _style_runs(paragraph, styled, cell_node, factor)
                cell_style = styled.style(cell_node)
                for side in ("left", "right", "top", "bottom"):
                    pad = px(cell_style.get(f"padding-{side}")) or 0.0
                    setattr(cell, f"margin_{side}", Emu(int(pad * 9525 * factor)))
                _cell_like_html(cell, cell_style, factor)
        for first_row, first_column, last_row, last_column in merges:
            table.cell(first_row, first_column).merge(table.cell(last_row, last_column))
        counts["tables"] += 1
        animation = _animation_of(node, css)
        if animation:
            effects.append((frame.shape_id, None, animation, "table"))
    for node in data.images:
        path, warning = local_image(source, node.attrs.get("src", ""))
        spot = place(node)
        if warning or spot is None:
            if warning:
                warnings.append(warning)
            continue
        picture = slide.shapes.add_picture(str(path), *spot)
        counts["images"] += 1
        animation = _animation_of(node, css)
        if animation:
            effects.append((picture.shape_id, None, animation, "picture"))
    for node in data.media:
        path, mime = _media_source(source, node, warnings)
        spot = place(node)
        if path is None or spot is None:
            continue
        slide.shapes.add_movie(str(path), *spot, mime_type=mime)
        counts["media"] += 1
    del Pt
    return effects


# PowerPoint's built-in "No Style, No Grid": the table shows only what the HTML gives it.
_PLAIN_TABLE_STYLE = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"


def _table_like_html(table, grid, styled, factor: float) -> None:
    """Column widths and row heights from the browser's cell boxes, without the default style's banding and fills."""
    from pptx.util import Emu

    table.first_row = False
    table.horz_banding = False
    properties = table._tbl.tblPr
    style_id = properties.find("{http://schemas.openxmlformats.org/drawingml/2006/main}tableStyleId")
    if style_id is not None:
        style_id.text = _PLAIN_TABLE_STYLE

    def single(node, attribute: str) -> bool:
        try:
            return int(node.attrs.get(attribute, "1") or 1) == 1
        except ValueError:
            return True

    for c in range(len(grid[0])):
        widths = [
            box["width"]
            for row in grid
            if row[c] is not None and single(row[c], "colspan") and (box := styled.box(row[c]))
        ]
        if widths:
            table.columns[c].width = Emu(max(1, int(widths[0] * 9525 * factor)))
    for r, row in enumerate(grid):
        heights = [
            box["height"] for cell in row if cell is not None and single(cell, "rowspan") and (box := styled.box(cell))
        ]
        if heights:
            table.rows[r].height = Emu(max(1, int(max(heights) * 9525 * factor)))


def _cell_like_html(cell, style: dict[str, str], factor: float) -> None:
    """A table cell's fill (with its opacity), CSS borders as cell lines, and vertical alignment."""
    from lxml import etree
    from pptx.enum.text import MSO_ANCHOR

    from . import slide_appearance as look

    fill = look.fill_of(style)
    if fill is None:
        cell.fill.background()
    else:
        cell.fill.solid()
        properties = cell._tc.get_or_add_tcPr()
        look._replace_fill(properties, fill, ("lnL", "lnR", "lnT", "lnB", "lnTlToBr", "lnBlToTr", "cell3D"))
    properties = cell._tc.get_or_add_tcPr()
    a = look.A
    drawn = {side: (width, hue, alpha) for side, width, hue, alpha in look.borders(style)}
    for index, (side, tag) in enumerate((("left", "lnL"), ("right", "lnR"), ("top", "lnT"), ("bottom", "lnB"))):
        for old in properties.findall(f"{{{a}}}{tag}"):
            properties.remove(old)
        line = etree.Element(f"{{{a}}}{tag}")
        if side in drawn:
            width, hue, alpha = drawn[side]
            line.set("w", str(max(1, int(width * look.EMU_PER_PX * factor))))
            line.append(look.solid_fill(hue, alpha))
        else:
            line.set("w", "0")
            line.append(etree.Element(f"{{{a}}}noFill"))
        properties.insert(index, line)
    cell.vertical_anchor = {"top": MSO_ANCHOR.TOP, "bottom": MSO_ANCHOR.BOTTOM}.get(
        style.get("vertical-align", ""), MSO_ANCHOR.MIDDLE
    )


def _draw_box(slide, spot, box: dict[str, float], style: dict[str, str], factor: float, counts) -> None:
    """One HTML box as a shape: fill (gradient, opacity), corners, borders and shadow; nothing when it shows none."""
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Emu

    from . import slide_appearance as look

    if style.get("visibility") == "hidden" or style.get("display") == "none":
        return
    try:
        opacity = float(style.get("opacity") or 1.0)
    except ValueError:
        opacity = 1.0
    fill = None if look.text_is_clipped_background(style) else look.fill_of(style, opacity)
    sides = look.borders(style)
    shadow = look.parse_shadow(style.get("box-shadow"), factor) if fill is not None else None
    if fill is None and not sides and shadow is None:
        return
    width, height = box["width"], box["height"]
    corner = look.radius(style.get("border-top-left-radius"), width, height)
    uniform = len(sides) == 4 and len({(w, h, a) for _side, w, h, a in sides}) == 1
    if fill is not None or uniform:
        if corner * 2 >= min(width, height) - 0.5 and abs(width - height) < 1:
            shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, *spot)
        elif corner > 0:
            shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, *spot)
            shape.adjustments[0] = min(0.5, corner / min(width, height))
        else:
            shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, *spot)
        look.set_shape_fill(shape, fill)
        if uniform:
            _side, line_width, hue, alpha = sides[0]
            look.set_outline(shape, hue, alpha * opacity, int(line_width * look.EMU_PER_PX * factor))
        else:
            shape.line.fill.background()
        if shadow is not None:
            look.add_shadow(shape, shadow)
        counts["shapes"] = counts.get("shapes", 0) + 1
    if not uniform:
        # Borders that differ by side (a card's coloured left edge, a heading's underline) are bars along them.
        left, top, w, h = (int(value) for value in spot)
        for side, line_width, hue, alpha in sides:
            thick = max(1, int(line_width * look.EMU_PER_PX * factor))
            bar = {
                "top": (left, top, w, thick),
                "bottom": (left, top + h - thick, w, thick),
                "left": (left, top, thick, h),
                "right": (left + w - thick, top, thick, h),
            }[side]
            shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, *(Emu(v) for v in bar))
            look.set_shape_fill(shape, look.solid_fill(hue, alpha * opacity))
            shape.line.fill.background()
            counts["shapes"] = counts.get("shapes", 0) + 1


def _draw_decoration(slide, place, node, styled, decoration: dict[str, str], factor: float, counts) -> None:
    """A positioned ::before/::after with a size and a background (a glow, a blob) as a shape."""
    from pptx.util import Emu

    from .html_styles import px

    box = styled.box(node)
    width, height = px(decoration.get("width")), px(decoration.get("height"))
    if not box or decoration.get("position") not in {"absolute", "fixed"} or not width or not height:
        return
    left, right = px(decoration.get("left")), px(decoration.get("right"))
    top, bottom = px(decoration.get("top")), px(decoration.get("bottom"))
    x = box["x"] + left if left is not None else box["x"] + box["width"] - (right or 0.0) - width
    y = box["y"] + top if top is not None else box["y"] + box["height"] - (bottom or 0.0) - height
    origin = place(node)
    if origin is None:
        return
    spot = (
        Emu(int(origin[0] + (x - box["x"]) * 9525 * factor)),
        Emu(int(origin[1] + (y - box["y"]) * 9525 * factor)),
        Emu(max(1, int(width * 9525 * factor))),
        Emu(max(1, int(height * 9525 * factor))),
    )
    style = {**decoration, "border-top-left-radius": decoration.get("border-top-left-radius", "")}
    _draw_box(slide, spot, {"x": x, "y": y, "width": width, "height": height}, style, factor, counts)


def _widen(frame, slide_width: int, share: float = 0.25) -> None:
    from pptx.enum.text import MSO_AUTO_SIZE, PP_ALIGN

    shape = frame._parent
    frame.auto_size = MSO_AUTO_SIZE.NONE
    alignment = frame.paragraphs[0].alignment
    extra = int(shape.width * share)
    if alignment == PP_ALIGN.CENTER:
        extra = min(extra, 2 * shape.left, 2 * max(0, slide_width - shape.left - shape.width))
        shape.left, shape.width = shape.left - extra // 2, shape.width + extra
    elif alignment == PP_ALIGN.RIGHT:
        extra = min(extra, shape.left)
        shape.left, shape.width = shape.left - extra, shape.width + extra
    else:
        shape.width = shape.width + max(0, min(extra, slide_width - shape.left - shape.width))


def _text_box_like(frame, styled, node, factor: float, slide_width: int) -> None:
    """Fit a text frame to its HTML box: padding as insets, flex centring, one browser line kept on one line, and
    `background-clip: text` gradients on the glyphs."""
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.util import Emu

    from . import slide_appearance as look
    from .html_styles import parse_gradient, px

    style = styled.style(node)
    for side, attribute in (
        ("left", "margin_left"),
        ("right", "margin_right"),
        ("top", "margin_top"),
        ("bottom", "margin_bottom"),
    ):
        inset = (px(style.get(f"padding-{side}")) or 0.0) + (px(style.get(f"border-{side}-width")) or 0.0)
        setattr(frame, attribute, Emu(int(inset * 9525 * factor)))
    frame.vertical_anchor = MSO_ANCHOR.TOP
    if style.get("display") in {"flex", "inline-flex"}:
        column = style.get("flex-direction", "row").startswith("column")
        main, cross = style.get("justify-content", ""), style.get("align-items", "")
        vertical, horizontal = (main, cross) if column else (cross, main)
        if vertical == "center":
            frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        if horizontal == "center":
            for paragraph in frame.paragraphs:
                paragraph.alignment = PP_ALIGN.CENTER
    try:
        lines = int(style.get("text-lines") or 0)
    except ValueError:
        lines = 0
    breaks = sum(1 for n in _walk(node) if n.tag == "br")
    if 0 < lines <= breaks + 1:
        # The browser broke the text only at its <br>s; a wider font (a fallback where Microsoft YaHei is missing)
        # must not wrap it further. Wrapping stays on, which every renderer honours, and the box gets room to grow
        # on the side its alignment leaves free.
        _widen(frame, slide_width)
    if look.text_is_clipped_background(style):
        gradient = parse_gradient(style.get("background-image"))
        if gradient:
            for paragraph in frame.paragraphs:
                for run in paragraph.runs:
                    look.gradient_text(run, gradient)


def _media_source(source: Path, node, warnings: list[str]):
    """The local file of an <audio>/<video> element and its MIME type, or (None, None) with a warning."""
    raw = node.attrs.get("src") or next(
        (c.attrs.get("src", "") for c in node.children if isinstance(c, _Node) and c.tag == "source"),
        "",
    )
    path, _warning = local_image(source, raw)
    mime = _MEDIA_TYPES.get(path.suffix.casefold()) if path else None
    if path is None or mime is None:
        warnings.append(
            f"<{node.tag}> {raw or '(no source)'} was not converted: "
            + ("the file is unavailable or outside the input folder." if path is None else "unsupported type.")
        )
        return None, None
    return path, mime


def _ancestors(node, parents):
    chain = []
    while id(node) in parents:
        node = parents[id(node)]
        chain.append(node)
    return chain


def _no_insets(frame) -> None:
    body = frame._txBody.find("{http://schemas.openxmlformats.org/drawingml/2006/main}bodyPr")
    for side in ("lIns", "tIns", "rIns", "bIns"):
        body.set(side, "0")


def _finish_slide(slide, data: _Slide, effects, css: _Css, counts, unknown_transitions: set[str]) -> None:
    """Speaker notes, the slide transition and the animation timing, shared by both layouts."""
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


def convert_html_to_pptx(
    input_path: str | Path, output_path: str | Path, fidelity: str = "editable", use_browser: bool = True
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    source, destination, path_errors = validate_office_paths(input_path, output_path, ".pptx")
    if path_errors:
        return False, {}, path_errors
    try:
        from pptx import Presentation
        from pptx.util import Emu, Inches
    except ImportError:
        return (
            False,
            {},
            [{"code": "CONVERTER_UNAVAILABLE", "message": "Install the html optional dependency: python-pptx."}],
        )
    from .html_styles import load as load_styles

    html, _encoding, decode_warning = decode_html_bytes(source.read_bytes())
    styled = load_styles(source, use_browser=use_browser, viewport=(1280, 720))
    parser = styled.parser
    css = parse_css(html)
    slides = collect_slides(styled.root)
    browser_ok = styled.mode == "browser"
    if fidelity == "appearance" and not browser_ok:
        return (
            False,
            {},
            [
                {
                    "code": "BROWSER_BACKEND_UNAVAILABLE",
                    "message": "Appearance mode places elements where the browser puts them: it needs Node.js, "
                    "Playwright and Edge (or Chromium via WPS_AGENT_EDGE).",
                }
            ],
        )
    # Per slide, not per deck: a slide without a <section> container (deck chrome such as a nav bar) falls back
    # to the editable layout instead of refusing the whole file.
    positioned_any = browser_ok and any(s.section is not None and styled.box(s.section) for s in slides)
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
    if fidelity == "appearance" and browser_ok and not positioned_any:
        warnings.append(
            "No slide had a <section> container with a browser layout; the editable layout was used for every slide."
        )

    presentation = Presentation()
    if positioned_any:
        # 16:9, like the 1280 x 720 viewport the browser laid the sections out in.
        presentation.slide_width, presentation.slide_height = Emu(12192000), Emu(6858000)
    layouts = presentation.slide_layouts
    width, height = presentation.slide_width, presentation.slide_height
    margin = Inches(0.5)
    counts = {"tables": 0, "images": 0, "media": 0, "notes": 0, "animations": 0, "transitions": 0}
    partial_animations = 0
    unknown_transitions: set[str] = set()
    by_index = {n.attrs.get("data-wps-i"): n for n in _walk(styled.root) if n.attrs.get("data-wps-i")}
    for index, data in enumerate(slides):
        is_positioned = browser_ok and data.section is not None and styled.box(data.section)
        slide = presentation.slides.add_slide(layouts[5] if is_positioned else layouts[1])
        effects: list[tuple[int, int | None, Animation, str]] = []
        if is_positioned:
            effects = _positioned_slide(slide, data, styled, css, source, fidelity == "appearance", counts, warnings)
            _finish_slide(slide, data, effects, css, counts, unknown_transitions)
            continue
        if fidelity == "appearance" and positioned_any:
            warnings.append(
                f"Slide {index + 1} has no <section> container with a browser layout; "
                "the editable layout was used for that slide."
            )
        # The editable layout never painted the slide's background, so light text on a dark section came out
        # white on white; paint the section's background (or the nearest ancestor's) here.
        _set_slide_background(slide, styled, _background_start(data))
        title_shape = slide.shapes.title
        if data.title is not None:
            _fill_paragraph(title_shape.text_frame.paragraphs[0], _runs(data.title))
            _style_runs(title_shape.text_frame.paragraphs[0], styled, data.title, 1.0)
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
                    _bullets(paragraph, line.node.tag == "li")
                    _style_runs(paragraph, styled, by_index.get(line.node.attrs.get("data-wps-i"), line.node), 1.0)
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
                                if cell_node.tag == "th":
                                    run.font.bold = True
                            original = by_index.get(cell_node.attrs.get("data-wps-i"), cell_node)
                            _style_runs(paragraph, styled, original, 1.0)
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
                path, mime = _media_source(source, node, warnings)
                if path is None:
                    continue
                movie = slide.shapes.add_movie(str(path), margin, position, width - 2 * margin, slot, mime_type=mime)
                counts["media"] += 1
                del movie
            position += slot
        _finish_slide(slide, data, effects, css, counts, unknown_transitions)
    partial_animations += counts.pop("partial_animations", 0)
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
