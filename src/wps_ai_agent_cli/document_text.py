from __future__ import annotations

from collections.abc import Iterable
import hashlib
import posixpath
import shlex
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile
from .ooxml import parse_xml_part, read_zip_part


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_R = "{http://schemas.openxmlformats.org/package/2006/relationships}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
PIC = "{http://schemas.openxmlformats.org/drawingml/2006/picture}"
EXCLUDED_TEXT_CONTAINERS = {f"{W}del", f"{W}moveFrom", f"{W}txbxContent"}
WORD_COORDINATE_MAX = 2_147_483_647
EMU_PER_TWIP = 635
WPS_DEFAULT_WRAP_DISTANCES = {
    "distT": "0",
    "distB": "0",
    "distL": "114300",
    "distR": "114300",
}
DRAWING_DIAGNOSTIC_VALUE_BYTE_LIMIT = 96
DRAWING_DIAGNOSTIC_COUNT_LIMIT = 128


def _bound_drawing_diagnostic_value(value: str) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= DRAWING_DIAGNOSTIC_VALUE_BYTE_LIMIT:
        return value, False

    prefix = encoded[:DRAWING_DIAGNOSTIC_VALUE_BYTE_LIMIT - 3]
    while True:
        try:
            return prefix.decode("utf-8") + "...", True
        except UnicodeDecodeError as exc:
            prefix = prefix[:exc.start]


def _drawing_relationship_issue(
    relationship_id: str | None,
    target: str | None,
    drawing_index: int,
    *,
    mode: str | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    issue: dict[str, object] = {"drawing_index": drawing_index}
    for field, value in (("relationship_id", relationship_id), ("target", target), ("mode", mode)):
        if field == "mode" and value is None:
            continue
        if isinstance(value, str):
            issue[field], truncated = _bound_drawing_diagnostic_value(value)
            if truncated:
                issue[f"{field}_truncated"] = True
        else:
            issue[field] = value
    if reason is not None:
        issue["reason"] = reason
    return issue


def _parse_ooxml_integer(value: str) -> int:
    lexical = value.strip(" \t\r\n")
    digits = lexical[1:] if lexical.startswith(("+", "-")) else lexical
    if not digits or not digits.isascii() or not digits.isdigit():
        raise ValueError("invalid OOXML integer lexical form")
    return int(lexical)


def _normalized_ooxml_integer(value: str) -> str:
    try:
        return str(_parse_ooxml_integer(value))
    except ValueError:
        return value


def _wrap_polygon_issue(points: list[tuple[int, int]]) -> str | None:
    if len(points) > 1 and points[-1] == points[0]:
        points = points[:-1]
    if len(points) < 3 or len(set(points)) < 3:
        return "degenerate_wrap_polygon"
    if any(points[index] == points[(index + 1) % len(points)] for index in range(len(points))):
        return "degenerate_wrap_polygon"

    area_twice = sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
    )
    if area_twice == 0:
        return "degenerate_wrap_polygon"

    def cross(a: tuple[int, int], b: tuple[int, int], c: tuple[int, int]) -> int:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(a: tuple[int, int], b: tuple[int, int], p: tuple[int, int]) -> bool:
        return (min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
                and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))

    def intersects(a: tuple[int, int], b: tuple[int, int],
                   c: tuple[int, int], d: tuple[int, int]) -> bool:
        ab_c, ab_d = cross(a, b, c), cross(a, b, d)
        cd_a, cd_b = cross(c, d, a), cross(c, d, b)
        if ((ab_c > 0 > ab_d or ab_d > 0 > ab_c)
                and (cd_a > 0 > cd_b or cd_b > 0 > cd_a)):
            return True
        return ((ab_c == 0 and on_segment(a, b, c))
                or (ab_d == 0 and on_segment(a, b, d))
                or (cd_a == 0 and on_segment(c, d, a))
                or (cd_b == 0 and on_segment(c, d, b)))

    count = len(points)
    for first in range(count):
        a, b = points[first], points[(first + 1) % count]
        for second in range(first + 1, count):
            if second == first + 1 or (first == 0 and second == count - 1):
                continue
            c, d = points[second], points[(second + 1) % count]
            if intersects(a, b, c, d):
                return "self_intersecting_wrap_polygon"
    return None


