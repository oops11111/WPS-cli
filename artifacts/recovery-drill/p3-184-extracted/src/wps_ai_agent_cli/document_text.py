from __future__ import annotations

from collections.abc import Iterable
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
EXCLUDED_TEXT_CONTAINERS = {f"{W}del", f"{W}moveFrom", f"{W}txbxContent"}


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
        root = ET.fromstring(archive.read("word/document.xml"))
    return list(_story_paragraphs(root))


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
                root = ET.fromstring(archive.read(name))
                if root.tag in {f"{W}{tag}" for tag in ("document", "hdr", "ftr", "footnotes", "endnotes", "comments")}:
                    # Never join different paragraphs, cells or stories into a match.
                    total += sum(paragraph.count(text) for paragraph in _story_paragraphs(root))
    return total


def docx_body_paragraphs(path: str | Path) -> list[str]:
    with ZipFile(path) as archive:
        payload = archive.read("word/document.xml")
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
        payload = archive.read("word/document.xml")
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
