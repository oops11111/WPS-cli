from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any

from .capabilities import WPS_COMPONENTS, powershell_executable, probe_wps_capabilities
from .errors import (
    COM_BACKEND_UNAVAILABLE,
    COM_OPERATION_FAILED,
    COM_OPERATION_TIMEOUT,
    INPUT_FILE_NOT_FOUND,
    UNSUPPORTED_COMPONENT,
)


def _load_win32com() -> Any | None:
    try:
        import win32com.client  # type: ignore[import-not-found]
    except ImportError:
        return None
    return win32com.client


def validate_smoke_inputs(component: str, input_path: str, output_path: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if component not in WPS_COMPONENTS:
        errors.append(
            {
                "code": UNSUPPORTED_COMPONENT,
                "message": f"Unsupported component: {component}",
            }
        )
    if not Path(input_path).exists():
        errors.append(
            {
                "code": INPUT_FILE_NOT_FOUND,
                "message": f"Input file not found: {input_path}",
            }
        )
    if not output_path:
        errors.append(
            {
                "code": INPUT_FILE_NOT_FOUND,
                "message": "Output file path is required.",
            }
        )
    return errors


def _run_powershell_com_smoke(
    component: str,
    prog_id: str,
    input_path: str,
    output_path: str,
    visible: bool,
) -> dict[str, Any]:
    params = {
        "component": component,
        "prog_id": prog_id,
        "input_path": str(Path(input_path).resolve()),
        "output_path": str(Path(output_path).resolve()),
        "visible": visible,
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
  if ($app.PSObject.Properties.Name -contains 'Visible') {{
    try {{ $app.Visible = [bool]$params.visible }} catch {{ }}
  }}

  switch ($params.component) {{
    'writer' {{
      $document = $app.Documents.Open($params.input_path)
      $document.SaveAs($params.output_path)
      $document.Close($false)
    }}
    'spreadsheets' {{
      $document = $app.Workbooks.Open($params.input_path)
      $document.SaveAs($params.output_path)
      $document.Close($false)
    }}
    'presentation' {{
      $document = $app.Presentations.Open($params.input_path, $false, $false, [bool]$params.visible)
      $document.SaveAs($params.output_path)
      $document.Close()
    }}
    default {{
      throw "Unsupported component: $($params.component)"
    }}
  }}

  [pscustomobject]@{{
    ok = $true
    component = $params.component
    prog_id = $params.prog_id
    backend = 'powershell-com'
    input_path = $params.input_path
    output_path = $params.output_path
  }} | ConvertTo-Json -Depth 5
}} catch {{
  [pscustomobject]@{{
    ok = $false
    component = $params.component
    prog_id = $params.prog_id
    backend = 'powershell-com'
    error_type = $_.Exception.GetType().FullName
    error_message = $_.Exception.Message
    position = $_.InvocationInfo.PositionMessage
  }} | ConvertTo-Json -Depth 5
  exit 2
}} finally {{
  if ($document -ne $null) {{
    try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) }} catch {{ }}
  }}
  if ($app -ne $null) {{
    try {{ $app.Quit() }} catch {{ }}
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
    if completed.returncode != 0:
        parsed_error = None
        try:
            parsed_error = json.loads(completed.stdout)
        except json.JSONDecodeError:
            parsed_error = None
        message = (completed.stderr or completed.stdout).strip()
        if isinstance(parsed_error, dict):
            message = parsed_error.get("error_message") or message
        return {
            "ok": False,
            "errors": [
                {
                    "code": COM_OPERATION_FAILED,
                    "message": message,
                }
            ],
            "data": {
                "component": component,
                "prog_id": prog_id,
                "backend": "powershell-com",
                "diagnostic": parsed_error,
            },
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {
            "ok": True,
            "component": component,
            "prog_id": prog_id,
            "backend": "powershell-com",
            "raw_output": completed.stdout.strip(),
        }
    return {"ok": True, "errors": [], "data": payload}


def run_spreadsheet_calc_smoke(
    input_path: str,
    output_path: str,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    validation_errors = validate_smoke_inputs("spreadsheets", input_path, output_path)
    if validation_errors:
        return {"ok": False, "errors": validation_errors, "data": {}}
    if Path(input_path).resolve() == Path(output_path).resolve():
        return {
            "ok": False,
            "errors": [
                {
                    "code": COM_OPERATION_FAILED,
                    "message": "Spreadsheet calculation smoke output_path must differ from input_path.",
                }
            ],
            "data": {},
        }

    capabilities = probe_wps_capabilities()
    selected_prog_id = capabilities["components"]["spreadsheets"]["selected_prog_id"]
    if not selected_prog_id:
        return {
            "ok": False,
            "errors": [
                {
                    "code": COM_BACKEND_UNAVAILABLE,
                    "message": "No registered WPS ProgID detected for spreadsheets.",
                }
            ],
            "data": {"capabilities": capabilities},
        }

    params = {
        "prog_id": selected_prog_id,
        "input_path": str(Path(input_path).resolve()),
        "output_path": str(Path(output_path).resolve()),
    }
    params_json = json.dumps(params)
    script = f"""
$ErrorActionPreference = 'Stop'
$params = @'
{params_json}
'@ | ConvertFrom-Json
$app = $null
$workbook = $null
try {{
  $app = New-Object -ComObject $params.prog_id
  try {{ $app.Visible = $false }} catch {{ }}
  try {{ $app.DisplayAlerts = $false }} catch {{ }}
  $workbook = $app.Workbooks.Open($params.input_path)
  $sheet = $workbook.Worksheets.Item(1)
  $sheet.Range("B4").Value2 = 7
  $sheet.Range("C4").Value2 = 11
  $sheet.Range("D4").Formula = "=B4+C4"
  try {{ $app.CalculateFull() }} catch {{ try {{ $app.Calculate() }} catch {{ $workbook.RefreshAll() }} }}
  $rawValue = $sheet.Range("D4").Value2
  $displayText = [string]$sheet.Range("D4").Text
  $expected = 18
  $passed = ([double]$rawValue -eq [double]$expected) -and ($displayText -match "18")
  if (Test-Path -LiteralPath $params.output_path) {{ Remove-Item -LiteralPath $params.output_path -Force }}
  $workbook.SaveAs($params.output_path)

  [pscustomobject]@{{
    ok = $passed
    backend = 'powershell-com'
    component = 'spreadsheets'
    prog_id = $params.prog_id
    input_path = $params.input_path
    output_path = $params.output_path
    cell = 'D4'
    formula = '=B4+C4'
    expected = $expected
    raw_value = $rawValue
    display_text = $displayText
  }} | ConvertTo-Json -Depth 5
}} catch {{
  [pscustomobject]@{{
    ok = $false
    backend = 'powershell-com'
    component = 'spreadsheets'
    prog_id = $params.prog_id
    error_type = $_.Exception.GetType().FullName
    error_message = $_.Exception.Message
    position = $_.InvocationInfo.PositionMessage
  }} | ConvertTo-Json -Depth 5
  exit 2
}} finally {{
  if ($workbook -ne $null) {{
    try {{ $workbook.Close($false) }} catch {{ }}
    try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($workbook) }} catch {{ }}
  }}
  if ($app -ne $null) {{
    try {{ $app.Quit() }} catch {{ }}
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
        try:
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
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "ok": False,
                "errors": [
                    {
                        "code": COM_OPERATION_TIMEOUT,
                        "message": f"Spreadsheet calculation smoke timed out after {timeout_seconds} seconds.",
                    }
                ],
                "data": {
                    "backend": "powershell-com",
                    "component": "spreadsheets",
                    "prog_id": selected_prog_id,
                    "input_path": params["input_path"],
                    "output_path": params["output_path"],
                    "timeout_seconds": timeout_seconds,
                    "stdout": exc.stdout if isinstance(exc.stdout, str) else "",
                    "stderr": exc.stderr if isinstance(exc.stderr, str) else "",
                },
            }
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

    if not payload.get("ok"):
        return {
            "ok": False,
            "errors": [
                {
                    "code": COM_OPERATION_FAILED,
                    "message": "Calculated raw/display values did not match expected result.",
                }
            ],
            "data": payload,
        }

    return {"ok": True, "errors": [], "data": payload}


def run_conversion_smoke(
    component: str,
    input_path: str,
    output_path: str,
    output_format: str,
) -> dict[str, Any]:
    validation_errors = validate_smoke_inputs(component, input_path, output_path)
    if validation_errors:
        return {"ok": False, "errors": validation_errors, "data": {}}
    if component != "writer" or output_format.lower() != "pdf":
        return {
            "ok": False,
            "errors": [
                {
                    "code": UNSUPPORTED_COMPONENT,
                    "message": "Only writer to pdf conversion smoke is implemented in Phase 0.",
                }
            ],
            "data": {},
        }

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
        "input_path": str(Path(input_path).resolve()),
        "output_path": str(Path(output_path).resolve()),
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
  $document = $app.Documents.Open($params.input_path)
  try {{
    $document.ExportAsFixedFormat($params.output_path, 17)
    $method = 'ExportAsFixedFormat'
  }} catch {{
    $document.SaveAs($params.output_path, 17)
    $method = 'SaveAs'
  }}
  $exists = Test-Path $params.output_path
  $length = if ($exists) {{ (Get-Item $params.output_path).Length }} else {{ 0 }}
  $passed = $exists -and ($length -gt 0)

  [pscustomobject]@{{
    ok = $passed
    backend = 'powershell-com'
    component = 'writer'
    prog_id = $params.prog_id
    input_path = $params.input_path
    output_path = $params.output_path
    direction = 'docx_to_pdf'
    conversion_method = $method
    retained = @('text content', 'page layout', 'basic tables', 'embedded images where supported by WPS')
    known_losses = @('PDF output is not editable as native WPS content', 'interactive Word fields may be flattened', 'result depends on installed WPS PDF export behavior')
    output_exists = $exists
    output_bytes = $length
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
    try {{ $app.Quit() }} catch {{ }}
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

    if not payload.get("ok"):
        return {
            "ok": False,
            "errors": [
                {
                    "code": COM_OPERATION_FAILED,
                    "message": "Conversion did not create a non-empty output file.",
                }
            ],
            "data": payload,
        }

    return {"ok": True, "errors": [], "data": payload}


def run_com_smoke(
    component: str,
    input_path: str,
    output_path: str,
    visible: bool = False,
) -> dict[str, Any]:
    validation_errors = validate_smoke_inputs(component, input_path, output_path)
    if validation_errors:
        return {"ok": False, "errors": validation_errors, "data": {}}

    capabilities = probe_wps_capabilities()
    selected_prog_id = capabilities["components"][component]["selected_prog_id"]
    if not selected_prog_id:
        return {
            "ok": False,
            "errors": [
                {
                    "code": COM_BACKEND_UNAVAILABLE,
                    "message": f"No registered WPS ProgID detected for {component}.",
                }
            ],
            "data": {"capabilities": capabilities},
        }

    win32com_client = _load_win32com()
    if win32com_client is None:
        return _run_powershell_com_smoke(
            component=component,
            prog_id=selected_prog_id,
            input_path=input_path,
            output_path=output_path,
            visible=visible,
        )

    app = None
    document = None
    try:
        app = win32com_client.DispatchEx(selected_prog_id)
        if hasattr(app, "Visible"):
            app.Visible = visible

        source = str(Path(input_path).resolve())
        target = str(Path(output_path).resolve())

        if component == "writer":
            document = app.Documents.Open(source)
            document.SaveAs(target)
        elif component == "spreadsheets":
            document = app.Workbooks.Open(source)
            document.SaveAs(target)
        elif component == "presentation":
            document = app.Presentations.Open(source, WithWindow=visible)
            document.SaveAs(target)
        else:
            raise ValueError(f"Unsupported component: {component}")

        return {
            "ok": True,
            "errors": [],
            "data": {
                "component": component,
                "prog_id": selected_prog_id,
                "backend": "pywin32-com",
                "input_path": source,
                "output_path": target,
            },
        }
    except Exception as exc:  # pragma: no cover - depends on local WPS COM
        return {
            "ok": False,
            "errors": [
                {
                    "code": COM_OPERATION_FAILED,
                    "message": str(exc),
                }
            ],
            "data": {
                "component": component,
                "prog_id": selected_prog_id,
            },
        }
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if app is not None:
            try:
                app.Quit()
            except Exception:
                pass
