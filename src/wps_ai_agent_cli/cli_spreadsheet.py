"""Spreadsheet document commands."""

from __future__ import annotations

import json

from .cli_common import BACKEND
from .models import CommandResponse, ValidationResult
from .spreadsheet_inspect import inspect_spreadsheet_range
from .spreadsheet_ops import (
    copy_spreadsheet_sheet,
    create_spreadsheet_sheet,
    delete_spreadsheet_sheet,
    list_spreadsheet_sheets,
    read_spreadsheet_range,
    rename_spreadsheet_sheet,
    set_spreadsheet_sheet_tab_color,
    set_spreadsheet_sheet_visibility,
    write_spreadsheet_formulas,
    write_spreadsheet_range,
)


def spreadsheet_read_response(
    request_id: str,
    document_id: str,
    range_address: str,
    sheet_name: str | None,
) -> CommandResponse:
    ok, result, errors = read_spreadsheet_range(
        document_id=document_id,
        range_address=range_address,
        sheet_name=sheet_name,
    )
    return CommandResponse(
        ok=ok,
        command="spreadsheet-read",
        request_id=request_id,
        backend=BACKEND,
        summary="Spreadsheet range read completed." if ok else "Spreadsheet range read failed.",
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "range_values_read",
                    "passed": bool(ok and "values" in result),
                    "details": result.get("range"),
                }
            ],
        ),
        errors=errors,
    )


def spreadsheet_sheets_response(request_id: str, document_id: str) -> CommandResponse:
    ok, result, errors = list_spreadsheet_sheets(document_id)
    return CommandResponse(
        ok=ok,
        command="spreadsheet-sheets",
        request_id=request_id,
        backend=BACKEND,
        summary="Spreadsheet worksheets listed." if ok else "Spreadsheet worksheet listing failed.",
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "worksheet_inventory_read_only",
                    "passed": bool(ok and result.get("read_only") and not result.get("saved")),
                    "details": result.get("sheet_count"),
                }
            ],
        ),
        errors=errors,
    )


def spreadsheet_rename_sheet_response(
    request_id: str,
    document_id: str,
    old_name: str,
    new_name: str,
    dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = rename_spreadsheet_sheet(
        document_id,
        old_name,
        new_name,
        request_id,
        dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="spreadsheet-rename-sheet",
        request_id=request_id,
        backend="wps-com" if not dry_run and ok and result.get("saved") else BACKEND,
        summary=(
            "Worksheet rename request replayed."
            if replayed
            else "Worksheet rename preview completed."
            if dry_run and ok
            else "Worksheet renamed."
            if ok
            else "Worksheet rename failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "ordered_sheet_names_read_back",
                    "passed": bool(ok and (dry_run or result.get("validation_passed"))),
                    "details": result.get("sheet_names_read_back", result.get("sheet_names_after")),
                }
            ],
        ),
        errors=errors,
    )


def spreadsheet_create_sheet_response(
    request_id: str,
    document_id: str,
    name: str,
    index: int | None,
    dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = create_spreadsheet_sheet(document_id, name, request_id, index, dry_run)
    return CommandResponse(
        ok=ok,
        command="spreadsheet-create-sheet",
        request_id=request_id,
        backend="wps-com" if not dry_run and ok else BACKEND,
        summary=(
            "Worksheet creation request replayed."
            if replayed
            else "Worksheet creation preview completed."
            if dry_run and ok
            else "Worksheet created."
            if ok
            else "Worksheet creation failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "ordered_sheet_names_read_back",
                    "passed": bool(ok and (dry_run or result.get("validation_passed"))),
                    "details": result.get("sheet_names_read_back", result.get("sheet_names_after")),
                },
            ],
        ),
        errors=errors,
    )


def spreadsheet_set_sheet_visibility_response(
    request_id: str,
    document_id: str,
    sheet_name: str,
    visible: bool,
    dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = set_spreadsheet_sheet_visibility(
        document_id, sheet_name, visible, request_id, dry_run
    )
    return CommandResponse(
        ok=ok,
        command="spreadsheet-set-sheet-visibility",
        request_id=request_id,
        backend="wps-com" if ok and result.get("saved") else BACKEND,
        summary=(
            "Worksheet visibility request replayed."
            if replayed
            else "Worksheet visibility preview completed."
            if dry_run and ok
            else "Worksheet visibility updated."
            if ok
            else "Worksheet visibility update failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "ordered_sheet_visibility_read_back",
                    "passed": bool(ok and (dry_run or result.get("validation_passed"))),
                    "details": result.get("sheet_states_read_back", result.get("sheet_states_after")),
                },
            ],
        ),
        errors=errors,
    )


def spreadsheet_delete_sheet_response(
    request_id: str, document_id: str, sheet_name: str, dry_run: bool
) -> CommandResponse:
    ok, result, errors, replayed = delete_spreadsheet_sheet(document_id, sheet_name, request_id, dry_run)
    return CommandResponse(
        ok=ok,
        command="spreadsheet-delete-sheet",
        request_id=request_id,
        backend="wps-com" if ok and result.get("saved") else BACKEND,
        summary=(
            "Worksheet deletion request replayed."
            if replayed
            else "Worksheet deletion preview completed."
            if dry_run and ok
            else "Worksheet deleted."
            if ok
            else "Worksheet deletion failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "ordered_sheet_names_read_back",
                    "passed": bool(ok and (dry_run or result.get("validation_passed"))),
                    "details": result.get("sheet_names_read_back", result.get("sheet_names_after")),
                },
            ],
        ),
        errors=errors,
    )


