from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .sessions import file_identity, get_document, refresh_document_identity
from .mutation_lock import DocumentBusyError, document_mutation_lock
from .state_store import atomic_write_json, read_json_state


OPERATIONS_FILE = "operations.json"

RECOVERY_GUIDANCE = {
    "no_evidence": [
        "Check task status and the current document before deciding whether to issue a new mutation request.",
    ],
    "retryable": [
        "The source still matches the recorded pre-mutation backup; retry only with the same request ID after confirming no external editor is active.",
    ],
    "ambiguous": [
        "Do not automatically retry or overwrite the changed source.",
        "Preserve the current file and recorded backup, compare them, then decide whether to restore or register the current file.",
    ],
    "recorded": [
        "Review the recorded result and validate the current document before any further mutation.",
    ],
    "recorded_repairable": [
        "The committed file is still present; replay the same request ID to repair the stale registration without repeating the mutation.",
    ],
    "recorded_changed": [
        "Do not replay or overwrite the current file; compare it with the committed result and backup before choosing recovery.",
    ],
    "recorded_unavailable": [
        "Restore access to the recorded document path and inspect the file before attempting replay.",
    ],
    "recorded_unverified": [
        "Do not retry the same mutation automatically; inspect the file and backup, validate the current state, then re-register only after a recovery decision.",
    ],
}


def operations_state_path(workspace: str | Path = ".") -> Path:
    return Path(workspace) / ".wps-agent" / OPERATIONS_FILE


def read_operations(workspace: str | Path = ".") -> dict[str, Any]:
    return read_json_state(operations_state_path(workspace), {"operations": {}})


def write_operations(state: dict[str, Any], workspace: str | Path = ".") -> None:
    state_file = operations_state_path(workspace)
    atomic_write_json(state_file, state)


def get_operation(request_id: str, workspace: str | Path = ".") -> dict[str, Any] | None:
    state = read_operations(workspace)
    operation = state.get("operations", {}).get(request_id)
    return dict(operation) if operation else None


def replay_operation(
    request_id: str,
    command: str,
    expected_fields: dict[str, Any],
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool] | None:
    existing = get_operation(request_id, workspace)
    if not existing:
        if command != "backup-document":
            for backup_suffix in (":backup", ":pre-restore"):
                backup = get_operation(f"{request_id}{backup_suffix}", workspace)
                if not backup or backup.get("command") != "backup-document":
                    continue
                backup_result = backup.get("result", {})
                if backup_result.get("document_id") != expected_fields.get("document_id"):
                    return False, {"request_id": request_id}, [{"code": "IDEMPOTENCY_CONFLICT", "message": "request_id has a backup for a different document."}], False
                source_path = backup_result.get("source_path")
                source_identity = backup_result.get("source_identity")
                try:
                    unchanged = bool(source_path and isinstance(source_identity, dict) and file_identity(Path(source_path)) == source_identity)
                except OSError:
                    unchanged = False
                if not unchanged:
                    return False, {"request_id": request_id, "backup": backup_result}, [{"code": "UNRECORDED_MUTATION_AMBIGUOUS", "message": "A backup exists for this request, but no operation record exists and the source changed; inspect the file and backup before retrying."}], False
        return None
    result = dict(existing.get("result", {}))
    conflicts = []
    if existing.get("command") != command:
        conflicts.append("command")
    conflicts.extend(
        field for field, expected in expected_fields.items()
        if result.get(field) != expected
    )
    if conflicts:
        return (
            False,
            {"request_id": request_id, "conflicting_fields": conflicts},
            [{"code": "IDEMPOTENCY_CONFLICT", "message": "request_id was already used with different operation arguments."}],
            False,
        )
    if existing.get("identity_capture_error") is not None:
        return False, result, [{"code": "OPERATION_IDENTITY_UNVERIFIED", "message": "Operation was recorded after save, but its file identity could not be captured; inspect and re-register the file before any new mutation."}], False
    if existing.get("source_identity_at_commit") is not None:
        document = get_document(str(result["document_id"]), workspace)
        if document is None:
            return False, result, [{"code": "DOCUMENT_NOT_FOUND", "message": "Recorded document is no longer registered."}], False
        try:
            current_identity = file_identity(Path(document["path"]))
        except OSError as exc:
            return False, result, [{"code": "DOCUMENT_IDENTITY_UNAVAILABLE", "message": str(exc)}], False
        registered_identity = {key: document.get(key) for key in current_identity}
        if registered_identity != current_identity:
            if current_identity != existing["source_identity_at_commit"]:
                return False, result, [{"code": "OPERATION_SOURCE_CHANGED", "message": "Recorded operation cannot repair a registration for a different file identity."}], False
            try:
                refresh_document_identity(str(result["document_id"]), workspace, current_identity)
            except (OSError, DocumentBusyError) as exc:
                return False, result, [{"code": "DOCUMENT_IDENTITY_UNAVAILABLE", "message": str(exc)}], False
    return True, result, [], True


