"""Computed styles and positions of HTML elements, for high-fidelity conversion (P13-004, P13-006).

Every element of the source gets a data-wps-i number. When Node.js, Playwright and a Chromium browser (Edge on
Windows) are available, the browser computes each element's style and box (decision 3 of docs/PHASE13_PLAN.md);
otherwise a built-in cascade does: user-agent defaults, <style> rules with type, class, id and descendant
selectors, inline style attributes and inheritance. The result says which one was used (`mode`).

Values are kept as CSS strings (as getComputedStyle returns them); the helpers below turn them into points,
colours and booleans for the converters.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .html_editable import _Node, _TreeParser, _walk
from .html_text import decode_html_bytes

_LAYOUT_SCRIPT = Path(__file__).with_name("html_layout_playwright.cjs")
ANNOTATION = "data-wps-i"
INHERITED = {
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "color",
    "letter-spacing",
    "text-align",
    "line-height",
    "visibility",
    "white-space",
}
DEFAULT_STYLE = {
    "display": "inline",
    "font-family": "Microsoft YaHei, Noto Sans CJK SC, sans-serif",
    "font-size": "16px",
    "font-weight": "400",
    "font-style": "normal",
    "color": "rgb(0, 0, 0)",
    "background-color": "rgba(0, 0, 0, 0)",
    "text-align": "start",
    "line-height": "normal",
    "text-decoration-line": "none",
}
_BLOCK = {
    "html",
    "body",
    "div",
    "p",
    "section",
    "article",
    "header",
    "footer",
    "main",
    "aside",
    "nav",
    "blockquote",
    "pre",
    "address",
    "figure",
    "figcaption",
    "ul",
    "ol",
    "dl",
    "dt",
    "dd",
    "details",
    "summary",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "caption",
}
# User-agent defaults the browser would apply (Chromium's), for the cascade.
_UA = {
    "body": {"margin-top": "8px", "margin-right": "8px", "margin-bottom": "8px", "margin-left": "8px"},
    "h1": {"font-size": "2em", "font-weight": "700", "margin-top": "0.67em", "margin-bottom": "0.67em"},
    "h2": {"font-size": "1.5em", "font-weight": "700", "margin-top": "0.83em", "margin-bottom": "0.83em"},
    "h3": {"font-size": "1.17em", "font-weight": "700", "margin-top": "1em", "margin-bottom": "1em"},
    "h4": {"font-weight": "700", "margin-top": "1.33em", "margin-bottom": "1.33em"},
    "h5": {"font-size": "0.83em", "font-weight": "700", "margin-top": "1.67em", "margin-bottom": "1.67em"},
    "h6": {"font-size": "0.67em", "font-weight": "700", "margin-top": "2.33em", "margin-bottom": "2.33em"},
    "p": {"margin-top": "1em", "margin-bottom": "1em"},
    "blockquote": {"margin-top": "1em", "margin-bottom": "1em", "margin-left": "40px"},
    "ul": {"margin-top": "1em", "margin-bottom": "1em", "padding-left": "40px"},
    "ol": {"margin-top": "1em", "margin-bottom": "1em", "padding-left": "40px"},
    "pre": {"font-family": "monospace", "white-space": "pre"},
    "code": {"font-family": "monospace"},
    "b": {"font-weight": "700"},
    "strong": {"font-weight": "700"},
    "th": {"font-weight": "700", "text-align": "center"},
    "i": {"font-style": "italic"},
    "em": {"font-style": "italic"},
    "u": {"text-decoration-line": "underline"},
    "s": {"text-decoration-line": "line-through"},
    "del": {"text-decoration-line": "line-through"},
    "a": {"color": "rgb(0, 0, 238)", "text-decoration-line": "underline"},
    "small": {"font-size": "smaller"},
}
_NAMED = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "yellow": (255, 255, 0),
    "navy": (0, 0, 128),
    "teal": (0, 128, 128),
    "silver": (192, 192, 192),
    "maroon": (128, 0, 0),
}


# ---------------------------------------------------------------------------------------------- annotation


class _Positions(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.starts: list[tuple[int, int, str]] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if self._skip:
            return
        line, column = self.getpos()
        self.starts.append((line, column, tag))
        if tag in {"script", "style"}:
            self._skip = 1

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._skip = 0


def annotate(html: str) -> str:
    """Give every start tag a data-wps-i number, in document order."""
    finder = _Positions()
    finder.feed(html)
    finder.close()
    # HTMLParser.getpos() counts lines by "\n" alone; splitlines() would also break at a lone "\r", U+2028 and
    # other separators and put every later number in the wrong place.
    offsets = [0]
    for line in html.split("\n"):
        offsets.append(offsets[-1] + len(line) + 1)
    insertions = []
    for number, (line, column, tag) in enumerate(finder.starts):
        start = offsets[line - 1] + column
        insertions.append((start + 1 + len(tag), f' {ANNOTATION}="{number}"'))
    pieces, last = [], 0
    for position, text in insertions:
        pieces.append(html[last:position])
        pieces.append(text)
        last = position
    pieces.append(html[last:])
    return "".join(pieces)


# ---------------------------------------------------------------------------------------------- CSS parsing


@dataclass
class _Rule:
    selector: list[tuple[str | None, list[str], str | None]]  # descendant chain of (tag, classes, id)
    specificity: tuple[int, int, int]
    order: int
    declarations: dict[str, str]


def declarations(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for declaration in text.split(";"):
        name, _, value = declaration.partition(":")
        name, value = name.strip().casefold(), value.strip()
        if not name or not value:
            continue
        value = re.sub(r"\s*!important\s*$", "", value)
        result.update(_expand(name, value))
    return result


def _expand(name: str, value: str) -> dict[str, str]:
    """Shorthands the converters read: margin, padding, border, background, font, text-decoration."""
    if name in {"margin", "padding"}:
        parts = value.split()
        top, right, bottom, left = (parts + parts * 3)[:4] if len(parts) == 1 else _box(parts)
        return {f"{name}-top": top, f"{name}-right": right, f"{name}-bottom": bottom, f"{name}-left": left}
    if name == "border" or re.fullmatch(r"border-(top|right|bottom|left)", name):
        sides = ["top", "right", "bottom", "left"] if name == "border" else [name.split("-")[1]]
        width, style, color = "medium", "none", "currentcolor"
        for token in re.findall(r"rgba?\([^)]*\)|\S+", value):
            if token in {"none", "solid", "dashed", "dotted", "double", "groove", "ridge", "inset", "outset", "hidden"}:
                style = token
            elif re.match(r"^[\d.]+(px|pt|em|rem)?$", token) or token in {"thin", "medium", "thick"}:
                width = token
            else:
                color = token
        result = {}
        for side in sides:
            result.update({f"border-{side}-width": width, f"border-{side}-style": style, f"border-{side}-color": color})
        return result
    if name == "background":
        color = re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|\b(" + "|".join(_NAMED) + r")\b", value)
        image = re.search(r"url\([^)]*\)", value)
        result = {}
        if color:
            result["background-color"] = color.group(0)
        if image:
            result["background-image"] = image.group(0)
        return result
    if name == "text-decoration":
        return {"text-decoration-line": value}
    if name == "font":
        match = re.match(r"(?:(italic|oblique)\s+)?(?:(bold|bolder|\d{3})\s+)?([\d.]+\w+)(?:/(\S+))?\s+(.+)", value)
        if match:
            result = {"font-size": match.group(3), "font-family": match.group(5)}
            if match.group(1):
                result["font-style"] = match.group(1)
            if match.group(2):
                result["font-weight"] = match.group(2)
            if match.group(4):
                result["line-height"] = match.group(4)
            return result
    if name == "page-break-before":
        return {"page-break-before": value, "break-before": "page" if value == "always" else value}
    return {name: value}


def _box(parts: list[str]) -> list[str]:
    if len(parts) == 2:
        return [parts[0], parts[1], parts[0], parts[1]]
    if len(parts) == 3:
        return [parts[0], parts[1], parts[2], parts[1]]
    return parts[:4]


def _simple(selector: str) -> tuple[str | None, list[str], str | None] | None:
    match = re.fullmatch(r"([a-zA-Z][\w-]*|\*)?((?:\.[\w-]+)*)(#[\w-]+)?((?:\.[\w-]+)*)", selector)
    if not match or not selector:
        return None
    tag = match.group(1) if match.group(1) not in {None, "*"} else None
    classes = [c for c in (match.group(2) + match.group(4)).split(".") if c]
    ident = match.group(3)[1:] if match.group(3) else None
    return (tag.casefold() if tag else None, classes, ident)


@dataclass
class StyleSheet:
    rules: list[_Rule] = field(default_factory=list)
    page: dict[str, str] = field(default_factory=dict)
    unsupported_selectors: set[str] = field(default_factory=set)

    @classmethod
    def parse(cls, css: str) -> StyleSheet:
        sheet = cls()
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        for body in re.findall(r"@page[^{]*\{([^{}]*)\}", css):
            sheet.page.update(declarations(body))
        css = re.sub(r"@(?:-webkit-)?keyframes\s+[\w-]+\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)
        css = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)
        css = re.sub(r"@page[^{]*\{[^{}]*\}", "", css)
        order = 0
        for selectors, body in re.findall(r"([^{}@]+)\{([^{}]*)\}", css):
            values = declarations(body)
            for selector in selectors.split(","):
                selector = selector.strip()
                if not selector:
                    continue
                parts = selector.split()
                chain = [_simple(part) for part in parts]
                if any(part is None for part in chain):
                    sheet.unsupported_selectors.add(selector)
                    continue
                specificity = (
                    sum(1 for p in chain if p[2]),
                    sum(len(p[1]) for p in chain),
                    sum(1 for p in chain if p[0]),
                )
                order += 1
                sheet.rules.append(_Rule(chain, specificity, order, values))
        return sheet


def _matches(simple: tuple[str | None, list[str], str | None], node: _Node) -> bool:
    tag, classes, ident = simple
    if tag and node.tag != tag:
        return False
    if ident and node.attrs.get("id") != ident:
        return False
    own = set(node.attrs.get("class", "").split())
    return all(c in own for c in classes)


def _rule_matches(rule: _Rule, node: _Node, ancestors: list[_Node]) -> bool:
    if not _matches(rule.selector[-1], node):
        return False
    remaining = rule.selector[:-1]
    for ancestor in reversed(ancestors):
        if not remaining:
            break
        if _matches(remaining[-1], ancestor):
            remaining = remaining[:-1]
    return not remaining


# ---------------------------------------------------------------------------------------------- values


def px(value: str | None, font_size: float = 16.0, parent_size: float | None = None) -> float | None:
    """A CSS length in CSS pixels (1px = 0.75pt), or None for auto, normal and unknown units."""
    if value is None:
        return None
    value = value.strip().casefold()
    named = {"thin": 1.0, "medium": 3.0, "thick": 5.0, "0": 0.0}
    if value in named:
        return named[value]
    match = re.fullmatch(r"(-?[\d.]+)(px|pt|em|rem|%|cm|mm|in)?", value)
    if not match:
        return None
    number, unit = float(match.group(1)), match.group(2) or "px"
    return {
        "px": number,
        "pt": number / 0.75,
        "em": number * font_size,
        "rem": number * 16.0,
        "%": number / 100 * (parent_size if parent_size is not None else font_size),
        "cm": number * 96 / 2.54,
        "mm": number * 96 / 25.4,
        "in": number * 96,
    }[unit]


def points(value: str | None, font_size: float = 16.0) -> float | None:
    length = px(value, font_size)
    return None if length is None else round(length * 0.75, 2)


def color(value: str | None) -> str | None:
    """A colour as RRGGBB, or None when it is transparent or unknown."""
    if not value:
        return None
    value = value.strip().casefold()
    match = re.fullmatch(r"rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)(?:[,\s/]+([\d.]+%?))?\s*\)", value)
    if match:
        alpha = match.group(4)
        if alpha is not None and (float(alpha.rstrip("%")) == 0):
            return None
        return "".join(f"{int(match.group(i)):02X}" for i in (1, 2, 3))
    match = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})(?:[0-9a-f]{2})?", value)
    if match:
        digits = match.group(1)
        return (digits if len(digits) == 6 else "".join(ch * 2 for ch in digits)).upper()
    if value in _NAMED:
        return "".join(f"{part:02X}" for part in _NAMED[value])
    return None


def color_alpha(value: str | None) -> tuple[str | None, float]:
    """A colour as RRGGBB and its opacity from 0 to 1; (None, 0.0) when transparent or unknown."""
    if not value:
        return None, 0.0
    match = re.fullmatch(
        r"rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)(?:[,\s/]+([\d.]+)(%?))?\s*\)", value.strip().casefold()
    )
    if match:
        alpha = 1.0 if match.group(4) is None else float(match.group(4)) / (100.0 if match.group(5) else 1.0)
        if alpha <= 0:
            return None, 0.0
        return "".join(f"{int(match.group(i)):02X}" for i in (1, 2, 3)), min(alpha, 1.0)
    hue = color(value)
    return (hue, 1.0) if hue else (None, 0.0)


def split_top_level(value: str, separator: str = ",") -> list[str]:
    """Split at separators outside parentheses: the parts of a gradient, or the layers of a background."""
    parts, depth, start = [], 0, 0
    for index, char in enumerate(value):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == separator and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    return [part for part in parts if part]


_GRADIENT = re.compile(r"(repeating-)?(linear|radial)-gradient\((.*)\)$", re.S)
_SIDES = {"top": 0.0, "right": 90.0, "bottom": 180.0, "left": 270.0}


def parse_gradient(value: str | None) -> dict[str, Any] | None:
    """The first gradient layer of a computed background-image.

    {"kind": "linear" or "radial", "angle": CSS degrees (0 is upwards, 90 to the right), "stops": [(RRGGBB, opacity,
    position from 0 to 1)]}, or None when there is no gradient this can read.
    """
    if not value or "gradient(" not in value:
        return None
    layer = split_top_level(value.strip())[0]
    match = _GRADIENT.match(layer)
    if not match:
        return None
    kind, args = match.group(2), split_top_level(match.group(3))
    angle = 180.0
    if args and not re.match(r"(rgba?\(|#|[a-z]+\s+\d|[a-z]+$)", args[0]) or (args and args[0].startswith("to ")):
        head = args.pop(0)
        degrees = re.fullmatch(r"(-?[\d.]+)(deg|turn|rad)", head)
        if degrees:
            number = float(degrees.group(1))
            angle = number * {"deg": 1.0, "turn": 360.0, "rad": 57.29577951308232}[degrees.group(2)]
        elif head.startswith("to "):
            sides = [_SIDES[word] for word in head[3:].split() if word in _SIDES]
            if len(sides) == 2:
                # A corner: halfway between the two sides, taking the wrap from left (270) to top (0/360) into account.
                first, second = sorted(sides)
                angle = (first + second) / 2 if second - first <= 180 else ((first + second + 360) / 2) % 360
            elif sides:
                angle = sides[0]
    elif kind == "radial" and args and not re.match(r"(rgba?\(|#)", args[0]):
        args.pop(0)  # shape and size of a radial gradient: drawn as a circle from the centre
    stops: list[tuple[str, float, float | None]] = []
    for arg in args:
        found = re.match(r"(rgba?\([^)]*\)|#[0-9a-fA-F]{3,8}|[a-zA-Z]+)\s*(-?[\d.]+%)?", arg)
        if not found:
            continue
        hue, alpha = color_alpha(found.group(1))
        position = float(found.group(2)[:-1]) / 100 if found.group(2) else None
        stops.append((hue or "000000", alpha if hue else 0.0, position))
    if len(stops) < 2:
        return None
    # Stops without a position are spread evenly between their neighbours, as CSS does.
    positions = [stop[2] for stop in stops]
    if positions[0] is None:
        positions[0] = 0.0
    if positions[-1] is None:
        positions[-1] = 1.0
    index = 0
    while index < len(positions):
        if positions[index] is None:
            end = index
            while positions[end] is None:
                end += 1
            low, high = positions[index - 1], positions[end]
            for offset, slot in enumerate(range(index, end), 1):
                positions[slot] = low + (high - low) * offset / (end - index + 1)
            index = end
        index += 1
    result = [
        (hue, alpha, max(0.0, min(1.0, position))) for (hue, alpha, _), position in zip(stops, positions, strict=True)
    ]
    # CSS fades to "transparent" in the neighbouring colour; a black transparent stop would darken the fade elsewhere.
    for index, (_hue, alpha, position) in enumerate(result):
        if alpha == 0.0:
            neighbour = next((r for r in result[index + 1 :] + result[:index][::-1] if r[1] > 0), None)
            if neighbour:
                result[index] = (neighbour[0], 0.0, position)
    return {"kind": kind, "angle": angle % 360, "stops": result}


def first_font(value: str | None) -> str | None:
    """The first concrete family of a font-family list (generic names map to common fonts)."""
    if not value:
        return None
    generic = {"sans-serif": "Microsoft YaHei", "serif": "SimSun", "monospace": "Consolas", "system-ui": None}
    for family in value.split(","):
        family = family.strip().strip("'\"")
        if not family:
            continue
        if family.casefold() in generic:
            return generic[family.casefold()]
        return family
    return None


def is_bold(style: dict[str, str]) -> bool:
    weight = style.get("font-weight", "400")
    return weight in {"bold", "bolder"} or (weight.isdigit() and int(weight) >= 600)


# ---------------------------------------------------------------------------------------------- provider


@dataclass
class StyledDocument:
    """The parsed HTML with each element's computed style (and box, from the browser)."""

    source: Path
    root: _Node
    mode: str  # "browser" or "cascade"
    styles: dict[int, dict[str, str]]
    boxes: dict[int, dict[str, float]]
    page: dict[str, str]
    css_text: str
    warnings: list[str] = field(default_factory=list)
    section_screenshots: list[str] = field(default_factory=list)
    browser: str | None = None
    parser: Any = None
    # Decorative ::before/::after boxes the browser reported for an element: {id(node): [computed values]}.
    pseudo: dict[int, list[dict[str, str]]] = field(default_factory=dict)

    def style(self, node: _Node) -> dict[str, str]:
        return self.styles.get(id(node), DEFAULT_STYLE)

    def box(self, node: _Node) -> dict[str, float] | None:
        return self.boxes.get(id(node))

    def pseudo_elements(self, node: _Node) -> list[dict[str, str]]:
        return self.pseudo.get(id(node), [])

    def inline_ancestors(self, node: _Node) -> list[_Node]:
        """The node and the inline elements around it, innermost first, up to its block."""
        parents = self.__dict__.get("_parents")
        if parents is None:
            parents = {id(c): n for n in _walk(self.root) for c in n.children if isinstance(c, _Node)}
            self.__dict__["_parents"] = parents
        chain = [node]
        while id(chain[-1]) in parents and self.style(chain[-1]).get("display", "inline") == "inline":
            chain.append(parents[id(chain[-1])])
        return chain

    def font_size(self, node: _Node) -> float:
        return px(self.style(node).get("font-size")) or 16.0


