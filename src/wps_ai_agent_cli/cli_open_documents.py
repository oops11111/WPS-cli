"""Commands on documents already open in WPS: list, selection read and edit, save and export."""

from __future__ import annotations

import json

from .models import CommandResponse, ValidationResult
from .open_documents import (
    delete_presentation_selection,
    delete_spreadsheet_selection,
    delete_writer_selection,
    export_open_document_copy,
    export_open_document_html,
    export_open_document_pdf,
    export_open_document_text,
    insert_presentation_selection,
    insert_writer_selection,
    list_open_documents,
    read_presentation_selection,
    read_spreadsheet_selection,
    read_writer_selection,
    replace_presentation_selection,
    replace_spreadsheet_selection,
    replace_writer_selection,
    save_as_open_document,
    save_open_document,
)


def open_documents_response(request_id: str, component: str | None, register: bool) -> CommandResponse:
    ok, result, errors = list_open_documents(component=component, register=register)
    documents = result.get("documents", [])
    return CommandResponse(
        ok=ok,
        command="open-documents",
        request_id=request_id,
        backend="wps-com",
        summary=(
            f"Attached to running WPS and found {len(documents)} open documents."
            if ok
            else "Could not list open WPS documents."
        ),
        data=result,
        validation=ValidationResult(status="not_applicable"),
        errors=errors,
    )


def writer_selection_read_response(request_id: str, document_id: str) -> CommandResponse:
    ok, result, errors = read_writer_selection(document_id)
    return CommandResponse(
        ok=ok,
        command="writer-selection-read",
        request_id=request_id,
        backend="wps-com",
        summary="Writer selection read." if ok else "Writer selection could not be read.",
        data=result,
        validation=ValidationResult(status="not_applicable"),
        errors=errors,
    )


def presentation_selection_read_response(request_id: str, document_id: str) -> CommandResponse:
    ok, result, errors = read_presentation_selection(document_id)
    return CommandResponse(
        ok=ok,
        command="presentation-selection-read",
        request_id=request_id,
        backend="wps-com",
        summary="Presentation selection read." if ok else "Presentation selection could not be read.",
        data=result,
        validation=ValidationResult(status="not_applicable"),
        errors=errors,
    )


def spreadsheet_selection_read_response(request_id: str, document_id: str) -> CommandResponse:
    ok, result, errors = read_spreadsheet_selection(document_id)
    return CommandResponse(
        ok=ok,
        command="spreadsheet-selection-read",
        request_id=request_id,
        backend="wps-com",
        summary="Spreadsheet selection read." if ok else "Spreadsheet selection could not be read.",
        data=result,
        validation=ValidationResult(status="not_applicable"),
        errors=errors,
    )


def spreadsheet_selection_replace_response(
    request_id: str,
    document_id: str,
    text: str | None,
    values_json: str | None,
    expected_selection_text: str | None,
    dry_run: bool,
) -> CommandResponse:
    values = None
    if values_json is not None:
        try:
            values = json.loads(values_json)
        except json.JSONDecodeError as exc:
            return CommandResponse(
                ok=False,
                command="spreadsheet-selection-replace",
                request_id=request_id,
                backend="wps-com",
                summary="Spreadsheet selection replace could not parse values_json.",
                data={},
                validation=ValidationResult(status="failed"),
                errors=[{"code": "INVALID_JSON", "message": str(exc)}],
            )
    ok, result, errors, replayed = replace_spreadsheet_selection(
        document_id,
        text,
        request_id,
        values=values,
        expected_selection_text=expected_selection_text,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="spreadsheet-selection-replace",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Spreadsheet selection replace request replayed from idempotency record."
            if replayed
            else "Spreadsheet selection replace dry-run completed."
            if dry_run and ok
            else "Spreadsheet selection replace completed."
            if ok
            else "Spreadsheet selection replace could not complete."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "selection_write_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": {
                        "read_back_text": result.get("read_back_text"),
                        "replacement_text": result.get("replacement_text"),
                        "fill_mode": result.get("fill_mode"),
                    },
                },
            ],
        ),
        errors=errors,
    )


def writer_selection_replace_response(
    request_id: str,
    document_id: str,
    text: str,
    expected_selection_text: str | None,
    dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = replace_writer_selection(
        document_id=document_id,
        text=text,
        request_id=request_id,
        expected_selection_text=expected_selection_text,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="writer-selection-replace",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Writer selection replace request replayed from idempotency record."
            if replayed
            else "Writer selection replace dry-run completed."
            if dry_run and ok
            else "Writer selection replace completed."
            if ok
            else "Writer selection replace could not complete."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "selection_write_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": {
                        "read_back_text": result.get("read_back_text"),
                        "replacement_text": result.get("replacement_text"),
                    },
                },
            ],
        ),
        errors=errors,
    )


