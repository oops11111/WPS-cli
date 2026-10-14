"""All-or-nothing file mutations.

WPS saves a document in place, which is not atomic, and a command can fail after the save: a read-back
mismatch or a failed source verification. Every mutation takes a backup before it writes. When a command
fails after changing the file, this module restores the pre-write backup atomically and checks the restored
bytes against the backup's hash, so the command either fully applies or is undone.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .backups import _restore_file_atomically
from .errors import COM_OPERATION_FAILED, ROLLBACK_BLOCKED, ROLLBACK_FAILED, ROLLED_BACK
from .operations import get_operation
from .sessions import file_identity, get_document


def _pre_write_backup(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    for candidate in (result, result.get("backup")):
        if isinstance(candidate, dict) and candidate.get("backup_path"):
            return str(candidate["backup_path"])
    return None


def _backup_for_request(request_id: str, workspace: str | Path) -> str | None:
    """The backup a command took before writing, from the ledger. Used when the command raised instead of returning."""
    record = get_operation(f"{request_id}:backup", workspace)
    if not record:
        return None
    backup_path = (record.get("result") or {}).get("backup_path")
    return str(backup_path) if backup_path else None


def _rollback_error(document_id: str, backup_file: str, reason: str) -> dict[str, str]:
    return {
        "code": ROLLBACK_FAILED,
        "message": (
            f"The command failed after changing the document and it could not be undone automatically: {reason}. "
            f"Restore the pre-write backup manually with restore-backup (document {document_id}, backup {backup_file})."
        ),
    }


def _undo_write(
    document_id: str, backup_file: str, workspace: str | Path
) -> tuple[dict[str, Any], dict[str, str] | None]:
    document = get_document(document_id, workspace)
    if document is None:
        return {"performed": False}, _rollback_error(document_id, backup_file, "the document is no longer registered")
    target = Path(document["path"])
    backup = Path(backup_file)
    try:
        backup_sha = file_identity(backup)["source_sha256"]
        current_sha = file_identity(target)["source_sha256"]
    except OSError as exc:
        return {"performed": False}, _rollback_error(document_id, backup_file, f"the file could not be read ({exc})")
    if current_sha == backup_sha:
        return {"performed": False, "reason": "the file already matches the pre-write backup"}, None
    write_error = _restore_file_atomically(backup, target)
    if write_error is not None and write_error.get("reason") == "file_locked":
        return {"performed": False, "blocked": "file_locked"}, None
    if write_error is not None:
        return {"performed": False}, _rollback_error(document_id, backup_file, write_error["message"])
    try:
        restored_sha = file_identity(target)["source_sha256"]
    except OSError as exc:
        return {"performed": True}, _rollback_error(
            document_id, backup_file, f"the restored file could not be read ({exc})"
        )
    if restored_sha != backup_sha:
        return {"performed": True}, _rollback_error(
            document_id, backup_file, "the restored file does not match the backup"
        )
    return {"performed": True, "restored_from": str(backup)}, None


def _open_in_wps(document_id: str, workspace: str | Path) -> tuple[bool | None, str | None]:
    """Whether WPS has the document open now, and why the answer is unknown when it is None.

    A failed probe must not change the rollback result, so an error here only means the answer is unknown.
    The reason is returned so that a null result can be diagnosed.
    """
    from . import open_documents  # imported here: open_documents imports this module

    document = get_document(document_id, workspace)
    if document is None:
        return None, "document is not registered in this workspace"
    try:
        ok, data, errors = open_documents.list_open_documents(component=document["component"], workspace=workspace)
    except Exception as exc:
        return None, f"probe raised {type(exc).__name__}: {exc}"
    if not ok:
        codes = ", ".join(error.get("code", "?") for error in errors) or "no error code"
        return None, f"probe returned an error ({codes})"
    target = str(Path(document["path"]).resolve()).lower()
    is_open = any(
        str(Path(item["full_name"]).resolve()).lower() == target
        for item in data.get("documents", [])
        if item.get("full_name")
    )
    return is_open, None


def _blocked_guidance(document_id: str, backup_file: str, open_in_wps: bool | None) -> str:
    state = "is open in WPS" if open_in_wps is True else "may be open in WPS"
    return (
        f"The write was saved by WPS and could not be undone, because the file is locked; the document {state}. "
        "The file still holds the rejected value. Close the document in WPS without saving, then restore the pre-write "
        f'backup with: restore-backup --document-id {document_id} --backup-path "{backup_file}" --request-id <new-id>. '
        "Or add --close-in-wps to that command to have it close the document for you; it refuses if WPS has unsaved "
        "changes."
    )


def _wps_guidance(open_in_wps: bool | None) -> str:
    if open_in_wps is True:
        return (
            "The document is open in WPS now: close it without saving or reload it, so WPS does not write the "
            "rejected content back."
        )
    if open_in_wps is False:
        return "The document is not open in WPS, so nothing else needs to be done."
    return (
        "Could not check whether the document is open in WPS. If it is, close it without saving or reload it, "
        "so WPS does not write the rejected content back."
    )


def _undo_failed(document_id, backup_file, workspace, result, errors, replayed):
    rollback, rollback_error = _undo_write(document_id, backup_file, workspace)
    result = {**result, "rollback": rollback}
    if rollback_error is not None:
        return False, result, [*errors, rollback_error], replayed
    locked = rollback.get("blocked") == "file_locked"
    if not rollback["performed"] and not locked:
        return False, result, errors, replayed
    open_in_wps, probe_error = _open_in_wps(document_id, workspace)
    rollback["open_in_wps"] = open_in_wps
    if probe_error is not None:
        rollback["open_in_wps_error"] = probe_error
    if locked:
        blocked = {"code": ROLLBACK_BLOCKED, "message": _blocked_guidance(document_id, backup_file, open_in_wps)}
        return False, result, [*errors, blocked], replayed
    undone = {
        "code": ROLLED_BACK,
        "message": (
            "The write was undone: the document file was restored from the pre-write backup and its hash matches it. "
            + _wps_guidance(open_in_wps)
        ),
    }
    return False, result, [*errors, undone], replayed


def atomic_mutation(operation: Callable[..., Any]) -> Callable[..., Any]:
    """Undo a failed mutation's write from its pre-write backup. Place it under @coordinated_mutation."""
    signature = inspect.signature(operation)

    @functools.wraps(operation)
    def wrapped(*args, **kwargs):
        bound = signature.bind_partial(*args, **kwargs)
        document_id = bound.arguments.get("document_id")
        request_id = bound.arguments.get("request_id")
        workspace = bound.arguments.get("workspace", ".")
        try:
            outcome = operation(*args, **kwargs)
        except Exception as exc:
            # The command raised after its backup was taken: undo any write it made, then report the failure.
            backup_file = (
                _backup_for_request(str(request_id), workspace)
                if document_id is not None and request_id is not None
                else None
            )
            if backup_file is None:
                raise
            error = {"code": COM_OPERATION_FAILED, "message": f"The command raised an unexpected exception: {exc}"}
            return _undo_failed(str(document_id), backup_file, workspace, {"document_id": document_id}, [error], False)
        ok, result, errors, replayed = outcome
        if ok or document_id is None:
            return outcome
        backup_file = _pre_write_backup(result)
        if backup_file is None:
            return outcome
        return _undo_failed(str(document_id), backup_file, workspace, result, errors, replayed)

    return wrapped
