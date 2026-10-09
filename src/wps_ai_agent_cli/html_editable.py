from __future__ import annotations

from dataclasses import dataclass, field
import base64
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
import hashlib
import os
import re
import tempfile
from typing import Any
from urllib.parse import urlsplit

from .html_text import decode_html_bytes


_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_SKIP = {"script", "style", "noscript", "template", "svg", "iframe", "object", "canvas"}
_BLOCKS = {"p", "div", "section", "article", "header", "footer", "main", "aside", "blockquote", "pre", "address"}
_HEADINGS = {f"h{i}": i for i in range(1, 7)}
_MAX_HTML_BYTES = 10 * 1024 * 1024
_MAX_IMAGE_BYTES = 20 * 1024 * 1024
_MAX_TOTAL_IMAGE_BYTES = 50 * 1024 * 1024
_MAX_IMAGES = 100


def _safe_link_target(value: str) -> bool:
    stripped = value.strip()
    if "\\" in stripped or any(ord(char) < 32 for char in stripped):
        return False
    parsed = urlsplit(stripped)
    return parsed.scheme.casefold() in {"http", "https", "mailto", "tel"} or (
        not parsed.scheme and not value.strip().startswith("//")
    )


def _bookmark_name(object_id: str) -> str:
    return "wps_" + hashlib.sha256(object_id.encode("utf-8")).hexdigest()[:32]


