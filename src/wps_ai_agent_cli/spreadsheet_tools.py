"""Sort, conditional formatting and data validation on a worksheet range (C-05).

Three more spreadsheet operations of the same shape as the others: offline checks, a backup, one WPS COM call
(guarded_com_mutation) that changes the range and saves, an offline read-back of the saved workbook with
openpyxl, and a rollback from the backup when the read-back does not match (atomic_mutation). They go through
WPS rather than openpyxl because saving a workbook with openpyxl drops what it does not model (charts, images,
pivot caches), which would damage the user's file.

What the read-back can prove differs by operation:

- sort: the data rows are the same rows as before, in an order consistent with the keys. Numbers and dates are
  checked strictly; text is ordered by WPS's own collation (pinyin for Chinese), which is not reproduced here, so
  for a text key only that equal keys ended up next to each other is checked, and the result says so.
- conditional formatting: one more rule of the requested kind on exactly that range, with the requested
  operator and values.
- data validation: the range carries one rule of the requested type, operator and values.
"""

from __future__ import annotations

import datetime as _dt
import functools
import json
import re
from pathlib import Path
from typing import Any

from openpyxl.utils.cell import column_index_from_string, get_column_letter, range_boundaries

from .atomic_mutation import atomic_mutation
from .backups import create_backup, guarded_com_mutation, verify_post_com_source
from .capabilities import probe_wps_capabilities
from .errors import COM_BACKEND_UNAVAILABLE, COM_OPERATION_FAILED, FORMULA_FUNCTION_NOT_ALLOWED, INPUT_FILE_NOT_FOUND
from .file_hold import probe_file_not_held
from .formula_safety import forbidden_formula_function
from .mutation_lock import coordinated_mutation
from .ooxml import load_workbook_guarded
from .operations import record_operation, replay_operation
from .powershell_runner import run_powershell_script
from .sessions import get_document
from .wps_script_snippets import ACQUIRE_WPS_APP, HIDE_LAUNCHED_APP, PRE_OPEN_GUARD, QUIET_ALERTS, RELEASE_WPS_APP

MAX_SORT_CELLS = 200_000
COLOR = re.compile(r"^#?[0-9A-Fa-f]{6}$")

# XlFormatConditionOperator / openpyxl operator names.
OPERATORS = {
    "between": (1, "between"),
    "not-between": (2, "notBetween"),
    "equal": (3, "equal"),
    "not-equal": (4, "notEqual"),
    "greater": (5, "greaterThan"),
    "less": (6, "lessThan"),
    "greater-or-equal": (7, "greaterThanOrEqual"),
    "less-or-equal": (8, "lessThanOrEqual"),
}
TWO_VALUES = {"between", "not-between"}
FORMAT_KINDS = ("cell-value", "color-scale", "data-bar", "duplicates")
FORMAT_RULE_TYPES = {
    "cell-value": "cellIs",
    "color-scale": "colorScale",
    "data-bar": "dataBar",
    "duplicates": "duplicateValues",
}
# XlDVType / openpyxl type names.
VALIDATION_TYPES = {
    "whole": (1, "whole"),
    "decimal": (2, "decimal"),
    "list": (3, "list"),
    "date": (4, "date"),
    "text-length": (6, "textLength"),
}

Outcome = tuple[bool, dict[str, Any], list[dict[str, str]], bool]


class _Refusal(Exception):
    def __init__(self, code: str, message: str, data: dict[str, Any] | None = None):
        super().__init__(message)
        self.error = {"code": code, "message": message}
        self.data = data or {}


