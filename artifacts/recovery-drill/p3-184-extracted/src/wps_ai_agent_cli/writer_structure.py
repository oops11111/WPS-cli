from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from .document_text import _paragraph_text


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
UNSTABLE_TEXT_CONTAINERS = {f"{W}{tag}" for tag in ("del", "moveFrom", "ins", "moveTo", "txbxContent")}


def _value(element: ET.Element | None) -> str | None:
    return element.get(f"{W}val") if element is not None else None


def read_writer_structure(path: str | Path) -> dict[str, Any]:
    with ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        styles_root = (
            ET.fromstring(archive.read("word/styles.xml"))
            if "word/styles.xml" in archive.namelist() else ET.Element(f"{W}styles")
        )
        stories = [("word/document.xml", document)]
        for name in sorted(archive.namelist()):
            if name.startswith(("word/header", "word/footer")) and name.endswith(".xml"):
                stories.append((name, ET.fromstring(archive.read(name))))

    body = document.find(f"{W}body")
    if body is None:
        raise ValueError("Writer structure requires Transitional OOXML with a document body.")
    paragraphs = list(body.findall(f"{W}p"))
    paragraph_indices = {paragraph: index for index, paragraph in enumerate(paragraphs, 1)}
    style_nodes = [style for style in styles_root.findall(f"{W}style") if style.get(f"{W}type") == "paragraph"]
    style_counts = Counter(style.get(f"{W}styleId") for style in style_nodes)
    styles = {style.get(f"{W}styleId"): style for style in style_nodes if style_counts[style.get(f"{W}styleId")] == 1}
    default_style = next((key for key, style in styles.items() if style.get(f"{W}default") in {"1", "true", "on"}), None)
    default_outline = styles_root.find(f"{W}docDefaults/{W}pPrDefault/{W}pPr/{W}outlineLvl")
    warnings = []
    items = []
    for index, paragraph in enumerate(paragraphs, 1):
        explicit_style = _value(paragraph.find(f"{W}pPr/{W}pStyle"))
        style_id = explicit_style if explicit_style is not None else default_style
        style = styles.get(style_id)
        outline = paragraph.find(f"{W}pPr/{W}outlineLvl")
        source = "paragraph" if outline is not None else None
        resolution = "resolved" if style is not None else "none"
        current = style_id
        seen = set()
        while current:
            if style_counts[current] > 1:
                resolution = "duplicate_style"
                break
            if current in seen:
                resolution = "cycle"
                break
            seen.add(current)
            inherited = styles.get(current)
            if inherited is None:
                resolution = "missing_style"
                break
            if outline is None:
                outline = inherited.find(f"{W}pPr/{W}outlineLvl")
                if outline is not None:
                    source = f"style:{current}"
            current = _value(inherited.find(f"{W}basedOn"))
        if outline is None and resolution not in {"cycle", "missing_style", "duplicate_style"}:
            outline = default_outline
            source = "document_default" if outline is not None else None
        level = None
        if outline is not None:
            try:
                level = int(_value(outline))
                if not 0 <= level <= 9:
                    raise ValueError
            except (TypeError, ValueError):
                level = None
                warnings.append({"paragraph_index": index, "code": "INVALID_OUTLINE_LEVEL"})
        if resolution in {"cycle", "missing_style", "duplicate_style"}:
            warnings.append({"paragraph_index": index, "code": resolution.upper(), "style_id": style_id})
        items.append({
            "paragraph_index": index,
            "style_id": style_id,
            "style_name": _value(style.find(f"{W}name")) if style is not None else None,
            "style_is_explicit": explicit_style is not None,
            "style_resolution": resolution,
            "outline_level": level,
            "outline_source": source,
            "heading_level": level + 1 if level is not None and level < 9 else None,
        })

    bookmarks = []
    for part, root in stories:
        parents = {child: parent for parent in root.iter() for child in parent}
        story_paragraphs = list(root.iter(f"{W}p"))
        story_paragraph_indices = {paragraph: index for index, paragraph in enumerate(story_paragraphs, 1)}

        def location(node: ET.Element) -> dict[str, Any]:
            ancestors = []
            cursor = parents.get(node)
            while cursor is not None:
                ancestors.append(cursor)
                cursor = parents.get(cursor)
            paragraph_index = None
            story_paragraph = next((ancestor for ancestor in ancestors if ancestor.tag == f"{W}p"), None)
            story_paragraph_index = story_paragraph_indices.get(story_paragraph)
            if any(ancestor.tag in {f"{W}del", f"{W}moveFrom", f"{W}ins", f"{W}moveTo"} for ancestor in ancestors):
                scope = "revision_excluded"
            elif any(ancestor.tag == f"{W}txbxContent" for ancestor in ancestors):
                scope = "text_box"
            elif part != "word/document.xml":
                scope = "header_footer"
            elif any(ancestor.tag == f"{W}tbl" for ancestor in ancestors):
                scope = "table"
            else:
                paragraph_index = next((paragraph_indices[a] for a in ancestors if a in paragraph_indices), None)
                scope = "body_paragraph" if paragraph_index is not None else "other_body"
            return {"part": part, "scope": scope, "paragraph_index": paragraph_index,
                    "story_paragraph_index": story_paragraph_index}

        def text_offset(paragraph: ET.Element, target: ET.Element) -> int | None:
            offset = 0

            def visit(node: ET.Element) -> int | None:
                nonlocal offset
                if node.tag in {f"{W}del", f"{W}moveFrom", f"{W}txbxContent"}:
                    return None
                if node is target:
                    return offset
                if node.tag == f"{W}t":
                    offset += len(node.text or "")
                elif node.tag == f"{W}tab":
                    offset += 1
                elif node.tag in {f"{W}br", f"{W}cr"}:
                    offset += 1
                elif node.tag in {f"{W}noBreakHyphen", f"{W}softHyphen"}:
                    offset += 1
                else:
                    for child in node:
                        result = visit(child)
                        if result is not None:
                            return result
                return None

            result = visit(paragraph)
            return result

        starts: dict[str | None, list] = {}
        ends: dict[str | None, list] = {}
        for position, node in enumerate(root.iter()):
            if node.tag == f"{W}bookmarkStart":
                starts.setdefault(node.get(f"{W}id"), []).append((position, node))
            elif node.tag == f"{W}bookmarkEnd":
                ends.setdefault(node.get(f"{W}id"), []).append((position, node))
        for bookmark_id in dict.fromkeys([*starts, *ends]):
            start_items, end_items = starts.get(bookmark_id, []), ends.get(bookmark_id, [])
            if bookmark_id is None or len(start_items) > 1 or len(end_items) > 1:
                status = "ambiguous"
            elif not start_items:
                status = "missing_start"
            elif not end_items:
                status = "missing_end"
            elif start_items[0][0] > end_items[0][0]:
                status = "reversed"
            else:
                status = "paired"
            start = start_items[0][1] if len(start_items) == 1 else None
            end = end_items[0][1] if len(end_items) == 1 else None
            start_location = location(start) if start is not None else None
            end_location = location(end) if end is not None else None
            paragraph = None
            if start_location and end_location and start_location["story_paragraph_index"] is not None \
                    and start_location["story_paragraph_index"] == end_location["story_paragraph_index"]:
                paragraph = story_paragraphs[int(start_location["story_paragraph_index"]) - 1]
            unstable_paragraph = paragraph is not None and any(
                node.tag in UNSTABLE_TEXT_CONTAINERS for node in paragraph.iter()
            )
            if start is not None and start_location and start_location["story_paragraph_index"] is not None:
                paragraph = story_paragraphs[int(start_location["story_paragraph_index"]) - 1]
                offset = text_offset(paragraph, start)
                if offset is not None:
                    start_location["text_offset"] = offset
            if end is not None and end_location and end_location["story_paragraph_index"] is not None:
                paragraph = story_paragraphs[int(end_location["story_paragraph_index"]) - 1]
                offset = text_offset(paragraph, end)
                if offset is not None:
                    end_location["text_offset"] = offset
            body_paragraph_range_supported = (
                status == "paired"
                and not unstable_paragraph
                and all(
                    endpoint is not None and endpoint["scope"] == "body_paragraph"
                    for endpoint in (start_location, end_location)
                )
                and start_location.get("paragraph_index") == end_location.get("paragraph_index")
                and "text_offset" in start_location and "text_offset" in end_location
                and start_location["text_offset"] <= end_location["text_offset"]
            )
            text_range_supported = (
                status == "paired"
                and not unstable_paragraph
                and start_location is not None and end_location is not None
                and start_location["part"] == end_location["part"]
                and start_location["scope"] == end_location["scope"]
                and start_location["scope"] in {"body_paragraph", "table", "header_footer"}
                and start_location["story_paragraph_index"] is not None
                and start_location["story_paragraph_index"] == end_location["story_paragraph_index"]
                and "text_offset" in start_location and "text_offset" in end_location
                and start_location.get("text_offset", -1) <= end_location.get("text_offset", -1)
            )
            bookmarks.append({
                "id": bookmark_id,
                "name": start.get(f"{W}name") if start is not None else None,
                "part": part,
                "status": status,
                "start": start_location,
                "end": end_location,
                "body_paragraph_range_supported": body_paragraph_range_supported,
                "text_range_supported": text_range_supported,
            })
    return {
        "paragraphs": items,
        "bookmarks": bookmarks,
        "warnings": warnings,
        "scope": {
            "paragraphs": "direct_body_paragraphs",
            "bookmark_parts": [part for part, _ in stories],
            "bookmark_precision": "character_offset_for_same_paragraph_in_supported_stories",
            "excluded_stories": ["footnotes", "endnotes", "comments"],
            "backend": "offline-ooxml",
        },
    }