def writer_selection_insert_response(
    request_id: str,
    document_id: str,
    text: str,
    expected_start: int | None,
    dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = insert_writer_selection(
        document_id=document_id,
        text=text,
        request_id=request_id,
        expected_start=expected_start,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="writer-selection-insert",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Writer selection insert request replayed from idempotency record."
            if replayed
            else "Writer selection insert dry-run completed."
            if dry_run and ok
            else "Writer selection insert completed."
            if ok
            else "Writer selection insert could not complete."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "selection_insert_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": {
                        "read_back_text": result.get("read_back_text"),
                        "insert_text": result.get("insert_text"),
                    },
                },
            ],
        ),
        errors=errors,
    )


def writer_selection_delete_response(
    request_id: str,
    document_id: str,
    expected_selection_text: str | None,
    dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = delete_writer_selection(
        document_id=document_id,
        request_id=request_id,
        expected_selection_text=expected_selection_text,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="writer-selection-delete",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Writer selection delete request replayed from idempotency record."
            if replayed
            else "Writer selection delete dry-run completed."
            if dry_run and ok
            else "Writer selection delete completed."
            if ok
            else "Writer selection delete could not complete."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "selection_delete_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": {
                        "read_back_text": result.get("read_back_text"),
                        "deleted_text": result.get("deleted_text"),
                    },
                },
            ],
        ),
        errors=errors,
    )


def spreadsheet_selection_delete_response(
    request_id: str,
    document_id: str,
    expected_selection_text: str | None,
    dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = delete_spreadsheet_selection(
        document_id=document_id,
        request_id=request_id,
        expected_selection_text=expected_selection_text,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="spreadsheet-selection-delete",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Spreadsheet selection delete request replayed from idempotency record."
            if replayed
            else "Spreadsheet selection delete dry-run completed."
            if dry_run and ok
            else "Spreadsheet selection delete completed."
            if ok
            else "Spreadsheet selection delete could not complete."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "selection_delete_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": {
                        "read_back_text": result.get("read_back_text"),
                        "deleted_text": result.get("deleted_text"),
                    },
                },
            ],
        ),
        errors=errors,
    )


def presentation_selection_replace_response(
    request_id: str,
    document_id: str,
    text: str,
    expected_selection_text: str | None,
    dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = replace_presentation_selection(
        document_id=document_id,
        text=text,
        request_id=request_id,
        expected_selection_text=expected_selection_text,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="presentation-selection-replace",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Presentation selection replace request replayed from idempotency record."
            if replayed
            else "Presentation selection replace dry-run completed."
            if dry_run and ok
            else "Presentation selection replace completed."
            if ok
            else "Presentation selection replace could not complete."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "selection_write_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": {
                        "read_back_text": result.get("read_back_text"),
                        "replacement_text": result.get("replacement_text"),
                    },
                },
            ],
        ),
        errors=errors,
    )


def presentation_selection_insert_response(
    request_id: str,
    document_id: str,
    text: str,
    expected_start: int | None,
    dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = insert_presentation_selection(
        document_id=document_id,
        text=text,
        request_id=request_id,
        expected_start=expected_start,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="presentation-selection-insert",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Presentation selection insert request replayed from idempotency record."
            if replayed
            else "Presentation selection insert dry-run completed."
            if dry_run and ok
            else "Presentation selection insert completed."
            if ok
            else "Presentation selection insert could not complete."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "selection_insert_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": {
                        "read_back_text": result.get("read_back_text"),
                        "insert_text": result.get("insert_text"),
                    },
                },
            ],
        ),
        errors=errors,
    )


def presentation_selection_delete_response(
    request_id: str,
    document_id: str,
    expected_selection_text: str | None,
    dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = delete_presentation_selection(
        document_id=document_id,
        request_id=request_id,
        expected_selection_text=expected_selection_text,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="presentation-selection-delete",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Presentation selection delete request replayed from idempotency record."
            if replayed
            else "Presentation selection delete dry-run completed."
            if dry_run and ok
            else "Presentation selection delete completed."
            if ok
            else "Presentation selection delete could not complete."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "selection_delete_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": {
                        "read_back_text": result.get("read_back_text"),
                        "deleted_text": result.get("deleted_text"),
                    },
                },
            ],
        ),
        errors=errors,
    )