# ---------------------------------------------------------------------------------------------------- shared
def _bounded_range(address: str) -> tuple[str, tuple[int, int, int, int]]:
    try:
        bounds = range_boundaries(str(address).replace("$", "").upper())
    except (ValueError, TypeError) as exc:
        raise _Refusal("INVALID_RANGE", f"Not a cell range: {address!r}; use A1:D10.") from exc
    if None in bounds:
        raise _Refusal("INVALID_RANGE", "Give a bounded range such as A1:D10, not whole rows or columns.")
    min_col, min_row, max_col, max_row = bounds
    return f"{get_column_letter(min_col)}{min_row}:{get_column_letter(max_col)}{max_row}", bounds


def _spreadsheet(document_id: str, command: str, workspace: str | Path) -> Path:
    document = get_document(document_id, workspace)
    if not document:
        raise _Refusal("DOCUMENT_NOT_FOUND", f"Document not registered: {document_id}")
    if document["component"] != "spreadsheets":
        raise _Refusal("UNSUPPORTED_COMPONENT", f"{command} requires a spreadsheet document.", {"document": document})
    path = Path(document["path"])
    if not path.exists():
        raise _Refusal(INPUT_FILE_NOT_FOUND, f"Input file not found: {path}", {"document": document})
    if path.suffix.casefold() not in {".xlsx", ".xlsm"}:
        raise _Refusal("INVALID_INPUT", f"{command} works on .xlsx files; convert other formats first.")
    held = probe_file_not_held(path, read_only=True, what="workbook")
    if held is not None:
        raise _Refusal(held["code"], held["message"], {"document_id": document_id, "path": str(path)})
    return path


def _sheet(workbook, sheet_name: str):
    if sheet_name not in workbook.sheetnames:
        raise _Refusal(
            "SHEET_NOT_FOUND", f"Worksheet not found: {sheet_name}", {"sheet_names": list(workbook.sheetnames)}
        )
    return workbook[sheet_name]


def _rgb(color: str) -> int:
    value = color.lstrip("#")
    return int(value[0:2], 16) + (int(value[2:4], 16) << 8) + (int(value[4:6], 16) << 16)


def _criterion(value: Any, what: str) -> str:
    """A rule value as WPS takes it: a number, a formula (=...), or text (quoted)."""
    if isinstance(value, bool) or value is None or (isinstance(value, str) and not value.strip()):
        raise _Refusal("INVALID_ARGUMENT", f"{what} is missing.")
    if isinstance(value, (int, float)):
        return repr(value) if isinstance(value, float) else str(value)
    text = str(value).strip()
    try:
        float(text)
        return text
    except ValueError:
        pass
    if text.startswith("="):
        forbidden = forbidden_formula_function(text)
        if forbidden:
            raise _Refusal(FORMULA_FUNCTION_NOT_ALLOWED, f"{what} uses {forbidden}(), which is not allowed.")
        return text
    return '="' + text.replace('"', '""') + '"'


def _stored(criterion: str) -> str:
    """How a rule value reads back from the saved file: without the leading = ."""
    return criterion[1:] if criterion.startswith("=") else criterion


