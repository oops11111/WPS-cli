from __future__ import annotations

import json
import hashlib
from pathlib import Path
import subprocess
import tempfile
from typing import Any
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from .backups import create_backup, guarded_com_mutation, verify_post_com_source
from .capabilities import powershell_executable, probe_wps_capabilities
from .document_text import (
    count_text_in_docx,
    count_text_in_docx_paragraph,
    docx_body_paragraphs,
    docx_body_paragraph_target,
    docx_body_story_paragraphs,
    docx_body_tables,
    docx_document_paragraphs,
    docx_body_table_topology,
    docx_body_link_field_semantics,
    docx_body_drawing_semantics,
    docx_bookmark_overlaps_link_or_field,
    docx_bookmark_precedes_character_anchor,
    docx_table_cell_text,
)
from .errors import COM_BACKEND_UNAVAILABLE, COM_OPERATION_FAILED, INPUT_FILE_NOT_FOUND
from .mutation_lock import coordinated_mutation
from .operations import record_operation, replay_operation
from .sessions import get_document
from .writer_structure import W, read_body_bookmark_text, read_supported_bookmark_text, read_writer_structure
from .wps_script_snippets import QUIT_IF_IDLE


BODY_PARTS = ("word/document.xml",)


def _body_ends_with_table(path: Path) -> bool:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    body = root.find(f"{W}body")
    content = [child for child in body if child.tag != f"{W}sectPr"] if body is not None else []
    return bool(content and content[-1].tag == f"{W}tbl")


