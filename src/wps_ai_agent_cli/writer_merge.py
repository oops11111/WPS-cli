"""Fill {{key}} placeholders in a Writer document from JSON data (C-03).

A placeholder is two braces around a name, with optional spaces: {{客户名称}}, {{ due_date }}. Writer splits text
into runs wherever formatting, spelling marks or editing history change, so a placeholder typed in WPS is often
spread over several runs. This module works on the package's XML directly: it joins each paragraph's text,
finds the placeholders there, and puts each value into the run where its placeholder starts, so the value keeps
that run's formatting. It covers the body (tables included), headers, footers, footnotes and endnotes.

The write is offline (no WPS), so the document must not be open in WPS; a held file is refused. Like the other
writes, it takes a backup first, replaces the file atomically, reads the result back, and is undone from the
backup if the read-back does not match (atomic_mutation).
"""

from __future__ import annotations

import io
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from .atomic_mutation import atomic_mutation
from .backups import create_backup, record_after_com_identity
from .conversion_paths import missing_dependency
from .errors import INPUT_FILE_NOT_FOUND
from .file_hold import probe_file_not_held
from .mutation_lock import coordinated_mutation
from .ooxml import check_archive_limits, read_zip_part
from .operations import record_operation, replay_operation
from .sessions import file_identity, get_document

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
PLACEHOLDER = re.compile(r"\{\{\s*([^{}\s][^{}\n]*?)\s*\}\}")
STORY_PARTS = re.compile(r"word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml")
MAX_VALUE_CHARS = 32_767
PLACEHOLDER_NOT_FOUND = "PLACEHOLDER_NOT_FOUND"
PLACEHOLDER_UNFILLED = "PLACEHOLDER_UNFILLED"


def _part_label(name: str) -> str:
    return name.removeprefix("word/").removesuffix(".xml")


def _parse(content: bytes):
    from lxml import etree

    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, remove_blank_text=False)
    return etree.fromstring(content, parser)


def _paragraph_texts(paragraph) -> list:
    """The paragraph's own w:t elements in order (not those of a text box's paragraphs inside it)."""
    return [text for text in paragraph.iter(f"{{{W}}}t") if next(text.iterancestors(f"{{{W}}}p")) is paragraph]


def _paragraphs(root) -> list:
    return list(root.iter(f"{{{W}}}p"))


def _joined(paragraph) -> str:
    return "".join(text.text or "" for text in _paragraph_texts(paragraph))


def normalize_data(data: Any) -> tuple[dict[str, str] | None, str | None]:
    """{key: text} from a JSON object of strings, numbers, booleans and nulls."""
    if not isinstance(data, dict) or not data:
        return None, "data must be a non-empty JSON object of placeholder names and values."
    values: dict[str, str] = {}
    for key, value in data.items():
        name = str(key).strip()
        if not name or "{" in name or "}" in name:
            return None, f"Not a placeholder name: {key!r}."
        if isinstance(value, (dict, list)):
            return None, f"The value of {key!r} must be text or a number, not {type(value).__name__}."
        if value is None:
            text = ""
        elif isinstance(value, bool):
            text = "true" if value else "false"
        else:
            text = str(value)
        if len(text) > MAX_VALUE_CHARS:
            return None, f"The value of {key!r} is longer than {MAX_VALUE_CHARS} characters."
        if any(ord(char) < 0x20 and char not in "\n\t" for char in text):
            return None, f"The value of {key!r} contains control characters."
        values[name] = text.replace("\r\n", "\n").replace("\r", "\n")
    return values, None


def scan(path: Path, values: dict[str, str]) -> dict[str, Any]:
    """Every placeholder by part, which keys are filled and which are not, without changing anything."""
    found: dict[str, dict[str, int]] = {}
    with ZipFile(path) as archive:
        check_archive_limits(archive)
        for name in archive.namelist():
            if not STORY_PARTS.fullmatch(name):
                continue
            root = _parse(read_zip_part(archive, name))
            for paragraph in _paragraphs(root):
                for match in PLACEHOLDER.finditer(_joined(paragraph)):
                    counts = found.setdefault(match.group(1), {})
                    counts[_part_label(name)] = counts.get(_part_label(name), 0) + 1
    filled = {key: parts for key, parts in found.items() if key in values}
    return {
        "placeholders": {key: sum(parts.values()) for key, parts in found.items()},
        "placeholder_parts": found,
        "replacements": sum(sum(parts.values()) for parts in filled.values()),
        "unfilled": sorted(key for key in found if key not in values),
        "unused_keys": sorted(key for key in values if key not in found),
    }


