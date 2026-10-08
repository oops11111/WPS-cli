from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .backups import list_backups, restore_backup
from .sessions import register_document
from .writer_ops import writer_table_write


def _unique_child_request_id(request_id: str, label: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{request_id}:{label}:{stamp}"


def _resolve_workspace_path(path: str, workspace: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else Path(workspace) / candidate


def run_writer_table_smoke(
    input_path: str,
    output_path: str,
    table_index: int,
    row: int,
    column: int,
    text: str,
    request_id: str,
    workspace: str | Path = ".",
) -> dict[str, Any]:
    source = Path(input_path)
    if not source.exists():
        return {
            "ok": False,
            "data": {"input_path": str(source), "output_path": output_path},
            "errors": [{"code": "INPUT_FILE_NOT_FOUND", "message": f"Input file not found: {source}"}],
        }

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

    registered_ok, document, register_errors = register_document("writer", str(target), workspace)
    if not registered_ok:
        return {
            "ok": False,
            "data": {"input_path": str(source), "output_path": str(target)},
            "errors": register_errors,
        }

    write_request_id = _unique_child_request_id(request_id, "write")
    write_ok, write_result, write_errors, write_replayed = writer_table_write(
        document_id=document["document_id"],
        table_index=table_index,
        row=row,
        column=column,
        text=text,
        request_id=write_request_id,
        dry_run=False,
        workspace=workspace,
    )

    backups_ok, backups_result, backup_errors = list_backups(document["document_id"], workspace)
    backup_path = write_result.get("backup", {}).get("backup_path") if isinstance(write_result, dict) else None
    backup_file = _resolve_workspace_path(backup_path, workspace) if backup_path else None
    backup_exists = bool(backup_file and backup_file.exists())

    restore_ok = False
    restore_result: dict[str, Any] = {}
    restore_errors: list[dict[str, str]] = []
    restore_replayed = False
    if backup_file and backup_exists:
        restore_ok, restore_result, restore_errors, restore_replayed = restore_backup(
            document_id=document["document_id"],
            request_id=_unique_child_request_id(request_id, "restore-dry-run"),
            backup_name=backup_file.name,
            dry_run=True,
            workspace=workspace,
        )

    validation_passed = bool(
        write_ok
        and write_result.get("validation_passed")
        and backups_ok
        and backups_result.get("count", 0) > 0
        and backup_exists
        and restore_ok
    )
    errors = []
    if write_errors:
        errors.extend(write_errors)
    if backup_errors:
        errors.extend(backup_errors)
    if restore_errors:
        errors.extend(restore_errors)
    if not validation_passed and not errors:
        errors.append({"code": "WRITER_TABLE_SMOKE_FAILED", "message": "Writer table smoke validation did not pass."})

    return {
        "ok": validation_passed,
        "data": {
            "input_path": str(source),
            "output_path": str(target),
            "output_bytes": target.stat().st_size if target.exists() else 0,
            "document": document,
            "writer_table": write_result,
            "writer_table_replayed": write_replayed,
            "writer_table_request_id": write_request_id,
            "backups": backups_result if backups_ok else {},
            "backup_exists": backup_exists,
            "restore_check": {
                "ok": restore_ok,
                "result": restore_result,
                "replayed": restore_replayed,
            },
            "validation_passed": validation_passed,
        },
        "errors": errors,
    }
