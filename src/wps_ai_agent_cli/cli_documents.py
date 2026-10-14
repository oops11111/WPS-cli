"""Document registration, backup, validation, snapshot, operation-record and recovery commands."""

from __future__ import annotations

from .backups import create_backup, list_backups, restore_backup
from .cli_common import BACKEND
from .models import CommandResponse, ValidationResult
from .operations import get_operation, inspect_mutation_request, list_operations
from .sessions import list_documents, register_document
from .snapshots import snapshot_document
from .task_status import (
    build_recovery_playbook,
    list_recovery_playbooks,
)
from .validators import validate_document


def register_document_response(request_id: str, component: str, path: str) -> CommandResponse:
    ok, record, errors = register_document(component=component, path=path)
    return CommandResponse(
        ok=ok,
        command="register-document",
        request_id=request_id,
        backend=BACKEND,
        summary="Document registered." if ok else "Document could not be registered.",
        data={"document": record} if record else {},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "document_path_exists",
                    "passed": ok,
                    "details": record.get("path") if record else path,
                }
            ],
        ),
        errors=errors,
    )


def documents_response(request_id: str) -> CommandResponse:
    documents = list_documents()
    return CommandResponse(
        ok=True,
        command="documents",
        request_id=request_id,
        backend=BACKEND,
        summary=f"Returned {len(documents)} registered documents.",
        data={"documents": documents},
        validation=ValidationResult(status="not_applicable"),
    )


def backup_document_response(request_id: str, document_id: str, dry_run: bool) -> CommandResponse:
    ok, result, errors, replayed = create_backup(
        document_id=document_id,
        request_id=request_id,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="backup-document",
        request_id=request_id,
        backend=BACKEND,
        summary=(
            "Backup request replayed from idempotency record."
            if replayed
            else "Backup dry-run completed."
            if dry_run and ok
            else "Backup created."
            if ok
            else "Backup could not be created."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "document_registered",
                    "passed": ok,
                    "details": document_id,
                },
                {
                    "name": "backup_created",
                    "passed": bool(result.get("created") or dry_run or replayed),
                    "details": result.get("backup_path"),
                },
            ],
        ),
        errors=errors,
    )


def list_backups_response(request_id: str, document_id: str | None) -> CommandResponse:
    ok, result, errors = list_backups(document_id=document_id)
    return CommandResponse(
        ok=ok,
        command="list-backups",
        request_id=request_id,
        backend=BACKEND,
        summary=(
            f"Returned {result.get('count', 0)} backups."
            if ok
            else "Backup inventory failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "backups_listed",
                    "passed": ok,
                    "details": {
                        "document_id": document_id,
                        "count": result.get("count"),
                    },
                }
            ],
        ),
        errors=errors,
    )


def restore_backup_response(
    request_id: str,
    document_id: str,
    backup_name: str | None,
    backup_path: str | None,
    dry_run: bool,
    close_in_wps: bool = False,
) -> CommandResponse:
    ok, result, errors, replayed = restore_backup(
        document_id=document_id,
        request_id=request_id,
        backup_name=backup_name,
        backup_path=backup_path,
        dry_run=dry_run,
        close_in_wps=close_in_wps,
    )
    return CommandResponse(
        ok=ok,
        command="restore-backup",
        request_id=request_id,
        backend=BACKEND,
        summary=(
            "Restore request replayed from idempotency record."
            if replayed
            else "Restore dry-run completed."
            if dry_run and ok
            else "Backup restored."
            if ok
            else "Backup restore failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "backup_selected",
                    "passed": ok,
                    "details": result.get("backup_path"),
                },
                {
                    "name": "pre_restore_backup_created",
                    "passed": bool(dry_run or replayed or result.get("pre_restore_backup", {}).get("created")),
                    "details": result.get("pre_restore_backup", {}).get("backup_path"),
                },
                {
                    "name": "target_restored",
                    "passed": bool(dry_run or replayed or result.get("restored")),
                    "details": result.get("target_path"),
                },
            ],
        ),
        errors=errors,
    )


def validate_document_response(
    request_id: str,
    document_id: str,
    contains: str | None,
    cell: str | None,
    equals: str | None,
) -> CommandResponse:
    ok, result, errors = validate_document(
        document_id=document_id,
        contains=contains,
        cell=cell,
        equals=equals,
    )
    component = result.get("component")
    checks = []
    if component == "writer":
        checks.append(
            {
                "name": "body_text_contains",
                "passed": ok,
                "details": {"text": contains, "count": result.get("count")},
            }
        )
    elif component == "spreadsheets":
        checks.append(
            {
                "name": "cell_value_equals",
                "passed": ok,
                "details": {
                    "cell": cell,
                    "expected": equals,
                    "actual": result.get("actual"),
                },
            }
        )
    else:
        checks.append({"name": "validation_supported", "passed": ok, "details": component})

    return CommandResponse(
        ok=ok,
        command="validate-document",
        request_id=request_id,
        backend=BACKEND,
        summary="Document validation completed." if ok else "Document validation failed.",
        data=result,
        validation=ValidationResult(status="passed" if ok else "failed", checks=checks),
        errors=errors,
    )