def _paragraph_text(paragraph: ET.Element) -> str:
    def fragments(node: ET.Element) -> Iterable[str]:
        if node.tag in EXCLUDED_TEXT_CONTAINERS or (node is not paragraph and node.tag == f"{W}p"):
            return
        if node.tag == f"{W}t":
            yield node.text or ""
        elif node.tag == f"{W}tab":
            yield "\t"
        elif node.tag in {f"{W}br", f"{W}cr"}:
            yield "\n"
        elif node.tag == f"{W}noBreakHyphen":
            yield "\u2011"
        elif node.tag == f"{W}softHyphen":
            yield "\u00ad"
        else:
            for child in node:
                yield from fragments(child)

    return "".join(fragments(paragraph))


def _story_paragraphs(node: ET.Element) -> Iterable[str]:
    if node.tag in EXCLUDED_TEXT_CONTAINERS:
        return
    if node.tag == f"{W}p":
        yield _paragraph_text(node)
    else:
        for child in node:
            yield from _story_paragraphs(child)


def docx_body_story_paragraphs(path: str | Path) -> list[str]:
    with ZipFile(path) as archive:
        root = parse_xml_part(archive, "word/document.xml")
    return list(_story_paragraphs(root))


def docx_document_paragraphs(path: str | Path) -> list[str]:
    with ZipFile(path) as archive:
        root = parse_xml_part(archive, "word/document.xml")
    return [_paragraph_text(paragraph) for paragraph in root.iter(f"{W}p")]


def count_text_in_docx(
    path: str | Path,
    text: str,
    parts: Iterable[str] | None = None,
) -> int:
    if not text:
        return 0
    part_filter = set(parts) if parts is not None else None
    total = 0
    with ZipFile(path) as archive:
        for name in archive.namelist():
            if part_filter is not None and name not in part_filter:
                continue
            if name.startswith("word/") and name.endswith(".xml"):
                root = parse_xml_part(archive, name)
                if root.tag in {f"{W}{tag}" for tag in ("document", "hdr", "ftr", "footnotes", "endnotes", "comments")}:
                    # Never join different paragraphs, cells or stories into a match.
                    total += sum(paragraph.count(text) for paragraph in _story_paragraphs(root))
    return total


def docx_body_paragraphs(path: str | Path) -> list[str]:
    with ZipFile(path) as archive:
        payload = read_zip_part(archive, "word/document.xml")
    root = ET.fromstring(payload)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:body/w:p", namespace):
        paragraphs.append(_paragraph_text(paragraph))
    return paragraphs


def docx_body_paragraph_target(path: str | Path, paragraph_index: int) -> dict[str, object]:
    paragraphs = docx_body_paragraphs(path)
    if not 1 <= paragraph_index <= len(paragraphs):
        raise ValueError("Body paragraph index out of range.")
    return {
        "body_paragraph_count": len(paragraphs),
        "expected_text": paragraphs[paragraph_index - 1],
    }


def count_text_in_docx_paragraph(path: str | Path, paragraph_index: int, text: str) -> int:
    if not text:
        return 0
    paragraphs = docx_body_paragraphs(path)
    if paragraph_index < 1 or paragraph_index > len(paragraphs):
        return 0
    return paragraphs[paragraph_index - 1].count(text)


def docx_body_tables(path: str | Path) -> list[list[list[str]]]:
    with ZipFile(path) as archive:
        payload = read_zip_part(archive, "word/document.xml")
    root = ET.fromstring(payload)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    tables = []
    for table in root.findall(".//w:body/w:tbl", namespace):
        rows = []
        for row in table.findall("./w:tr", namespace):
            cells = []
            for cell in row.findall("./w:tc", namespace):
                texts = [
                    node.text or ""
                    for node in cell.findall(".//w:t", namespace)
                ]
                cells.append("".join(texts))
            rows.append(cells)
        tables.append(rows)
    return tables


