from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Callable

from .operations import record_operation, replay_operation
from .sessions import get_document
from .sessions import file_identity
from .mutation_lock import coordinated_mutation, coordinated_request


def _backup_path(document_id: str, source_path: Path, workspace: str | Path = ".") -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    suffix = "".join(source_path.suffixes) or ".bak"
    filename = f"{source_path.stem}.{stamp}{suffix}"
    return Path(workspace) / ".wps-agent" / "backups" / document_id / filename


def _backup_dir(document_id: str, workspace: str | Path = ".") -> Path:
    return Path(workspace) / ".wps-agent" / "backups" / document_id


BACKUP_STAMP_RE = re.compile(r"(\d{8}T\d{12,20}Z)")


def _parse_backup_created_at(path: Path) -> str | None:
    match = BACKUP_STAMP_RE.search(path.name)
    if not match:
        return None
    stamp = match.group(1)
    try:
        parsed = datetime.strptime(stamp, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return parsed.isoformat()


def list_backups(
    document_id: str | None = None,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    root = Path(workspace) / ".wps-agent" / "backups"
    if document_id:
        document = get_document(document_id, workspace)
        if not document:
            return (
                False,
                {},
                [{"code": "DOCUMENT_NOT_FOUND", "message": f"Document not registered: {document_id}"}],
            )
        backup_dirs = [_backup_dir(document_id, workspace)]
    else:
        backup_dirs = sorted([item for item in root.iterdir() if item.is_dir()]) if root.exists() else []

    backups = []
    for backup_dir in backup_dirs:
        current_document_id = backup_dir.name
        for backup_file in sorted(backup_dir.iterdir()) if backup_dir.exists() else []:
            if not backup_file.is_file():
                continue
            backups.append(
                {
                    "document_id": current_document_id,
                    "backup_name": backup_file.name,
                    "backup_path": str(backup_file),
                    "backup_bytes": backup_file.stat().st_size,
                    "created_at": _parse_backup_created_at(backup_file),
                }
            )

    backups.sort(key=lambda item: (item["document_id"], item["backup_name"]))
    return (
        True,
        {
            "document_id": document_id,
            "count": len(backups),
            "backups": backups,
        },
        [],
    )


@coordinated_request
def create_backup(
    document_id: str,
    request_id: str,
    dry_run: bool = False,
    workspace: str | Path = ".",
    allow_stale_registration: bool = False,
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    replay = replay_operation(
        request_id, "backup-document", {"document_id": document_id, "dry_run": dry_run}, workspace,
    )
    if replay is not None:
        return replay

    document = get_document(document_id, workspace)
    if not document:
        return (
            False,
            {},
            [{"code": "DOCUMENT_NOT_FOUND", "message": f"Document not registered: {document_id}"}],
            False,
        )

    source_path = Path(document["path"])
    if not source_path.is_file():
        return (
            False,
            {"document": document},
            [{"code": "INPUT_FILE_NOT_FOUND", "message": f"Input file not found: {source_path}"}],
            False,
        )

    try:
        source_identity = file_identity(source_path)
    except OSError as exc:
        return False, {"document": document}, [
            {"code": "DOCUMENT_IDENTITY_UNAVAILABLE", "message": str(exc)}
        ], False
    expected_identity = {key: document.get(key) for key in source_identity}
    if not allow_stale_registration and expected_identity != source_identity:
        code = "DOCUMENT_IDENTITY_UNVERIFIED" if any(value is None for value in expected_identity.values()) else "DOCUMENT_IDENTITY_CHANGED"
        return False, {"document": document}, [{"code": code, "message": "Document identity differs from registration; register the current file before writing."}], False

    target_path = _backup_path(document_id, source_path, workspace)
    result = {
        "document_id": document_id,
        "component": document["component"],
        "source_path": str(source_path),
        "backup_path": str(target_path),
        "dry_run": dry_run,
        "created": False,
        "source_identity": source_identity,
    }
    if dry_run:
        return True, result, [], False

    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source_path, target_path)
        stable_copy = (
            file_identity(source_path) == source_identity
            and file_identity(target_path)["source_sha256"] == source_identity["source_sha256"]
        )
    except OSError:
        stable_copy = False
    if not stable_copy:
        return False, {**result, "backup_path": str(target_path)}, [
            {"code": "DOCUMENT_CHANGED_DURING_BACKUP", "message": "Source changed while creating the backup; no mutation was started."}
        ], False
    result["created"] = True
    result["backup_bytes"] = target_path.stat().st_size
    record_operation(request_id, "backup-document", result, workspace)
    return True, result, [], False


def verify_backup_source(path: str | Path, backup: dict[str, Any]) -> dict[str, str] | None:
    source = Path(path)
    expected = backup.get("source_identity")
    backup_path = backup.get("backup_path")
    if not isinstance(expected, dict) or not all(key in expected for key in ("source_sha256", "file_device", "file_inode")):
        return {"code": "BACKUP_SOURCE_UNVERIFIED", "message": "Backup lacks source identity evidence; create a new backup before writing."}
    if not backup_path or not backup.get("created") or Path(backup.get("source_path", "")).resolve() != source.resolve():
        return {"code": "BACKUP_SOURCE_UNVERIFIED", "message": "Backup does not identify this source file."}
    try:
        if file_identity(source) != expected:
            return {"code": "DOCUMENT_CHANGED_AFTER_BACKUP", "message": "Source changed after the backup and before WPS mutation."}
        if file_identity(Path(backup_path))["source_sha256"] != expected["source_sha256"]:
            return {"code": "BACKUP_CHANGED_AFTER_CREATION", "message": "Backup bytes changed before WPS mutation."}
    except OSError as exc:
        return {"code": "BACKUP_SOURCE_UNAVAILABLE", "message": str(exc)}
    return None


def guarded_com_mutation(path: str | Path, backup: dict[str, Any], operation: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    error = verify_backup_source(path, backup)
    if error is not None:
        return {"ok": False, "errors": [error], "data": {"backend": "source-preflight"}}
    result = operation()
    if result.get("ok"):
        try:
            result["data"] = {**result.get("data", {}), "source_identity_after_com": file_identity(Path(path))}
        except OSError as exc:
            return {"ok": False, "errors": [{"code": "DOCUMENT_UNAVAILABLE_AFTER_COM", "message": str(exc)}],
                    "data": result.get("data", {})}
    return result


def verify_post_com_source(path: str | Path, mutation: dict[str, Any]) -> dict[str, str] | None:
    expected = mutation.get("data", {}).get("source_identity_after_com")
    if not isinstance(expected, dict):
        return {"code": "POST_COM_SOURCE_UNVERIFIED", "message": "WPS mutation has no post-save source identity evidence."}
    try:
        if file_identity(Path(path)) != expected:
            return {"code": "DOCUMENT_CHANGED_AFTER_COM", "message": "Source changed after WPS saved and before validation completed."}
    except OSError as exc:
        return {"code": "DOCUMENT_UNAVAILABLE_AFTER_COM", "message": str(exc)}
    return None


def _resolve_backup_file(
    document_id: str,
    backup_name: str | None,
    backup_path: str | None,
    workspace: str | Path = ".",
) -> tuple[Path | None, list[dict[str, str]]]:
    if bool(backup_name) == bool(backup_path):
        return (
            None,
            [{"code": "INVALID_ARGUMENT", "message": "Provide exactly one of backup_name or backup_path."}],
        )

    backup_root = _backup_dir(document_id, workspace).resolve()
    candidate = (backup_root / backup_name).resolve() if backup_name else Path(str(backup_path)).resolve()
    try:
        candidate.relative_to(backup_root)
    except ValueError:
        return (
            None,
            [{"code": "INVALID_BACKUP_PATH", "message": "Backup must be inside the document backup directory."}],
        )
    if not candidate.exists() or not candidate.is_file():
        return (
            None,
            [{"code": "BACKUP_NOT_FOUND", "message": f"Backup not found: {candidate}"}],
        )
    return candidate, []


@coordinated_mutation
def restore_backup(
    document_id: str,
    request_id: str,
    backup_name: str | None = None,
    backup_path: str | None = None,
    dry_run: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    requested_backup_path = str(Path(backup_path).resolve()) if backup_path else None
    replay = replay_operation(
        request_id, "restore-backup",
        {"document_id": document_id, "requested_backup_name": backup_name, "requested_backup_path": requested_backup_path, "dry_run": dry_run},
        workspace,
    )
    if replay is not None:
        return replay

    document = get_document(document_id, workspace)
    if not document:
        return (
            False,
            {},
            [{"code": "DOCUMENT_NOT_FOUND", "message": f"Document not registered: {document_id}"}],
            False,
        )
    target_path = Path(document["path"])
    if not target_path.exists():
        return (
            False,
            {"document": document},
            [{"code": "INPUT_FILE_NOT_FOUND", "message": f"Input file not found: {target_path}"}],
            False,
        )

    backup_file, backup_errors = _resolve_backup_file(
        document_id,
        backup_name=backup_name,
        backup_path=backup_path,
        workspace=workspace,
    )
    if backup_errors or backup_file is None:
        return False, {"document": document}, backup_errors, False

    result = {
        "document_id": document_id,
        "component": document["component"],
        "target_path": str(target_path),
        "backup_path": str(backup_file),
        "backup_name": backup_file.name,
        "requested_backup_name": backup_name,
        "requested_backup_path": requested_backup_path,
        "dry_run": dry_run,
        "restored": False,
    }
    if dry_run:
        return True, result, [], False

    pre_restore_ok, pre_restore_result, pre_restore_errors, pre_restore_replayed = create_backup(
        document_id=document_id,
        request_id=f"{request_id}:pre-restore",
        dry_run=False,
        workspace=workspace,
        allow_stale_registration=True,
    )
    if not pre_restore_ok:
        return False, {"restore": result, "pre_restore_backup": pre_restore_result}, pre_restore_errors, False

    shutil.copy2(backup_file, target_path)
    result["restored"] = True
    result["restored_bytes"] = target_path.stat().st_size
    result["pre_restore_backup"] = pre_restore_result
    result["pre_restore_backup_replayed"] = pre_restore_replayed
    record_operation(request_id, "restore-backup", result, workspace)
    return True, result, [], False