def snapshot_document_response(request_id: str, document_id: str) -> CommandResponse:
    ok, result, errors = snapshot_document(document_id=document_id)
    component = result.get("component")
    checks = []
    if component == "writer":
        checks.append(
            {
                "name": "writer_text_structure_snapshotted",
                "passed": ok,
                "details": {
                    "paragraph_count": result.get("paragraph_count"),
                    "non_empty_paragraph_count": result.get("non_empty_paragraph_count"),
                },
            }
        )
    elif component == "spreadsheets":
        checks.append(
            {
                "name": "spreadsheet_formula_errors_scanned",
                "passed": ok,
                "details": {
                    "sheet_count": result.get("sheet_count"),
                    "formula_count": result.get("formula_count"),
                    "formula_error_count": result.get("formula_error_count"),
                },
            }
        )
    elif component == "presentation":
        checks.append(
            {
                "name": "presentation_text_objects_counted",
                "passed": ok,
                "details": {
                    "slide_count": result.get("slide_count"),
                    "text_object_count": result.get("text_object_count"),
                    "non_empty_text_object_count": result.get("non_empty_text_object_count"),
                },
            }
        )
    else:
        checks.append({"name": "snapshot_supported", "passed": ok, "details": component})

    return CommandResponse(
        ok=ok,
        command="snapshot-document",
        request_id=request_id,
        backend=BACKEND,
        summary="Document snapshot returned." if ok else "Document snapshot failed.",
        data=result,
        validation=ValidationResult(status="passed" if ok else "failed", checks=checks),
        errors=errors,
    )


def operation_response(request_id: str, operation_request_id: str) -> CommandResponse:
    operation = get_operation(operation_request_id)
    ok = operation is not None
    return CommandResponse(
        ok=ok,
        command="operation",
        request_id=request_id,
        backend=BACKEND,
        summary="Operation returned." if ok else "Operation not found.",
        data={"operation": operation} if operation else {},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "operation_exists",
                    "passed": ok,
                    "details": operation_request_id,
                }
            ],
        ),
        errors=[] if ok else [{"code": "OPERATION_NOT_FOUND", "message": f"Operation not found: {operation_request_id}"}],
    )


def operations_response(request_id: str) -> CommandResponse:
    operations = list_operations()
    return CommandResponse(
        ok=True,
        command="operations",
        request_id=request_id,
        backend=BACKEND,
        summary=f"Returned {len(operations)} recorded operations.",
        data={"operations": operations},
        validation=ValidationResult(status="not_applicable"),
    )


def mutation_request_inspect_response(request_id: str, operation_request_id: str) -> CommandResponse:
    inspection = inspect_mutation_request(operation_request_id)
    status = inspection["status"]
    return CommandResponse(
        ok=True,
        command="mutation-request-inspect",
        request_id=request_id,
        backend=BACKEND,
        summary=f"Mutation request evidence: {status}.",
        data={"mutation_request": inspection},
        validation=ValidationResult(status="warning" if status in {
            "ambiguous", "recorded_unverified", "recorded_unavailable",
            "recorded_repairable", "recorded_changed",
        } else "passed"),
    )


def task_recovery_response(request_id: str, task_id: str) -> CommandResponse:
    playbook = build_recovery_playbook(task_id)
    evidence = playbook.get("evidence", {})
    found = bool(evidence.get("task_status_found"))
    return CommandResponse(
        ok=True,
        command="task-recovery",
        request_id=request_id,
        backend=BACKEND,
        summary=(
            f"Recovery playbook returned for {task_id}."
            if found
            else f"Recovery playbook returned for missing task status {task_id}."
        ),
        data={"recovery_playbook": playbook},
        validation=ValidationResult(
            status="passed" if found else "warning",
            checks=[
                {
                    "name": "task_status_found",
                    "passed": found,
                    "details": {
                        "task_id": task_id,
                        "scenario": playbook.get("scenario"),
                    },
                }
            ],
        ),
    )


def task_recovery_playbooks_response(request_id: str) -> CommandResponse:
    playbooks = list_recovery_playbooks()
    return CommandResponse(
        ok=True,
        command="task-recovery-playbooks",
        request_id=request_id,
        backend=BACKEND,
        summary=f"Returned {len(playbooks)} recovery playbooks.",
        data={"recovery_playbooks": playbooks},
        validation=ValidationResult(status="not_applicable"),
    )