def _run_writer_replace_com(
    path: str,
    find_text: str,
    replace_text: str,
    paragraph_index: int | None = None,
) -> dict[str, Any]:
    capabilities = probe_wps_capabilities()
    selected_prog_id = capabilities["components"]["writer"]["selected_prog_id"]
    if not selected_prog_id:
        return {
            "ok": False,
            "errors": [
                {
                    "code": COM_BACKEND_UNAVAILABLE,
                    "message": "No registered WPS ProgID detected for writer.",
                }
            ],
            "data": {"capabilities": capabilities},
        }

    params = {
        "prog_id": selected_prog_id,
        "path": str(Path(path).resolve()),
        "find_text": find_text,
        "replace_text": replace_text,
        "paragraph_index": paragraph_index,
        "paragraph_target": docx_body_paragraph_target(path, paragraph_index) if paragraph_index is not None else None,
    }
    params_json = json.dumps(params)
    script = f"""
$ErrorActionPreference = 'Stop'
$params = @'
{params_json}
'@ | ConvertFrom-Json
$app = $null
$document = $null
try {{
  $app = New-Object -ComObject $params.prog_id
  try {{ $app.Visible = $false }} catch {{ }}
  $document = $app.Documents.Open($params.path)
  if ($null -ne $params.paragraph_index) {{
    $paragraphCount = $document.Paragraphs.Count
    $target = $params.paragraph_target
    $bodyParagraphs = @()
    for ($i = 1; $i -le $paragraphCount; $i++) {{
      $candidate = $document.Paragraphs.Item($i).Range
      if (-not $candidate.Information(12)) {{ $bodyParagraphs += $candidate }}
    }}
    if ($bodyParagraphs.Count -ne [int]$target.body_paragraph_count) {{
      throw "WPS body paragraph collection differs from the offline body."
    }}
    $range = $bodyParagraphs[[int]$params.paragraph_index - 1]
    $actualText = [string]$range.Text
    $actualText = $actualText.TrimEnd([char[]]@([char]13, [char]7)).Replace([string][char]11, "`n")
    if ($actualText -cne [string]$target.expected_text) {{
      throw "WPS paragraph text differs from the offline target."
    }}
  }} else {{
    $range = $document.Content
  }}
  $replaceCount = 0
  $rangeStart = $range.Start
  $rangeEnd = $range.End
  while ($true) {{
    $find = $range.Find
    [void]$find.ClearFormatting()
    $find.Forward = $true
    $find.Wrap = 0
    $find.Format = $false
    $find.MatchCase = $true
    $find.MatchWholeWord = $false
    $find.MatchWildcards = $false
    $find.MatchSoundsLike = $false
    $find.MatchAllWordForms = $false
    $matched = $find.Execute(([string]$params.find_text).Replace('^', '^^'))
    if (-not $matched) {{ break }}
    if ($range.Start -lt $rangeStart -or $range.End -gt $rangeEnd -or $range.End -le $range.Start) {{
      throw "Find returned a match outside the selected range."
    }}
    if ([string]$range.Text -cne [string]$params.find_text) {{
      throw "Find returned a non-literal match."
    }}
    $oldLength = $range.End - $range.Start
    $range.Text = $params.replace_text
    $rangeEnd += ($range.End - $range.Start) - $oldLength
    $replaceCount += 1
    $start = $range.End
    if ($start -ge $rangeEnd) {{ break }}
    $range = $document.Range($start, $rangeEnd)
  }}
  $document.Save()

  [pscustomobject]@{{
    ok = $true
    backend = 'powershell-com'
    component = 'writer'
    prog_id = $params.prog_id
    path = $params.path
    find_text = $params.find_text
    replace_text = $params.replace_text
    paragraph_index = $params.paragraph_index
    replace_count = $replaceCount
  }} | ConvertTo-Json -Depth 5
}} catch {{
  [pscustomobject]@{{
    ok = $false
    backend = 'powershell-com'
    component = 'writer'
    prog_id = $params.prog_id
    error_type = $_.Exception.GetType().FullName
    error_message = $_.Exception.Message
    position = $_.InvocationInfo.PositionMessage
  }} | ConvertTo-Json -Depth 5
  exit 2
}} finally {{
  if ($document -ne $null) {{
    try {{ $document.Close($false) }} catch {{ }}
    try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) }} catch {{ }}
  }}
  if ($app -ne $null) {{
    try {{ {QUIT_IF_IDLE} }} catch {{ }}
    try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) }} catch {{ }}
  }}
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}}
"""
    script_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".ps1",
            delete=False,
            encoding="utf-8-sig",
        ) as script_file:
            script_file.write(script)
            script_path = script_file.name
        completed = subprocess.run(
            [
                powershell_executable(),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
            ],
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=120,
        )
    finally:
        if script_path:
            try:
                Path(script_path).unlink(missing_ok=True)
            except OSError:
                pass

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = None

    if completed.returncode != 0 or not isinstance(payload, dict):
        return {
            "ok": False,
            "errors": [
                {
                    "code": COM_OPERATION_FAILED,
                    "message": (
                        payload.get("error_message")
                        if isinstance(payload, dict)
                        else (completed.stderr or completed.stdout).strip()
                    ),
                }
            ],
            "data": {"diagnostic": payload, "backend": "powershell-com"},
        }
    return {"ok": True, "errors": [], "data": payload}