def _run_sheet_script(path: str, sheet_name: str, params: dict[str, Any], body: str) -> dict[str, Any]:
    """Open the workbook in WPS, run body with $sheet and $params, save, and return the $out it fills."""
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
    params_json = json.dumps({**params, "prog_id": prog_id, "path": str(Path(path).resolve()), "sheet": sheet_name})
    script = f"""
$ErrorActionPreference = 'Stop'
$params = @'
{params_json}
'@ | ConvertFrom-Json
{PRE_OPEN_GUARD}
$app = $null; $workbook = $null
$missing = [System.Reflection.Missing]::Value
try {{
  {ACQUIRE_WPS_APP}
  {HIDE_LAUNCHED_APP}
  {QUIET_ALERTS}
  $wpsPreOpen = Test-WpsPathOpen $app.Workbooks $params.path
  $workbook = Open-WpsDocument $app.Workbooks $params.path $wpsPreOpen
  Assert-WpsPreOpenSaved $wpsPreOpen $workbook
  $sheet = $workbook.Worksheets.Item($params.sheet)
  $range = $sheet.Range($params.range)
  $out = @{{ ok = $true; backend = 'powershell-com'; prog_id = $params.prog_id; sheet_name = [string]$sheet.Name }}
{body}
  $workbook.Save()
  [pscustomobject]$out | ConvertTo-Json -Depth 5 -Compress
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
            "errors": [{"code": COM_OPERATION_FAILED, "message": payload.get("error_message", "WPS could not do it.")}],
            "data": {"diagnostic": payload},
        }
    return {"ok": True, "errors": [], "data": payload}


def _commit(
    command: str,
    document_id: str,
    request_id: str,
    path: Path,
    preview: dict[str, Any],
    run_com,
    read_back,
    workspace: str | Path,
) -> Outcome:
    """Backup, the WPS change, the read-back and the operation record; a failure is rolled back by the caller."""
    backup_ok, backup, backup_errors, backup_replayed = create_backup(
        document_id, f"{request_id}:backup", workspace=workspace
    )
    if not backup_ok:
        return False, {"preview": preview, "backup": backup}, backup_errors, False
    mutation = guarded_com_mutation(path, backup, run_com)
    if not mutation["ok"]:
        return False, {"preview": preview, "backup": backup, "mutation": mutation["data"]}, mutation["errors"], False
    checks, details = read_back()
    validation_passed = all(checks.values())
    result = {
        **preview,
        "dry_run": False,
        "backup": backup,
        "backup_replayed": backup_replayed,
        "wps_report": {key: value for key, value in mutation["data"].items() if key not in {"ok", "prog_id"}},
        "read_back": details,
        "checks": checks,
        "validation_passed": validation_passed,
    }
    if not validation_passed:
        failed = ", ".join(name for name, passed in checks.items() if not passed)
        return (
            False,
            result,
            [{"code": "VALIDATION_FAILED", "message": f"The saved workbook did not read back: {failed}."}],
            False,
        )
    post_error = verify_post_com_source(path, mutation)
    if post_error is not None:
        return False, result, [post_error], False
    record_operation(request_id, command, result, workspace)
    return True, result, [], False


def _guarded(operation):
    """Turn a _Refusal raised before any write into the usual (False, data, errors, False)."""

    @functools.wraps(operation)  # keeps the signature: atomic_mutation reads document_id and request_id from it
    def run(*args, **kwargs) -> Outcome:
        try:
            return operation(*args, **kwargs)
        except _Refusal as refusal:
            return False, refusal.data, [refusal.error], False

    return run


# ------------------------------------------------------------------------------------------------------- sort
def parse_sort_keys(
    keys: list[str], bounds: tuple[int, int, int, int], header: list[Any] | None
) -> list[dict[str, Any]]:
    """[{"column": index, "letter": "B", "descending": bool}] from "B:desc" or "销量:asc" (a header name)."""
    min_col, _min_row, max_col, _max_row = bounds
    if not keys or len(keys) > 3:
        raise _Refusal("INVALID_ARGUMENT", "Give one to three sort keys, such as B:desc or 销量:asc.")
    parsed = []
    for key in keys:
        name, _, order = str(key).rpartition(":") if ":" in str(key) else (str(key), "", "asc")
        order = order.strip().lower() or "asc"
        if order not in {"asc", "desc"}:
            raise _Refusal("INVALID_ARGUMENT", f"Sort order must be asc or desc: {key!r}.")
        name = name.strip()
        column = None
        if re.fullmatch(r"[A-Za-z]{1,3}", name):
            column = column_index_from_string(name.upper())
        elif header is not None:
            matches = [min_col + index for index, value in enumerate(header) if str(value).strip() == name]
            column = matches[0] if len(matches) == 1 else None
        if column is None or not min_col <= column <= max_col:
            raise _Refusal("INVALID_ARGUMENT", f"Sort key {name!r} is not a column of the range (or a unique header).")
        parsed.append({"column": column, "letter": get_column_letter(column), "descending": order == "desc"})
    return parsed


def _comparable(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, _dt.datetime):
        return value.timestamp()
    if isinstance(value, _dt.date):
        return _dt.datetime(value.year, value.month, value.day).timestamp()
    return None


def check_sorted(rows: list[tuple], keys: list[dict[str, Any]], min_col: int) -> tuple[bool, str]:
    """Whether rows are ordered by keys as far as can be told without WPS's text collation."""
    strictness = "strict"
    for upper, lower in zip(rows, rows[1:], strict=False):
        for key in keys:
            a, b = upper[key["column"] - min_col], lower[key["column"] - min_col]
            if a == b:
                continue
            if a is None or b is None or a == "" or b == "":
                if a is None or a == "":
                    return False, "blank cells sort last in either order"
                break
            x, y = _comparable(a), _comparable(b)
            if x is None or y is None:
                strictness = "text keys: grouping only"
                break
            if (x > y) != key["descending"] and x != y:
                return False, f"{key['letter']}: {a!r} comes before {b!r}"
            break
    if strictness != "strict":
        first = keys[0]["column"] - min_col
        seen, last = set(), object()
        for row in rows:
            if row[first] != last:
                if row[first] in seen:
                    return False, f"equal values of {keys[0]['letter']} are not next to each other"
                seen.add(row[first])
                last = row[first]
    return True, strictness