def _locate(lengths: list[int], offset: int, is_end: bool) -> tuple[int, int]:
    """(index of the w:t, offset inside it) for an offset into the joined original text.

    lengths are the w:t lengths before any change. An offset on a boundary between two elements belongs to the
    right one when it starts a placeholder and to the left one when it ends one, so a value never lands in the
    run before its placeholder.
    """
    position = 0
    for index, length in enumerate(lengths):
        inside = offset <= position + length if is_end else offset < position + length
        if length and inside:
            return index, offset - position
        position += length
    return len(lengths) - 1, lengths[-1]


def _set_text(element, text: str) -> None:
    element.text = text
    if text != text.strip() or "  " in text:
        element.set(XML_SPACE, "preserve")


def _put_lines(element, text: str) -> None:
    """Set a w:t to text; each newline becomes a w:br and each tab a w:tab, inside the same run."""
    from lxml import etree

    pieces = re.split(r"([\n\t])", text)
    _set_text(element, pieces[0])
    anchor = element
    for index in range(1, len(pieces), 2):
        mark = etree.Element(f"{{{W}}}{'br' if pieces[index] == chr(10) else 'tab'}")
        anchor.addnext(mark)
        anchor = mark
        if pieces[index + 1]:
            follow = etree.Element(f"{{{W}}}t")
            _set_text(follow, pieces[index + 1])
            anchor.addnext(follow)
            anchor = follow


def fill_paragraph(paragraph, values: dict[str, str]) -> int:
    """Replace the filled placeholders of one paragraph in place; return how many were replaced.

    Each value goes into the w:t where its placeholder starts (keeping that run's formatting); the rest of a
    placeholder spread over later w:t elements is cut from them. Matches are handled from the last to the first,
    so the offsets of earlier matches still point at text that has not changed.
    """
    texts = _paragraph_texts(paragraph)
    if not texts:
        return 0
    lengths = [len(text.text or "") for text in texts]
    joined = "".join(text.text or "" for text in texts)
    matches = [match for match in PLACEHOLDER.finditer(joined) if match.group(1) in values]
    changed: set[int] = set()
    for match in reversed(matches):
        value = values[match.group(1)]
        first, start = _locate(lengths, match.start(), is_end=False)
        last, end = _locate(lengths, match.end(), is_end=True)
        head = (texts[first].text or "")[:start]
        if first == last:
            _set_text(texts[first], head + value + (texts[first].text or "")[end:])
        else:
            _set_text(texts[last], (texts[last].text or "")[end:])
            for middle in range(first + 1, last):
                _set_text(texts[middle], "")
            _set_text(texts[first], head + value)
        changed.add(first)
    for index in changed:
        if any(mark in (texts[index].text or "") for mark in "\n\t"):
            _put_lines(texts[index], texts[index].text or "")
    return len(matches)


def expected_texts(path: Path, values: dict[str, str]) -> dict[str, list[str]]:
    """Each story part's paragraph texts (w:t only) as they must read after the merge."""

    def substitute(match: re.Match) -> str:
        key = match.group(1)
        return values[key].replace("\n", "").replace("\t", "") if key in values else match.group(0)

    expected: dict[str, list[str]] = {}
    with ZipFile(path) as archive:
        for name in archive.namelist():
            if STORY_PARTS.fullmatch(name):
                root = _parse(read_zip_part(archive, name))
                expected[name] = [PLACEHOLDER.sub(substitute, _joined(p)) for p in _paragraphs(root)]
    return expected


def actual_texts(path: Path) -> dict[str, list[str]]:
    actual: dict[str, list[str]] = {}
    with ZipFile(path) as archive:
        for name in archive.namelist():
            if STORY_PARTS.fullmatch(name):
                root = _parse(read_zip_part(archive, name))
                actual[name] = [_joined(p) for p in _paragraphs(root)]
    return actual


def merge_package(source: Path, values: dict[str, str]) -> tuple[bytes, int]:
    """The merged package's bytes and the number of replacements; every other part is copied unchanged."""
    from lxml import etree

    buffer = io.BytesIO()
    replaced = 0
    with ZipFile(source) as archive, ZipFile(buffer, "w") as merged:
        check_archive_limits(archive)
        for info in archive.infolist():
            content = read_zip_part(archive, info.filename)
            if STORY_PARTS.fullmatch(info.filename):
                root = _parse(content)
                count = sum(fill_paragraph(paragraph, values) for paragraph in _paragraphs(root))
                if count:
                    replaced += count
                    content = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            merged.writestr(info, content, compress_type=info.compress_type or ZIP_DEFLATED)
    return buffer.getvalue(), replaced


