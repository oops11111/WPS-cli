from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .backups import create_backup, guarded_com_mutation, verify_post_com_source
from .capabilities import WPS_COMPONENTS
from .errors import COM_OPERATION_FAILED, INPUT_FILE_NOT_FOUND
from .mutation_lock import coordinated_mutation
from .operations import record_operation, replay_operation
from .powershell_runner import run_powershell_script
from .sessions import file_identity, get_document, register_document, stable_document_id
from .wps_script_snippets import ATTACH_RUNNING_INSTANCE


MAX_SELECTION_CHARS = 4096
HTML_EXPORT_SUFFIXES = {".html", ".htm"}

_COMPONENT_COLLECTIONS = {
    "writer": ("Documents", "ActiveDocument"),
    "spreadsheets": ("Workbooks", "ActiveWorkbook"),
    "presentation": ("Presentations", "ActivePresentation"),
}

NO_RUNNING_WPS_INSTANCE = "NO_RUNNING_WPS_INSTANCE"
DOCUMENT_NOT_OPEN = "DOCUMENT_NOT_OPEN"
DOCUMENT_HAS_UNSAVED_CHANGES = "DOCUMENT_HAS_UNSAVED_CHANGES"
SELECTION_UNAVAILABLE = "SELECTION_UNAVAILABLE"
SELECTION_EMPTY = "SELECTION_EMPTY"
SELECTION_MISMATCH = "SELECTION_MISMATCH"
SELECTION_TOO_LARGE = "SELECTION_TOO_LARGE"
SELECTION_SPANS_STRUCTURE = "SELECTION_SPANS_STRUCTURE"
OUTPUT_EXISTS = "OUTPUT_EXISTS"
EXPORT_OUTPUT_MISSING = "EXPORT_OUTPUT_MISSING"

_SCRIPT_HEAD = """
$ErrorActionPreference = 'Stop'
$params = @'
__PARAMS_JSON__
'@ | ConvertFrom-Json
"""

_ATTACHED_WRITER_WRAPPER = (
    _SCRIPT_HEAD
    + ATTACH_RUNNING_INSTANCE
    + """
$app = $null
$doc = $null
try {
  $app = Get-RunningWpsApp @($params.prog_ids)
  if ($null -eq $app) {
    [pscustomobject]@{ ok = $true; status = 'no_instance' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $doc = Find-OpenWriterDocument $app $params.path
  if ($null -eq $doc) {
    [pscustomobject]@{ ok = $true; status = 'not_open' } | ConvertTo-Json -Depth 5
    exit 0
  }
  __ACTION_BODY__
} catch {
  [pscustomobject]@{
    ok = $false
    backend = 'powershell-com'
    error_type = $_.Exception.GetType().FullName
    error_message = $_.Exception.Message
    position = $_.InvocationInfo.PositionMessage
  } | ConvertTo-Json -Depth 5
  exit 2
} finally {
  if ($doc -ne $null) { try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) } catch { } }
  if ($app -ne $null) { try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) } catch { } }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}
"""
)

_LIST_SCRIPT = (
    _SCRIPT_HEAD
    + ATTACH_RUNNING_INSTANCE
    + """
function Get-Safe([scriptblock]$block) { try { return & $block } catch { return $null } }
$instances = @()
foreach ($spec in $params.components) {
  $app = Get-RunningWpsApp @($spec.prog_ids)
  if ($null -eq $app) { continue }
  try {
    $collection = $app.($spec.collection)
    $activeFullName = Get-Safe { [string]$app.($spec.active).FullName }
    $documents = @()
    $count = [int]$collection.Count
    for ($i = 1; $i -le $count; $i++) {
      $item = $collection.Item($i)
      $fullName = Get-Safe { [string]$item.FullName }
      $documents += [pscustomobject]@{
        name = Get-Safe { [string]$item.Name }
        full_name = $fullName
        saved = Get-Safe { [bool]$item.Saved }
        read_only = Get-Safe { [bool]$item.ReadOnly }
        active = [bool]($null -ne $activeFullName -and $fullName -eq $activeFullName)
      }
    }
    $instances += [pscustomobject]@{
      component = $spec.component
      version = Get-Safe { [string]$app.Version }
      documents = $documents
    }
  } finally {
    try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) } catch { }
  }
}
[pscustomobject]@{ ok = $true; backend = 'powershell-com'; instances = $instances } | ConvertTo-Json -Depth 6
"""
)