def docx_body_table_topology(path: str | Path) -> list[dict[str, object]]:
    with ZipFile(path) as archive:
        root = parse_xml_part(archive, "word/document.xml")
    body = root.find(f"{W}body")
    if body is None:
        return []

    def property_value(parent: ET.Element, tag: str) -> str | None:
        element = parent.find(tag)
        return element.get(f"{W}val") if element is not None else None

    tables = []
    for table in body.findall(f"{W}tbl"):
        grid = table.find(f"{W}tblGrid")
        rows = []
        for row in table.findall(f"{W}tr"):
            cells = []
            for cell in row.findall(f"{W}tc"):
                merge = cell.find(f"{W}tcPr/{W}vMerge")
                cells.append({
                    "grid_span": property_value(cell, f"{W}tcPr/{W}gridSpan") or "1",
                    "vertical_merge": merge.get(f"{W}val", "continue") if merge is not None else None,
                    "paragraph_count": len(cell.findall(f"{W}p")),
                    "nested_table_count": len(cell.findall(f"{W}tbl")),
                })
            rows.append({
                "grid_before": property_value(row, f"{W}trPr/{W}gridBefore") or "0",
                "grid_after": property_value(row, f"{W}trPr/{W}gridAfter") or "0",
                "cells": cells,
            })
        tables.append({
            "grid_column_count": len(grid.findall(f"{W}gridCol")) if grid is not None else None,
            "rows": rows,
        })
    return tables


def docx_body_link_field_semantics(path: str | Path) -> dict[str, list[dict[str, object]]]:
    with ZipFile(path) as archive:
        root = parse_xml_part(archive, "word/document.xml")
        rels = (
            parse_xml_part(archive, "word/_rels/document.xml.rels")
            if "word/_rels/document.xml.rels" in archive.namelist() else None
        )
    relationships = {
        rel.get("Id"): {"target": rel.get("Target"), "mode": rel.get("TargetMode")}
        for rel in rels.findall(f"{PKG_R}Relationship")
    } if rels is not None else {}
    body = root.find(f"{W}body")
    if body is None:
        return {"hyperlinks": [], "fields": [], "unresolved_links": [], "unresolved_fields": []}

    def field_semantics(instruction: str, result_text: str) -> None:
        try:
            tokens = [token.strip('"') for token in shlex.split(instruction, posix=False)]
        except ValueError:
            unresolved_fields.append({"instruction": instruction, "text": result_text})
            return
        if not tokens:
            unresolved_fields.append({"instruction": instruction, "text": result_text})
            return
        if tokens and tokens[0].upper() == "HYPERLINK":
            target = tokens[1] if len(tokens) > 1 and not tokens[1].startswith("\\") else None
            anchor = None
            for index, token in enumerate(tokens[:-1]):
                if token.lower() == "\\l":
                    anchor = tokens[index + 1]
            if not target and not anchor:
                unresolved_fields.append({"instruction": instruction, "text": result_text})
                return
            hyperlinks.append({"target": target, "anchor": anchor, "text": result_text})
        else:
            fields.append({"instruction_tokens": tokens, "text": result_text})

    hyperlinks = []
    fields = []
    unresolved_links = []
    unresolved_fields = []
    field_stack = []
    for node in body.iter():
        if node.tag == f"{W}hyperlink":
            rel_id = node.get(f"{R}id")
            relationship = relationships.get(rel_id) if rel_id else None
            anchor = node.get(f"{W}anchor")
            target = relationship.get("target") if relationship else None
            if (rel_id and not target) or (not rel_id and not anchor):
                unresolved_links.append({"relationship_id": rel_id, "anchor": anchor})
            hyperlinks.append({
                "anchor": anchor,
                "target": target,
                "text": _paragraph_text(node),
            })
        elif node.tag == f"{W}fldSimple":
            if field_stack:
                unresolved_fields.append({"reason": "nested_simple_field"})
            else:
                field_semantics(node.get(f"{W}instr") or "", _paragraph_text(node))
        elif node.tag == f"{W}fldChar":
            kind = node.get(f"{W}fldCharType")
            if kind == "begin":
                if field_stack:
                    unresolved_fields.append({"reason": "nested_field"})
                field_stack.append({"instruction": [], "result": [], "in_result": False})
            elif kind == "separate" and field_stack and not field_stack[-1]["in_result"]:
                field_stack[-1]["in_result"] = True
            elif kind == "end" and field_stack and field_stack[-1]["in_result"]:
                current = field_stack.pop()
                field_semantics("".join(current["instruction"]), "".join(current["result"]))
            else:
                unresolved_fields.append({"field_char_type": kind})
        elif node.tag == f"{W}instrText" and field_stack:
            field_stack[-1]["instruction"].append(node.text or "")
        elif node.tag == f"{W}instrText":
            unresolved_fields.append({"instruction_text_outside_field": node.text or ""})
        elif node.tag in {f"{W}t", f"{W}tab", f"{W}br", f"{W}cr"} and field_stack:
            if field_stack[-1]["in_result"]:
                field_stack[-1]["result"].append(
                    node.text or "" if node.tag == f"{W}t" else
                    "\t" if node.tag == f"{W}tab" else "\n"
                )
    unresolved_fields.extend({"unclosed_instruction": "".join(item["instruction"])} for item in field_stack)
    return {
        "hyperlinks": hyperlinks,
        "fields": fields,
        "unresolved_links": unresolved_links,
        "unresolved_fields": unresolved_fields,
    }