def browser_runtime() -> tuple[str | None, str | None]:
    from .html_render import _resolve_browser_runtime

    if os.environ.get("WPS_AGENT_NO_BROWSER") == "1":
        return None, None
    return _resolve_browser_runtime()


def _cascade(root: _Node, sheet: StyleSheet) -> dict[int, dict[str, str]]:
    styles: dict[int, dict[str, str]] = {}

    def visit(node: _Node, ancestors: list[_Node], inherited: dict[str, str]) -> None:
        style = {key: value for key, value in inherited.items() if key in INHERITED}
        style["display"] = "block" if node.tag in _BLOCK else ("table-cell" if node.tag in {"td", "th"} else "inline")
        declared: dict[str, str] = dict(_UA.get(node.tag, {}))
        matched = sorted(
            (rule for rule in sheet.rules if _rule_matches(rule, node, ancestors)),
            key=lambda rule: (rule.specificity, rule.order),
        )
        for rule in matched:
            declared.update(rule.declarations)
        if node.attrs.get("style"):
            declared.update(declarations(node.attrs["style"]))
        parent_size = px(inherited.get("font-size")) or 16.0
        for name, value in declared.items():
            if name == "font-size":
                if value in {"smaller", "larger"}:
                    value = f"{parent_size * (0.83 if value == 'smaller' else 1.2)}px"
                length = px(value, parent_size, parent_size)
                style[name] = f"{length}px" if length is not None else inherited.get(name, "16px")
            elif value == "inherit":
                style[name] = inherited.get(name, DEFAULT_STYLE.get(name, ""))
            else:
                style[name] = value
        size = px(style.get("font-size")) or parent_size
        for name in list(style):
            if name.startswith(("margin", "padding", "text-indent", "letter-spacing")) or name.endswith("-width"):
                length = px(style[name], size, None)
                if length is not None:
                    style[name] = f"{length}px"
        if style.get("line-height", "normal") not in {"normal"}:
            value = style["line-height"]
            if re.fullmatch(r"[\d.]+", value):
                style["line-height"] = f"{float(value) * size}px"
            else:
                length = px(value, size, size)
                if length is not None:
                    style["line-height"] = f"{length}px"
        styles[id(node)] = style
        for child in node.children:
            if isinstance(child, _Node):
                visit(child, [*ancestors, node], style)

    visit(root, [], dict(DEFAULT_STYLE))
    return styles