def _run_sort_com(path: str, sheet_name: str, range_address: str, keys: list[dict[str, Any]], has_header: bool):
    body = """
  $keys = @($params.keys)
  $k = @($missing, $missing, $missing); $o = @(1, 1, 1)
  for ($i = 0; $i -lt $keys.Count; $i++) {
    $k[$i] = $sheet.Range($keys[$i].cell)
    if ($keys[$i].descending) { $o[$i] = 2 }
  }
  $header = 2; if ($params.has_header) { $header = 1 }
  [void]$range.Sort($k[0], $o[0], $k[1], $missing, $o[1], $k[2], $o[2], $header)
  $out.sorted_rows = [int]$range.Rows.Count
"""
    first_row = int(re.search(r"\d+", range_address).group())
    params = {
        "range": range_address,
        "keys": [{"cell": f"{key['letter']}{first_row}", "descending": key["descending"]} for key in keys],
        "has_header": has_header,
    }
    return _run_sheet_script(path, sheet_name, params, body)


@coordinated_mutation
@atomic_mutation
@_guarded
def sort_spreadsheet_range(
    document_id: str,
    sheet_name: str,
    range_address: str,
    keys: list[str],
    request_id: str,
    has_header: bool = True,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> Outcome:
    """Sort the rows of a range by up to three columns, in WPS, with backup, read-back and rollback."""
    replay = replay_operation(
        request_id,
        "spreadsheet-sort",
        {
            "document_id": document_id,
            "sheet_name": sheet_name,
            "range": range_address,
            "keys": keys,
            "dry_run": dry_run,
        },
        workspace,
    )
    if replay is not None:
        return replay
    normalized, bounds = _bounded_range(range_address)
    min_col, min_row, max_col, max_row = bounds
    if (max_col - min_col + 1) * (max_row - min_row + 1) > MAX_SORT_CELLS:
        raise _Refusal("INVALID_RANGE", f"Sorting is limited to {MAX_SORT_CELLS} cells.")
    if max_row - min_row + 1 < (3 if has_header else 2):
        raise _Refusal("INVALID_RANGE", "The range needs at least two data rows to sort.")
    path = _spreadsheet(document_id, "spreadsheet-sort", workspace)

    def rows_of(data_only: bool):
        workbook = load_workbook_guarded(path, data_only=data_only)
        try:
            sheet = _sheet(workbook, sheet_name)
            if not data_only:
                for merged in sheet.merged_cells.ranges:
                    if not (
                        merged.max_col < min_col
                        or merged.min_col > max_col
                        or merged.max_row < min_row
                        or merged.min_row > max_row
                    ):
                        raise _Refusal(
                            "INVALID_RANGE", f"The range overlaps merged cells {merged.coord}; WPS cannot sort it."
                        )
            cells = list(sheet.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col))
            if not data_only:
                formulas = [cell.coordinate for row in cells for cell in row if cell.data_type == "f"]
                if formulas:
                    raise _Refusal(
                        "SORT_RANGE_HAS_FORMULAS",
                        f"The range holds formulas ({', '.join(formulas[:5])}); sorting would move them and change what "
                        "they refer to. Sort a range of values, or copy the values first.",
                    )
            return [tuple(cell.value for cell in row) for row in cells]
        finally:
            workbook.close()

    rows_of(data_only=False)
    before = rows_of(data_only=True)
    header = list(before[0]) if has_header else None
    parsed = parse_sort_keys(keys, bounds, header)
    data_before = before[1:] if has_header else before
    preview = {
        "document_id": document_id,
        "path": str(path),
        "sheet_name": sheet_name,
        "range": range_address,
        "normalized_range": normalized,
        "keys": keys,
        "sort_keys": [{"column": key["letter"], "order": "desc" if key["descending"] else "asc"} for key in parsed],
        "has_header": has_header,
        "data_rows": len(data_before),
        "dry_run": dry_run,
    }
    if dry_run:
        return True, preview, [], False

    def read_back():
        after = rows_of(data_only=True)
        data_after = after[1:] if has_header else after
        ordered, how = check_sorted(data_after, parsed, min_col)

        def key(row):
            return json.dumps(row, default=str, ensure_ascii=False)

        same_rows = sorted(map(key, data_before)) == sorted(map(key, data_after))
        header_kept = not has_header or after[0] == before[0]
        return (
            {"same_rows": same_rows, "header_kept": header_kept, "ordered": ordered},
            {"order_check": how, "first_rows": [list(row) for row in data_after[:3]]},
        )

    return _commit(
        "spreadsheet-sort",
        document_id,
        request_id,
        path,
        preview,
        lambda: _run_sort_com(str(path), sheet_name, normalized, parsed, has_header),
        read_back,
        workspace,
    )