def docx_body_drawing_semantics(path: str | Path) -> dict[str, list[dict[str, object]]]:
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        root = parse_xml_part(archive, "word/document.xml")
        rels = (
            parse_xml_part(archive, "word/_rels/document.xml.rels")
            if "word/_rels/document.xml.rels" in names else None
        )
        relationships = {
            rel.get("Id"): {"target": rel.get("Target"), "mode": rel.get("TargetMode")}
            for rel in rels.findall(f"{PKG_R}Relationship")
        } if rels is not None else {}
        body = root.find(f"{W}body")
        drawings = []
        unresolved = []
        anchors = list(body.iter(f"{WP}anchor")) if body is not None else []
        drawing_nodes = [
            node for node in body.iter()
            if node.tag in {f"{WP}inline", f"{WP}anchor"}
        ] if body is not None else []
        drawing_indices = {node: index for index, node in enumerate(drawing_nodes)}

        def anchor_height(node: ET.Element) -> tuple[int, int]:
            try:
                value = int(node.get("relativeHeight", ""))
            except ValueError:
                unresolved.append({
                    "drawing_type": "anchor", "drawing_index": drawing_indices[node],
                    "reason": "invalid_relative_height",
                })
                value = 0
            return value, anchors.index(node)

        anchor_order = {
            node: rank for rank, node in enumerate(sorted(anchors, key=anchor_height))
        }

        def structure(node: ET.Element) -> dict[str, object] | None:
            if node.tag in {f"{WP}effectExtent", f"{A}picLocks", f"{A}avLst"}:
                return None
            attributes: dict[str, object] = {}
            for name, value in sorted(node.attrib.items()):
                if node.tag in {
                    f"{WP}wrapSquare", f"{WP}wrapTight", f"{WP}wrapThrough",
                    f"{WP}wrapTopAndBottom",
                } and name == "wrapText" and value == "bothSides":
                    continue
                if name == "id" and node.tag in {f"{WP}docPr", f"{PIC}cNvPr"}:
                    continue
                if name == "name" and node.tag == f"{PIC}cNvPr":
                    continue
                if node.tag in {f"{WP}inline", f"{WP}anchor"} and name in {
                    "distT", "distB", "distL", "distR",
                }:
                    continue
                if node.tag == f"{WP}anchor" and name == "relativeHeight":
                    continue
                if name in {f"{R}embed", f"{R}link"}:
                    relationship = relationships.get(value)
                    if relationship is None or not relationship.get("target"):
                        unresolved.append(_drawing_relationship_issue(
                            value, None, drawing_indices[drawing],
                            reason="unresolved_drawing_structure",
                        ))
                    attributes[name] = relationship
                elif node.tag in {f"{WP}start", f"{WP}lineTo"} and name in {"x", "y"}:
                    try:
                        attributes[name] = str(_parse_ooxml_integer(value))
                    except ValueError:
                        attributes[name] = value
                else:
                    attributes[name] = value
            if node.tag in {
                f"{WP}wrapSquare", f"{WP}wrapTight", f"{WP}wrapThrough",
                f"{WP}wrapTopAndBottom",
            } and node.get("wrapText", "bothSides") == "bothSides":
                attributes["wrapText"] = "bothSides"
            return {
                "tag": node.tag,
                "attributes": attributes,
                "text": node.text if node.text and node.text.strip() else None,
                "children": [item for child in node if (item := structure(child)) is not None],
            }

        if body is not None:
            for drawing in drawing_nodes:
                current_drawing_index = drawing_indices[drawing]
                if drawing.tag == f"{WP}anchor":
                    wrap_tags = {
                        f"{WP}wrapNone", f"{WP}wrapSquare", f"{WP}wrapTight",
                        f"{WP}wrapThrough", f"{WP}wrapTopAndBottom",
                    }
                    wrap_elements = [child for child in drawing if child.tag in wrap_tags]
                    if len(wrap_elements) != 1:
                        unresolved.append({
                            "drawing_type": "anchor", "drawing_index": current_drawing_index,
                            "reason": "missing_or_ambiguous_wrap",
                        })
                    else:
                        wrap = wrap_elements[0]
                        wrap_text = wrap.get("wrapText", "bothSides")
                        if wrap_text not in {"bothSides", "left", "right", "largest"}:
                            unresolved.append({
                                "drawing_type": "anchor", "drawing_index": current_drawing_index,
                                "reason": "invalid_wrap_text",
                            })
                        if wrap.tag == f"{WP}wrapTopAndBottom" and wrap_text != "bothSides":
                            unresolved.append({
                                "drawing_type": "anchor",
                                "drawing_index": current_drawing_index,
                                "reason": "unsupported_top_and_bottom_wrap_text",
                            })
                        if wrap.tag in {f"{WP}wrapTight", f"{WP}wrapThrough"}:
                            polygon = wrap.find(f"{WP}wrapPolygon")
                            start = polygon.find(f"{WP}start") if polygon is not None else None
                            lines = list(polygon.findall(f"{WP}lineTo")) if polygon is not None else []
                            points = ([start] if start is not None else []) + lines
                            if start is None or len(lines) < 2:
                                unresolved.append({
                                    "drawing_type": "anchor", "drawing_index": current_drawing_index,
                                    "reason": "invalid_wrap_polygon_shape",
                                })
                            coordinates = []
                            for point in points:
                                try:
                                    x = _parse_ooxml_integer(point.get("x", ""))
                                    y = _parse_ooxml_integer(point.get("y", ""))
                                except ValueError:
                                    unresolved.append({
                                        "drawing_type": "anchor", "drawing_index": current_drawing_index,
                                        "reason": "invalid_wrap_polygon_coordinate",
                                    })
                                    continue
                                if not 0 <= x <= 21600 or not 0 <= y <= 21600:
                                    unresolved.append({
                                        "drawing_type": "anchor", "drawing_index": current_drawing_index,
                                        "reason": "wrap_polygon_coordinate_out_of_range",
                                    })
                                coordinates.append((x, y))
                            polygon_issue = _wrap_polygon_issue(coordinates)
                            if polygon_issue:
                                unresolved.append({
                                    "drawing_type": "anchor", "drawing_index": current_drawing_index,
                                    "reason": polygon_issue,
                                })
                    for name in ("distT", "distB", "distL", "distR"):
                        raw_distance = drawing.get(name)
                        if raw_distance is not None:
                            try:
                                distance = _parse_ooxml_integer(raw_distance)
                                valid_distance = (
                                    0 <= distance <= WORD_COORDINATE_MAX
                                    and distance % EMU_PER_TWIP == 0
                                )
                            except ValueError:
                                valid_distance = False
                            if not valid_distance:
                                unresolved.append({
                                    "drawing_type": "anchor", "drawing_index": current_drawing_index,
                                    "reason": "invalid_wrap_distance", "attribute": name,
                                })
                extent = drawing.find(f"{WP}extent")
                properties = drawing.find(f"{WP}docPr")
                graphic_data = drawing.find(f".//{A}graphicData")
                image_refs = []
                for blip in drawing.iter(f"{A}blip"):
                    rel_id = blip.get(f"{R}embed") or blip.get(f"{R}link")
                    relationship = relationships.get(rel_id) if rel_id else None
                    target = relationship.get("target") if relationship else None
                    mode = relationship.get("mode") if relationship else None
                    part_hash = None
                    if mode not in {None, "Internal", "External"}:
                        unresolved.append(_drawing_relationship_issue(
                            rel_id, target, current_drawing_index,
                            mode=mode, reason="invalid_relationship_target_mode",
                        ))
                    elif target and mode != "External":
                        part_name = (target.lstrip("/") if target.startswith("/") else
                                     posixpath.normpath(posixpath.join("word", target)))
                        if part_name == ".." or part_name.startswith("../"):
                            unresolved.append(_drawing_relationship_issue(
                                rel_id, target, current_drawing_index,
                                reason="target_outside_package",
                            ))
                        elif part_name in names:
                            part_hash = hashlib.sha256(read_zip_part(archive, part_name)).hexdigest()
                        else:
                            unresolved.append(_drawing_relationship_issue(
                                rel_id, target, current_drawing_index,
                            ))
                    elif not target:
                        unresolved.append(_drawing_relationship_issue(
                            rel_id, target, current_drawing_index,
                        ))
                    image_refs.append({"target": target, "mode": mode, "sha256": part_hash})
                if not image_refs:
                    unresolved.append({
                        "drawing_type": drawing.tag, "drawing_index": current_drawing_index,
                        "reason": "missing_image_reference",
                    })
                drawings.append({
                    "type": "inline" if drawing.tag == f"{WP}inline" else "anchor",
                    "relative_height_order": anchor_order.get(drawing) if drawing.tag == f"{WP}anchor" else None,
                    "wrap_distances": ({
                        name: _normalized_ooxml_integer(drawing.get(name, WPS_DEFAULT_WRAP_DISTANCES[name]))
                        for name in ("distT", "distB", "distL", "distR")
                    } if drawing.tag == f"{WP}anchor" else None),
                    "extent": ({"cx": extent.get("cx"), "cy": extent.get("cy")} if extent is not None else None),
                    "object": ({
                        "name": properties.get("name"),
                        "descr": properties.get("descr"),
                        "title": properties.get("title"),
                    } if properties is not None else None),
                    "graphic_data_uri": graphic_data.get("uri") if graphic_data is not None else None,
                    "images": image_refs,
                    "structure": structure(drawing),
                })
    if len(unresolved) > DRAWING_DIAGNOSTIC_COUNT_LIMIT:
        omitted = unresolved[DRAWING_DIAGNOSTIC_COUNT_LIMIT - 1:]
        unresolved = unresolved[:DRAWING_DIAGNOSTIC_COUNT_LIMIT - 1]
        unresolved.append({
            "drawing_index": omitted[0].get("drawing_index"),
            "reason": "additional_drawing_diagnostics_truncated",
            "omitted_count": len(omitted),
        })
    return {"drawings": drawings, "unresolved_drawings": unresolved}


