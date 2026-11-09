"""Create a chart from a worksheet range (C-04).

The ninth spreadsheet operation of the same shape as the sheet operations in spreadsheet_ops: checks offline,
a backup, one WPS COM call that adds the chart and saves (guarded_com_mutation), then an offline read-back of the
saved package, and a rollback from the backup when the read-back does not match (atomic_mutation).

WPS adds the chart with ChartObjects().Add and SetSourceData, the API WPS Spreadsheets shares with Excel. The
read-back does not trust WPS's own answer: it opens the saved .xlsx, follows the sheet's drawing to its charts,
and checks that exactly one chart was added, of the requested type, with the requested title and with every
series reading from inside the requested range.
"""

from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from openpyxl.utils.cell import column_index_from_string, get_column_letter, range_boundaries

from .atomic_mutation import atomic_mutation
from .backups import create_backup, guarded_com_mutation, verify_post_com_source
from .capabilities import probe_wps_capabilities
from .errors import COM_BACKEND_UNAVAILABLE, COM_OPERATION_FAILED, INPUT_FILE_NOT_FOUND
from .file_hold import probe_file_not_held
from .mutation_lock import coordinated_mutation
from .ooxml import load_workbook_guarded, parse_xml_part
from .operations import record_operation, replay_operation
from .powershell_runner import run_powershell_script
from .sessions import get_document
from .wps_script_snippets import ACQUIRE_WPS_APP, HIDE_LAUNCHED_APP, PRE_OPEN_GUARD, QUIET_ALERTS, RELEASE_WPS_APP

# Excel/WPS XlChartType values, and the DrawingML element each one is saved as.
CHART_TYPES = {
    "column": {"xl": 51, "element": "barChart", "bar_dir": "col"},
    "bar": {"xl": 57, "element": "barChart", "bar_dir": "bar"},
    "line": {"xl": 4, "element": "lineChart", "bar_dir": None},
    "pie": {"xl": 5, "element": "pieChart", "bar_dir": None},
}
PLOT_BY = {"auto": None, "rows": 1, "columns": 2}  # XlRowCol
MAX_CELLS = 10_000

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
_REF = re.compile(r"^(?:'((?:[^']|'')+)'|([^!]+))!\$?([A-Z]{1,3})\$?(\d+)(?::\$?([A-Z]{1,3})\$?(\d+))?$")


def _rels(archive: ZipFile, part: str) -> dict[str, str]:
    folder, name = posixpath.split(part)
    rels_name = posixpath.join(folder, "_rels", f"{name}.rels")
    if rels_name not in archive.namelist():
        return {}
    root = parse_xml_part(archive, rels_name)
    targets = {}
    for rel in root.findall("pkg:Relationship", NS):
        target = rel.get("Target", "")
        resolved = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(folder, target))
        targets[rel.get("Id", "")] = resolved
    return targets


def _sheet_part(archive: ZipFile, sheet_name: str) -> str | None:
    workbook = parse_xml_part(archive, "xl/workbook.xml")
    rels = _rels(archive, "xl/workbook.xml")
    for sheet in workbook.findall("main:sheets/main:sheet", NS):
        if sheet.get("name") == sheet_name:
            return rels.get(sheet.get(f"{{{NS['rel']}}}id", ""))
    return None


def _describe_chart(archive: ZipFile, part: str) -> dict[str, Any]:
    root = parse_xml_part(archive, part)
    plot = root.find("c:chart/c:plotArea", NS)
    kinds = []
    refs = []
    if plot is not None:
        for child in plot:
            tag = child.tag.rsplit("}", 1)[-1]
            if not tag.endswith("Chart"):
                continue
            direction = child.find("c:barDir", NS)
            kinds.append({"element": tag, "bar_dir": direction.get("val") if direction is not None else None})
            for series in child.findall("c:ser", NS):
                for formula in series.findall(".//c:f", NS):
                    if formula.text:
                        refs.append(formula.text.strip())
    title = root.find("c:chart/c:title", NS)
    title_text = "".join(node.text or "" for node in title.iter(f"{{{NS['a']}}}t")) if title is not None else ""
    return {"part": part, "types": kinds, "title": title_text, "refs": refs}