def read_body_bookmark_text(path: str | Path, name: str) -> tuple[dict[str, Any] | None, str | None]:
    structure = read_writer_structure(path)
    matches = [item for item in structure["bookmarks"] if item["name"] == name]
    if len(matches) != 1:
        return None, None
    bookmark = matches[0]
    if not bookmark["body_paragraph_range_supported"]:
        return bookmark, None
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read(bookmark["start"]["part"]))
    body = root.find(f"{W}body")
    paragraphs = list(body.findall(f"{W}p")) if body is not None else []
    paragraph_index = int(bookmark["start"]["paragraph_index"])
    if paragraph_index < 1 or paragraph_index > len(paragraphs):
        return bookmark, None
    text = _paragraph_text(paragraphs[paragraph_index - 1])
    start = int(bookmark["start"]["text_offset"])
    end = int(bookmark["end"]["text_offset"])
    if start > end or end > len(text):
        return bookmark, None
    return bookmark, text[start:end]


def read_supported_bookmark_text(path: str | Path, name: str) -> tuple[dict[str, Any] | None, str | None]:
    structure = read_writer_structure(path)
    matches = [item for item in structure["bookmarks"] if item["name"] == name]
    if len(matches) != 1:
        return None, None
    bookmark = matches[0]
    if not bookmark["text_range_supported"]:
        return bookmark, None
    start_location, end_location = bookmark["start"], bookmark["end"]
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read(bookmark["part"]))
    paragraphs = list(root.iter(f"{W}p"))
    paragraph_index = int(start_location["story_paragraph_index"])
    if not 1 <= paragraph_index <= len(paragraphs):
        return bookmark, None
    text = _paragraph_text(paragraphs[paragraph_index - 1])
    start, end = int(start_location["text_offset"]), int(end_location["text_offset"])
    if not 0 <= start <= end <= len(text):
        return bookmark, None
    return bookmark, text[start:end]
