from __future__ import annotations

import posixpath
from pathlib import Path
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile
from .ooxml import parse_xml_part, read_zip_part


DRAWING_TEXT = "{http://schemas.openxmlformats.org/drawingml/2006/main}t"
PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
RELATIONSHIP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


class PresentationStructureError(ValueError):
    pass


def _slide_parts(archive: ZipFile) -> list[tuple[int, str]]:
    try:
        root = parse_xml_part(archive, "ppt/presentation.xml")
        if root.tag != f"{{{PRESENTATION_NS}}}presentation":
            raise PresentationStructureError("Unsupported presentation XML namespace or root.")
        slides = root.findall(f"{{{PRESENTATION_NS}}}sldIdLst/{{{PRESENTATION_NS}}}sldId")
        if not slides:
            return []
        rel_root = parse_xml_part(archive, "ppt/_rels/presentation.xml.rels")
        relationships = {}
        for rel in rel_root.findall(f"{{{PACKAGE_REL_NS}}}Relationship"):
            rel_id = rel.get("Id")
            if not rel_id or rel_id in relationships:
                raise PresentationStructureError("Missing or duplicate presentation relationship ID.")
            relationships[rel_id] = rel
        parts = []
        seen = set()
        for index, slide in enumerate(slides, start=1):
            rel_id = slide.get(f"{{{RELATIONSHIP_NS}}}id")
            rel = relationships.get(rel_id)
            if rel is None or rel.get("Type") != f"{RELATIONSHIP_NS}/slide":
                raise PresentationStructureError(f"Invalid slide relationship: {rel_id}")
            target = urlsplit(rel.get("Target", ""))
            if rel.get("TargetMode", "Internal") != "Internal" or target.scheme or target.netloc or target.query or target.fragment:
                raise PresentationStructureError(f"Slide target must be an internal package part: {rel_id}")
            path = unquote(target.path)
            if not path or "\\" in path:
                raise PresentationStructureError(f"Invalid slide target: {rel_id}")
            part = posixpath.normpath(path.lstrip("/") if path.startswith("/") else posixpath.join("ppt", path))
            if part.startswith("../") or part not in archive.namelist() or part in seen:
                raise PresentationStructureError(f"Missing, duplicate or invalid slide part: {part}")
            seen.add(part)
            parts.append((index, part))
        return parts
    except (KeyError, ET.ParseError) as exc:
        raise PresentationStructureError(f"Cannot resolve presentation slide order: {exc}") from exc


def pptx_slide_texts(path: str | Path) -> list[dict[str, object]]:
    source = Path(path)
    slides = []
    with ZipFile(source) as archive:
        for slide_number, part_name in _slide_parts(archive):
            root = parse_xml_part(archive, part_name)
            text = "".join(node.text or "" for node in root.iter(DRAWING_TEXT))
            slides.append(
                {
                    "slide_index": slide_number,
                    "part": part_name,
                    "text": text,
                }
            )
    return slides


def pptx_text_objects(path: str | Path) -> list[dict[str, object]]:
    source = Path(path)
    objects = []
    namespace = {
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    }
    shape_tag = f"{{{namespace['p']}}}sp"
    graphic_frame_tag = f"{{{namespace['p']}}}graphicFrame"
    with ZipFile(source) as archive:
        for slide_number, part_name in _slide_parts(archive):
            root = parse_xml_part(archive, part_name)
            object_index = 0
            for node in root.iter():
                text = None
                object_type = None
                placeholder_type = None
                if node.tag == shape_tag:
                    text_body = node.find("./p:txBody", namespace)
                    if text_body is None:
                        continue
                    match_segments = [
                        "".join(item.text or "" for item in paragraph.findall(".//a:t", namespace))
                        for paragraph in text_body.findall("./a:p", namespace)
                    ]
                    text = "".join(match_segments)
                    placeholder = node.find("./p:nvSpPr/p:nvPr/p:ph", namespace)
                    placeholder_type = placeholder.get("type") if placeholder is not None else None
                    object_type = "shape"
                elif node.tag == graphic_frame_tag:
                    table = node.find("./a:graphic/a:graphicData/a:tbl", namespace)
                    if table is None:
                        continue
                    table_rows = []
                    match_segments = []
                    for row in table.findall("./a:tr", namespace):
                        cells = []
                        for cell in row.findall("./a:tc", namespace):
                            cell_paragraphs = [
                                "".join(item.text or "" for item in paragraph.findall(".//a:t", namespace))
                                for paragraph in cell.findall("./a:txBody/a:p", namespace)
                            ]
                            cell_text = "\n".join(cell_paragraphs)
                            cells.append(cell_text)
                            match_segments.extend(cell_paragraphs)
                        table_rows.append("\t".join(cells))
                    text = "\n".join(table_rows)
                    object_type = "table"
                else:
                    continue
                object_index += 1
                objects.append(
                    {
                        "slide_index": slide_number,
                        "object_index": object_index,
                        "part": part_name,
                        "object_type": object_type,
                        "text": text,
                        "match_segments": match_segments,
                        "text_length": len(text),
                        "is_empty": text == "",
                        "placeholder_type": placeholder_type,
                    }
                )
    return objects


def count_text_in_pptx(
    path: str | Path,
    needle: str,
    slide_index: int | None = None,
) -> int:
    if not needle:
        return 0
    count = 0
    for item in pptx_text_objects(path):
        if slide_index is not None and item["slide_index"] != slide_index:
            continue
        segments = item.get("match_segments", [item["text"]])
        count += sum(str(segment).count(needle) for segment in segments)
    return count