def sheet_charts(path: str | Path, sheet_name: str) -> list[dict[str, Any]]:
    """The charts drawn on a worksheet of a saved .xlsx, read from the package."""
    with ZipFile(path) as archive:
        sheet = _sheet_part(archive, sheet_name)
        if sheet is None:
            return []
        charts = []
        worksheet = parse_xml_part(archive, sheet)
        sheet_rels = _rels(archive, sheet)
        for drawing in worksheet.findall("main:drawing", NS):
            drawing_part = sheet_rels.get(drawing.get(f"{{{NS['rel']}}}id", ""))
            if not drawing_part or drawing_part not in archive.namelist():
                continue
            for target in _rels(archive, drawing_part).values():
                if posixpath.basename(posixpath.dirname(target)) == "charts" and target in archive.namelist():
                    charts.append(_describe_chart(archive, target))
        return charts


def _ref_inside(ref: str, sheet_name: str, bounds: tuple[int, int, int, int]) -> bool:
    """Whether a chart formula such as 'Sales'!$B$2:$B$9 points inside bounds on sheet_name."""
    found = _REF.match(ref.strip())
    if not found:
        return False
    sheet = found.group(1).replace("''", "'") if found.group(1) is not None else found.group(2)
    if sheet != sheet_name:
        return False
    first_col = column_index_from_string(found.group(3))
    last_col = column_index_from_string(found.group(5) or found.group(3))
    first_row, last_row = int(found.group(4)), int(found.group(6) or found.group(4))
    min_col, min_row, max_col, max_row = bounds
    return min_col <= first_col <= last_col <= max_col and min_row <= first_row <= last_row <= max_row


def _signature(chart: dict[str, Any]) -> str:
    return json.dumps({key: chart[key] for key in ("types", "title", "refs")}, sort_keys=True, ensure_ascii=False)


def _run_spreadsheet_chart_create_com(
    path: str,
    sheet_name: str,
    range_address: str,
    anchor: str,
    chart_type: str,
    plot_by: str,
    title: str | None,
    width: float,
    height: float,
) -> dict[str, Any]:
    capabilities = probe_wps_capabilities()
    prog_id = capabilities["components"]["spreadsheets"]["selected_prog_id"]
    if not prog_id:
        return {
            "ok": False,
            "errors": [
                {"code": COM_BACKEND_UNAVAILABLE, "message": "No registered WPS ProgID detected for spreadsheets."}
            ],
            "data": {"capabilities": capabilities},
        }
    params_json = json.dumps(
        {
            "prog_id": prog_id,
            "path": str(Path(path).resolve()),
            "sheet": sheet_name,
            "range": range_address,
            "anchor": anchor,
            "chart_type": CHART_TYPES[chart_type]["xl"],
            "plot_by": PLOT_BY[plot_by],
            "title": title or "",
            "width": float(width),
            "height": float(height),
        }
    )
    script = f"""
$ErrorActionPreference = 'Stop'
$params = @'
{params_json}
'@ | ConvertFrom-Json
{PRE_OPEN_GUARD}
$app = $null; $workbook = $null
try {{
  {ACQUIRE_WPS_APP}
  {HIDE_LAUNCHED_APP}
  {QUIET_ALERTS}
  $wpsPreOpen = Test-WpsPathOpen $app.Workbooks $params.path
  $workbook = Open-WpsDocument $app.Workbooks $params.path $wpsPreOpen
  Assert-WpsPreOpenSaved $wpsPreOpen $workbook
  $sheet = $workbook.Worksheets.Item($params.sheet)
  $source = $sheet.Range($params.range)
  $anchor = $sheet.Range($params.anchor)
  $before = [int]$sheet.ChartObjects().Count
  $object = $sheet.ChartObjects().Add([double]$anchor.Left, [double]$anchor.Top, [double]$params.width, [double]$params.height)
  $chart = $object.Chart
  $chart.ChartType = [int]$params.chart_type
  if ($null -eq $params.plot_by) {{ [void]$chart.SetSourceData($source) }} else {{ [void]$chart.SetSourceData($source, [int]$params.plot_by) }}
  if ($params.title) {{ $chart.HasTitle = $true; $chart.ChartTitle.Text = [string]$params.title }}
  $workbook.Save()
  $title = ''
  if ($chart.HasTitle) {{ $title = [string]$chart.ChartTitle.Text }}
  [pscustomobject]@{{
    ok = $true; backend = 'powershell-com'; prog_id = $params.prog_id; sheet_name = [string]$sheet.Name
    chart_name = [string]$object.Name; chart_type = [int]$chart.ChartType; title = $title
    series_count = [int]$chart.SeriesCollection().Count; charts_before = $before; charts_after = [int]$sheet.ChartObjects().Count
  }} | ConvertTo-Json -Depth 5 -Compress
}} catch {{
  [pscustomobject]@{{ ok = $false; error_message = $_.Exception.Message }} | ConvertTo-Json -Depth 5 -Compress
  exit 2
}} finally {{
  if ($workbook -ne $null) {{ if (-not $wpsPreOpen) {{ try {{ $workbook.Close($false) }} catch {{ }} }}; try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($workbook) }} catch {{ }} }}
  if ($app -ne $null) {{ try {{ {RELEASE_WPS_APP} }} catch {{ }}; try {{ [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) }} catch {{ }} }}
  [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}}
"""
    payload, failure = run_powershell_script(script)
    if failure is not None:
        return failure
    if not payload.get("ok"):
        return {
            "ok": False,
            "errors": [
                {"code": COM_OPERATION_FAILED, "message": payload.get("error_message", "WPS could not add the chart.")}
            ],
            "data": {"diagnostic": payload},
        }
    return {"ok": True, "errors": [], "data": payload}


