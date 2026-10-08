from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import BadZipFile
import hashlib
import xml.etree.ElementTree as ET

from .document_text import docx_body_paragraphs
from .sessions import get_document
from .writer_structure import read_supported_bookmark_text, read_writer_structure


def inspect_writer_structure(
    document_id: str, limit: int = 50, workspace: str | Path = ".",
    section: str = "all", offset: int = 0, bookmark_name: str | None = None,
    expected_sha256: str | None = None,
    include_text: bool = False, text_limit: int = 200,
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    if not 1 <= limit <= 200:
        return False, {}, [{"code": "INVALID_LIMIT", "message": "Limit must be between 1 and 200."}]
    if section not in {"all", "headings", "styles", "bookmarks", "warnings"}:
        return False, {}, [{"code": "INVALID_SECTION", "message": "Unknown Writer structure section."}]
    if offset < 0 or (section == "all" and offset != 0):
        return False, {}, [{"code": "INVALID_OFFSET", "message": "Offset must be non-negative and requires one selected section."}]
    if bookmark_name is not None and (not bookmark_name or len(bookmark_name) > 256 or section != "bookmarks"):
        return False, {}, [{"code": "INVALID_BOOKMARK_QUERY", "message": "Bookmark name must be 1-256 characters and requires the bookmarks section."}]
    if include_text and (bookmark_name is None or section != "bookmarks" or offset != 0):
        return False, {}, [{"code": "INVALID_BOOKMARK_TEXT_QUERY", "message": "Text inspection requires an exact bookmark name at offset zero."}]
    if not 1 <= text_limit <= 4096:
        return False, {}, [{"code": "INVALID_TEXT_LIMIT", "message": "Text limit must be between 1 and 4096."}]
    if expected_sha256 is not None and (len(expected_sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in expected_sha256)):
        return False, {}, [{"code": "INVALID_SOURCE_HASH", "message": "Expected SHA-256 must be 64 hexadecimal characters."}]
    document = get_document(document_id, workspace)
    if not document:
        return False, {}, [{"code": "DOCUMENT_NOT_FOUND", "message": f"Document not registered: {document_id}"}]
    if document.get("component") != "writer":
        return False, {}, [{"code": "UNSUPPORTED_COMPONENT", "message": "Writer structure inspection requires a Writer document."}]
    path = Path(document["path"])
    if not path.is_file():
        return False, {}, [{"code": "INPUT_FILE_NOT_FOUND", "message": f"Input file not found: {path}"}]
    try:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if expected_sha256 is not None and digest.lower() != expected_sha256.lower():
            return False, {}, [{"code": "WRITER_SOURCE_CHANGED", "message": "Document hash differs from the requested page source."}]
        structure = read_writer_structure(path)
        texts = docx_body_paragraphs(path)
        value_matches = [item for item in structure["bookmarks"] if item["name"] == bookmark_name] if include_text else []
        bookmark_text = None
        if len(value_matches) == 1 and value_matches[0]["text_range_supported"]:
            _, bookmark_text = read_supported_bookmark_text(path, bookmark_name)
        with path.open("rb") as stream:
            after_digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != after_digest:
            return False, {}, [{"code": "WRITER_SOURCE_CHANGED", "message": "Document changed during structure inspection."}]
    except (BadZipFile, KeyError, ET.ParseError, ValueError, OSError) as exc:
        return False, {}, [{"code": "WRITER_STRUCTURE_INVALID", "message": str(exc)}]
    headings = [
        {**item, "preview": " ".join(texts[item["paragraph_index"] - 1].split())[:120]}
        for item in structure["paragraphs"] if item["heading_level"] is not None
    ]
    styles = sorted({
        (item["style_id"], item["style_name"], item["style_resolution"])
        for item in structure["paragraphs"] if item["style_id"] is not None
    }, key=lambda item: (item[0], item[1] or ""))
    bookmarks = structure["bookmarks"]
    matching_bookmarks = [item for item in bookmarks if item["name"] == bookmark_name] if bookmark_name is not None else bookmarks
    sections = {
        "headings": headings,
        "styles": [{"style_id": item[0], "style_name": item[1], "resolution": item[2]} for item in styles],
        "bookmarks": matching_bookmarks,
        "warnings": structure["warnings"],
    }
    selected = sections if section == "all" else {section: sections[section]}
    pagination = {
        name: {
            "offset": offset,
            "returned_count": len(items[offset:offset + limit]),
            "total_count": len(items),
            "next_offset": offset + limit if offset + limit < len(items) else None,
        }
        for name, items in selected.items()
    }
    scope = dict(structure["scope"])
    scope["bookmark_part_count"] = len(scope["bookmark_parts"])
    scope["bookmark_parts"] = scope["bookmark_parts"][:200]
    result = {
        "document_id": document_id,
        "path": str(path),
        "source_sha256": digest,
        "evidence_backend": "offline-ooxml",
        "wps_validated": False,
        "scope": scope,
        "limit": limit,
        "section": section,
        "offset": offset,
        "pagination": pagination,
        "paragraph_count": len(structure["paragraphs"]),
        "heading_count": len(headings),
        "style_count": len(styles),
        "bookmark_count": len(bookmarks),
        "warning_count": len(structure["warnings"]),
        "truncated": any(item["next_offset"] is not None for item in pagination.values()),
    }
    result.update({name: items[offset:offset + limit] for name, items in selected.items()})
    if bookmark_name is not None:
        result["bookmark_query"] = {
            "name": bookmark_name,
            "match_count": len(matching_bookmarks),
            "status": "missing" if not matching_bookmarks else "unique" if len(matching_bookmarks) == 1 else "ambiguous",
        }
    if include_text:
        if not value_matches:
            value_status = "missing"
        elif len(value_matches) > 1:
            value_status = "ambiguous"
        elif not value_matches[0]["text_range_supported"]:
            value_status = "unsupported_scope"
        elif bookmark_text is None:
            value_status = "invalid_range"
        elif bookmark_text == "":
            value_status = "empty"
        else:
            value_status = "available"
        result["bookmark_value"] = {
            "name": bookmark_name,
            "status": value_status,
            "bookmark_status": value_matches[0]["status"] if len(value_matches) == 1 else None,
            "text": bookmark_text[:text_limit] if bookmark_text is not None else None,
            "text_length": len(bookmark_text) if bookmark_text is not None else None,
            "truncated": bookmark_text is not None and len(bookmark_text) > text_limit,
            "text_limit": text_limit,
        }
    return True, result, []
