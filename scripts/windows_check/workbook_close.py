"""Try several ways to close a workbook WPS opened the usual way, and record what each does (P8-005).

Phase 7 found that a workbook opened by double-click and reached through the Running Object Table does not close:
Close($false) failed with RPC_E_SERVERFAULT, Close() with 0x800A01A8, and stopping et.exe made WPS start a
recovery instance. Two fixes were tried without knowing why. This module finds out first.

Each attempt writes a new workbook into its own workspace, opens it in WPS with the registered open command (as a
user's double-click does, or with /Automation for the control group), tries one way of closing it, and records:
how the script attached, the exception and its HRESULT if the call failed, whether the workbook was still in
Workbooks two seconds later, whether `open-documents` still lists it, and the WPS processes with their command
lines (a recovery instance shows `recover` in its command line). Then the runner's own cleanup closes what is left
and ends the WPS processes the attempt started.

Read-only for the user: it only opens and closes workbooks it wrote itself, and runs when no WPS process is running.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

FIXTURE = "close-check.xlsx"

# Each way of closing, as the PowerShell it runs on $doc, the workbook found in $app.Workbooks.
METHODS: dict[str, str] = {
    "close": "$doc.Close() — what close_unchanged_document tries first since P7-007",
    "close_false": "$doc.Close($false) — what it tried before P7-007",
    "close_false_missing": "$doc.Close($false, [Type]::Missing, $false) — every argument given",
    "saved_then_close": "$doc.Saved = $true, then $doc.Close()",
    "item_by_name": "$app.Workbooks.Item($doc.Name).Close() — the object WPS returns for the name",
    "rot_object": "Close() on the workbook object registered in the Running Object Table itself",
    "invoke_member": "IDispatch Close through InvokeMember with no arguments, past the PowerShell COM adapter",
    "window_close": "$doc.Windows.Item(1).Close() — the workbook's only window",
}
# /Automation starts WPS registered for automation: the control group, where closing is expected to work.
CONTROL_METHODS = ("close", "close_false")
LAUNCHES = ("default", "automation")


def default_plan() -> list[tuple[str, str]]:
    return [("default", method) for method in METHODS] + [("automation", method) for method in CONTROL_METHODS]


_ATTEMPT_BODY = r"""
  function Get-CloseFailure($record) {
    $e = $record.Exception
    while ($null -ne $e.InnerException) { $e = $e.InnerException }
    return [ordered]@{ hresult = ('0x{0:X8}' -f $e.HResult); type = $e.GetType().FullName; message = $e.Message }
  }
  $attempt = [ordered]@{
    method = [string]$params.method
    attached_via = $script:WpsAttachedVia
    name = $null
    saved_before = $null
    in_rot = $null
    returned = $false
    error = $null
    listed_after = $null
    list_error = $null
  }
  try { $attempt.name = [string]$doc.Name } catch { }
  try { $attempt.saved_before = [bool]$doc.Saved } catch { }
  $target = ConvertTo-WpsComparablePath $params.path
  $rotDoc = $null
  foreach ($registered in @([WpsAgent.Rot]::Find([string[]]@('.xlsx')))) {
    try {
      if ([string]::Equals((ConvertTo-WpsComparablePath ([string]$registered.FullName)), $target, [System.StringComparison]::OrdinalIgnoreCase)) {
        $rotDoc = $registered
      }
    } catch { }
  }
  $attempt.in_rot = $null -ne $rotDoc
  try {
    switch ([string]$params.method) {
      'close' { [void]$doc.Close() }
      'close_false' { [void]$doc.Close($false) }
      'close_false_missing' { [void]$doc.Close($false, [Type]::Missing, $false) }
      'saved_then_close' { $doc.Saved = $true; [void]$doc.Close() }
      'item_by_name' { [void]$app.Workbooks.Item([string]$doc.Name).Close() }
      'rot_object' {
        if ($null -eq $rotDoc) { throw 'the workbook is not registered in the Running Object Table' }
        [void]$rotDoc.Close()
      }
      'invoke_member' {
        [void][System.__ComObject].InvokeMember('Close', [System.Reflection.BindingFlags]::InvokeMethod, $null, $doc, $null)
      }
      'window_close' { [void]$doc.Windows.Item(1).Close() }
      default { throw ('unknown method ' + [string]$params.method) }
    }
    $attempt.returned = $true
  } catch {
    $attempt.error = Get-CloseFailure $_
  }
  Start-Sleep -Seconds 2
  try { $attempt.listed_after = $null -ne (Find-OpenWorkbook $app $params.path) } catch { $attempt.list_error = Get-CloseFailure $_ }
  if ($null -ne $rotDoc) { try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($rotDoc) } catch { } }
  [pscustomobject]@{ ok = $true; status = 'attempted'; attempt = $attempt } | ConvertTo-Json -Depth 6