def docx_bookmark_overlaps_link_or_field(
    path: str | Path, bookmark_name: str, story_paragraph_index: int,
    start_offset: int, end_offset: int,
) -> bool:
    with ZipFile(path) as archive:
        root = parse_xml_part(archive, "word/document.xml")
    paragraphs = list(root.iter(f"{W}p"))
    if not 1 <= story_paragraph_index <= len(paragraphs):
        return True
    paragraph = paragraphs[story_paragraph_index - 1]
    start_marker = next((node for node in paragraph.iter(f"{W}bookmarkStart")
                         if node.get(f"{W}name") == bookmark_name), None)
    if start_marker is None:
        return True
    bookmark_id = start_marker.get(f"{W}id")
    offset = 0
    spans: list[tuple[int, int]] = []
    field_stack: list[int | None] = []
    ordered_nodes = list(paragraph.iter())
    start_position = ordered_nodes.index(start_marker)
    end_marker = next((node for node in ordered_nodes[start_position + 1:]
                       if node.tag == f"{W}bookmarkEnd" and node.get(f"{W}id") == bookmark_id), None)
    marker_inside = False
    if end_marker is not None:
        end_position = ordered_nodes.index(end_marker)
        marker_inside = any(node.tag in {f"{W}drawing", f"{W}pict"}
                             for node in ordered_nodes[start_position + 1:end_position])

    def visit(node: ET.Element, semantic_ancestor: bool = False) -> None:
        nonlocal offset, marker_inside
        if node.tag in EXCLUDED_TEXT_CONTAINERS or (node is not paragraph and node.tag == f"{W}p"):
            return
        if node.tag in {f"{W}bookmarkStart", f"{W}bookmarkEnd"}:
            same_start = node is start_marker
            same_end = node.tag == f"{W}bookmarkEnd" and node.get(f"{W}id") == bookmark_id
            if (same_start or same_end) and (semantic_ancestor or field_stack):
                marker_inside = True
        if node.tag == f"{W}fldChar":
            kind = node.get(f"{W}fldCharType")
            if kind == "begin":
                field_stack.append(None)
            elif kind == "separate" and field_stack:
                field_stack[-1] = offset
            elif kind == "end" and field_stack:
                field_start = field_stack.pop()
                if field_start is not None:
                    spans.append((field_start, offset))
        if node.tag == f"{W}t":
            offset += len(node.text or "")
        elif node.tag in {f"{W}tab", f"{W}br", f"{W}cr", f"{W}noBreakHyphen", f"{W}softHyphen"}:
            offset += 1
        semantic = node.tag in {f"{W}hyperlink", f"{W}fldSimple", f"{W}drawing", f"{W}pict"}
        span_start = offset
        for child in node:
            visit(child, semantic_ancestor or semantic)
        if semantic:
            spans.append((span_start, offset))

    visit(paragraph)
    return marker_inside or any(start_offset < stop and begin < end_offset for begin, stop in spans)


