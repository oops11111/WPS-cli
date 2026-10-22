"""Conversions that WPS itself performs (P13-007): its own formats, the legacy Office formats, ODF, PDF and PNG.

WPS opens the source hidden and saves a copy with SaveAs and the format code below (the WPS family formats .wps,
.et and .dps, and the templates, are chosen by the file extension); PDF goes through ExportAsFixedFormat. PNG output
is one image per page or slide: WPS exports a PDF to a temporary folder and each page is rendered with pypdfium2
(the ``fidelity`` extra) at the requested resolution, as ``<name>-001.png``, ``<name>-002.png`` and so on.

A pair WPS cannot write (a document saved as a workbook, say) is refused with FORMAT_NOT_SUPPORTED_BY_WPS before
WPS starts (decision 9).
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any

from .capabilities import probe_wps_capabilities
from .errors import COM_BACKEND_UNAVAILABLE, COM_OPERATION_FAILED
from .powershell_runner import run_powershell_script
from .wps_script_snippets import ACQUIRE_WPS_APP, HIDE_LAUNCHED_APP, PRE_OPEN_GUARD, QUIET_ALERTS, RELEASE_WPS_APP

FORMAT_NOT_SUPPORTED_BY_WPS = "FORMAT_NOT_SUPPORTED_BY_WPS"
BUSY_RETRIES = 2
BUSY_WAIT_SECONDS = 5
# WPS still busy with, or not yet letting go of, the previous call's file: worth a wait and another try.
_BUSY = (
    "0x80010001",
    "RPC_E_CALL_REJECTED",
    "0x8001010A",
    "RPC_E_SERVERCALL_RETRYLATER",
    "DOCUMENT_HELD_OPEN",
    "being used by another process",
)

# Component, the formats WPS opens, and the SaveAs code for each format it writes (None: by extension). The Open
# calls are the ones the conversion smoke test verified on Windows; the source is never saved, only copied.
FAMILIES: dict[str, dict[str, Any]] = {
    "writer": {
        "collection": "Documents",
        # ConfirmConversions $false: no "convert file from" prompt for .odt, .rtf or .txt, which would hang.
        # ReadOnly, not in the recent list: the source is only read, and WPS has nothing to ask about saving it.
        "open": "$document = $app.Documents.Open($source, $false, $true, $false)",
        "inputs": {".doc", ".docx", ".docm", ".dot", ".dotx", ".wps", ".wpt", ".rtf", ".odt", ".txt", ".xml"},
        "outputs": {
            ".doc": 0,
            ".dot": 1,
            ".txt": 7,
            ".rtf": 6,
            ".docx": 16,
            ".dotx": 14,
            ".odt": 23,
            ".wps": None,
            ".wpt": None,
        },
        "pdf": "$document.ExportAsFixedFormat($pdf, 17)",
        "pdf_fallback": "$document.SaveAs($pdf, 17)",
        "save": "try { $document.SaveAs2($target, $format) } catch { $document.SaveAs($target, $format) }",
        "save_default": "try { $document.SaveAs2($target) } catch { $document.SaveAs($target) }",
    },
    "spreadsheets": {
        "collection": "Workbooks",
        "open": "$document = $app.Workbooks.Open($source)",
        "inputs": {".xls", ".xlsx", ".xlsm", ".xlt", ".xltx", ".et", ".ett", ".ods", ".csv"},
        "outputs": {
            ".xls": 56,
            ".xlsx": 51,
            ".xlsm": 52,
            ".xltx": 54,
            ".ods": 60,
            ".csv": 6,
            ".et": None,
            ".ett": None,
        },
        "pdf": "$document.ExportAsFixedFormat(0, $pdf)",
        "pdf_fallback": "$document.ExportAsFixedFormat($pdf, 0)",
        "save": "$document.SaveAs($target, $format)",
        "save_default": "$document.SaveAs($target)",
    },
    "presentation": {
        "collection": "Presentations",
        "open": "$document = $app.Presentations.Open($source, $false, $false, $false)",
        "inputs": {".ppt", ".pptx", ".pptm", ".pot", ".potx", ".pps", ".ppsx", ".dps", ".dpt", ".odp"},
        "outputs": {
            ".ppt": 1,
            ".pot": 5,
            ".pptx": 24,
            ".potx": 26,
            ".ppsx": 28,
            ".odp": 35,
            ".dps": None,
            ".dpt": None,
        },
        "pdf": "$document.ExportAsFixedFormat($pdf, 2)",
        "pdf_fallback": "$document.SaveAs($pdf, 32)",
        "save": "$document.SaveAs($target, $format)",
        "save_default": "$document.SaveAs($target)",
    },
}

WPS_INPUTS = set().union(*(family["inputs"] for family in FAMILIES.values()))
WPS_OUTPUTS = set().union(*(family["outputs"] for family in FAMILIES.values())) | {".pdf", ".png"}


def family_of(path: Path) -> str | None:
    suffix = path.suffix.casefold()
    for name, family in FAMILIES.items():
        if suffix in family["inputs"]:
            return name
    return None


def plan(source: Path, destination: Path) -> tuple[str | None, int | None, str, list[dict[str, str]]]:
    """(component, SaveAs code, mode: save, save_default, pdf or png) for the pair, or the refusal."""
    component = family_of(source)
    suffix = destination.suffix.casefold()
    if component is None:
        return (
            None,
            None,
            "",
            [
                {
                    "code": FORMAT_NOT_SUPPORTED_BY_WPS,
                    "message": f"WPS does not open {source.suffix or 'files without an extension'} files.",
                }
            ],
        )
    outputs = FAMILIES[component]["outputs"]
    if suffix == ".pdf":
        return component, None, "pdf", []
    if suffix == ".png":
        return component, None, "png", []
    if suffix not in outputs:
        writable = ", ".join(sorted(set(outputs) | {".pdf", ".png"}))
        return (
            None,
            None,
            "",
            [
                {
                    "code": FORMAT_NOT_SUPPORTED_BY_WPS,
                    "message": f"WPS cannot save a {source.suffix} file as {suffix}; it can write {writable}.",
                }
            ],
        )
    code = outputs[suffix]
    return component, code, "save" if code is not None else "save_default", []


def _script(component: str, mode: str, params: dict[str, Any]) -> str:
    family = FAMILIES[component]
    params_json = json.dumps(params)
    if mode in {"pdf", "png"}:
        action = f"""
  $pdf = $params.pdf_path
  try {{ {family["pdf"]}; $method = 'ExportAsFixedFormat' }} catch {{ {family["pdf_fallback"]}; $method = 'SaveAs' }}
  $written = $pdf