"""


def attempt_script() -> str:
    from wps_ai_agent_cli.open_document_scripts.spreadsheet import _ATTACHED_SPREADSHEET_WRAPPER

    return _ATTACHED_SPREADSHEET_WRAPPER.replace("__ACTION_BODY__", _ATTEMPT_BODY)


def run_close_script(path: Path, method: str) -> dict[str, Any]:
    """Attach to the running WPS Spreadsheets, find the workbook and close it with one method. Returns its JSON."""
    from wps_ai_agent_cli.capabilities import WPS_COMPONENTS
    from wps_ai_agent_cli.open_documents import _run_script

    result = _run_script(
        attempt_script(),
        {"prog_ids": list(WPS_COMPONENTS["spreadsheets"]), "path": str(path.resolve()), "method": method},
        timeout_seconds=120,
    )
    if not result["ok"]:
        return {"status": "script_failed", "errors": result["errors"]}
    return result["data"] or {"status": "no_output"}


def run_attempt(
    launch: str,
    method: str,
    runner: Any,
    root: Path,
    processes: Callable[[], list[dict[str, Any]]],
    *,
    close: Callable[[Path, str], dict[str, Any]] = run_close_script,
    settle: float = 3.0,
) -> dict[str, Any]:
    """Open a new workbook in WPS, close it with `method`, record what happened, then clean up."""
    from wps_ai_agent_cli.open_documents import _listed_in_wps

    workspace = root / f"{launch}-{method}"
    workspace.mkdir(parents=True, exist_ok=True)
    path = workspace / FIXTURE
    runner.write_fixture(workspace, FIXTURE)
    result: dict[str, Any] = {"launch": launch, "method": method, "workspace": str(workspace)}
    result["processes_before"] = processes()
    runner.WPS_LAUNCH = launch
    release, reason = runner.open_in_wps(path, "spreadsheets")
    if release is None:
        result["setup_failed"] = reason
        return result
    try:
        payload = close(path, method)
        result["status"] = payload.get("status")
        result["attempt"] = payload.get("attempt") or {}
        if payload.get("errors"):
            result["errors"] = payload["errors"]
        time.sleep(settle)
        result["listed_by_cli"] = _listed_in_wps("spreadsheets", path)
        result["processes_after"] = processes()
    finally:
        result["cleanup"] = release()
    return result


def outcome(result: dict[str, Any]) -> str:
    """One word for the table: closed, failed but closed, failed and still open, or why nothing was tried."""
    if result.get("setup_failed"):
        return "setup failed"
    attempt = result.get("attempt") or {}
    if result.get("status") != "attempted":
        return f"not attempted ({result.get('status')})"
    gone = result.get("listed_by_cli") is False
    if attempt.get("returned"):
        return "closed" if gone else "returned, still open"
    return "failed, closed anyway" if gone else "failed, still open"


def recovery_processes(items: list[dict[str, Any]] | None) -> list[str]:
    return [
        f"{item.get('name')} {item.get('id')}"
        for item in items or []
        if "recover" in str(item.get("command_line") or "").casefold()
    ]


def results_table(results: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Launch | Method | Attached via | In ROT | Outcome | HRESULT | Message | Recovery instance | Cleanup |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        attempt = result.get("attempt") or {}
        error = attempt.get("error") or {}
        message = str(error.get("message") or result.get("setup_failed") or "").replace("|", "\\|").replace("\n", " ")
        recovery = ", ".join(recovery_processes(result.get("processes_after"))) or "none"
        cleanup = str(result.get("cleanup") or "").replace("|", "\\|")
        lines.append(
            f"| {result['launch']} | `{result['method']}` | {attempt.get('attached_via') or ''} "
            f"| {attempt.get('in_rot')} | {outcome(result)} | {error.get('hresult') or ''} | {message} "
            f"| {recovery} | {cleanup} |"
        )
    return lines