def _replace_file(path: Path, content: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".merge.tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


@coordinated_mutation
@atomic_mutation
def writer_merge(
    document_id: str,
    data: Any,
    request_id: str,
    dry_run: bool = False,
    require_all: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    """Fill the document's {{key}} placeholders from data, with backup, read-back and rollback."""
    replay = replay_operation(
        request_id,
        "writer-merge",
        {"document_id": document_id, "data": data, "dry_run": dry_run, "require_all": require_all},
        workspace,
    )
    if replay is not None:
        return replay
    values, problem = normalize_data(data)
    if problem:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": problem}], False
    try:
        import lxml  # noqa: F401  (python-docx brings it)
    except ImportError:
        ok, empty, errors = missing_dependency("html", "python-docx")
        return ok, empty, errors, False
    document = get_document(document_id, workspace)
    if not document:
        return False, {}, [{"code": "DOCUMENT_NOT_FOUND", "message": f"Document not registered: {document_id}"}], False
    if document["component"] != "writer":
        return (
            False,
            {"document": document},
            [{"code": "UNSUPPORTED_COMPONENT", "message": "writer-merge requires a writer document."}],
            False,
        )
    path = Path(document["path"])
    if not path.exists():
        return (
            False,
            {"document": document},
            [{"code": INPUT_FILE_NOT_FOUND, "message": f"Input file not found: {path}"}],
            False,
        )
    if path.suffix.casefold() not in {".docx", ".docm", ".dotx"}:
        return (
            False,
            {"document": document},
            [{"code": "INVALID_INPUT", "message": "writer-merge fills .docx files; convert other formats first."}],
            False,
        )
    held = probe_file_not_held(path, read_only=True, what="document")
    if held is not None:
        return False, {"document_id": document_id, "path": str(path)}, [held], False

    found = scan(path, values)
    preview = {
        "document_id": document_id,
        "path": str(path),
        "data": data,
        "dry_run": dry_run,
        "require_all": require_all,
        **found,
    }
    if found["unfilled"] and require_all:
        return (
            False,
            preview,
            [
                {
                    "code": PLACEHOLDER_UNFILLED,
                    "message": "No value for: " + ", ".join(found["unfilled"]) + ". Nothing was changed.",
                }
            ],
            False,
        )
    if dry_run:
        return True, preview, [], False
    if found["replacements"] == 0:
        message = (
            "None of the given names appears as a {{placeholder}} in the document."
            if found["placeholders"]
            else "The document has no {{placeholder}}."
        )
        return False, preview, [{"code": PLACEHOLDER_NOT_FOUND, "message": message}], False

    backup_ok, backup, backup_errors, backup_replayed = create_backup(
        document_id, f"{request_id}:backup", workspace=workspace
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup}, backup_errors, False
    expected = expected_texts(path, values)
    content, replaced = merge_package(path, values)
    _replace_file(path, content)
    record_after_com_identity(path, file_identity(path))  # this command's own write, for a rollback check

    actual = actual_texts(path)
    # A filled name may still show as {{name}} only where a value itself spells one: none was missed.
    remaining = sum(
        1
        for lines in actual.values()
        for line in lines
        for match in PLACEHOLDER.finditer(line)
        if match.group(1) in values
    )
    allowed = sum(
        1
        for lines in expected.values()
        for line in lines
        for match in PLACEHOLDER.finditer(line)
        if match.group(1) in values
    )
    validation_passed = actual == expected and replaced == found["replacements"] and remaining == allowed

    result = {
        **preview,
        "dry_run": False,
        "backup": backup,
        "backup_replayed": backup_replayed,
        "replaced": replaced,
        "remaining_filled_placeholders": remaining - allowed,
        "readback_matches_expected": actual == expected,
        "validation_passed": validation_passed,
    }
    if not validation_passed:
        return (
            False,
            result,
            [{"code": "VALIDATION_FAILED", "message": "The merged document did not read back as expected."}],
            False,
        )
    record_operation(request_id, "writer-merge", result, workspace)
    return True, result, [], False