def save_open_document_response(
    request_id: str,
    document_id: str,
    dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = save_open_document(
        document_id=document_id,
        request_id=request_id,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="save-open-document",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Open document save request replayed from idempotency record."
            if replayed
            else "Open document save dry-run completed."
            if dry_run and ok
            else "Open document saved."
            if ok
            else "Open document could not be saved."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "backup_created",
                    "passed": bool(
                        dry_run
                        or not result.get("would_modify")
                        or result.get("backup", {}).get("created")
                        or replayed
                    ),
                    "details": (result.get("backup") or {}).get("backup_path"),
                },
                {
                    "name": "save_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": {
                        "saved": result.get("saved"),
                        "wrote": result.get("wrote"),
                        "source_still_open": result.get("source_still_open"),
                    },
                },
            ],
        ),
        errors=errors,
    )


def save_as_open_document_response(
    request_id: str,
    component: str,
    name: str,
    output: str,
    dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = save_as_open_document(
        component=component,
        name=name,
        output=output,
        request_id=request_id,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="save-as-open-document",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Untitled open-document SaveAs request replayed from idempotency record."
            if replayed
            else "Untitled open-document SaveAs dry-run completed."
            if dry_run and ok
            else "Untitled open document saved to a new path and registered."
            if ok
            else "Untitled open document could not be saved to a new path."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "no_source_backup",
                    "passed": True,
                    "details": "Untitled SaveAs has no prior on-disk source to back up.",
                },
                {
                    "name": "save_as_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": {
                        "saved": result.get("saved"),
                        "wrote": result.get("wrote"),
                        "path_matched": result.get("path_matched"),
                        "source_still_open": result.get("source_still_open"),
                        "document_id": result.get("document_id"),
                    },
                },
            ],
        ),
        errors=errors,
    )


def export_open_document_response(request_id: str, document_id: str, output: str) -> CommandResponse:
    ok, result, errors, replayed = export_open_document_html(
        document_id=document_id, output=output, request_id=request_id,
    )
    return CommandResponse(
        ok=ok,
        command="export-open-document",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Open document export request replayed from idempotency record."
            if replayed
            else "Open document exported to HTML."
            if ok
            else "Open document could not be exported."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {"name": "output_created", "passed": bool(ok), "details": result.get("output")},
                {"name": "source_unchanged", "passed": bool(result.get("source_unchanged")), "details": result.get("source_path")},
            ],
        ),
        errors=errors,
    )


def export_open_document_pdf_response(request_id: str, document_id: str, output: str) -> CommandResponse:
    ok, result, errors, replayed = export_open_document_pdf(
        document_id=document_id, output=output, request_id=request_id,
    )
    return CommandResponse(
        ok=ok,
        command="export-open-document-pdf",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Open document PDF export request replayed from idempotency record."
            if replayed
            else "Open document exported to PDF."
            if ok
            else "Open document could not be exported to PDF."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {"name": "output_created", "passed": bool(ok), "details": result.get("output")},
                {"name": "source_unchanged", "passed": bool(result.get("source_unchanged")), "details": result.get("source_path")},
            ],
        ),
        errors=errors,
    )


def export_open_document_copy_response(request_id: str, document_id: str, output: str) -> CommandResponse:
    ok, result, errors, replayed = export_open_document_copy(
        document_id=document_id, output=output, request_id=request_id,
    )
    return CommandResponse(
        ok=ok,
        command="export-open-document-copy",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Open document native copy request replayed from idempotency record."
            if replayed
            else "Open document copied to a new native-format path."
            if ok
            else "Open document could not be copied."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {"name": "output_created", "passed": bool(ok), "details": result.get("output")},
                {"name": "source_unchanged", "passed": bool(result.get("source_unchanged")), "details": result.get("source_path")},
            ],
        ),
        errors=errors,
    )


def export_open_document_text_response(request_id: str, document_id: str, output: str) -> CommandResponse:
    ok, result, errors, replayed = export_open_document_text(
        document_id=document_id, output=output, request_id=request_id,
    )
    return CommandResponse(
        ok=ok,
        command="export-open-document-text",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Open document text export request replayed from idempotency record."
            if replayed
            else "Open document exported to plain text."
            if ok
            else "Open document could not be exported to plain text."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {"name": "output_created", "passed": bool(ok), "details": result.get("output")},
                {"name": "source_unchanged", "passed": bool(result.get("source_unchanged")), "details": result.get("source_path")},
            ],
        ),
        errors=errors,
    )