def _run_writer_bookmark_fill_com(path: str, name: str, value: str, expected_text: str) -> dict[str, Any]:
    capabilities = probe_wps_capabilities()
    prog_id = capabilities["components"]["writer"]["selected_prog_id"]
    if not prog_id:
        return {"ok": False, "errors": [{"code": COM_BACKEND_UNAVAILABLE, "message": "No registered WPS ProgID detected for writer."}], "data": {"capabilities": capabilities}}
    params_json = json.dumps({"prog_id": prog_id, "path": str(Path(path).resolve()), "name": name, "value": value, "expected_text": expected_text})
    script = f"""
$ErrorActionPreference = 'Stop'
$params = @'
{params_json}
'@ | ConvertFrom-Json
$app = $null
$document = $null
try {{
  $app = New-Object -ComObject $params.prog_id
  try {{ $app.Visible = $false }} catch {{ }}
  $document = $app.Documents.Open($params.path)
  if (-not $document.Bookmarks.Exists($params.name)) {{ throw "Bookmark not found in WPS: $($params.name)" }}
  $bookmark = $document.Bookmarks.Item($params.name)
  $range = $bookmark.Range
  if ([string]$range.Text -cne [string]$params.expected_text) {{ throw "WPS bookmark text differs from offline target." }}
  $range.Text = [string]$params.value
  $newRange = $document.Range($range.Start, $range.End)
  if ($document.Bookmarks.Exists($params.name)) {{ $document.Bookmarks.Item($params.name).Delete() }}
  [void]$document.Bookmarks.Add($params.name, $newRange)
  $document.Save()
  $actual = [string]$document.Bookmarks.Item($params.name).Range.Text
  if ($actual -cne [string]$params.value) {{ throw "WPS bookmark read-back differs from requested text." }}
  [pscustomobject]@{{ ok = $true; backend = 'powershell-com'; prog_id = $params.prog_id; bookmark_name = $params.name; value_length = $actual.Length }} | ConvertTo-Json -Depth 5
}} catch {{
  [pscustomobject]@{{ ok = $false; backend = 'powershell-com'; error_type = $_.Exception.GetType().FullName; error_message = $_.Exception.Message; position = $_.InvocationInfo.PositionMessage }} | ConvertTo-Json -Depth 5
  exit 2
}} finally {{
  if ($document -ne $null) {{ try {{ $document.Close($false) }} catch {{ }}; try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) }} catch {{ }} }}
  if ($app -ne $null) {{ try {{ {QUIT_IF_IDLE} }} catch {{ }}; try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) }} catch {{ }} }}
  [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}}
"""
    script_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8-sig") as script_file:
            script_file.write(script)
            script_path = script_file.name
        completed = subprocess.run(
            [powershell_executable(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            check=False, capture_output=True, encoding="utf-8", errors="replace", text=True, timeout=120,
        )
    finally:
        if script_path:
            Path(script_path).unlink(missing_ok=True)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = None
    if completed.returncode != 0 or not isinstance(payload, dict):
        return {"ok": False, "errors": [{"code": COM_OPERATION_FAILED, "message": payload.get("error_message") if isinstance(payload, dict) else (completed.stderr or completed.stdout).strip()}], "data": {"diagnostic": payload, "backend": "powershell-com"}}
    return {"ok": True, "errors": [], "data": payload}


@coordinated_mutation
def writer_fill_bookmark(
    document_id: str, bookmark_name: str, value: str, request_id: str,
    dry_run: bool = False, workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replacement_digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    replay = replay_operation(
        request_id, "writer-fill-bookmark",
        {"document_id": document_id, "bookmark_name": bookmark_name, "replacement_digest": replacement_digest, "dry_run": dry_run},
        workspace,
    )
    if replay is not None:
        return replay
    if not bookmark_name or bookmark_name.startswith("_"):
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "bookmark_name must be a non-reserved, non-empty name."}], False
    document = get_document(document_id, workspace)
    if not document:
        return False, {}, [{"code": "DOCUMENT_NOT_FOUND", "message": f"Document not registered: {document_id}"}], False
    if document["component"] != "writer":
        return False, {"document": document}, [{"code": "UNSUPPORTED_COMPONENT", "message": "writer-fill-bookmark requires a Writer document."}], False
    path = Path(document["path"])
    if not path.exists():
        return False, {"document": document}, [{"code": INPUT_FILE_NOT_FOUND, "message": f"Input file not found: {path}"}], False
    structure = read_writer_structure(path)
    named = [item for item in structure["bookmarks"] if item["name"] == bookmark_name]
    if not named:
        return False, {"document_id": document_id, "bookmark_name": bookmark_name}, [{"code": "BOOKMARK_NOT_FOUND", "message": f"Bookmark not found: {bookmark_name}"}], False
    if len(named) != 1:
        return False, {"document_id": document_id, "bookmark_name": bookmark_name}, [{"code": "BOOKMARK_AMBIGUOUS", "message": f"Bookmark name is not unique: {bookmark_name}"}], False
    bookmark = named[0]
    body_scope = bookmark["body_paragraph_range_supported"]
    start_location, end_location = bookmark.get("start") or {}, bookmark.get("end") or {}
    table_location_keys = ("table_index", "row", "column", "story_paragraph_index")
    table_scope = (
        not body_scope and bookmark["text_range_supported"]
        and bookmark["part"] == "word/document.xml"
        and start_location.get("scope") == end_location.get("scope") == "table"
        and all(start_location.get(key) is not None and start_location.get(key) == end_location.get(key)
                for key in table_location_keys)
    )
    if not body_scope and not table_scope:
        return False, {"document_id": document_id, "bookmark": bookmark}, [{"code": "BOOKMARK_SCOPE_UNSUPPORTED", "message": "Only paired bookmarks within one direct body paragraph or direct-body table cell are supported."}], False
    if table_scope and (len(value) > 4096 or "\r" in value or "\n" in value):
        return False, {"document_id": document_id, "bookmark": bookmark}, [{"code": "INVALID_ARGUMENT", "message": "Table-cell bookmark value must be at most 4096 characters on one line."}], False
    _, current_text = (
        read_body_bookmark_text(path, bookmark_name) if body_scope
        else read_supported_bookmark_text(path, bookmark_name)
    )
    if current_text is None:
        return False, {"document_id": document_id, "bookmark": bookmark}, [{"code": "BOOKMARK_SCOPE_UNSUPPORTED", "message": "Bookmark text range could not be resolved."}], False
    paragraph_index = int(start_location["paragraph_index"] if body_scope else start_location["story_paragraph_index"])
    paragraphs = docx_body_paragraphs(path) if body_scope else docx_document_paragraphs(path)
    tables_before = docx_body_tables(path)
    table_topology_before = docx_body_table_topology(path) if table_scope else None
    semantic_neighbors_before = docx_body_link_field_semantics(path) if table_scope else None
    if table_scope and (
        semantic_neighbors_before["unresolved_links"]
        or semantic_neighbors_before["unresolved_fields"]
    ):
        return False, {"document_id": document_id, "bookmark": bookmark}, [{"code": "BOOKMARK_SCOPE_UNSUPPORTED", "message": "Table-cell bookmark writes require well-formed, resolvable body links and fields."}], False
    drawings_before = docx_body_drawing_semantics(path) if table_scope else None
    if table_scope and drawings_before["unresolved_drawings"]:
        return False, {"document_id": document_id, "bookmark": bookmark}, [{
            "code": "BOOKMARK_SCOPE_UNSUPPORTED",
            "message": "Table-cell bookmark writes require supported body drawing semantics.",
            "details": drawings_before["unresolved_drawings"],
        }], False
    trailing_table_before = _body_ends_with_table(path)
    old_paragraph = paragraphs[paragraph_index - 1]
    start_offset = int(bookmark["start"]["text_offset"])
    end_offset = int(bookmark["end"]["text_offset"])
    if table_scope and docx_bookmark_overlaps_link_or_field(
        path, bookmark_name, paragraph_index, start_offset, end_offset,
    ):
        return False, {"document_id": document_id, "bookmark": bookmark}, [{"code": "BOOKMARK_SCOPE_UNSUPPORTED", "message": "Table-cell bookmark range may not overlap a hyperlink or field."}], False
    if table_scope and docx_bookmark_precedes_character_anchor(path, bookmark_name, paragraph_index):
        return False, {"document_id": document_id, "bookmark": bookmark}, [{"code": "BOOKMARK_SCOPE_UNSUPPORTED", "message": "Table-cell bookmark writes may not precede a character-relative drawing anchor in the same paragraph."}], False
    expected_paragraph = old_paragraph[:start_offset] + value + old_paragraph[end_offset:]
    preview = {
        "document_id": document_id, "component": "writer", "path": str(path),
        "bookmark_name": bookmark_name, "scope": "body_paragraph" if body_scope else "table_cell",
        "replacement_digest": replacement_digest,
        "paragraph_index": paragraph_index, "current_text_length": len(current_text),
        "replacement_text_length": len(value), "dry_run": dry_run,
    }
    if table_scope:
        preview["table_index"] = start_location["table_index"]
        preview["row"] = start_location["row"]
        preview["column"] = start_location["column"]
    if dry_run:
        return True, preview, [], False
    backup_ok, backup_result, backup_errors, backup_replayed = create_backup(
        document_id=document_id, request_id=f"{request_id}:backup", workspace=workspace,
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup_result}, backup_errors, False
    mutation = guarded_com_mutation(
        path, backup_result,
        lambda: _run_writer_bookmark_fill_com(str(path), bookmark_name, value, current_text),
    )
    if not mutation["ok"]:
        return False, {"preview": preview, "backup": backup_result, "mutation": mutation["data"]}, mutation["errors"], False
    after_structure = read_writer_structure(path)
    after_named = [item for item in after_structure["bookmarks"] if item["name"] == bookmark_name]
    after_text = (
        (read_body_bookmark_text(path, bookmark_name) if body_scope
         else read_supported_bookmark_text(path, bookmark_name))[1]
        if len(after_named) == 1 else None
    )
    after_paragraphs = docx_body_paragraphs(path) if body_scope else docx_document_paragraphs(path)
    expected_paragraphs = list(paragraphs)
    expected_paragraphs[paragraph_index - 1] = expected_paragraph
    body_tail_normalized = trailing_table_before and after_paragraphs == [*expected_paragraphs, ""]
    after_location = (after_named[0].get("start") or {}) if len(after_named) == 1 else {}
    table_location_preserved = (
        not table_scope or (
            all(after_location.get(key) == start_location[key] for key in table_location_keys)
            and docx_body_table_topology(path) == table_topology_before
            and docx_body_link_field_semantics(path) == semantic_neighbors_before
            and docx_body_drawing_semantics(path) == drawings_before
        )
    )
    readback_passed = (
        len(after_named) == 1 and (
            after_named[0]["body_paragraph_range_supported"] if body_scope
            else after_named[0]["text_range_supported"] and after_location.get("scope") == "table"
        )
        and after_text == value
        and (after_paragraphs == expected_paragraphs or body_tail_normalized)
        and (docx_body_tables(path) == tables_before if body_scope else table_location_preserved)
    )
    result = {
        **preview, "dry_run": False, "backup": backup_result,
        "backup_replayed": backup_replayed, "replace_backend": mutation["data"].get("backend"),
        "readback_passed": readback_passed,
        "body_tail_normalized": body_tail_normalized,
    }
    post_error = verify_post_com_source(path, mutation)
    if post_error is not None:
        return False, result, [post_error], False
    if not readback_passed:
        return False, result, [{"code": "VALIDATION_FAILED", "message": "Bookmark fill read-back did not match the expected range and paragraph."}], False
    record_operation(request_id, "writer-fill-bookmark", result, workspace)
    return True, result, [], False


def _run_writer_table_write_com(
    path: str,
    table_index: int,
    row: int,
    column: int,
    text: str,
) -> dict[str, Any]:
    capabilities = probe_wps_capabilities()
    selected_prog_id = capabilities["components"]["writer"]["selected_prog_id"]
    if not selected_prog_id:
        return {
            "ok": False,
            "errors": [
                {
                    "code": COM_BACKEND_UNAVAILABLE,
                    "message": "No registered WPS ProgID detected for writer.",
                }
            ],
            "data": {"capabilities": capabilities},
        }

    params = {
        "prog_id": selected_prog_id,
        "path": str(Path(path).resolve()),
        "table_index": table_index,
        "row": row,
        "column": column,
        "text": text,
    }
    params_json = json.dumps(params)
    script = f"""
$ErrorActionPreference = 'Stop'
$params = @'
{params_json}
'@ | ConvertFrom-Json
$app = $null
$document = $null
try {{
  $app = New-Object -ComObject $params.prog_id
  try {{ $app.Visible = $false }} catch {{ }}
  $document = $app.Documents.Open($params.path)
  $tableCount = $document.Tables.Count
  if ([int]$params.table_index -lt 1 -or [int]$params.table_index -gt $tableCount) {{
    throw "Table index out of range: $($params.table_index)"
  }}
  $table = $document.Tables.Item([int]$params.table_index)
  $cell = $table.Cell([int]$params.row, [int]$params.column)
  $beforeText = $cell.Range.Text
  $cell.Range.Text = [string]$params.text
  $document.Save()
  $afterText = $table.Cell([int]$params.row, [int]$params.column).Range.Text

  [pscustomobject]@{{
    ok = $true
    backend = 'powershell-com'
    component = 'writer'
    prog_id = $params.prog_id
    path = $params.path
    table_index = [int]$params.table_index
    row = [int]$params.row
    column = [int]$params.column
    table_count = $tableCount
    previous_text = $beforeText.TrimEnd([char]13, [char]7)
    read_back_text = $afterText.TrimEnd([char]13, [char]7)
  }} | ConvertTo-Json -Depth 5
}} catch {{
  [pscustomobject]@{{
    ok = $false
    backend = 'powershell-com'
    component = 'writer'
    prog_id = $params.prog_id
    error_type = $_.Exception.GetType().FullName
    error_message = $_.Exception.Message
    position = $_.InvocationInfo.PositionMessage
  }} | ConvertTo-Json -Depth 5
  exit 2
}} finally {{
  if ($document -ne $null) {{
    try {{ $document.Close($false) }} catch {{ }}
    try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) }} catch {{ }}
  }}
  if ($app -ne $null) {{
    try {{ {QUIT_IF_IDLE} }} catch {{ }}
    try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) }} catch {{ }}
  }}
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}}
"""
    script_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".ps1",
            delete=False,
            encoding="utf-8-sig",
        ) as script_file:
            script_file.write(script)
            script_path = script_file.name
        completed = subprocess.run(
            [
                powershell_executable(),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
            ],
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=120,
        )
    finally:
        if script_path:
            try:
                Path(script_path).unlink(missing_ok=True)
            except OSError:
                pass

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = None

    if completed.returncode != 0 or not isinstance(payload, dict):
        return {
            "ok": False,
            "errors": [
                {
                    "code": COM_OPERATION_FAILED,
                    "message": (
                        payload.get("error_message")
                        if isinstance(payload, dict)
                        else (completed.stderr or completed.stdout).strip()
                    ),
                }
            ],
            "data": {"diagnostic": payload, "backend": "powershell-com"},
        }
    return {"ok": True, "errors": [], "data": payload}


