from __future__ import annotations

from pathlib import Path
from typing import Any

from .document_text import count_text_in_docx
from .errors import INPUT_FILE_NOT_FOUND
from .sessions import get_document
from .writer_ops import BODY_PARTS


def _normalize(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return "" if value is None else str(value)


def validate_document(
    document_id: str,
    contains: str | None = None,
    cell: str | None = None,
    equals: str | None = None,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    document = get_document(document_id, workspace)
    if not document:
        return (
            False,
            {},
            [{"code": "DOCUMENT_NOT_FOUND", "message": f"Document not registered: {document_id}"}],
        )

    path = Path(document["path"])
    if not path.exists():
        return (
            False,
            {"document": document},
            [{"code": INPUT_FILE_NOT_FOUND, "message": f"Input file not found: {path}"}],
        )

    if document["component"] == "writer":
        if not contains:
            return (
                False,
                {"document": document},
                [{"code": "INVALID_ARGUMENT", "message": "writer validation requires --contains."}],
            )
        count = count_text_in_docx(path, contains, parts=BODY_PARTS)
        result = {
            "document_id": document_id,
            "component": "writer",
            "path": str(path),
            "scope": "body",
            "contains": contains,
            "count": count,
        }
        if count <= 0:
            return (
                False,
                result,
                [{"code": "VALIDATION_FAILED", "message": "Expected text was not found."}],
            )
        return True, result, []

    if document["component"] == "spreadsheets":
        if not cell or equals is None:
            return (
                False,
                {"document": document},
                [{"code": "INVALID_ARGUMENT", "message": "spreadsheet validation requires --cell and --equals."}],
            )
        try:
            from openpyxl import load_workbook
        except ImportError:
            return (
                False,
                {"document": document},
                [{"code": "DEPENDENCY_MISSING", "message": "openpyxl is required for spreadsheet validation."}],
            )

        workbook = load_workbook(path, data_only=True, read_only=True)
        try:
            sheet = workbook.worksheets[0]
            value = sheet[cell].value
        finally:
            workbook.close()

        normalized = _normalize(value)
        passed = normalized == equals
        result = {
            "document_id": document_id,
            "component": "spreadsheets",
            "path": str(path),
            "sheet": sheet.title,
            "cell": cell,
            "expected": equals,
            "actual": normalized,
        }
        if not passed:
            return (
                False,
                result,
                [{"code": "VALIDATION_FAILED", "message": "Cell value did not match expected value."}],
            )
        return True, result, []

    return (
        False,
        {"document": document},
        [{"code": "UNSUPPORTED_COMPONENT", "message": f"Validation is not implemented for {document['component']}."}],
    )
