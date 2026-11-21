"""Measured, bounded static disclosure decoration; never assumes a UA default."""

import math
from copy import deepcopy

ROLE = "wps-ai-agent-cli:closed-details-marker:v1"
WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"


def marker_size(styled, summary):
    """Return (points, warning): explicit none is deliberately silent."""
    outer = styled.style(summary)
    if outer.get("list-style-type") == "none" or outer.get("list-style") == "none":
        return None, None
    data = styled.summary_markers.get(id(summary))
    if data and data.get("style", {}).get("list-style-type") == "none":
        return None, None
    warning = "Closed details marker was not preserved: unsupported or unavailable measured marker metadata."
    if styled.mode != "browser" or not data:
        return None, warning
    if outer.get("letter-spacing") != "normal" or outer.get("text-decoration-line") != "none":
        return None, warning
    style, marker = data.get("style", {}), data.get("marker", {})
    required = {
        "display": "list-item",
        "list-style-type": "disclosure-closed",
        "list-style-position": "inside",
        "list-style-image": "none",
        "direction": "ltr",
        "writing-mode": "horizontal-tb",
        "text-indent": "0px",
    }
    if any(style.get(k) != v for k, v in required.items()) or marker.get("content") != "normal":
        return None, warning
    if any(
        marker.get(k) != style.get(k) or not marker.get(k)
        for k in ("font-size", "font-family", "font-weight", "font-style", "color")
    ):
        return None, warning
    if (
        marker.get("color") != "rgb(0, 0, 0)"
        or marker.get("font-style") != "normal"
        or marker.get("font-weight") != "400"
    ):
        return None, warning
    if any(
        outer.get(f"padding-{side}") != "0px" or outer.get(f"border-{side}-width") != "0px"
        for side in ("left", "right", "top", "bottom")
    ):
        return None, warning
    rects = data.get("textRects", [])
    if len(rects) != 1 or outer.get("text-lines") != "1":
        return None, warning
    try:
        font = marker["font-size"]
        if not font.endswith("px"):
            return None, warning
        size = float(font[:-2]) * 0.75
        advance = (rects[0]["x"] - data["box"]["x"]) * 0.75
        width = rects[0]["width"]
        if (
            not all(math.isfinite(v) for v in (size, advance, width))
            or size <= 0
            or width <= 0
            or abs(advance - 1.06 * size) > 0.05
        ):
            return None, warning
    except (ValueError, KeyError, TypeError):
        return None, warning
    return size, None


def insert_marker(paragraph, size):
    from docx.oxml import parse_xml
    from docx.oxml.ns import qn
    from docx.shared import Pt

    cx, cy = round(1.06 * size * 12700), round(0.66 * size * 12700)
    ids = [
        int(n.get("id"))
        for part in paragraph.part.package.parts
        if (root := getattr(part, "element", None)) is not None
        for n in root.findall(".//" + qn("wp:docPr"))
        if n.get("id", "").isdigit()
    ]
    identifier = max(ids + [0]) + 1
    xml = f'''<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:wps="{WPS}" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><mc:Choice Requires="wps"><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:docPr id="{identifier}" name="Closed details marker" descr="{ROLE}"/><wp:cNvGraphicFramePr/><a:graphic><a:graphicData uri="{WPS}"><wps:wsp><wps:cNvSpPr/><wps:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="0" t="0" r="0" b="0"/><a:pathLst><a:path w="10600" h="6600" stroke="0" fill="norm"><a:moveTo><a:pt x="0" y="0"/></a:moveTo><a:lnTo><a:pt x="5676" y="3300"/></a:lnTo><a:lnTo><a:pt x="0" y="6600"/></a:lnTo><a:close/></a:path></a:pathLst></a:custGeom><a:solidFill><a:srgbClr val="000000"/></a:solidFill><a:ln><a:noFill/></a:ln></wps:spPr><wps:bodyPr/></wps:wsp></a:graphicData></a:graphic></wp:inline></w:drawing></mc:Choice></mc:AlternateContent>'''
    first = next((r for r in paragraph.runs if r.text), None)
    run = paragraph.add_run()
    if first is not None and first._r.rPr is not None:
        run._r.insert(0, deepcopy(first._r.rPr))
    run.font.size = Pt(size)
    run.font.hidden = False
    run._r.append(parse_xml(xml))
    if first is not None:
        first._r.addprevious(run._r)


def is_managed_marker(drawing):
    """Only our identified vector primitive is decorative, never a named picture."""
    from docx.oxml.ns import qn

    docpr = drawing.find(".//" + qn("wp:docPr"))
    graphic = drawing.find(".//" + qn("a:graphicData"))
    path = drawing.find(".//" + qn("a:path"))
    ink = drawing.find(".//" + qn("a:solidFill") + "/" + qn("a:srgbClr"))
    if (
        docpr is None
        or docpr.get("descr") != ROLE
        or graphic is None
        or graphic.get("uri") != WPS
        or path is None
        or drawing.find(qn("wp:inline")) is None
        or ink is None
        or ink.get("val") != "000000"
    ):
        return False
    points = path.findall(".//" + qn("a:pt"))
    return (
        path.get("w") == "10600"
        and path.get("h") == "6600"
        and path.get("stroke") == "0"
        and [(p.get("x"), p.get("y")) for p in points] == [("0", "0"), ("5676", "3300"), ("0", "6600")]
        and drawing.find(".//" + qn("a:blip")) is None
    )