"""
    else:
        save = family[mode]
        action = f"""
  $target = $params.output_path
  $format = $params.format_code
  {save}
  $method = 'SaveAs'
  $written = $target
"""
    return f"""
$ErrorActionPreference = 'Stop'
$params = @'
{params_json}
'@ | ConvertFrom-Json
{PRE_OPEN_GUARD}
$app = $null
$document = $null
try {{
  {ACQUIRE_WPS_APP}
  {HIDE_LAUNCHED_APP}
  {QUIET_ALERTS}
  Assert-WpsSingleInstance $params.prog_id
  Assert-WpsInputNotOpen (Test-WpsPathOpen $app.{family["collection"]} $params.input_path)
  Assert-WpsFileNotHeld $params.input_path 'input document' $true
  $source = (ConvertTo-WpsLocalPath $params.input_path)
  $wpsCountBefore = [int]$app.{family["collection"]}.Count
  Set-Content -LiteralPath $params.stage_path -Value 'opening the input' -Encoding UTF8
  {family["open"]}
  if ([int]$app.{family["collection"]}.Count -le $wpsCountBefore) {{ $document = $null; Stop-WpsConcurrentOpen 'input document' '' }}
  Set-Content -LiteralPath $params.stage_path -Value 'saving the output' -Encoding UTF8
  {action}
  Set-Content -LiteralPath $params.stage_path -Value 'closing' -Encoding UTF8
  $exists = Test-Path $written
  $length = if ($exists) {{ (Get-Item $written).Length }} else {{ 0 }}
  [pscustomobject]@{{
    ok = ($exists -and ($length -gt 0))
    backend = 'powershell-com'
    component = $params.component
    prog_id = $params.prog_id
    input_path = $params.input_path
    written_path = $written
    conversion_method = $method
    format_code = $params.format_code
    output_bytes = $length
  }} | ConvertTo-Json -Depth 5
}} catch {{
  [pscustomobject]@{{
    ok = $false
    backend = 'powershell-com'
    component = $params.component
    prog_id = $params.prog_id
    error_type = $_.Exception.GetType().FullName
    error_message = $_.Exception.Message
  }} | ConvertTo-Json -Depth 5
  exit 2
}} finally {{
  if ($document -ne $null) {{
    try {{ $document.Close($false) }} catch {{ try {{ $document.Close() }} catch {{ }} }}
    try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) }} catch {{ }}
  }}
  if ($app -ne $null) {{
    try {{ {RELEASE_WPS_APP} }} catch {{ }}
    try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) }} catch {{ }}
  }}
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}}
"""


def render_pdf_pages(pdf: Path, destination: Path, dpi: int = 150) -> list[str]:
    """Each page of ``pdf`` as ``<destination stem>-001.png`` ... next to ``destination``."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(pdf))
    written = []
    try:
        for index in range(len(document)):
            page = document[index]
            image = page.render(scale=dpi / 72).to_pil()
            path = destination.with_name(f"{destination.stem}-{index + 1:03d}.png")
            image.save(path)
            written.append(str(path))
            page.close()
    finally:
        document.close()
    return written