def list_operations(workspace: str | Path = ".") -> list[dict[str, Any]]:
    state = read_operations(workspace)
    records = [dict(record) for record in state.get("operations", {}).values()]
    return sorted(records, key=lambda item: item.get("recorded_at", ""))


def inspect_mutation_request(request_id: str, workspace: str | Path = ".") -> dict[str, Any]:
    operation = get_operation(request_id, workspace)
    operation_identity = None
    backups = []
    for suffix in (":backup", ":pre-restore"):
        backup = get_operation(f"{request_id}{suffix}", workspace)
        if backup and backup.get("command") == "backup-document":
            result = backup.get("result", {})
            source_path = result.get("source_path")
            expected = result.get("source_identity")
            try:
                current = file_identity(Path(source_path)) if source_path else None
            except OSError:
                current = None
            backups.append({
                "request_id": backup["request_id"],
                "document_id": result.get("document_id"),
                "source_path": source_path,
                "backup_path": result.get("backup_path"),
                "source_identity": expected,
                "current_identity": current,
                "source_matches_backup": bool(isinstance(expected, dict) and current == expected),
            })
    if operation:
        committed = operation.get("source_identity_at_commit")
        if operation.get("identity_capture_error"):
            status = "recorded_unverified"
        elif isinstance(committed, dict):
            document_id = operation.get("result", {}).get("document_id")
            document = get_document(str(document_id), workspace) if document_id else None
            try:
                current = file_identity(Path(document["path"])) if document else None
            except OSError:
                current = None
            registered = {key: document.get(key) for key in committed} if document else None
            operation_identity = {
                "committed": committed,
                "current": current,
                "registered_matches_current": bool(current is not None and registered == current),
                "current_matches_commit": bool(current is not None and current == committed),
            }
            if current is None:
                status = "recorded_unavailable"
            elif operation_identity["registered_matches_current"]:
                status = "recorded"
            elif operation_identity["current_matches_commit"]:
                status = "recorded_repairable"
            else:
                status = "recorded_changed"
        else:
            status = "recorded"
    elif not backups:
        status = "no_evidence"
    elif all(backup["source_matches_backup"] for backup in backups):
        status = "retryable"
    else:
        status = "ambiguous"
    return {
        "request_id": request_id,
        "status": status,
        "operation": operation,
        "operation_identity": operation_identity,
        "backups": backups,
        "recovery_guidance": RECOVERY_GUIDANCE[status],
    }


def record_operation(
    request_id: str,
    command: str,
    result: dict[str, Any],
    workspace: str | Path = ".",
) -> dict[str, Any]:
    document_id = result.get("document_id")
    needs_identity = command != "backup-document" and document_id and result.get("saved") is not False
    document = get_document(str(document_id), workspace) if needs_identity else None
    commit_identity = None
    capture_error = None
    if document:
        try:
            commit_identity = file_identity(Path(document["path"]))
        except OSError as exc:
            capture_error = str(exc)
    with document_mutation_lock("state:operations", workspace):
        state = read_operations(workspace)
        record = {
            "request_id": request_id,
            "command": command,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
        }
        if commit_identity is not None:
            record["source_identity_at_commit"] = commit_identity
        if capture_error is not None:
            record["identity_capture_error"] = capture_error
        state.setdefault("operations", {})[request_id] = record
        write_operations(state, workspace)
    if commit_identity is not None:
        refresh_document_identity(str(document_id), workspace, commit_identity)
    if capture_error is not None:
        raise OSError(f"Operation recorded, but document identity could not be captured: {capture_error}")
    return record