_SELECTION_READ_BODY = """
  $window = $doc.ActiveWindow
  if ($null -eq $window) {
    [pscustomobject]@{ ok = $true; status = 'no_window' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $sel = $window.Selection
  $start = [int]$sel.Start
  $end = [int]$sel.End
  $text = [string]$sel.Text
  $paragraphIndex = $null
  try {
    $firstParagraph = $sel.Paragraphs.Item(1).Range.Start
    if ([int]$firstParagraph -le 0) { $paragraphIndex = 1 }
    else { $paragraphIndex = [int]$doc.Range(0, [int]$firstParagraph).Paragraphs.Count + 1 }
  } catch { }
  $pageNumber = $null
  try { $pageNumber = [int]$sel.Information(3) } catch { }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'writer'
    name = [string]$doc.Name
    saved = [bool]$doc.Saved
    start = $start
    end = $end
    selection_text = $text
    paragraph_index = $paragraphIndex
    page_number = $pageNumber
  } | ConvertTo-Json -Depth 5
"""

_SELECTION_REPLACE_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $start = [int]$params.expected_start
  $end = [int]$params.expected_end
  $range = $doc.Range($start, $end)
  if (([string]$range.Text) -cne [string]$params.expected_text) {
    [pscustomobject]@{ ok = $true; status = 'selection_changed'; current_text = [string]$range.Text } | ConvertTo-Json -Depth 5
    exit 0
  }
  $replacement = [string]$params.text
  $range.Text = $replacement
  $doc.Save()
  $readBack = [string]$doc.Range($start, $start + $replacement.Length).Text
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'writer'
    start = $start
    end = $end
    read_back_text = $readBack
  } | ConvertTo-Json -Depth 5
"""

_EXPORT_HTML_BODY = """
  if (-not [bool]$doc.Saved) {
    [pscustomobject]@{ ok = $true; status = 'unsaved' } | ConvertTo-Json -Depth 5
    exit 0
  }
  $copy = $null
  $method = 'SaveAs2'
  try {
    $copy = $app.Documents.Add([string]$doc.FullName)
    try { $copy.SaveAs2([string]$params.output, 10) }
    catch { $method = 'SaveAs'; $copy.SaveAs([string]$params.output, 10) }
  } finally {
    if ($copy -ne $null) {
      try { $copy.Close($false) } catch { }
      try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($copy) } catch { }
    }
  }
  [pscustomobject]@{
    ok = $true
    status = 'ok'
    backend = 'powershell-com'
    component = 'writer'
    export_method = $method
    source_still_open = [bool]($null -ne (Find-OpenWriterDocument $app $params.path))
  } | ConvertTo-Json -Depth 5