_WINDOW_TITLES_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System; using System.Collections.Generic; using System.Runtime.InteropServices; using System.Text;
public static class WpsWindows {
  delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
  [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc callback, IntPtr lParam);
  [DllImport("user32.dll")] static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] static extern int GetClassName(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr hWnd, out Rect rect);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
  // Takes the device context, not a Graphics: on PowerShell 7 the drawing types live in an assembly this compiled
  // type cannot reference (CS1069, Windows check on f8ed7bd).
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
  public static List<object[]> Visible(HashSet<uint> pids) {
    var found = new List<object[]>();
    EnumWindows((hWnd, l) => {
      uint pid; GetWindowThreadProcessId(hWnd, out pid);
      if (pids.Contains(pid) && IsWindowVisible(hWnd)) {
        var text = new StringBuilder(256); GetWindowText(hWnd, text, 256);
        var name = new StringBuilder(256); GetClassName(hWnd, name, 256);
        Rect r; GetWindowRect(hWnd, out r);
        found.Add(new object[] { text.ToString(), name.ToString(), hWnd, r.Right - r.Left, r.Bottom - r.Top });
      }
      return true;
    }, IntPtr.Zero);
    return found;
  }
}
'@
$pids = New-Object 'System.Collections.Generic.HashSet[uint32]'
Get-Process -Name wps, et, wpp -ErrorAction SilentlyContinue | ForEach-Object { [void]$pids.Add([uint32]$_.Id) }
$stamp = Get-Date -Format 'yyyyMMddTHHmmss'
$index = 0
$windows = foreach ($w in [WpsWindows]::Visible($pids)) {
  $index++
  $image = ''
  if ($w[3] -ge 20 -and $w[4] -ge 20) {
    # A picture of the window: a dialog with no title still shows what it asks. PrintWindow draws the window
    # itself, so another window on top of it does not hide it as in a screen copy (Windows check on c205851).
    try {
      $bitmap = New-Object System.Drawing.Bitmap $w[3], $w[4]
      $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
      $hdc = $graphics.GetHdc()
      try { [void][WpsWindows]::PrintWindow($w[2], $hdc, 2) } finally { $graphics.ReleaseHdc($hdc) }
      $image = Join-Path $env:TEMP "wps-agent-timeout-$stamp-$index.png"
      $bitmap.Save($image, [System.Drawing.Imaging.ImageFormat]::Png)
      $graphics.Dispose(); $bitmap.Dispose()
    } catch { $image = '' }
  }
  [pscustomobject]@{ title = $w[0]; class = $w[1]; width = $w[3]; height = $w[4]; image = $image }
}
@{ windows = @($windows) } | ConvertTo-Json -Depth 3
"""


def _wps_windows() -> list[dict[str, Any]]:
    """WPS's visible windows after a timeout, each with a screenshot when it has a size: a dialog WPS waits on
    names itself here, or shows what it asks when it has no title (Windows check on c55d04e: two untitled Qt
    windows while an .odt was opening)."""
    payload, failure = run_powershell_script(_WINDOW_TITLES_SCRIPT, 30)
    if failure is not None or not payload:
        return []
    return [window for window in payload.get("windows") or [] if isinstance(window, dict)][:10]


def _describe_window(window: dict[str, Any]) -> str:
    name = window.get("title") or f"untitled {window.get('class') or 'window'}"
    shown = f"{name} {window.get('width')}x{window.get('height')}"
    return f"{shown} ({window['image']})" if window.get("image") else shown


def wps_convert(
    input_path: str | Path, output_path: str | Path, dpi: int = 150, timeout_seconds: int = 180
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    from .conversion_paths import check_paths

    source, destination, errors = check_paths(input_path, output_path, WPS_INPUTS, WPS_OUTPUTS)
    if errors:
        if errors[0]["code"] in {"INVALID_INPUT", "INVALID_OUTPUT"}:
            _component, _code, _mode, refusal = plan(Path(input_path), Path(output_path))
            if refusal:
                return False, {}, refusal
        return False, {}, errors
    component, code, mode, refusal = plan(source, destination)
    if refusal:
        return False, {}, refusal
    if mode == "png":
        try:
            import pypdfium2  # noqa: F401
        except ImportError:
            return (
                False,
                {},
                [{"code": "CONVERTER_UNAVAILABLE", "message": "Install the fidelity optional dependency: pypdfium2."}],
            )
        first = destination.with_name(f"{destination.stem}-001.png")
        if first.exists():
            return False, {}, [{"code": "OUTPUT_ALREADY_EXISTS", "message": f"Refusing to overwrite: {first}"}]
    capabilities = probe_wps_capabilities()
    prog_id = capabilities["components"][component]["selected_prog_id"]
    if not prog_id:
        return (
            False,
            {"capabilities": capabilities},
            [{"code": COM_BACKEND_UNAVAILABLE, "message": f"No registered WPS ProgID detected for {component}."}],
        )
    with tempfile.TemporaryDirectory(prefix="wps-convert-") as tmp:
        pdf_path = (
            str(destination) if mode == "pdf" else str(Path(tmp) / f"{destination.stem}.pdf") if mode == "png" else ""
        )
        params = {
            "prog_id": prog_id,
            "component": component,
            "input_path": str(source),
            "output_path": str(destination),
            "pdf_path": pdf_path,
            "format_code": code,
            "stage_path": str(Path(tmp) / "stage.txt"),
        }
        stage = Path(params["stage_path"])
        for attempt in range(BUSY_RETRIES + 1):
            stage.write_text("starting WPS", encoding="utf-8")
            payload, failure = run_powershell_script(
                _script(component, mode, params),
                timeout_seconds,
                timeout_message=f"WPS conversion timed out after {timeout_seconds} seconds.",
                timeout_data={"component": component, "input_path": str(source)},
                failure_data={"component": component},
            )
            # WPS still finishing the previous call rejects new ones (RPC_E_CALL_REJECTED): wait and retry.
            reply = json.dumps(failure if failure is not None else payload, ensure_ascii=False)
            if attempt == BUSY_RETRIES or not any(marker in reply for marker in _BUSY):
                break
            time.sleep(BUSY_WAIT_SECONDS * (attempt + 1))
        if failure is not None:
            errors = failure["errors"]
            if errors and errors[0].get("code") == "COM_OPERATION_TIMEOUT":
                # Say where WPS stopped, so a hang (a dialog on open, say) can be told from a slow save.
                where = stage.read_text(encoding="utf-8-sig").strip() if stage.is_file() else "unknown"
                windows = _wps_windows()
                shown = f" Open WPS windows: {'; '.join(map(_describe_window, windows))}." if windows else ""
                if where == "opening the input" and source.suffix.casefold() in {".odt", ".ods", ".odp"}:
                    # Windows check on c205851: WPS asked about a "damaged" ODF 1.3 file from LibreOffice.
                    shown += (
                        " WPS may be asking whether to open a file it reads as damaged; ODF 1.3 files with"
                        " LibreOffice extensions do this, so save the file as ODF 1.2 or as .docx/.xlsx/.pptx."
                    )
                errors = [{**errors[0], "message": f"{errors[0]['message']} WPS was {where}.{shown}"}, *errors[1:]]
                failure.setdefault("data", {}).update({"stage": where, "wps_windows": windows})
            return False, failure.get("data", {}), errors
        if not payload.get("ok"):
            return (
                False,
                payload,
                [
                    {
                        "code": COM_OPERATION_FAILED,
                        "message": str(payload.get("error_message") or "WPS did not write a non-empty output file."),
                    }
                ],
            )
        pages = render_pdf_pages(Path(pdf_path), destination, dpi) if mode == "png" else []
    data: dict[str, Any] = {
        "input_path": str(source),
        "output_path": str(destination),
        "format": destination.suffix.casefold().lstrip("."),
        "backend": "powershell-com",
        "component": component,
        "prog_id": prog_id,
        "format_code": code,
        "conversion_method": payload.get("conversion_method"),
        "warnings": [],
    }
    if mode == "png":
        data["output_path"] = None
        data["pages"] = pages
        data["dpi"] = dpi
    return True, data, []
