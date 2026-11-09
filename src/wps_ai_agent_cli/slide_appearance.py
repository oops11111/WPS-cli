"""DrawingML for HTML boxes on a slide (P13-006 appearance mode).

The browser's computed style of an element becomes a shape that looks like it: a solid or gradient fill with its
opacity, rounded corners or an oval, an outline when all four borders match and a bar per side when they do not, an
outer shadow, and gradient-filled text for `background-clip: text`. python-pptx has no API for gradient stops with
opacity, shadows or text gradients, so those are written as XML.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Any

from .html_styles import color_alpha, parse_gradient, px, split_top_level

if TYPE_CHECKING:
    from lxml import etree

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
EMU_PER_PX = 9525
_FILLS = {f"{{{A}}}{name}" for name in ("noFill", "solidFill", "gradFill", "blipFill", "pattFill", "grpFill")}


def _a(tag: str, **attrs: str) -> etree._Element:
    from lxml import etree  # with python-pptx (the html extra)

    return etree.Element(f"{{{A}}}{tag}", {key: str(value) for key, value in attrs.items()})


def color_element(hue: str, alpha: float = 1.0) -> etree._Element:
    element = _a("srgbClr", val=hue)
    if alpha < 1.0:
        element.append(_a("alpha", val=str(round(max(0.0, alpha) * 100000))))
    return element


def solid_fill(hue: str, alpha: float = 1.0) -> etree._Element:
    fill = _a("solidFill")
    fill.append(color_element(hue, alpha))
    return fill


def gradient_fill(gradient: dict[str, Any], opacity: float = 1.0) -> etree._Element:
    """A gradFill from parse_gradient(): linear at the CSS angle, or radial from the centre."""
    fill = _a("gradFill", rotWithShape="1")
    stops = _a("gsLst")
    for hue, alpha, position in sorted(gradient["stops"], key=lambda stop: stop[2]):
        stop = _a("gs", pos=str(round(position * 100000)))
        stop.append(color_element(hue, alpha * opacity))
        stops.append(stop)
    fill.append(stops)
    if gradient["kind"] == "radial":
        path = _a("path", path="circle")
        path.append(_a("fillToRect", l="50000", t="50000", r="50000", b="50000"))
        fill.append(path)
    else:
        # CSS measures from "upwards" clockwise; DrawingML from "to the right" clockwise.
        fill.append(_a("lin", ang=str(round(((gradient["angle"] - 90) % 360) * 60000)), scaled="0"))
    return fill


def fill_of(style: dict[str, str], opacity: float = 1.0) -> etree._Element | None:
    """The fill a box's background gives: its gradient, else its colour; None when it shows nothing."""
    gradient = parse_gradient(style.get("background-image"))
    if gradient:
        return gradient_fill(gradient, opacity)
    hue, alpha = color_alpha(style.get("background-color"))
    if hue and alpha * opacity > 0:
        return solid_fill(hue, alpha * opacity)
    return None


def _replace_fill(parent: etree._Element, fill: etree._Element, after: tuple[str, ...]) -> None:
    for old in [child for child in parent if child.tag in _FILLS]:
        parent.remove(old)
    anchor = None
    for child in parent:
        if child.tag in {f"{{{A}}}{name}" for name in after}:
            anchor = child
    if anchor is None:
        parent.insert(0, fill)
    else:
        anchor.addnext(fill)


def set_shape_fill(shape, fill: etree._Element | None) -> None:
    if fill is None:
        shape.fill.background()
        return
    _replace_fill(shape._element.spPr, fill, ("xfrm", "custGeom", "prstGeom"))


def set_background(slide, fill: etree._Element) -> None:
    slide.background.fill.solid()  # creates <p:bg><p:bgPr> with a fill python-pptx manages
    background_properties = slide._element.cSld.bg.bgPr
    _replace_fill(background_properties, fill, ())


def set_outline(shape, hue: str, alpha: float, width_emu: int) -> None:
    line = shape.line
    line.width = max(1, width_emu)
    _replace_fill(line._get_or_add_ln(), solid_fill(hue, alpha), ())


def parse_shadow(value: str | None, factor: float) -> dict[str, Any] | None:
    """The first outer shadow of a computed box-shadow ("rgba(0, 0, 0, 0.08) 0px 1px 3px 0px")."""
    if not value or value.strip() == "none":
        return None
    first = split_top_level(value)[0]
    if "inset" in first.split():
        return None
    found = re.match(r"(rgba?\([^)]*\)|#[0-9a-fA-F]{3,8})\s+(.*)$", first.strip())
    if not found:
        return None
    hue, alpha = color_alpha(found.group(1))
    lengths = [px(part) or 0.0 for part in found.group(2).split()]
    if not hue or alpha <= 0 or len(lengths) < 2:
        return None
    x, y = lengths[0], lengths[1]
    blur = lengths[2] if len(lengths) > 2 else 0.0
    return {
        "hue": hue,
        "alpha": alpha,
        "distance": round(math.hypot(x, y) * EMU_PER_PX * factor),
        "direction": round((math.degrees(math.atan2(y, x)) % 360) * 60000),
        "blur": round(blur * EMU_PER_PX * factor),
    }


def add_shadow(shape, shadow: dict[str, Any]) -> None:
    effects = _a("effectLst")
    outer = _a(
        "outerShdw",
        blurRad=str(shadow["blur"]),
        dist=str(shadow["distance"]),
        dir=str(shadow["direction"]),
        algn="ctr",
        rotWithShape="0",
    )
    outer.append(color_element(shadow["hue"], shadow["alpha"]))
    effects.append(outer)
    properties = shape._element.spPr
    for old in properties.findall(f"{{{A}}}effectLst"):
        properties.remove(old)
    line = properties.find(f"{{{A}}}ln")
    if line is not None:
        line.addnext(effects)
    else:
        properties.append(effects)


def gradient_text(run, gradient: dict[str, Any]) -> None:
    """Fill a run's glyphs with a gradient (CSS background-clip: text)."""
    properties = run._r.get_or_add_rPr()
    for old in [child for child in properties if child.tag in _FILLS]:
        properties.remove(old)
    line = properties.find(f"{{{A}}}ln")
    fill = gradient_fill(gradient)
    if line is not None:
        line.addnext(fill)
    else:
        properties.insert(0, fill)


def radius(value: str | None, width: float, height: float) -> float:
    """A corner radius in CSS pixels; a percentage is of the shorter side."""
    if not value:
        return 0.0
    first = value.split()[0]
    if first.endswith("%"):
        try:
            return float(first[:-1]) / 100 * min(width, height)
        except ValueError:
            return 0.0
    return px(first) or 0.0


def borders(style: dict[str, str]) -> list[tuple[str, float, str, float]]:
    """The visible borders: (side, width in CSS pixels, RRGGBB, opacity)."""
    found = []
    for side in ("top", "right", "bottom", "left"):
        width = px(style.get(f"border-{side}-width")) or 0.0
        if width <= 0 or style.get(f"border-{side}-style") in {None, "", "none", "hidden"}:
            continue
        hue, alpha = color_alpha(style.get(f"border-{side}-color"))
        if hue:
            found.append((side, width, hue, alpha))
    return found


def text_is_clipped_background(style: dict[str, str]) -> bool:
    """`background-clip: text` with transparent glyphs: the background paints the text, not a box."""
    clip = f"{style.get('background-clip', '')} {style.get('-webkit-background-clip', '')}"
    if "text" not in clip.split():
        return False
    fill = style.get("-webkit-text-fill-color") or style.get("color")
    return color_alpha(fill)[0] is None