def _refuse(code: str, message: str, data: dict[str, Any] | None = None):
    return False, data or {}, [{"code": code, "message": message}], False


@coordinated_mutation
@atomic_mutation
def create_spreadsheet_chart(
    document_id: str,
    sheet_name: str,
    range_address: str,
    chart_type: str,
    request_id: str,
    title: str | None = None,
    anchor: str | None = None,
    plot_by: str = "auto",
    width: float = 480.0,
    height: float = 288.0,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    """Add a chart of range_address to sheet_name, with backup, read-back and rollback."""
    replay = replay_operation(
        request_id,
        "spreadsheet-chart-create",
        {
            "document_id": document_id,
            "sheet_name": sheet_name,
            "range": range_address,
            "chart_type": chart_type,
            "title": title,
            "dry_run": dry_run,
        },
        workspace,
    )
    if replay is not None:
        return replay
    if chart_type not in CHART_TYPES:
        return _refuse("INVALID_ARGUMENT", f"chart_type must be one of: {', '.join(CHART_TYPES)}.")
    if plot_by not in PLOT_BY:
        return _refuse("INVALID_ARGUMENT", "series_in must be auto, rows or columns.")
    if not (50 <= width <= 2000 and 50 <= height <= 2000):
        return _refuse("INVALID_ARGUMENT", "width and height are 50 to 2000 points.")
    title = title.strip() if title else None
    if title and len(title) > 255:
        return _refuse("INVALID_ARGUMENT", "The title is at most 255 characters.")
    try:
        min_col, min_row, max_col, max_row = range_boundaries(range_address.replace("$", "").upper())
    except (ValueError, TypeError):
        return _refuse("INVALID_RANGE", f"Not a cell range: {range_address!r}; use A1:D10.")
    if None in (min_col, min_row, max_col, max_row):
        return _refuse("INVALID_RANGE", "Give a bounded range such as A1:D10, not whole rows or columns.")
    cells = (max_col - min_col + 1) * (max_row - min_row + 1)
    if cells < 2 or cells > MAX_CELLS:
        return _refuse("INVALID_RANGE", f"The range must hold 2 to {MAX_CELLS} cells; it holds {cells}.")
    normalized_range = f"{get_column_letter(min_col)}{min_row}:{get_column_letter(max_col)}{max_row}"
    if anchor is None:
        anchor_address = f"{get_column_letter(max_col + 2)}{min_row}"
    else:
        try:
            a_col, a_row, a_col2, a_row2 = range_boundaries(anchor.replace("$", "").upper())
        except (ValueError, TypeError):
            return _refuse("INVALID_RANGE", f"Not a cell: {anchor!r}.")
        if None in (a_col, a_row) or (a_col, a_row) != (a_col2, a_row2):
            return _refuse("INVALID_RANGE", "anchor is one cell, such as F2.")
        anchor_address = f"{get_column_letter(a_col)}{a_row}"

    document = get_document(document_id, workspace)
    if not document:
        return _refuse("DOCUMENT_NOT_FOUND", f"Document not registered: {document_id}")
    if document["component"] != "spreadsheets":
        return _refuse(
            "UNSUPPORTED_COMPONENT", "spreadsheet-chart-create requires a spreadsheet document.", {"document": document}
        )
    path = Path(document["path"])
    if not path.exists():
        return _refuse(INPUT_FILE_NOT_FOUND, f"Input file not found: {path}", {"document": document})
    if path.suffix.casefold() not in {".xlsx", ".xlsm"}:
        return _refuse("INVALID_INPUT", "spreadsheet-chart-create works on .xlsx files; convert other formats first.")
    held = probe_file_not_held(path, read_only=True, what="workbook")
    if held is not None:
        return False, {"document_id": document_id, "path": str(path)}, [held], False

    workbook = load_workbook_guarded(path, data_only=True, read_only=True)
    try:
        if sheet_name not in workbook.sheetnames:
            return _refuse(
                "SHEET_NOT_FOUND", f"Worksheet not found: {sheet_name}", {"sheet_names": list(workbook.sheetnames)}
            )
        numbers = sum(
            1
            for row in workbook[sheet_name].iter_rows(
                min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col, values_only=True
            )
            for value in row
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        )
    finally:
        workbook.close()
    if numbers == 0:
        return _refuse("INVALID_RANGE", f"{sheet_name}!{normalized_range} holds no numbers to chart.")
    before = sheet_charts(path, sheet_name)
    preview = {
        "document_id": document_id,
        "path": str(path),
        "sheet_name": sheet_name,
        "range": range_address,
        "normalized_range": normalized_range,
        "chart_type": chart_type,
        "title": title,
        "anchor": anchor_address,
        "series_in": plot_by,
        "width": width,
        "height": height,
        "numeric_cells": numbers,
        "charts_before": len(before),
        "dry_run": dry_run,
    }
    if dry_run:
        return True, preview, [], False

    backup_ok, backup, backup_errors, backup_replayed = create_backup(
        document_id, f"{request_id}:backup", workspace=workspace
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup}, backup_errors, False
    mutation = guarded_com_mutation(
        path,
        backup,
        lambda: _run_spreadsheet_chart_create_com(
            str(path), sheet_name, normalized_range, anchor_address, chart_type, plot_by, title, width, height
        ),
    )
    if not mutation["ok"]:
        return False, {"preview": preview, "backup": backup, "mutation": mutation["data"]}, mutation["errors"], False

    after = sheet_charts(path, sheet_name)
    remaining = [_signature(chart) for chart in before]
    added = []
    for chart in after:
        signature = _signature(chart)
        if signature in remaining:
            remaining.remove(signature)
        else:
            added.append(chart)
    expected = CHART_TYPES[chart_type]
    bounds = (min_col, min_row, max_col, max_row)
    new_chart = added[0] if len(added) == 1 else None
    checks = {
        "one_chart_added": len(after) == len(before) + 1 and len(added) == 1,
        "type_matches": bool(
            new_chart
            and any(
                kind["element"] == expected["element"]
                and (expected["bar_dir"] is None or kind["bar_dir"] == expected["bar_dir"])
                for kind in new_chart["types"]
            )
        ),
        "title_matches": bool(new_chart and (not title or new_chart["title"] == title)),
        "series_inside_range": bool(
            new_chart and new_chart["refs"] and all(_ref_inside(ref, sheet_name, bounds) for ref in new_chart["refs"])
        ),
    }
    validation_passed = all(checks.values())
    result = {
        **preview,
        "dry_run": False,
        "backup": backup,
        "backup_replayed": backup_replayed,
        "chart_backend": mutation["data"].get("backend"),
        "wps_report": {
            key: mutation["data"].get(key)
            for key in ("chart_name", "chart_type", "title", "series_count", "charts_before", "charts_after")
        },
        "chart_read_back": new_chart,
        "charts_after": len(after),
        "checks": checks,
        "validation_passed": validation_passed,
    }
    if not validation_passed:
        failed = ", ".join(name for name, passed in checks.items() if not passed)
        return (
            False,
            result,
            [{"code": "VALIDATION_FAILED", "message": f"The saved chart did not read back: {failed}."}],
            False,
        )
    post_error = verify_post_com_source(path, mutation)
    if post_error is not None:
        return False, result, [post_error], False
    record_operation(request_id, "spreadsheet-chart-create", result, workspace)
    return True, result, [], False
