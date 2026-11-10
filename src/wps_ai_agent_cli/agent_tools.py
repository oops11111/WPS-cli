"""Tools that save an agent round trips: batch (C-07), get by path (C-08), document view and check (C-09).

- batch runs a list of tool calls in order, each through the same adapter as an MCP tools/call
  (mcp_adapter.call_mcp_tool), so argument checks, the destructive-tool confirm gate and every write's own
  backup and read-back apply to each item exactly as if it were called alone. It stops at the first failure
  unless told to continue, and reports every item.
- get reads one target named by a path: /sheet["销售"]/cell["C12"], /paragraph[3], /table[1]/cell[2,3], /slide[2].
- document-view summarises a document (outline, counts, sheets, slides); document-check lists problems an agent
  should look at before handing a document over (unfilled placeholders, heading jumps, formula errors, empty
  slides). Both only read.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .document_text import docx_body_paragraphs, docx_body_tables
from .sessions import get_document

MAX_BATCH_ITEMS = 50
BATCH_BLOCKED = {"batch", "wps_agent_batch", "mcp-call", "wps_agent_mcp_call", "mcp-server", "wps_agent_mcp_server"}
PATH_SYNTAX_INVALID = "PATH_SYNTAX_INVALID"
PATH_TARGET_NOT_FOUND = "PATH_TARGET_NOT_FOUND"
EXCEL_ERRORS = ("#REF!", "#DIV/0!", "#N/A", "#VALUE!", "#NAME?", "#NUM!", "#NULL!")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

Result = tuple[bool, dict[str, Any], list[dict[str, str]]]


def _fail(code: str, message: str, data: dict[str, Any] | None = None) -> Result:
    return False, data or {}, [{"code": code, "message": message}]


def _reading(document: dict[str, Any], read) -> Result:
    """Run a reader; a file WPS holds is DOCUMENT_HELD_OPEN and a damaged one INVALID_INPUT, not a traceback."""
    from .file_hold import held_open_error, is_share_conflict

    try:
        return read()
    except OSError as exc:
        if is_share_conflict(exc):
            error = held_open_error("document", str(exc))
            return _fail(error["code"], error["message"], {"path": document["path"]})
        return _fail("INVALID_INPUT", f"{document['path']} could not be read: {exc}")
    except (
        Exception
    ) as exc:  # zipfile, XML, openpyxl and python-pptx raise many types for a damaged file  # noqa: BLE001
        return _fail("INVALID_INPUT", f"{Path(document['path']).name} could not be read as a document: {exc}")


def _document(document_id: str, workspace: str | Path) -> tuple[dict[str, Any] | None, Result | None]:
    document = get_document(document_id, workspace)
    if not document:
        return None, _fail("DOCUMENT_NOT_FOUND", f"Document not registered: {document_id}")
    if not Path(document["path"]).exists():
        return None, _fail("INPUT_FILE_NOT_FOUND", f"Input file not found: {document['path']}", {"document": document})
    return document, None


# --------------------------------------------------------------------------------------------------- C-07 batch
def _tool_name(name: str) -> str | None:
    from .mcp_schema import list_mcp_tool_schemas

    for schema in list_mcp_tool_schemas():
        if name in (schema["name"], schema["cli_command"]):
            return schema["name"]
    return None


def parse_batch(commands: Any) -> tuple[list[dict[str, Any]] | None, str | None]:
    """[{"tool": name, "arguments": {...}}] checked: known tools, objects, at most MAX_BATCH_ITEMS, no nesting."""
    if not isinstance(commands, list) or not commands:
        return None, 'commands must be a non-empty JSON array of {"tool": ..., "arguments": {...}}.'
    if len(commands) > MAX_BATCH_ITEMS:
        return None, f"A batch holds at most {MAX_BATCH_ITEMS} commands; it has {len(commands)}."
    items = []
    for index, item in enumerate(commands, 1):
        if not isinstance(item, dict) or not isinstance(item.get("tool"), str):
            return None, f"Command {index} is not an object with a tool name."
        arguments = item.get("arguments", {})
        if not isinstance(arguments, dict):
            return None, f"Command {index}: arguments must be an object."
        if item["tool"] in BATCH_BLOCKED:
            return None, f"Command {index}: {item['tool']} cannot run inside a batch."
        name = _tool_name(item["tool"])
        if name is None:
            return None, f"Command {index}: unknown tool {item['tool']!r}."
        items.append({"tool": name, "arguments": arguments})
    return items, None


def run_batch(commands: Any, request_id: str, continue_on_error: bool = False) -> Result:
    """Run each command through the MCP adapter, in order; stop at the first failure unless continue_on_error."""
    from .mcp_adapter import call_mcp_tool

    items, problem = parse_batch(commands)
    if problem:
        return _fail("INVALID_ARGUMENT", problem)
    results = []
    stopped_at = None
    for index, item in enumerate(items, 1):
        arguments = {"request_id": f"{request_id}:{index}", **item["arguments"]}
        ok, data, errors = call_mcp_tool(item["tool"], arguments)
        response = data.get("response") or {}
        results.append(
            {
                "index": index,
                "tool": item["tool"],
                "request_id": arguments["request_id"],
                "ok": ok,
                "summary": response.get("summary"),
                "data": response.get("data"),
                "errors": errors,
            }
        )
        if not ok and not continue_on_error:
            stopped_at = index
            break
    failed = [result["index"] for result in results if not result["ok"]]
    data = {
        "commands": len(items),
        "ran": len(results),
        "succeeded": len(results) - len(failed),
        "failed": failed,
        "stopped_at": stopped_at,
        "skipped": len(items) - len(results),
        "continue_on_error": continue_on_error,
        "results": results,
    }
    if failed:
        first = results[failed[0] - 1]
        reason = first["errors"][0]["message"] if first["errors"] else "it failed"
        return _fail(
            "BATCH_COMMAND_FAILED",
            f"Command {failed[0]} ({first['tool']}) failed: {reason}"
            + (f" The {data['skipped']} commands after it were not run." if stopped_at else ""),
            data,
        )
    return True, data, []


# ---------------------------------------------------------------------------------------------------- C-08 get
_SEGMENT = re.compile(r'/([a-z]+)(?:\[(?:"((?:[^"\\]|\\.)*)"|(\d+)(?:\s*,\s*(\d+))?)\])?')


def parse_path(path: str) -> list[tuple[str, Any]]:
    """[("sheet", "销售"), ("cell", "C12")] from '/sheet["销售"]/cell["C12"]'; [("table", 1), ("cell", (2, 3))]."""
    text = (path or "").strip()
    if not text.startswith("/"):
        raise ValueError('A path starts with /, such as /paragraph[3] or /sheet["Sheet1"]/cell["A1"].')
    segments = []
    position = 0
    for match in _SEGMENT.finditer(text):
        if match.start() != position:
            break
        name, quoted, first, second = match.groups()
        if quoted is not None:
            value: Any = quoted.replace('\\"', '"').replace("\\\\", "\\")
        elif second is not None:
            value = (int(first), int(second))
        elif first is not None:
            value = int(first)
        else:
            value = None
        segments.append((name, value))
        position = match.end()
    if position != len(text) or not segments:
        raise ValueError(f'Not a path: {path!r}. Segments look like /name, /name[3], /name[2,3] or /name["text"].')
    return segments


def _shape(segments: list[tuple[str, Any]]) -> str:
    def kind(value: Any) -> str:
        return (
            "" if value is None else "[s]" if isinstance(value, str) else "[n,n]" if isinstance(value, tuple) else "[n]"
        )

    return "".join(f"/{name}{kind(value)}" for name, value in segments)


SPREADSHEET_PATHS = ("/sheets", '/sheet["名称"]', '/sheet["名称"]/cell["C12"]', '/sheet["名称"]/range["A1:D10"]')
WRITER_PATHS = ("/paragraphs", "/paragraph[N]", "/headings", "/tables", "/table[N]", "/table[N]/cell[行,列]")
PRESENTATION_PATHS = ("/slides", "/slide[N]")


def _get_spreadsheet(document: dict[str, Any], segments, workspace) -> Result:
    from .spreadsheet_ops import list_spreadsheet_sheets, read_spreadsheet_range

    shape = _shape(segments)
    if shape == "/sheets":
        return list_spreadsheet_sheets(document["document_id"], workspace)
    if shape.startswith("/sheet[s]"):
        sheet = segments[0][1]
        if shape == "/sheet[s]":
            from .ooxml import load_workbook_guarded

            workbook = load_workbook_guarded(document["path"], read_only=True)
            try:
                if sheet not in workbook.sheetnames:
                    return _fail(
                        PATH_TARGET_NOT_FOUND, f"No worksheet {sheet!r}.", {"sheet_names": workbook.sheetnames}
                    )
                ws = workbook[sheet]
                return (
                    True,
                    {
                        "sheet": sheet,
                        "dimensions": ws.calculate_dimension(),
                        "max_row": ws.max_row,
                        "max_column": ws.max_column,
                    },
                    [],
                )
            finally:
                workbook.close()
        if shape in ("/sheet[s]/cell[s]", "/sheet[s]/range[s]"):
            return read_spreadsheet_range(document["document_id"], segments[1][1], sheet, workspace)
    return _fail(PATH_SYNTAX_INVALID, f"A spreadsheet path is one of: {', '.join(SPREADSHEET_PATHS)}.")


def _get_writer(document: dict[str, Any], segments) -> Result:
    path = document["path"]
    shape = _shape(segments)
    if shape == "/paragraphs":
        texts = docx_body_paragraphs(path)
        return True, {"count": len(texts), "paragraphs": [{"index": n, "text": t} for n, t in enumerate(texts, 1)]}, []
    if shape == "/paragraph[n]":
        texts = docx_body_paragraphs(path)
        number = segments[0][1]
        if not 1 <= number <= len(texts):
            return _fail(PATH_TARGET_NOT_FOUND, f"Paragraph {number} does not exist; the body has {len(texts)}.")
        from .writer_structure import read_writer_structure

        info = read_writer_structure(path)["paragraphs"][number - 1]
        return (
            True,
            {
                "index": number,
                "text": texts[number - 1],
                "style": info.get("style_name"),
                "heading_level": info.get("heading_level"),
            },
            [],
        )
    if shape == "/headings":
        return True, {"headings": _outline(path)}, []
    if shape == "/tables":
        tables = docx_body_tables(path)
        return (
            True,
            {
                "count": len(tables),
                "tables": [
                    {"index": n, "rows": len(t), "columns": max((len(r) for r in t), default=0)}
                    for n, t in enumerate(tables, 1)
                ],
            },
            [],
        )
    if shape in ("/table[n]", "/table[n]/cell[n,n]"):
        tables = docx_body_tables(path)
        number = segments[0][1]
        if not 1 <= number <= len(tables):
            return _fail(PATH_TARGET_NOT_FOUND, f"Table {number} does not exist; the body has {len(tables)}.")
        table = tables[number - 1]
        if shape == "/table[n]":
            return True, {"index": number, "rows": table}, []
        row, column = segments[1][1]
        if not (1 <= row <= len(table) and 1 <= column <= len(table[row - 1])):
            return _fail(PATH_TARGET_NOT_FOUND, f"Cell {row},{column} is outside table {number} ({len(table)} rows).")
        return True, {"table": number, "row": row, "column": column, "text": table[row - 1][column - 1]}, []
    return _fail(PATH_SYNTAX_INVALID, f"A writer path is one of: {', '.join(WRITER_PATHS)}.")


def _get_presentation(document: dict[str, Any], segments) -> Result:
    from .presentation_text import pptx_slide_texts, pptx_text_objects

    path = document["path"]
    shape = _shape(segments)
    slides = pptx_slide_texts(path)
    if shape == "/slides":
        return (
            True,
            {
                "count": len(slides),
                "slides": [{"index": s["slide_index"], "text": str(s["text"])[:200]} for s in slides],
            },
            [],
        )
    if shape == "/slide[n]":
        number = segments[0][1]
        if not any(s["slide_index"] == number for s in slides):
            return _fail(PATH_TARGET_NOT_FOUND, f"Slide {number} does not exist; the deck has {len(slides)}.")
        objects = [item for item in pptx_text_objects(path) if item.get("slide_index") == number]
        return True, {"index": number, "text_objects": objects}, []
    return _fail(PATH_SYNTAX_INVALID, f"A presentation path is one of: {', '.join(PRESENTATION_PATHS)}.")


def get_by_path(document_id: str, path: str, workspace: str | Path = ".") -> Result:
    """Read the one target a path names, from the file (no WPS)."""
    document, failure = _document(document_id, workspace)
    if failure:
        return failure
    try:
        segments = parse_path(path)
    except ValueError as exc:
        return _fail(PATH_SYNTAX_INVALID, str(exc))
    component = document["component"]
    if component == "spreadsheets":
        ok, data, errors = _reading(document, lambda: _get_spreadsheet(document, segments, workspace))
    elif component == "writer":
        ok, data, errors = _reading(document, lambda: _get_writer(document, segments))
    else:
        ok, data, errors = _reading(document, lambda: _get_presentation(document, segments))
    # The target path wins over a reader's own "path" key (the file), which is reported as file.
    return (
        ok,
        {**(data or {}), "document_id": document_id, "component": component, "file": document["path"], "path": path},
        errors,
    )


# ------------------------------------------------------------------------------------------ C-09 view and check
def _outline(path: str | Path) -> list[dict[str, Any]]:
    from .writer_structure import read_writer_structure

    texts = docx_body_paragraphs(path)
    outline = []
    for info in read_writer_structure(path)["paragraphs"]:
        level = info.get("heading_level")
        number = info["paragraph_index"]
        if level and number <= len(texts) and texts[number - 1].strip():
            outline.append({"level": level, "paragraph": number, "text": texts[number - 1]})
    return outline


def _docx_pictures(path: str | Path) -> int:
    from .ooxml import read_zip_part

    with ZipFile(path) as archive:
        content = read_zip_part(archive, "word/document.xml")
    return content.count(b"<wp:inline") + content.count(b"<wp:anchor")


def _view_writer(path: str) -> dict[str, Any]:
    texts = docx_body_paragraphs(path)
    tables = docx_body_tables(path)
    non_empty = [text for text in texts if text.strip()]
    return {
        "paragraphs": len(texts),
        "non_empty_paragraphs": len(non_empty),
        "characters": sum(len(text) for text in texts),
        "title": non_empty[0] if non_empty else None,
        "outline": _outline(path),
        "tables": [
            {"index": n, "rows": len(t), "columns": max((len(r) for r in t), default=0)}
            for n, t in enumerate(tables, 1)
        ],
        "pictures": _docx_pictures(path),
    }


def _view_spreadsheet(path: str) -> dict[str, Any]:
    from .ooxml import load_workbook_guarded
    from .spreadsheet_chart import sheet_charts

    workbook = load_workbook_guarded(path)
    try:
        sheets = []
        for ws in workbook.worksheets:
            formulas = sum(1 for row in ws.iter_rows() for cell in row if cell.data_type == "f")
            sheets.append(
                {
                    "name": ws.title,
                    "state": ws.sheet_state,
                    "dimensions": ws.calculate_dimension(),
                    "max_row": ws.max_row,
                    "max_column": ws.max_column,
                    "formulas": formulas,
                    "merged_ranges": len(ws.merged_cells.ranges),
                    "charts": len(sheet_charts(path, ws.title)),
                }
            )
        return {"sheets": sheets, "sheet_count": len(sheets)}
    finally:
        workbook.close()


def _view_presentation(path: str) -> dict[str, Any]:
    from .presentation_text import pptx_slide_texts

    slides = pptx_slide_texts(path)
    return {
        "slide_count": len(slides),
        "slides": [
            {"index": s["slide_index"], "characters": len(str(s["text"])), "text": str(s["text"])[:120]} for s in slides
        ],
    }


def document_view(document_id: str, workspace: str | Path = ".") -> Result:
    """A read-only summary: the writer outline and counts, the sheets, or the slides."""
    document, failure = _document(document_id, workspace)
    if failure:
        return failure
    reader = {"writer": _view_writer, "spreadsheets": _view_spreadsheet, "presentation": _view_presentation}[
        document["component"]
    ]
    ok, view, errors = _reading(document, lambda: (True, reader(document["path"]), []))
    if not ok:
        return ok, view, errors
    return True, {"document_id": document_id, "component": document["component"], "path": document["path"], **view}, []


def _issue(severity: str, code: str, where: str, message: str) -> dict[str, str]:
    return {"severity": severity, "code": code, "where": where, "message": message}


def _check_writer(path: str) -> list[dict[str, str]]:
    from .writer_merge import scan

    issues = []
    for name, count in scan(Path(path), {})["placeholders"].items():
        issues.append(
            _issue(
                "warning",
                "PLACEHOLDER_UNFILLED",
                "{{" + name + "}}",
                f"{count} unfilled placeholder(s) {{{{{name}}}}}.",
            )
        )
    previous = 0
    for heading in _outline(path):
        if heading["level"] > previous + 1:
            issues.append(
                _issue(
                    "warning",
                    "HEADING_LEVEL_SKIPPED",
                    f"paragraph {heading['paragraph']}",
                    f"Heading level {heading['level']} follows level {previous}: {heading['text'][:40]}",
                )
            )
        previous = heading["level"]
    texts = docx_body_paragraphs(path)
    run = 0
    for number, text in enumerate(texts, 1):
        run = run + 1 if not text.strip() else 0
        if run == 3:
            issues.append(
                _issue(
                    "info",
                    "EMPTY_PARAGRAPHS",
                    f"paragraph {number - 2}",
                    "Three or more empty paragraphs in a row (spacing by blank lines).",
                )
            )
    for index, table in enumerate(docx_body_tables(path), 1):
        empty = sum(1 for row in table for cell in row if not cell.strip())
        if table and empty == sum(len(row) for row in table):
            issues.append(_issue("warning", "TABLE_EMPTY", f"table {index}", "The table has no text in any cell."))
    return issues


def _check_spreadsheet(path: str) -> list[dict[str, str]]:
    from .ooxml import load_workbook_guarded

    issues = []
    formulas = load_workbook_guarded(path)
    values = load_workbook_guarded(path, data_only=True)
    try:
        for ws in formulas.worksheets:
            cached = values[ws.title]
            if ws.max_row == 1 and ws.max_column == 1 and ws["A1"].value is None:
                issues.append(_issue("info", "SHEET_EMPTY", ws.title, "The worksheet is empty."))
                continue
            for row in ws.iter_rows():
                for cell in row:
                    value = cached[cell.coordinate].value
                    where = f"{ws.title}!{cell.coordinate}"
                    if isinstance(value, str) and value in EXCEL_ERRORS:
                        issues.append(_issue("error", "FORMULA_ERROR", where, f"The cell shows {value}."))
                    if cell.data_type == "f":
                        formula = str(cell.value)
                        if re.search(r"\[[^\]]+\.xls[xmb]?\]", formula, re.IGNORECASE):
                            issues.append(
                                _issue(
                                    "warning",
                                    "EXTERNAL_LINK",
                                    where,
                                    f"The formula reads another workbook: {formula[:80]}",
                                )
                            )
                        if value is None:
                            issues.append(
                                _issue(
                                    "info",
                                    "FORMULA_NOT_CALCULATED",
                                    where,
                                    "No cached value: the workbook was saved without calculating.",
                                )
                            )
    finally:
        formulas.close()
        values.close()
    return issues


def _check_presentation(path: str) -> list[dict[str, str]]:
    from .presentation_text import pptx_slide_texts

    issues = []
    seen: dict[str, int] = {}
    for slide in pptx_slide_texts(path):
        text = str(slide["text"]).strip()
        where = f"slide {slide['slide_index']}"
        if not text:
            issues.append(
                _issue(
                    "warning",
                    "SLIDE_WITHOUT_TEXT",
                    where,
                    "The slide has no text (a picture-only slide, or a forgotten one).",
                )
            )
        elif text in seen:
            issues.append(_issue("info", "SLIDE_DUPLICATE_TEXT", where, f"Same text as slide {seen[text]}."))
        else:
            seen[text] = slide["slide_index"]
        if "{{" in text and "}}" in text:
            issues.append(
                _issue("warning", "PLACEHOLDER_UNFILLED", where, "The slide has an unfilled {{placeholder}}.")
            )
    return issues


def document_check(document_id: str, workspace: str | Path = ".", limit: int = 200) -> Result:
    """A read-only list of problems to look at before handing the document over; ok even when it finds some."""
    document, failure = _document(document_id, workspace)
    if failure:
        return failure
    checker = {"writer": _check_writer, "spreadsheets": _check_spreadsheet, "presentation": _check_presentation}[
        document["component"]
    ]
    ok, found, errors = _reading(document, lambda: (True, {"issues": checker(document["path"])}, []))
    if not ok:
        return ok, found, errors
    issues = found["issues"]
    counts = {
        severity: sum(1 for issue in issues if issue["severity"] == severity)
        for severity in ("error", "warning", "info")
    }
    return (
        True,
        {
            "document_id": document_id,
            "component": document["component"],
            "path": document["path"],
            "counts": counts,
            "issues": issues[:limit],
            "truncated": len(issues) > limit,
        },
        [],
    )


def load_commands(commands_json: str | None, commands_file: str | None) -> tuple[Any, str | None]:
    try:
        if commands_file is not None:
            return json.loads(Path(commands_file).read_text(encoding="utf-8-sig")), None
        return json.loads(commands_json or ""), None
    except (OSError, ValueError) as exc:
        return None, f"commands are not readable JSON: {exc}"
