"""Create a blank document offline and register it (C-01).

Before this, every task needed an existing file. ``document-new`` writes an empty .docx, .xlsx or .pptx
without starting WPS (python-docx, openpyxl, python-pptx), optionally with a title, and registers it so the
returned document_id goes straight into the existing read and write commands. The file is created with an
exclusive open: an existing path is never overwritten.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from .conversion_paths import missing_dependency
from .sessions import register_document
from .workspace_boundary import boundary_error

SUFFIXES = {"writer": ".docx", "spreadsheets": ".xlsx", "presentation": ".pptx"}
# 16:9, the size WPS Presentation and PowerPoint use for a new deck.
SLIDE_SIZE = (12192000, 6858000)


def _error(code: str, message: str) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    return False, {}, [{"code": code, "message": message}]


def _writer_bytes(title: str | None) -> bytes:
    from docx import Document

    document = Document()
    if title:
        document.add_heading(title, level=0)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _spreadsheet_bytes(title: str | None) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    if title:
        workbook.active.title = title
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _presentation_bytes(title: str | None) -> bytes:
    from pptx import Presentation

    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = SLIDE_SIZE
    if title:
        slide = presentation.slides.add_slide(presentation.slide_layouts[0])
        slide.shapes.title.text = title
    buffer = io.BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()


def _read_back(component: str, path: Path) -> dict[str, Any]:
    """What the new file holds, read with the same library that will read it later."""
    if component == "writer":
        from docx import Document

        paragraphs = [paragraph.text for paragraph in Document(str(path)).paragraphs]
        return {"paragraphs": paragraphs}
    if component == "spreadsheets":
        from .ooxml import load_workbook_guarded

        workbook = load_workbook_guarded(path, read_only=True)
        try:
            return {"sheet_names": list(workbook.sheetnames)}
        finally:
            workbook.close()
    from pptx import Presentation

    presentation = Presentation(str(path))
    titles = [slide.shapes.title.text if slide.shapes.title is not None else "" for slide in presentation.slides]
    return {"slide_count": len(titles), "slide_titles": titles}


def create_document(
    component: str,
    path: str | Path,
    title: str | None = None,
    register: bool = True,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    """Write a blank document of ``component`` at ``path`` and (by default) register it."""
    if component not in SUFFIXES:
        return _error("UNSUPPORTED_COMPONENT", f"Unsupported component: {component}")
    destination = Path(path).expanduser().resolve()
    outside = boundary_error(destination, "Document path")
    if outside is not None:
        return False, {}, [outside]
    suffix = SUFFIXES[component]
    if destination.suffix.casefold() != suffix:
        return _error("INVALID_OUTPUT", f"A new {component} document must be a {suffix} file.")
    if destination.exists():
        return _error("OUTPUT_ALREADY_EXISTS", f"Refusing to overwrite existing file: {destination}")
    if not destination.parent.is_dir():
        return _error("OUTPUT_DIRECTORY_NOT_FOUND", f"Output directory does not exist: {destination.parent}")
    title = title.strip() if title else None
    if component == "spreadsheets" and title:
        from .spreadsheet_ops import _validate_sheet_title

        invalid = _validate_sheet_title(title)
        if invalid is not None:
            return False, {}, [invalid]

    builders = {"writer": _writer_bytes, "spreadsheets": _spreadsheet_bytes, "presentation": _presentation_bytes}
    try:
        content = builders[component](title)
    except ImportError:
        package = {"writer": "python-docx", "presentation": "python-pptx"}.get(component, "openpyxl")
        return missing_dependency("html", package)
    try:
        # "x": created only if nothing is there, so a file that appeared since the check is never replaced.
        with open(destination, "xb") as handle:
            handle.write(content)
    except FileExistsError:
        return _error("OUTPUT_ALREADY_EXISTS", f"Refusing to overwrite existing file: {destination}")
    except OSError as exc:
        return _error("OUTPUT_WRITE_FAILED", f"Could not write {destination}: {exc}")

    contents = _read_back(component, destination)
    expected_title_found = (
        not title
        or (component == "writer" and title in contents["paragraphs"])
        or (component == "spreadsheets" and contents["sheet_names"] == [title])
        or (component == "presentation" and contents["slide_titles"] == [title])
    )
    data: dict[str, Any] = {
        "component": component,
        "path": str(destination),
        "title": title,
        "size": destination.stat().st_size,
        "contents": contents,
        "validation_passed": expected_title_found,
        "registered": False,
    }
    if not expected_title_found:
        return False, data, [{"code": "VALIDATION_FAILED", "message": "The new document does not hold the title."}]
    if register:
        ok, record, errors = register_document(component, str(destination), workspace)
        if not ok:
            return False, data, errors
        data["registered"] = True
        data["document_id"] = record["document_id"]
        data["document"] = record
    return True, data, []