# ------------------------------------------------------------------------------------- conditional formatting
def _conditional_rules(path: Path, sheet_name: str) -> list[dict[str, Any]]:
    workbook = load_workbook_guarded(path)
    try:
        sheet = _sheet(workbook, sheet_name)
        rules = []
        for formatting in sheet.conditional_formatting:
            for rule in formatting.rules:
                rules.append(
                    {
                        "range": str(formatting.sqref),
                        "type": rule.type,
                        "operator": rule.operator,
                        "formula": [str(item) for item in (rule.formula or [])],
                    }
                )
        return rules
    finally:
        workbook.close()


def _run_conditional_format_com(path: str, sheet_name: str, params: dict[str, Any]):
    body = """
  if ($params.replace) { [void]$range.FormatConditions.Delete() }
  $before = [int]$range.FormatConditions.Count
  switch ($params.kind) {
    'cell-value' {
      if ($params.formula2) { $rule = $range.FormatConditions.Add(1, [int]$params.operator, $params.formula1, $params.formula2) }
      else { $rule = $range.FormatConditions.Add(1, [int]$params.operator, $params.formula1) }
      $rule.Interior.Color = [int]$params.fill
      if ($null -ne $params.font) { $rule.Font.Color = [int]$params.font }
    }
    'duplicates' {
      $rule = $range.FormatConditions.AddUniqueValues()
      $rule.DupeUnique = 1
      $rule.Interior.Color = [int]$params.fill
      if ($null -ne $params.font) { $rule.Font.Color = [int]$params.font }
    }
    'color-scale' { [void]$range.FormatConditions.AddColorScale([int]$params.color_scale_points) }
    'data-bar' { [void]$range.FormatConditions.AddDatabar() }
  }
  $out.rules_before = $before
  $out.rules_after = [int]$range.FormatConditions.Count
"""
    return _run_sheet_script(path, sheet_name, params, body)