def spreadsheet_copy_sheet_response(
    request_id: str, document_id: str, source_name: str, new_name: str, index: int | None, dry_run: bool
) -> CommandResponse:
    ok, result, errors, replayed = copy_spreadsheet_sheet(
        document_id, source_name, new_name, request_id, index, dry_run
    )
    return CommandResponse(
        ok=ok,
        command="spreadsheet-copy-sheet",
        request_id=request_id,
        backend="wps-com" if ok and result.get("saved") else BACKEND,
        summary=(
            "Worksheet copy request replayed."
            if replayed
            else "Worksheet copy preview completed."
            if dry_run and ok
            else "Worksheet copied."
            if ok
            else "Worksheet copy failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "ordered_copy_and_cell_read_back",
                    "passed": bool(ok and (dry_run or result.get("validation_passed"))),
                    "details": result.get("sheet_names_read_back", result.get("sheet_names_after")),
                },
            ],
        ),
        errors=errors,
    )


def spreadsheet_set_sheet_tab_color_response(
    request_id: str, document_id: str, sheet_name: str, color: str, dry_run: bool
) -> CommandResponse:
    ok, result, errors, replayed = set_spreadsheet_sheet_tab_color(document_id, sheet_name, color, request_id, dry_run)
    return CommandResponse(
        ok=ok,
        command="spreadsheet-set-sheet-tab-color",
        request_id=request_id,
        backend="wps-com" if ok and result.get("saved") else BACKEND,
        summary=(
            "Worksheet tab color request replayed."
            if replayed
            else "Worksheet tab color preview completed."
            if dry_run and ok
            else "Worksheet tab color updated."
            if ok
            else "Worksheet tab color update failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "tab_color_read_back",
                    "passed": bool(ok and (dry_run or result.get("validation_passed"))),
                    "details": result.get("tab_color_read_back", result.get("color")),
                },
            ],
        ),
        errors=errors,
    )


def spreadsheet_inspect_response(
    request_id: str, document_id: str, range_address: str, sheet_name: str | None
) -> CommandResponse:
    ok, result, errors = inspect_spreadsheet_range(document_id, range_address, sheet_name)
    return CommandResponse(
        ok=ok,
        command="spreadsheet-inspect",
        request_id=request_id,
        backend="wps-com",
        summary="Spreadsheet calculation and display inspection completed without saving."
        if ok
        else "Spreadsheet inspection failed.",
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {"name": "read_only", "passed": bool(result.get("read_only")), "details": result.get("saved")},
                {
                    "name": "formula_cache_display_fields",
                    "passed": bool(
                        ok
                        and all(
                            "formula" in cell
                            and "saved_cached_value" in cell
                            and "recalculated_value" in cell
                            and "displayed_text" in cell
                            for cell in result.get("cells", [])
                        )
                    ),
                    "details": len(result.get("cells", [])),
                },
            ],
        ),
        errors=errors,
    )


def spreadsheet_write_response(
    request_id: str,
    document_id: str,
    range_address: str,
    values_json: str,
    sheet_name: str | None,
    dry_run: bool,
) -> CommandResponse:
    try:
        values = json.loads(values_json)
    except json.JSONDecodeError as exc:
        return CommandResponse(
            ok=False,
            command="spreadsheet-write",
            request_id=request_id,
            backend=BACKEND,
            summary="Spreadsheet write could not parse values_json.",
            data={},
            validation=ValidationResult(status="failed"),
            errors=[{"code": "INVALID_JSON", "message": str(exc)}],
        )
    ok, result, errors, replayed = write_spreadsheet_range(
        document_id=document_id,
        range_address=range_address,
        values=values,
        request_id=request_id,
        sheet_name=sheet_name,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="spreadsheet-write",
        request_id=request_id,
        backend="wps-com" if not dry_run else BACKEND,
        summary=(
            "Spreadsheet write request replayed from idempotency record."
            if replayed
            else "Spreadsheet write dry-run completed."
            if dry_run and ok
            else "Spreadsheet write completed."
            if ok
            else "Spreadsheet write failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "range_shape_valid",
                    "passed": ok,
                    "details": {
                        "range": range_address,
                        "row_count": result.get("row_count"),
                        "column_count": result.get("column_count"),
                    },
                },
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "write_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": result.get("read_back_values"),
                },
            ],
        ),
        errors=errors,
    )


def spreadsheet_formula_write_response(
    request_id: str,
    document_id: str,
    range_address: str,
    formulas_json: str,
    expected_values_json: str,
    sheet_name: str | None,
    dry_run: bool,
) -> CommandResponse:
    try:
        formulas = json.loads(formulas_json)
        expected_values = json.loads(expected_values_json)
    except json.JSONDecodeError as exc:
        return CommandResponse(
            ok=False,
            command="spreadsheet-formula-write",
            request_id=request_id,
            backend=BACKEND,
            summary="Spreadsheet formula write could not parse JSON arguments.",
            data={},
            validation=ValidationResult(status="failed"),
            errors=[{"code": "INVALID_JSON", "message": str(exc)}],
        )
    ok, result, errors, replayed = write_spreadsheet_formulas(
        document_id=document_id,
        range_address=range_address,
        formulas=formulas,
        expected_values=expected_values,
        request_id=request_id,
        sheet_name=sheet_name,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="spreadsheet-formula-write",
        request_id=request_id,
        backend="wps-com" if not dry_run else BACKEND,
        summary=(
            "Spreadsheet formula write request replayed from idempotency record."
            if replayed
            else "Spreadsheet formula write dry-run completed."
            if dry_run and ok
            else "Spreadsheet formula write completed."
            if ok
            else "Spreadsheet formula write failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "formula_range_shape_valid",
                    "passed": ok,
                    "details": {
                        "range": range_address,
                        "row_count": result.get("row_count"),
                        "column_count": result.get("column_count"),
                    },
                },
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "calculation_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": result.get("read_back_values"),
                },
            ],
        ),
        errors=errors,
    )
