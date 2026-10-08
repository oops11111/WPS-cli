from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .mutation_lock import DocumentBusyError, document_mutation_lock
from .state_store import atomic_write_json, read_json_state


STATE_DIR = ".wps-agent"
DOCUMENTS_FILE = "documents.json"
SUPPORTED_COMPONENTS = {"writer", "spreadsheets", "presentation"}
REGISTRATION_LOCK_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    component: str
    path: str
    registered_at: str
    exists: bool
    source_sha256: str
    file_device: int
    file_inode: int


def file_identity(path: Path) -> dict[str, int | str]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        info = os.fstat(stream.fileno())
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
    ):
        raise OSError("File changed while its identity was read.")
    return {"source_sha256": digest.hexdigest().upper(), "file_device": info.st_dev, "file_inode": info.st_ino}


def stable_document_id(component: str, path: str) -> str:
    canonical = os.path.normcase(str(Path(path).resolve()))
    digest = hashlib.sha256(f"{component}:{canonical}".encode("utf-8")).hexdigest()[:16]
    return f"doc_{digest}"


def _state_path(workspace: str | Path = ".") -> Path:
    return Path(workspace) / STATE_DIR / DOCUMENTS_FILE


def _read_state(workspace: str | Path = ".") -> dict[str, Any]:
    return read_json_state(_state_path(workspace), {"documents": {}})


def _write_state(state: dict[str, Any], workspace: str | Path = ".") -> None:
    state_file = _state_path(workspace)
    atomic_write_json(state_file, state)


def register_document(component: str, path: str, workspace: str | Path = ".") -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    if component not in SUPPORTED_COMPONENTS:
        return (
            False,
            {},
            [{"code": "UNSUPPORTED_COMPONENT", "message": f"Unsupported component: {component}"}],
        )

    document_path = Path(path)
    resolved = str(document_path.resolve())
    document_id = stable_document_id(component, resolved)
    try:
        with document_mutation_lock(document_id, workspace, REGISTRATION_LOCK_TIMEOUT_SECONDS):
            if not document_path.is_file():
                return False, {}, [{"code": "INPUT_FILE_NOT_FOUND", "message": f"Input file not found: {path}"}]
            try:
                identity = file_identity(document_path)
            except OSError as exc:
                return False, {}, [{"code": "DOCUMENT_IDENTITY_UNAVAILABLE", "message": str(exc)}]
            with document_mutation_lock("state:documents", workspace, REGISTRATION_LOCK_TIMEOUT_SECONDS):
                state = _read_state(workspace)
                record = DocumentRecord(
                    document_id=document_id,
                    component=component,
                    path=resolved,
                    registered_at=datetime.now(timezone.utc).isoformat(),
                    exists=True,
                    **identity,
                )
                state.setdefault("documents", {})[document_id] = asdict(record)
                _write_state(state, workspace)
                return True, asdict(record), []
    except DocumentBusyError as exc:
        return False, {}, [{"code": "DOCUMENT_BUSY", "message": str(exc)}]


def list_documents(workspace: str | Path = ".") -> list[dict[str, Any]]:
    state = _read_state(workspace)
    records = []
    for record in state.get("documents", {}).values():
        current = dict(record)
        current["exists"] = Path(current["path"]).exists()
        records.append(current)
    return sorted(records, key=lambda item: item["document_id"])


def get_document(document_id: str, workspace: str | Path = ".") -> dict[str, Any] | None:
    state = _read_state(workspace)
    record = state.get("documents", {}).get(document_id)
    if not record:
        return None
    current = dict(record)
    current["exists"] = Path(current["path"]).exists()
    return current


def refresh_document_identity(
    document_id: str,
    workspace: str | Path = ".",
    expected_identity: dict[str, int | str] | None = None,
) -> None:
    with document_mutation_lock("state:documents", workspace, REGISTRATION_LOCK_TIMEOUT_SECONDS):
        state = _read_state(workspace)
        record = state.get("documents", {}).get(document_id)
        if record is None:
            return
        current_identity = file_identity(Path(record["path"]))
        if expected_identity is not None and current_identity != expected_identity:
            raise OSError("Document changed after the operation identity was captured.")
        record.update(current_identity)
        _write_state(state, workspace)