def _browser_layout(
    annotated: Path, root_dir: Path, node: str, browser: str, viewport: tuple[int, int], shots_dir: Path | None
) -> dict[str, Any]:
    request = {
        "input_path": str(annotated),
        "resource_root": str(root_dir),
        "browser_executable": browser,
        "viewport_width": viewport[0],
        "viewport_height": viewport[1],
        "timeout_seconds": 60,
        "section_screenshots_dir": str(shots_dir) if shots_dir else None,
    }
    completed = subprocess.run(
        [node, str(_LAYOUT_SCRIPT)],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    try:
        return json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return {"ok": False, "message": (completed.stderr or completed.stdout)[:500]}


def load(
    source: str | Path,
    *,
    use_browser: bool = True,
    viewport: tuple[int, int] = (1280, 720),
    screenshots_dir: Path | None = None,
) -> StyledDocument:
    """Parse the HTML at source and compute each element's style, with the browser when it is available."""
    path = Path(source)
    html, _encoding, _warning = decode_html_bytes(path.read_bytes())
    marked = annotate(html)
    parser = _TreeParser()
    parser.feed(marked)
    parser.close()
    css_text = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.S | re.I))
    for node in _walk(parser.root):
        if node.tag == "link" and node.attrs.get("rel", "").casefold() == "stylesheet":
            href = node.attrs.get("href", "")
            linked = (path.parent / href).resolve() if href and not re.match(r"^[a-z][\w+.-]*:", href, re.I) else None
            if linked and linked.is_file() and path.parent.resolve() in linked.parents:
                css_text = linked.read_text(encoding="utf-8", errors="replace") + "\n" + css_text
    sheet = StyleSheet.parse(css_text)
    nodes = {node.attrs.get(ANNOTATION): node for node in _walk(parser.root) if node.attrs.get(ANNOTATION)}
    warnings: list[str] = []
    node_bin, browser = browser_runtime() if use_browser else (None, None)
    if node_bin and browser and _LAYOUT_SCRIPT.is_file():
        # Next to the source, so that relative image and style references resolve as they do for the source.
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=".wps-layout-", suffix=".html", delete=False
        )
        try:
            with handle:
                handle.write(marked)
            reply = _browser_layout(Path(handle.name), path.parent, node_bin, browser, viewport, screenshots_dir)
        finally:
            Path(handle.name).unlink(missing_ok=True)
        if reply.get("ok"):
            styles, boxes, pseudo = {}, {}, {}
            for key, entry in reply["elements"].items():
                node = nodes.get(key)
                if node is not None:
                    decorations = entry["style"].pop("pseudo", None)
                    if decorations:
                        pseudo[id(node)] = decorations
                    styles[id(node)] = entry["style"]
                    boxes[id(node)] = entry["box"]
            # Elements the browser does not report (the parser's document root) inherit the defaults.
            return StyledDocument(
                path,
                parser.root,
                "browser",
                styles,
                boxes,
                sheet.page,
                css_text,
                warnings,
                list(reply.get("section_screenshots") or []),
                reply.get("browser"),
                parser,
                pseudo,
            )
        warnings.append(
            f"The browser could not lay the page out ({reply.get('message', 'no reply')}); used the cascade."
        )
    if sheet.unsupported_selectors:
        warnings.append(
            "Selectors the built-in cascade does not support were ignored: "
            + ", ".join(sorted(sheet.unsupported_selectors))[:300]
        )
    return StyledDocument(
        path, parser.root, "cascade", _cascade(parser.root, sheet), {}, sheet.page, css_text, warnings, parser=parser
    )


def has_browser() -> bool:
    node, browser = browser_runtime()
    return bool(node and browser and _LAYOUT_SCRIPT.is_file())