@coordinated_mutation
def writer_replace(
    document_id: str,
    find_text: str,
    replace_text: str,
    request_id: str,
    dry_run: bool = False,
    paragraph_index: int | None = None,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replay = replay_operation(
        request_id, "writer-replace",
        {"document_id": document_id, "find_text": find_text, "replace_text": replace_text, "paragraph_index": paragraph_index, "dry_run": dry_run},
        workspace,
    )
    if replay is not None:
        return replay

    if not find_text:
        return (
            False,
            {},
            [{"code": "INVALID_ARGUMENT", "message": "find_text must not be empty."}],
            False,
        )
    if paragraph_index is not None and paragraph_index < 1:
        return (
            False,
            {},
            [{"code": "INVALID_ARGUMENT", "message": "paragraph_index must be 1 or greater."}],
            False,
        )

    document = get_document(document_id, workspace)
    if not document:
        return (
            False,
            {},
            [{"code": "DOCUMENT_NOT_FOUND", "message": f"Document not registered: {document_id}"}],
            False,
        )
    if document["component"] != "writer":
        return (
            False,
            {"document": document},
            [{"code": "UNSUPPORTED_COMPONENT", "message": "writer-replace requires a writer document."}],
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

    paragraph_count = len(docx_body_paragraphs(path))
    if paragraph_index is not None and paragraph_index > paragraph_count:
        return (
            False,
            {
                "document_id": document_id,
                "component": "writer",
                "path": str(path),
                "scope": "paragraph",
                "paragraph_index": paragraph_index,
                "paragraph_count": paragraph_count,
            },
            [{"code": "PARAGRAPH_NOT_FOUND", "message": f"Paragraph index out of range: {paragraph_index}"}],
            False,
        )

    if paragraph_index is None:
        expected_texts = [
            text.replace(find_text, replace_text)
            for text in docx_body_story_paragraphs(path)
        ]
        before_count = count_text_in_docx(path, find_text, parts=BODY_PARTS)
        scope = "body"
    else:
        expected_texts = list(docx_body_paragraphs(path))
        expected_texts[paragraph_index - 1] = expected_texts[paragraph_index - 1].replace(find_text, replace_text)
        before_count = count_text_in_docx_paragraph(path, paragraph_index, find_text)
        scope = "paragraph"
    preview = {
        "document_id": document_id,
        "component": "writer",
        "path": str(path),
        "find_text": find_text,
        "replace_text": replace_text,
        "scope": scope,
        "paragraph_index": paragraph_index,
        "paragraph_count": paragraph_count,
        "matches": before_count,
        "dry_run": dry_run,
    }
    if dry_run:
        return True, preview, [], False
    if before_count == 0:
        return (
            False,
            preview,
            [{"code": "TEXT_NOT_FOUND", "message": "No matching text found before replace."}],
            False,
        )

    backup_ok, backup_result, backup_errors, backup_replayed = create_backup(
        document_id=document_id,
        request_id=f"{request_id}:backup",
        dry_run=False,
        workspace=workspace,
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup_result}, backup_errors, False

    replace_result = guarded_com_mutation(
        path, backup_result,
        lambda: _run_writer_replace_com(
            str(path), find_text, replace_text, paragraph_index=paragraph_index,
        ),
    )
    if not replace_result["ok"]:
        return False, {"preview": preview, "backup": backup_result, "replace": replace_result["data"]}, replace_result["errors"], False

    actual_texts = (
        docx_body_story_paragraphs(path)
        if paragraph_index is None else docx_body_paragraphs(path)
    )
    changed_paragraphs = [
        index for index, (expected, actual) in enumerate(zip(expected_texts, actual_texts), 1)
        if expected != actual
    ]
    if len(expected_texts) != len(actual_texts):
        changed_paragraphs.extend(range(min(len(expected_texts), len(actual_texts)) + 1, max(len(expected_texts), len(actual_texts)) + 1))
    remaining_find_count = (
        count_text_in_docx(path, find_text, parts=BODY_PARTS)
        if paragraph_index is None
        else count_text_in_docx_paragraph(path, paragraph_index, find_text)
    )
    replaced_count = int(replace_result["data"].get("replace_count", 0))
    old_text_allowed = bool(replace_text and find_text in replace_text)
    validation_passed = (
        replaced_count == before_count
        and actual_texts == expected_texts
        and (old_text_allowed or remaining_find_count == 0)
    )
    result = {
        **preview,
        "dry_run": False,
        "backup": backup_result,
        "backup_replayed": backup_replayed,
        "replace_backend": replace_result["data"].get("backend"),
        "backend_replace_count": replace_result["data"].get("replace_count"),
        "matches_before": before_count,
        "remaining_find_count": remaining_find_count,
        "replace_count": replaced_count,
        "expected_replace_count": before_count,
        "readback_matches_expected": actual_texts == expected_texts,
        "changed_paragraph_indices": changed_paragraphs,
        "old_text_allowed_after_replace": old_text_allowed,
        "validation_passed": validation_passed,
    }
    post_error = verify_post_com_source(path, replace_result)
    if post_error is not None:
        return False, result, [post_error], False
    if not validation_passed:
        return (
            False,
            result,
            [{"code": "VALIDATION_FAILED", "message": "Replacement validation did not pass."}],
            False,
        )

    record_operation(request_id, "writer-replace", result, workspace)
    return True, result, [], False


@coordinated_mutation
def writer_table_write(
    document_id: str,
    table_index: int,
    row: int,
    column: int,
    text: str,
    request_id: str,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replay = replay_operation(
        request_id, "writer-table-write",
        {"document_id": document_id, "table_index": table_index, "row": row, "column": column, "replacement_text": text, "dry_run": dry_run},
        workspace,
    )
    if replay is not None:
        return replay

    if table_index < 1 or row < 1 or column < 1:
        return (
            False,
            {},
            [{"code": "INVALID_ARGUMENT", "message": "table_index, row, and column must be 1 or greater."}],
            False,
        )

    document = get_document(document_id, workspace)
    if not document:
        return (
            False,
            {},
            [{"code": "DOCUMENT_NOT_FOUND", "message": f"Document not registered: {document_id}"}],
            False,
        )
    if document["component"] != "writer":
        return (
            False,
            {"document": document},
            [{"code": "UNSUPPORTED_COMPONENT", "message": "writer-table-write requires a writer document."}],
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

    tables = docx_body_tables(path)
    table_count = len(tables)
    if table_index > table_count:
        return (
            False,
            {
                "document_id": document_id,
                "component": "writer",
                "path": str(path),
                "table_index": table_index,
                "table_count": table_count,
            },
            [{"code": "TABLE_NOT_FOUND", "message": f"Table index out of range: {table_index}"}],
            False,
        )
    current_text = docx_table_cell_text(path, table_index, row, column)
    if current_text is None:
        selected_table = tables[table_index - 1]
        return (
            False,
            {
                "document_id": document_id,
                "component": "writer",
                "path": str(path),
                "table_index": table_index,
                "table_count": table_count,
                "row": row,
                "column": column,
                "row_count": len(selected_table),
                "column_count": max((len(item) for item in selected_table), default=0),
            },
            [{"code": "CELL_NOT_FOUND", "message": f"Cell out of range: row {row}, column {column}"}],
            False,
        )

    preview = {
        "document_id": document_id,
        "component": "writer",
        "path": str(path),
        "table_index": table_index,
        "table_count": table_count,
        "row": row,
        "column": column,
        "current_text": current_text,
        "replacement_text": text,
        "would_modify": current_text != text,
        "dry_run": dry_run,
    }
    if dry_run:
        return True, preview, [], False

    backup_ok, backup_result, backup_errors, backup_replayed = create_backup(
        document_id=document_id,
        request_id=f"{request_id}:backup",
        dry_run=False,
        workspace=workspace,
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup_result}, backup_errors, False

    write_result = guarded_com_mutation(
        path, backup_result,
        lambda: _run_writer_table_write_com(
            str(path), table_index=table_index, row=row, column=column, text=text,
        ),
    )
    if not write_result["ok"]:
        return False, {"preview": preview, "backup": backup_result, "write": write_result["data"]}, write_result["errors"], False

    final_tables = docx_body_tables(path)
    read_back_text = docx_table_cell_text(path, table_index, row, column)
    final_table_count = len(final_tables)
    table_count_preserved = final_table_count == table_count
    validation_passed = read_back_text == text
    result = {
        **preview,
        "dry_run": False,
        "backup": backup_result,
        "backup_replayed": backup_replayed,
        "write_backend": write_result["data"].get("backend"),
        "backend_read_back_text": write_result["data"].get("read_back_text"),
        "read_back_text": read_back_text,
        "final_table_count": final_table_count,
        "table_count_preserved": table_count_preserved,
        "validation_passed": validation_passed,
    }
    post_error = verify_post_com_source(path, write_result)
    if post_error is not None:
        return False, result, [post_error], False
    if not validation_passed:
        return (
            False,
            result,
            [{"code": "VALIDATION_FAILED", "message": "Writer table cell validation did not pass."}],
            False,
        )

    record_operation(request_id, "writer-table-write", result, workspace)
    return True, result, [], False