@coordinated_mutation
@atomic_mutation
@_guarded
def add_conditional_format(
    document_id: str,
    sheet_name: str,
    range_address: str,
    kind: str,
    request_id: str,
    operator: str | None = None,
    value1: Any = None,
    value2: Any = None,
    fill_color: str = "#FFC7CE",
    font_color: str | None = "#9C0006",
    color_scale_points: int = 3,
    replace: bool = False,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> Outcome:
    """Add one conditional format rule to a range, in WPS, with backup, read-back and rollback."""
    replay = replay_operation(
        request_id,
        "spreadsheet-conditional-format",
        {
            "document_id": document_id,
            "sheet_name": sheet_name,
            "range": range_address,
            "kind": kind,
            "dry_run": dry_run,
        },
        workspace,
    )
    if replay is not None:
        return replay
    if kind not in FORMAT_KINDS:
        raise _Refusal("INVALID_ARGUMENT", f"kind must be one of: {', '.join(FORMAT_KINDS)}.")
    normalized, _bounds = _bounded_range(range_address)
    params: dict[str, Any] = {
        "range": normalized,
        "kind": kind,
        "replace": replace,
        "color_scale_points": color_scale_points,
    }
    expected_operator, expected_formula = None, []
    if kind == "cell-value":
        if operator not in OPERATORS:
            raise _Refusal("INVALID_ARGUMENT", f"operator must be one of: {', '.join(OPERATORS)}.")
        formula1 = _criterion(value1, "value1")
        formula2 = _criterion(value2, "value2") if operator in TWO_VALUES else None
        params.update({"operator": OPERATORS[operator][0], "formula1": formula1, "formula2": formula2})
        expected_operator = OPERATORS[operator][1]
        expected_formula = [_stored(formula1)] + ([_stored(formula2)] if formula2 else [])
    if kind in {"cell-value", "duplicates"}:
        for name, color in (("fill_color", fill_color), ("font_color", font_color)):
            if color is not None and not COLOR.match(color):
                raise _Refusal("INVALID_ARGUMENT", f"{name} must be #RRGGBB.")
        params["fill"] = _rgb(fill_color)
        params["font"] = _rgb(font_color) if font_color else None
    if kind == "color-scale" and color_scale_points not in (2, 3):
        raise _Refusal("INVALID_ARGUMENT", "color_scale_points is 2 or 3.")
    path = _spreadsheet(document_id, "spreadsheet-conditional-format", workspace)
    before = _conditional_rules(path, sheet_name)
    preview = {
        "document_id": document_id,
        "path": str(path),
        "sheet_name": sheet_name,
        "range": range_address,
        "normalized_range": normalized,
        "kind": kind,
        "operator": operator,
        "values": [value for value in (value1, value2) if value is not None],
        "replace": replace,
        "rules_on_sheet_before": len(before),
        "dry_run": dry_run,
    }
    if dry_run:
        return True, preview, [], False

    def matches(rule: dict[str, Any]) -> bool:
        if rule["range"] != normalized or rule["type"] != FORMAT_RULE_TYPES[kind]:
            return False
        if kind == "cell-value":
            return (
                rule["operator"] == expected_operator and [item.strip() for item in rule["formula"]] == expected_formula
            )
        return True

    def read_back():
        after = _conditional_rules(path, sheet_name)
        if replace:
            # The range's earlier rules were deleted, so it now carries exactly the new one.
            on_range = [rule for rule in after if rule["range"] == normalized]
            checks = {
                "one_rule_on_range": len(on_range) == 1,
                "rule_matches": len(on_range) == 1 and matches(on_range[0]),
            }
            return checks, {"rules_on_sheet_after": len(after), "rules_on_range": on_range}
        remaining = list(before)
        new = []
        for rule in after:
            if rule in remaining:
                remaining.remove(rule)
            else:
                new.append(rule)
        checks = {
            "one_rule_added": len(after) == len(before) + 1 and len(new) == 1 and not remaining,
            "rule_matches": len(new) == 1 and matches(new[0]),
        }
        return checks, {"rules_on_sheet_after": len(after), "new_rules": new}

    return _commit(
        "spreadsheet-conditional-format",
        document_id,
        request_id,
        path,
        preview,
        lambda: _run_conditional_format_com(str(path), sheet_name, params),
        read_back,
        workspace,
    )


# ---------------------------------------------------------------------------------------------- data validation
def _validations(path: Path, sheet_name: str) -> list[dict[str, Any]]:
    workbook = load_workbook_guarded(path)
    try:
        sheet = _sheet(workbook, sheet_name)
        return [
            {
                "ranges": str(item.sqref).split(),
                "type": item.type,
                "operator": item.operator,
                "formula1": item.formula1,
                "formula2": item.formula2,
                "allow_blank": bool(item.allow_blank),
                "error": item.error,
                "prompt": item.prompt,
            }
            for item in sheet.data_validations.dataValidation
        ]
    finally:
        workbook.close()


def _date_formula(value: Any) -> str:
    text = str(value).strip()
    if text.startswith("="):
        return _criterion(text, "value")
    try:
        day = _dt.date.fromisoformat(text)
    except ValueError as exc:
        raise _Refusal("INVALID_ARGUMENT", f"Dates are YYYY-MM-DD or a formula: {value!r}.") from exc
    return f"=DATE({day.year},{day.month},{day.day})"


def _same_formula(stored: str | None, expected: str, validation_type: str) -> bool:
    if stored is None:
        return False
    stored = stored.strip()
    if stored == expected:
        return True
    found = re.fullmatch(r"DATE\((\d+),(\d+),(\d+)\)", expected)
    if validation_type == "date" and found:
        try:
            serial = float(stored)
        except ValueError:
            return False
        day = _dt.date(1899, 12, 30) + _dt.timedelta(days=int(serial))
        return day == _dt.date(*(int(part) for part in found.groups()))
    try:
        return float(stored) == float(expected)
    except ValueError:
        return False


def _run_validation_com(path: str, sheet_name: str, params: dict[str, Any]):
    body = """
  $v = $range.Validation
  [void]$v.Delete()
  $operator = $missing; if ($null -ne $params.operator) { $operator = [int]$params.operator }
  $formula2 = $missing; if ($params.formula2) { $formula2 = $params.formula2 }
  [void]$v.Add([int]$params.type, 1, $operator, $params.formula1, $formula2)
  $v.IgnoreBlank = [bool]$params.allow_blank
  if ($params.input_message) { $v.InputMessage = [string]$params.input_message; $v.ShowInput = $true }
  if ($params.error_message) { $v.ErrorMessage = [string]$params.error_message }
  $v.ShowError = $true
  $out.validation_type = [int]$v.Type
  $out.formula1 = [string]$v.Formula1
"""
    return _run_sheet_script(path, sheet_name, params, body)


@coordinated_mutation
@atomic_mutation
@_guarded
def set_data_validation(
    document_id: str,
    sheet_name: str,
    range_address: str,
    validation_type: str,
    request_id: str,
    values: list[str] | None = None,
    operator: str | None = None,
    value1: Any = None,
    value2: Any = None,
    allow_blank: bool = True,
    input_message: str | None = None,
    error_message: str | None = None,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> Outcome:
    """Set the data validation of a range (replacing any it had), in WPS, with backup, read-back and rollback."""
    replay = replay_operation(
        request_id,
        "spreadsheet-data-validation",
        {
            "document_id": document_id,
            "sheet_name": sheet_name,
            "range": range_address,
            "validation_type": validation_type,
            "dry_run": dry_run,
        },
        workspace,
    )
    if replay is not None:
        return replay
    if validation_type not in VALIDATION_TYPES:
        raise _Refusal("INVALID_ARGUMENT", f"type must be one of: {', '.join(VALIDATION_TYPES)}.")
    normalized, _bounds = _bounded_range(range_address)
    xl_type, stored_type = VALIDATION_TYPES[validation_type]
    params: dict[str, Any] = {
        "range": normalized,
        "type": xl_type,
        "allow_blank": allow_blank,
        "input_message": (input_message or "")[:255],
        "error_message": (error_message or "")[:255],
        "operator": None,
        "formula2": None,
    }
    if validation_type == "list":
        items = [str(item).strip() for item in (values or []) if str(item).strip()]
        if len(items) == 1 and items[0].startswith("="):
            params["formula1"] = _criterion(items[0], "values")
            expected1 = _stored(params["formula1"])
        else:
            if not items or any("," in item or '"' in item for item in items):
                raise _Refusal(
                    "INVALID_ARGUMENT", "values is a list of choices without commas or quotes, or one =range."
                )
            joined = ",".join(items)
            if len(joined) > 255:
                raise _Refusal(
                    "INVALID_ARGUMENT",
                    "A list of choices is at most 255 characters; put them in cells and give =range.",
                )
            params["formula1"] = joined
            expected1 = f'"{joined}"'
        expected_operator, expected2 = None, None
    else:
        operator = operator or "between"
        if operator not in OPERATORS:
            raise _Refusal("INVALID_ARGUMENT", f"operator must be one of: {', '.join(OPERATORS)}.")
        convert = _date_formula if validation_type == "date" else (lambda value: _criterion(value, "value"))
        if value1 is None or (operator in TWO_VALUES and value2 is None):
            raise _Refusal(
                "INVALID_ARGUMENT", f"{operator} needs {'value1 and value2' if operator in TWO_VALUES else 'value1'}."
            )
        params["formula1"] = convert(value1)
        params["formula2"] = convert(value2) if operator in TWO_VALUES else None
        params["operator"] = OPERATORS[operator][0]
        expected_operator = OPERATORS[operator][1]
        expected1 = _stored(params["formula1"])
        expected2 = _stored(params["formula2"]) if params["formula2"] else None
    path = _spreadsheet(document_id, "spreadsheet-data-validation", workspace)
    before = _validations(path, sheet_name)
    preview = {
        "document_id": document_id,
        "path": str(path),
        "sheet_name": sheet_name,
        "range": range_address,
        "normalized_range": normalized,
        "validation_type": validation_type,
        "operator": operator if validation_type != "list" else None,
        "formula1": params["formula1"],
        "formula2": params["formula2"],
        "validations_on_sheet_before": len(before),
        "dry_run": dry_run,
    }
    if dry_run:
        return True, preview, [], False

    def read_back():
        after = _validations(path, sheet_name)
        covering = [item for item in after if normalized in item["ranges"]]
        rule = covering[0] if len(covering) == 1 else None
        operator_ok = bool(rule) and (expected_operator is None or (rule["operator"] or "between") == expected_operator)
        return (
            {
                "one_rule_on_range": rule is not None,
                "type_matches": bool(rule) and rule["type"] == stored_type,
                "operator_matches": operator_ok,
                "values_match": bool(rule)
                and _same_formula(rule["formula1"], expected1, validation_type)
                and (expected2 is None or _same_formula(rule["formula2"], expected2, validation_type)),
            },
            {"rule": rule, "validations_on_sheet_after": len(after)},
        )

    return _commit(
        "spreadsheet-data-validation",
        document_id,
        request_id,
        path,
        preview,
        lambda: _run_validation_com(str(path), sheet_name, params),
        read_back,
        workspace,
    )