"""


def _render(script: str, params: dict[str, Any]) -> str:
    return script.replace("__PARAMS_JSON__", json.dumps(params))


def _run_script(script: str, params: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    payload, failure = run_powershell_script(_render(script, params), timeout_seconds=timeout_seconds)
    if failure is not None:
        return failure
    return {"ok": True, "errors": [], "data": payload}


def _writer_prog_ids() -> list[str]:
    return list(WPS_COMPONENTS["writer"])


def _run_open_documents_com(components: list[str]) -> dict[str, Any]:
    specs = [
        {
            "component": name,
            "prog_ids": list(WPS_COMPONENTS[name]),
            "collection": _COMPONENT_COLLECTIONS[name][0],
            "active": _COMPONENT_COLLECTIONS[name][1],
        }
        for name in components
    ]
    return _run_script(_LIST_SCRIPT, {"components": specs}, timeout_seconds=60)


def _run_writer_attached_com(action: str, params: dict[str, Any]) -> dict[str, Any]:
    body = {
        "selection-read": _SELECTION_READ_BODY,
        "selection-replace": _SELECTION_REPLACE_BODY,
        "export-html": _EXPORT_HTML_BODY,
    }[action]
    script = _ATTACHED_WRITER_WRAPPER.replace("__ACTION_BODY__", body)
    return _run_script(script, {"prog_ids": _writer_prog_ids(), **params}, timeout_seconds=120)


def _status_error(status: str | None, path: str) -> dict[str, str] | None:
    if status == "ok":
        return None
    messages = {
        "no_instance": (
            NO_RUNNING_WPS_INSTANCE,
            "No running WPS Writer instance was found. Open the document in WPS first; this command never launches WPS or closes a running instance.",
        ),
        "not_open": (
            DOCUMENT_NOT_OPEN,
            f"The registered document is not open in the running WPS Writer instance: {path}",
        ),
        "unsaved": (
            DOCUMENT_HAS_UNSAVED_CHANGES,
            "The open document has unsaved changes; save it in WPS first so the backup and file-based verification match what is open.",
        ),
        "no_window": (SELECTION_UNAVAILABLE, "The open document has no active window, so there is no selection to read."),
        "selection_changed": (
            SELECTION_MISMATCH,
            "The selection or its text changed between preview and write; no change was made.",
        ),
    }
    code, message = messages.get(str(status), (COM_OPERATION_FAILED, f"Unexpected attach status: {status}"))
    return {"code": code, "message": message}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _validate_text(text: str, label: str) -> dict[str, str] | None:
    if len(text) > MAX_SELECTION_CHARS or any(ord(char) < 32 or ord(char) == 127 for char in text):
        return {
            "code": "INVALID_ARGUMENT",
            "message": f"{label} must be at most {MAX_SELECTION_CHARS} characters on one line without control characters.",
        }
    return None


def _writer_document(document_id: str, workspace: str | Path) -> tuple[dict[str, Any] | None, dict[str, Any], list[dict[str, str]]]:
    document = get_document(document_id, workspace)
    if not document:
        return None, {}, [{"code": "DOCUMENT_NOT_FOUND", "message": f"Document not registered: {document_id}"}]
    if document["component"] != "writer":
        return None, {"document": document}, [
            {"code": "UNSUPPORTED_COMPONENT", "message": "This command requires a registered writer document."}
        ]
    if not Path(document["path"]).exists():
        return None, {"document": document}, [
            {"code": INPUT_FILE_NOT_FOUND, "message": f"Input file not found: {document['path']}"}
        ]
    return document, {}, []


def list_open_documents(
    component: str | None = None,
    register: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    if component is not None and component not in WPS_COMPONENTS:
        return False, {}, [{"code": "UNSUPPORTED_COMPONENT", "message": f"Unsupported component: {component}"}]
    components = [component] if component else list(WPS_COMPONENTS)

    result = _run_open_documents_com(components)
    if not result["ok"]:
        return False, {"probed_components": components, **result["data"]}, result["errors"]
    payload = result["data"] or {}
    if payload.get("ok") is False:
        return False, {"probed_components": components, "diagnostic": payload}, [
            {"code": COM_OPERATION_FAILED, "message": str(payload.get("error_message") or "Attach failed.")}
        ]

    instances = []
    documents: list[dict[str, Any]] = []
    for instance in _as_list(payload.get("instances")):
        name = instance.get("component")
        entries = []
        for item in _as_list(instance.get("documents")):
            full_name = item.get("full_name") or ""
            path_exists = bool(full_name) and Path(full_name).is_file()
            entry = {
                "component": name,
                "name": item.get("name"),
                "full_name": full_name,
                "saved": item.get("saved"),
                "read_only": item.get("read_only"),
                "active": bool(item.get("active")),
                "path_exists": path_exists,
                "document_id": None,
                "registered": False,
            }
            if path_exists:
                known = get_document(stable_document_id(name, full_name), workspace)
                if known is None and register:
                    ok, record, errors = register_document(name, full_name, workspace)
                    entry["register_errors"] = errors if not ok else []
                    known = record if ok else None
                if known is not None:
                    entry["document_id"] = known["document_id"]
                    entry["registered"] = True
            entries.append(entry)
        instances.append({"component": name, "version": instance.get("version"), "document_count": len(entries)})
        documents.extend(entries)

    data = {
        "probed_components": components,
        "instances": instances,
        "documents": documents,
        "attached_without_launching": True,
        "note": "Documents are matched by path; unsaved or untitled documents have no stable document_id. Use document_id, not the active window, to target a document.",
    }
    if not instances:
        return False, data, [
            {"code": NO_RUNNING_WPS_INSTANCE, "message": "No running WPS instance was found for the probed components; nothing was launched."}
        ]
    return True, data, []


def read_writer_selection(
    document_id: str,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    document, data, errors = _writer_document(document_id, workspace)
    if document is None:
        return False, data, errors
    path = str(Path(document["path"]).resolve())
    result = _run_writer_attached_com("selection-read", {"path": path})
    if not result["ok"]:
        return False, {"document_id": document_id, "path": path, **result["data"]}, result["errors"]
    payload = result["data"] or {}
    if payload.get("ok") is False:
        return False, {"document_id": document_id, "path": path, "diagnostic": payload}, [
            {"code": COM_OPERATION_FAILED, "message": str(payload.get("error_message") or "Selection read failed.")}
        ]
    error = _status_error(payload.get("status"), path)
    if error:
        return False, {"document_id": document_id, "path": path}, [error]

    text = str(payload.get("selection_text") or "")
    start, end = int(payload["start"]), int(payload["end"])
    return True, {
        "document_id": document_id,
        "component": "writer",
        "path": path,
        "saved": payload.get("saved"),
        "start": start,
        "end": end,
        "collapsed": start == end,
        "selection_length": end - start,
        "selection_text": text[:MAX_SELECTION_CHARS],
        "selection_text_truncated": len(text) > MAX_SELECTION_CHARS,
        "paragraph_index": payload.get("paragraph_index"),
        "page_number": payload.get("page_number"),
        "page_info_verified": False,
        "page_note": "Page is not a first-class object; page_number comes from the selection's active end and is unverified on this WPS version. Target content (selection, paragraph, bookmark, keyword) rather than page numbers.",
    }, []


def _check_replaceable_selection(selection: dict[str, Any], expected: str | None) -> dict[str, str] | None:
    text = selection["selection_text"]
    if selection["collapsed"]:
        return {"code": SELECTION_EMPTY, "message": "The selection is empty; select the text to replace first."}
    if selection["selection_length"] > MAX_SELECTION_CHARS or selection["selection_text_truncated"]:
        return {"code": SELECTION_TOO_LARGE, "message": f"The selection is longer than {MAX_SELECTION_CHARS} characters."}
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        return {
            "code": SELECTION_SPANS_STRUCTURE,
            "message": "The selection includes paragraph, line, table-cell or other control marks; shrink it to plain text within one paragraph.",
        }
    if selection["selection_length"] != len(text):
        return {
            "code": SELECTION_SPANS_STRUCTURE,
            "message": "The selection contains non-text objects such as fields or drawings; shrink it to plain text.",
        }
    if expected is not None and expected != text:
        return {"code": SELECTION_MISMATCH, "message": "The current selection text does not match expected_selection_text."}
    return None


@coordinated_mutation
def replace_writer_selection(
    document_id: str,
    text: str,
    request_id: str,
    expected_selection_text: str | None = None,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replay = replay_operation(
        request_id,
        "writer-selection-replace",
        {
            "document_id": document_id,
            "replacement_text": text,
            "expected_selection_text": expected_selection_text,
            "dry_run": dry_run,
        },
        workspace,
    )
    if replay is not None:
        return replay

    for value, label in ((text, "Replacement text"), (expected_selection_text, "expected_selection_text")):
        if value is not None:
            invalid = _validate_text(value, label)
            if invalid:
                return False, {}, [invalid], False

    ok, selection, errors = read_writer_selection(document_id, workspace)
    if not ok:
        return False, selection, errors, False
    problem = _check_replaceable_selection(selection, expected_selection_text)
    if problem:
        return False, {"selection": selection}, [problem], False

    preview = {
        "document_id": document_id,
        "component": "writer",
        "path": selection["path"],
        "start": selection["start"],
        "end": selection["end"],
        "paragraph_index": selection["paragraph_index"],
        "selection_text": selection["selection_text"],
        "replacement_text": text,
        "expected_selection_text": expected_selection_text,
        "would_modify": selection["selection_text"] != text,
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

    path = Path(selection["path"])
    write_result = guarded_com_mutation(
        path,
        backup_result,
        lambda: _run_writer_attached_com(
            "selection-replace",
            {
                "path": str(path),
                "text": text,
                "expected_start": selection["start"],
                "expected_end": selection["end"],
                "expected_text": selection["selection_text"],
            },
        ),
    )
    if not write_result["ok"]:
        return False, {"preview": preview, "backup": backup_result, "write": write_result["data"]}, write_result["errors"], False
    payload = write_result["data"]
    status_error = _status_error(payload.get("status"), str(path))
    if status_error:
        return False, {"preview": preview, "backup": backup_result, "write": payload}, [status_error], False

    read_back_text = payload.get("read_back_text")
    validation_passed = read_back_text == text
    result = {
        **preview,
        "dry_run": False,
        "backup": backup_result,
        "backup_replayed": backup_replayed,
        "write_backend": payload.get("backend"),
        "read_back_text": read_back_text,
        "validation_passed": validation_passed,
        "selection_preserved": False,
        "note": "The replaced range is edited by position; the user's selection in WPS is not restored.",
    }
    post_error = verify_post_com_source(path, write_result)
    if post_error is not None:
        return False, result, [post_error], False
    if not validation_passed:
        return False, result, [
            {"code": "VALIDATION_FAILED", "message": "Selection replacement read-back did not match the replacement text."}
        ], False

    record_operation(request_id, "writer-selection-replace", result, workspace)
    return True, result, [], False


HTML_EXPORT_KNOWN_LOSSES = [
    "HTML export is a lossy, filtered rendition: page layout, headers/footers, some styles, fields and drawing objects may change or be flattened.",
    "Images and styles are written to a companion folder next to the HTML file; keep them together.",
    "Fidelity on this WPS version is unverified until measured with a real fixture.",
]


@coordinated_mutation
def export_open_document_html(
    document_id: str,
    output: str,
    request_id: str,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    output_path = Path(output)
    replay = replay_operation(
        request_id,
        "export-open-document",
        {"document_id": document_id, "output": str(output_path.resolve())},
        workspace,
    )
    if replay is not None:
        return replay

    document, data, errors = _writer_document(document_id, workspace)
    if document is None:
        return False, data, errors
    source = Path(document["path"]).resolve()
    resolved_output = output_path.resolve()
    if resolved_output.suffix.lower() not in HTML_EXPORT_SUFFIXES:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Output must end in .html or .htm; only HTML export of open Writer documents is supported."}], False
    if resolved_output == source:
        return False, {}, [{"code": "INVALID_ARGUMENT", "message": "Output must differ from the source document."}], False
    if resolved_output.exists():
        return False, {"output": str(resolved_output)}, [{"code": OUTPUT_EXISTS, "message": "Output already exists; choose a new path. Nothing was overwritten."}], False
    if not resolved_output.parent.is_dir():
        return False, {"output": str(resolved_output)}, [{"code": "INVALID_ARGUMENT", "message": "Output directory does not exist."}], False

    try:
        identity_before = file_identity(source)
    except OSError as exc:
        return False, {}, [{"code": "DOCUMENT_IDENTITY_UNAVAILABLE", "message": str(exc)}], False

    result = _run_writer_attached_com("export-html", {"path": str(source), "output": str(resolved_output)})
    if not result["ok"]:
        return False, {"document_id": document_id, **result["data"]}, result["errors"], False
    payload = result["data"] or {}
    if payload.get("ok") is False:
        return False, {"document_id": document_id, "diagnostic": payload}, [
            {"code": COM_OPERATION_FAILED, "message": str(payload.get("error_message") or "HTML export failed.")}
        ], False
    status_error = _status_error(payload.get("status"), str(source))
    if status_error:
        return False, {"document_id": document_id}, [status_error], False

    exported = resolved_output.is_file() and resolved_output.stat().st_size > 0
    try:
        source_unchanged = file_identity(source) == identity_before
    except OSError:
        source_unchanged = False
    companion = [
        str(item)
        for item in resolved_output.parent.glob(f"{resolved_output.stem}*")
        if item.is_dir()
    ]
    export_result = {
        "document_id": document_id,
        "component": "writer",
        "source_path": str(source),
        "output": str(resolved_output),
        "format": "html",
        "output_bytes": resolved_output.stat().st_size if exported else 0,
        "companion_directories": companion,
        "export_method": payload.get("export_method"),
        "source_still_open": payload.get("source_still_open"),
        "source_unchanged": source_unchanged,
        "known_losses": HTML_EXPORT_KNOWN_LOSSES,
        "validation_passed": bool(exported and source_unchanged and payload.get("source_still_open")),
    }
    if not exported:
        return False, export_result, [{"code": EXPORT_OUTPUT_MISSING, "message": "WPS reported success but no HTML output file was produced."}], False
    if not source_unchanged:
        return False, export_result, [{"code": "DOCUMENT_CHANGED_AFTER_COM", "message": "The source document changed during export; inspect it before continuing."}], False

    record_operation(request_id, "export-open-document", export_result, workspace)
    return True, export_result, [], False