def docx_bookmark_precedes_character_anchor(
    path: str | Path, bookmark_name: str, story_paragraph_index: int,
) -> bool:
    with ZipFile(path) as archive:
        root = parse_xml_part(archive, "word/document.xml")
    paragraphs = list(root.iter(f"{W}p"))
    if not 1 <= story_paragraph_index <= len(paragraphs):
        return True
    paragraph = paragraphs[story_paragraph_index - 1]
    nodes = list(paragraph.iter())
    start = next((node for node in nodes if node.tag == f"{W}bookmarkStart"
                  and node.get(f"{W}name") == bookmark_name), None)
    if start is None:
        return True
    bookmark_id = start.get(f"{W}id")
    end = next((node for node in nodes[nodes.index(start) + 1:]
                if node.tag == f"{W}bookmarkEnd" and node.get(f"{W}id") == bookmark_id), None)
    if end is None:
        return True
    end_position = nodes.index(end)
    return any(
        node.tag == f"{WP}anchor"
        and (position := node.find(f"{WP}positionH")) is not None
        and position.get("relativeFrom") == "character"
        and nodes.index(node) > end_position
        for node in nodes
    )


def docx_table_cell_text(path: str | Path, table_index: int, row: int, column: int) -> str | None:
    tables = docx_body_tables(path)
    if table_index < 1 or table_index > len(tables):
        return None
    selected_table = tables[table_index - 1]
    if row < 1 or row > len(selected_table):
        return None
    selected_row = selected_table[row - 1]
    if column < 1 or column > len(selected_row):
        return None
    return selected_row[column - 1]