@dataclass
class _Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[_Node | str] = field(default_factory=list)


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("document")
        self.stack = [self.root]
        self.suppressed = 0
        self.unsupported: set[str] = set()
        self.warnings: set[str] = set()
        self.unsupported_elements: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "style":
            self.unsupported.add("embedded CSS")
        elif tag == "script":
            self.warnings.add("Scripts and executable content were omitted.")
        elif tag in {"noscript", "template", "svg", "iframe", "object", "canvas"}:
            self.unsupported_elements.add(tag)
        if self.suppressed:
            if tag in _SKIP:
                self.suppressed += 1
            return
        if tag in _SKIP:
            self.suppressed = 1
            return
        if tag in {"li", "p", "tr", "td", "th"}:
            while len(self.stack) > 1 and self.stack[-1].tag == tag:
                self.stack.pop()
        node = _Node(tag, {key.lower(): value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.suppressed:
            if tag in _SKIP:
                self.suppressed -= 1
            return
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self.suppressed and self.stack[-1].tag == "document":
            return
        if not self.suppressed and data:
            self.stack[-1].children.append(data)


def _text(node: _Node) -> str:
    pieces: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            pieces.append(child)
        elif child.tag == "br":
            pieces.append("\n")
        elif child.tag == "img":
            alt = child.attrs.get("alt", "").strip()
            if alt:
                pieces.append(alt)
        elif child.tag == "a":
            label = _text(child)
            href = child.attrs.get("href", "").strip()
            pieces.append(f"{label} ({href})" if href and href not in label else label)
        else:
            pieces.append(_text(child))
    return re.sub(r"[\t\r\f\v ]+", " ", "".join(pieces)).strip()


def _walk(node: _Node):
    yield node
    for child in node.children:
        if isinstance(child, _Node):
            yield from _walk(child)


def _validate_editable_paths(input_path: str | Path, output_path: str | Path) -> tuple[Path, Path, list[dict[str, str]]]:
    source = Path(input_path).expanduser().resolve()
    destination = Path(output_path).expanduser().resolve()
    if source.suffix.casefold() not in {".html", ".htm"}:
        return source, destination, [{"code": "INVALID_INPUT", "message": "Input must be an .html or .htm file."}]
    if not source.is_file():
        return source, destination, [{"code": "INPUT_FILE_NOT_FOUND", "message": f"HTML input not found: {source}"}]
    if source.stat().st_size > _MAX_HTML_BYTES:
        return source, destination, [{"code": "INPUT_TOO_LARGE", "message": "HTML input exceeds the 10 MiB limit."}]
    if destination.suffix.casefold() != ".docx" or destination == source:
        return source, destination, [{"code": "INVALID_OUTPUT", "message": "Output must be a separate .docx file."}]
    if destination.exists():
        return source, destination, [{"code": "OUTPUT_ALREADY_EXISTS", "message": f"Refusing to overwrite existing output: {destination}"}]
    if not destination.parent.is_dir():
        return source, destination, [{"code": "OUTPUT_DIRECTORY_NOT_FOUND", "message": f"Output directory does not exist: {destination.parent}"}]
    return source, destination, []



def convert_html_editable(input_path: str | Path, output_path: str | Path) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    source, destination, path_errors = _validate_editable_paths(input_path, output_path)
    if path_errors:
        return False, {}, path_errors
    try:
        from docx import Document
        from docx.shared import Inches
    except ImportError:
        return False, {}, [{"code": "CONVERTER_UNAVAILABLE", "message": "Install the html optional dependency: python-docx."}]

    parser = _TreeParser()
    html_text, source_encoding, decode_warning = decode_html_bytes(source.read_bytes())
    parser.feed(html_text)
    nodes = list(_walk(parser.root))
    html_root = next((node for node in nodes if node.tag == "html"), None)
    meta = next((node for node in nodes if node.tag == "meta" and node.attrs.get("name", "").casefold() == "wps-agent-schema"), None)
    schema_version = (html_root.attrs.get("data-wps-schema") if html_root else None) or (meta.attrs.get("content") if meta else None)
    owned_schema = schema_version == "wps-agent-html/v1"
    if owned_schema:
        from .html_roundtrip import build_html_roundtrip_mapping
        valid, _, validation_errors = build_html_roundtrip_mapping(source)
        if not valid:
            return False, {}, validation_errors
    unsupported_css = sorted(parser.unsupported | {
        f"inline style on <{node.tag}>" for node in nodes if node.attrs.get("style")
    } | {
        f"class selector on <{node.tag}>" for node in nodes if node.attrs.get("class")
    } | {
        f"id selector on <{node.tag}>" for node in nodes if node.attrs.get("id")
    } | {
        "linked CSS" for node in nodes if node.tag == "link" and node.attrs.get("rel", "").casefold() == "stylesheet"
    })
    supported_tags = _VOID | _SKIP | _BLOCKS | set(_HEADINGS) | {
        "html", "head", "body", "title", "span", "a", "b", "strong", "i", "em", "u", "s", "small",
        "sub", "sup", "code", "abbr", "cite", "del", "ins", "q", "ul", "ol", "li", "table",
        "thead", "tbody", "tfoot", "tr", "td", "th", "figure", "figcaption",
    }
    warnings = sorted(parser.warnings | {
        f"Unsupported element <{node.tag}> omitted or flattened to text."
        for node in nodes
        if node is not parser.root and node.tag not in supported_tags
    } | {
        f"Unsupported element <{tag}> omitted." for tag in parser.unsupported_elements
    } | {
        "Scripts and executable content were omitted." for node in nodes if node.tag == "script"
    })
    if decode_warning:
        warnings.append(decode_warning)
    document = Document()
    bookmark_counter = 0
    bookmark_count = 0

    def add_bookmark(paragraph_element, object_id: str) -> None:
        nonlocal bookmark_counter, bookmark_count
        if not owned_schema or not object_id:
            return
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn

        bookmark_counter += 1
        start = OxmlElement("w:bookmarkStart")
        start.set(qn("w:id"), str(bookmark_counter))
        start.set(qn("w:name"), _bookmark_name(object_id))
        end = OxmlElement("w:bookmarkEnd")
        end.set(qn("w:id"), str(bookmark_counter))
        paragraph_element.append(start)
        paragraph_element.append(end)
        bookmark_count += 1
    image_nodes: list[tuple[_Node, Path | bytes]] = []
    image_bytes = 0
    root = source.parent.resolve()
    for node in nodes:
        if node.tag != "img":
            continue
        if len(image_nodes) >= _MAX_IMAGES:
            warnings.append(f"Image count truncated to {_MAX_IMAGES}.")
            continue
        raw = node.attrs.get("src", "").strip()
        if owned_schema and raw.startswith("data:"):
            try:
                header, encoded = raw.split(",", 1)
                mime = header[5:].split(";", 1)[0].casefold()
                if mime not in {"image/png", "image/jpeg", "image/gif"} or ";base64" not in header.casefold():
                    raise ValueError("unsupported data image format")
                image_data = base64.b64decode(encoded, validate=True)
                if not image_data or len(image_data) > _MAX_IMAGE_BYTES or image_bytes + len(image_data) > _MAX_TOTAL_IMAGE_BYTES:
                    raise ValueError("image size limit exceeded")
                image_nodes.append((node, image_data))
                image_bytes += len(image_data)
            except (ValueError, base64.binascii.Error):
                warnings.append("Owned HTML data image is invalid or exceeds its size limit.")
            continue
        if not raw or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", raw):
            warnings.append(f"Image with non-local or empty source omitted: {raw or '(empty)'}")
            continue
        try:
            image = (source.parent / raw.split("#", 1)[0].split("?", 1)[0]).resolve(strict=True)
            image.relative_to(root)
            size = image.stat().st_size
            if not image.is_file() or size > _MAX_IMAGE_BYTES or image_bytes + size > _MAX_TOTAL_IMAGE_BYTES:
                raise ValueError("image size or type limit exceeded")
            image_nodes.append((node, image))
            image_bytes += size
        except (OSError, ValueError):
            warnings.append(f"Local image unavailable or outside input directory: {raw}")
    image_map = {id(node): image for node, image in image_nodes}
    counts = {"paragraphs": 0, "headings": 0, "lists": 0, "tables": 0, "images": 0}

    def add_image(node: _Node, paragraph=None) -> None:
        image = image_map.get(id(node))
        if image is not None:
            picture_source = BytesIO(image) if isinstance(image, bytes) else str(image)
            shape = document.add_picture(picture_source, width=Inches(5.5))
            if paragraph is None:
                paragraph = shape._inline
                while paragraph is not None and paragraph.tag != "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p":
                    paragraph = paragraph.getparent()
            if paragraph is not None:
                add_bookmark(paragraph, node.attrs.get("data-wps-object-id", ""))
            counts["images"] += 1

    def add_text_with_links(paragraph, node: _Node) -> None:
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.opc.constants import RELATIONSHIP_TYPE as RT

        for child in node.children:
            if isinstance(child, str):
                paragraph.add_run(child)
            elif child.tag == "br":
                paragraph.add_run().add_break()
            elif child.tag == "img":
                add_image(child, paragraph._p)
            elif child.tag == "a":
                label = _text(child)
                href = child.attrs.get("href", "").strip()
                if label and href and _safe_link_target(href):
                    relation = paragraph.part.relate_to(href, RT.HYPERLINK, is_external=True)
                    hyperlink = OxmlElement("w:hyperlink")
                    hyperlink.set(qn("r:id"), relation)
                    run = OxmlElement("w:r")
                    props = OxmlElement("w:rPr")
                    color = OxmlElement("w:color")
                    color.set(qn("w:val"), "0563C1")
                    underline = OxmlElement("w:u")
                    underline.set(qn("w:val"), "single")
                    props.append(color)
                    props.append(underline)
                    run.append(props)
                    text = OxmlElement("w:t")
                    text.text = label
                    run.append(text)
                    hyperlink.append(run)
                    paragraph._p.append(hyperlink)
                    if owned_schema and child.attrs.get("data-wps-object-id"):
                        add_bookmark(paragraph._p, child.attrs["data-wps-object-id"])
                else:
                    paragraph.add_run(label)
                    if href and not _safe_link_target(href):
                        warnings.append("Unsafe hyperlink target omitted.")
            else:
                add_text_with_links(paragraph, child)

    def add_blocks(container: _Node, list_style: str | None = None) -> None:
        for node in container.children:
            if isinstance(node, str):
                text = node.strip()
                if text:
                    document.add_paragraph(text)
                    counts["paragraphs"] += 1
                continue
            tag = node.tag
            if tag in _HEADINGS:
                text = _text(node)
                if text:
                    paragraph = document.add_heading(level=_HEADINGS[tag])
                    add_bookmark(paragraph._p, node.attrs.get("data-wps-object-id", ""))
                    add_text_with_links(paragraph, node)
                    counts["headings"] += 1
            elif tag == "p" or tag in {"blockquote", "pre", "address"}:
                text = _text(node)
                if text:
                    paragraph = document.add_paragraph()
                    add_bookmark(paragraph._p, node.attrs.get("data-wps-object-id", ""))
                    add_text_with_links(paragraph, node)
                    if tag == "blockquote":
                        paragraph.style = "Quote"
                    elif tag == "pre":
                        paragraph.style = "No Spacing"
                    counts["paragraphs"] += 1
            elif tag in {"ul", "ol"}:
                style = "List Number" if tag == "ol" else "List Bullet"
                for item in node.children:
                    if isinstance(item, _Node) and item.tag == "li":
                        text = _text(item)
                        if text:
                            paragraph = document.add_paragraph(style=style)
                            add_bookmark(paragraph._p, item.attrs.get("data-wps-object-id", ""))
                            add_text_with_links(paragraph, item)
                            counts["lists"] += 1
            elif tag == "table":
                rows = [item for item in _walk(node) if item.tag == "tr"]
                cells = [[_text(cell) for cell in row.children if isinstance(cell, _Node) and cell.tag in {"td", "th"}] for row in rows]
                columns = max((len(row) for row in cells), default=0)
                if cells and columns:
                    table = document.add_table(rows=len(cells), cols=columns)
                    table.style = "Table Grid"
                    for row_index, row_node in enumerate(rows):
                        source_cells = [cell for cell in row_node.children if isinstance(cell, _Node) and cell.tag in {"td", "th"}]
                        first_cell_paragraph = table.cell(row_index, 0).paragraphs[0]._p
                        if row_index == 0:
                            add_bookmark(first_cell_paragraph, node.attrs.get("data-wps-object-id", ""))
                        add_bookmark(first_cell_paragraph, row_node.attrs.get("data-wps-object-id", ""))
                        for column_index, cell_node in enumerate(source_cells):
                            cell = table.cell(row_index, column_index)
                            paragraph = cell.paragraphs[0]
                            add_bookmark(paragraph._p, cell_node.attrs.get("data-wps-object-id", ""))
                            add_text_with_links(paragraph, cell_node)
                    counts["tables"] += 1
            elif tag == "img":
                add_image(node)
            elif tag in _BLOCKS or tag in {"body", "html", "main", "section", "article"}:
                add_blocks(node)

    try:
        add_blocks(parser.root)
        if not any(counts.values()):
            return False, {}, [{"code": "NO_SUPPORTED_CONTENT", "message": "No supported semantic HTML content was found."}]
        document.core_properties.title = next((_text(node) for node in nodes if node.tag == "title" and _text(node)), "HTML conversion")
        handle = tempfile.NamedTemporaryFile(prefix=f".{destination.stem}.", suffix=".docx", dir=destination.parent, delete=False)
        temporary = Path(handle.name)
        handle.close()
        document.save(temporary)
        payload = temporary.read_bytes()
        os.link(temporary, destination)
        temporary.unlink()
    except Exception as exc:  # noqa: BLE001
        if "temporary" in locals():
            temporary.unlink(missing_ok=True)
        return False, {}, [{"code": "CONVERSION_FAILED", "message": str(exc)[:500]}]
    warnings = sorted(set(warnings))
    return True, {
        "input_path": str(source), "output_path": str(destination),
        "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
        "backend": "python-docx-semantic-mapping", "editable": True,
        "mapped_objects": counts, "unsupported_css": unsupported_css,
        "warnings": warnings, "fidelity": "semantic-content; CSS layout is not preserved",
        "source_encoding": source_encoding,
        "javascript_executed": False, "remote_resources_fetched": False,
        "roundtrip_bookmarks": bookmark_count,
    }, []
