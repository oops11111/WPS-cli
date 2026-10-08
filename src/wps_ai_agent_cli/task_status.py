from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


TASK_STATUS_FILE = "task_statuses.json"
TERMINAL_STATES = {"succeeded", "failed", "cancelled"}
VALID_STATES = {"pending", "running", *TERMINAL_STATES}
_STATUS_THREAD_LOCK = Lock()


RECOVERY_PLAYBOOKS: dict[str, dict[str, Any]] = {
    "pending": {
        "scenario": "pending",
        "title": "Task has not started",
        "summary": "The task status exists but the operation has not reported running work yet.",
        "safe_to_retry": True,
        "recommended_steps": [
            "Check whether an operation record already exists for the tracked request_id.",
            "If there is no operation record and the target document has not changed, start the operation.",
            "Reuse the same task_id when restarting so the agent does not create duplicate status records.",
        ],
    },
    "running": {
        "scenario": "interrupted_or_running",
        "title": "Task may still be running or may have been interrupted",
        "summary": "The task is not terminal. Treat it as ambiguous until the operation ledger and document evidence are checked.",
        "safe_to_retry": False,
        "recommended_steps": [
            "Poll task-status first; do not blindly rerun a mutating command.",
            "Check the operation ledger by request_id or result_ref.",
            "Inspect the target document with snapshot-document or validate-document when a document_id is available.",
            "List backups before attempting recovery or retry.",
            "Only retry after confirming the previous run did not complete or after restoring a known-good backup.",
        ],
    },
    "succeeded": {
        "scenario": "succeeded",
        "title": "Task completed successfully",
        "summary": "The task is terminal and successful. Recovery is normally not required.",
        "safe_to_retry": False,
        "recommended_steps": [
            "Inspect the operation record if result details are needed.",
            "Run validation or snapshot commands for post-change verification.",
            "Avoid retrying with a new request_id unless a separate follow-up change is required.",
        ],
    },
    "failed": {
        "scenario": "failed",
        "title": "Task failed",
        "summary": "The task is terminal and failed. Inspect errors and backup state before retrying.",
        "safe_to_retry": False,
        "recommended_steps": [
            "Read task-status and operation details to identify the failing step.",
            "List backups for the document_id and restore the latest known-good backup if partial mutation is suspected.",
            "Validate or snapshot the document before retrying.",
            "Retry with a new request_id only after evidence shows the previous attempt is no longer active.",
        ],
    },
    "cancelled": {
        "scenario": "cancelled",
        "title": "Task was cancelled",
        "summary": "The task is terminal because execution was cancelled before normal completion.",
        "safe_to_retry": False,
        "recommended_steps": [
            "Check whether the operation created an output, backup, or partial document change.",
            "Restore a known-good backup if the document is not in the expected state.",
            "Start a new task_id and request_id after cleanup is complete.",
        ],
    },
    "missing": {
        "scenario": "ambiguous_missing_status",
        "title": "Task status is missing",
        "summary": "No task status record exists for the supplied task_id. Treat the situation as ambiguous.",
        "safe_to_retry": False,
        "recommended_steps": [
            "Search operations by the request_id if one is known.",
            "Check documents, snapshots, and backups for evidence of a prior run.",
            "Avoid rerunning mutating commands until the previous attempt is accounted for.",
            "Create a task status record before starting a new long-running operation.",
        ],
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def task_status_state_path(workspace: str | Path = ".") -> Path:
    return Path(workspace) / ".wps-agent" / TASK_STATUS_FILE


@contextmanager
def _status_transaction(workspace: str | Path):
    state_file = task_status_state_path(workspace)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    # Keep a stable lock inode separate from the JSON replaced on every commit.
    with _STATUS_THREAD_LOCK, state_file.with_suffix(".lock").open("a+b") as lock_file:
        if os.name == "nt":
            import msvcrt

            # Windows permits locking a range beyond EOF; no racing initialization write.
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _read_task_statuses_unlocked(workspace: str | Path = ".") -> dict[str, Any]:
    state_file = task_status_state_path(workspace)
    if not state_file.exists():
        return {"tasks": {}}
    return json.loads(state_file.read_text(encoding="utf-8"))


def read_task_statuses(workspace: str | Path = ".") -> dict[str, Any]:
    if not task_status_state_path(workspace).exists():
        return {"tasks": {}}
    with _status_transaction(workspace):
        return _read_task_statuses_unlocked(workspace)


def _write_task_statuses_unlocked(state: dict[str, Any], workspace: str | Path = ".") -> None:
    state_file = task_status_state_path(workspace)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=state_file.parent,
                                         prefix=".task-status-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, state_file)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_task_statuses(state: dict[str, Any], workspace: str | Path = ".") -> None:
    with _status_transaction(workspace):
        _write_task_statuses_unlocked(state, workspace)


def _validate_state(state: str) -> list[dict[str, str]]:
    if state not in VALID_STATES:
        return [
            {
                "code": "INVALID_STATE",
                "message": f"State must be one of: {', '.join(sorted(VALID_STATES))}",
            }
        ]
    return []


def _validate_progress(progress_percent: int) -> list[dict[str, str]]:
    if progress_percent < 0 or progress_percent > 100:
        return [
            {
                "code": "INVALID_PROGRESS",
                "message": "progress_percent must be between 0 and 100.",
            }
        ]
    return []


def create_task_status(
    command: str,
    request_id: str,
    task_id: str | None = None,
    document_id: str | None = None,
    message: str | None = None,
    recovery_guidance: list[str] | None = None,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    with _status_transaction(workspace):
        return _create_task_status_unlocked(command, request_id, task_id, document_id,
                                            message, recovery_guidance, workspace)


def _create_task_status_unlocked(
    command: str,
    request_id: str,
    task_id: str | None = None,
    document_id: str | None = None,
    message: str | None = None,
    recovery_guidance: list[str] | None = None,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]], bool]:
    state = _read_task_statuses_unlocked(workspace)
    resolved_task_id = task_id or f"task_{uuid4().hex[:16]}"
    existing = state.setdefault("tasks", {}).get(resolved_task_id)
    if existing:
        owner = {"command": command, "request_id": request_id, "document_id": document_id}
        if any(existing.get(key) != value for key, value in owner.items()):
            return False, dict(existing), [{
                "code": "TASK_ID_CONFLICT",
                "message": "Task ID belongs to a different command, request, or document.",
            }], False
        return True, dict(existing), [], True

    timestamp = _now()
    record = {
        "task_id": resolved_task_id,
        "command": command,
        "request_id": request_id,
        "document_id": document_id,
        "state": "pending",
        "terminal": False,
        "progress_percent": 0,
        "message": message or "Task is pending.",
        "recovery_guidance": recovery_guidance or [],
        "created_at": timestamp,
        "updated_at": timestamp,
        "started_at": None,
        "completed_at": None,
        "result_ref": None,
    }
    state["tasks"][resolved_task_id] = record
    _write_task_statuses_unlocked(state, workspace)
    return True, record, [], False


def update_task_status(
    task_id: str,
    state_value: str,
    progress_percent: int | None = None,
    message: str | None = None,
    recovery_guidance: list[str] | None = None,
    result_ref: str | None = None,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    with _status_transaction(workspace):
        return _update_task_status_unlocked(task_id, state_value, progress_percent,
                                            message, recovery_guidance, result_ref, workspace)


def _update_task_status_unlocked(
    task_id: str,
    state_value: str,
    progress_percent: int | None = None,
    message: str | None = None,
    recovery_guidance: list[str] | None = None,
    result_ref: str | None = None,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    errors = _validate_state(state_value)
    if progress_percent is not None:
        errors.extend(_validate_progress(progress_percent))
    if errors:
        return False, {}, errors

    state = _read_task_statuses_unlocked(workspace)
    record = state.get("tasks", {}).get(task_id)
    if not record:
        return (
            False,
            {},
            [{"code": "TASK_STATUS_NOT_FOUND", "message": f"Task status not found: {task_id}"}],
        )
    if record.get("terminal"):
        return (
            False,
            dict(record),
            [{"code": "TASK_ALREADY_TERMINAL", "message": f"Task is already terminal: {task_id}"}],
        )

    timestamp = _now()
    previous_state = record.get("state")
    record["state"] = state_value
    record["terminal"] = state_value in TERMINAL_STATES
    record["updated_at"] = timestamp
    if previous_state == "pending" and state_value == "running":
        record["started_at"] = timestamp
    if record["terminal"]:
        record["completed_at"] = timestamp
        record["progress_percent"] = 100 if state_value == "succeeded" else record.get("progress_percent", 0)
    elif progress_percent is not None:
        record["progress_percent"] = progress_percent
    if progress_percent is not None and not record["terminal"]:
        record["progress_percent"] = progress_percent
    if message is not None:
        record["message"] = message
    if recovery_guidance is not None:
        record["recovery_guidance"] = recovery_guidance
    if result_ref is not None:
        record["result_ref"] = result_ref

    state.setdefault("tasks", {})[task_id] = record
    _write_task_statuses_unlocked(state, workspace)
    return True, dict(record), []


def get_task_status(task_id: str, workspace: str | Path = ".") -> dict[str, Any] | None:
    state = read_task_statuses(workspace)
    record = state.get("tasks", {}).get(task_id)
    return dict(record) if record else None


def list_task_statuses(workspace: str | Path = ".") -> list[dict[str, Any]]:
    state = read_task_statuses(workspace)
    records = [dict(record) for record in state.get("tasks", {}).values()]
    return sorted(records, key=lambda item: item.get("updated_at", ""))


def _operation_reference(record: dict[str, Any]) -> str | None:
    return record.get("result_ref") or record.get("request_id")


def _command_hint(command: str, **flags: str | None) -> str:
    parts = ["python -m wps_ai_agent_cli", command]
    for name, value in flags.items():
        if value:
            parts.extend([f"--{name.replace('_', '-')}", value])
    return " ".join(parts)


def _recovery_commands(record: dict[str, Any] | None) -> list[str]:
    if not record:
        return [
            _command_hint("operations"),
            _command_hint("documents"),
        ]

    commands = [_command_hint("task-status", task_id=record.get("task_id"))]
    operation_ref = _operation_reference(record)
    if operation_ref:
        commands.append(_command_hint("operation", request=operation_ref))
    document_id = record.get("document_id")
    if document_id:
        commands.extend(
            [
                _command_hint("list-backups", document_id=document_id),
                _command_hint("snapshot-document", document_id=document_id),
            ]
        )
    return commands


def _recovery_evidence(record: dict[str, Any] | None, task_id: str) -> dict[str, Any]:
    if not record:
        return {
            "task_id": task_id,
            "task_status_found": False,
            "state": "missing",
            "terminal": False,
        }
    return {
        "task_id": record.get("task_id"),
        "task_status_found": True,
        "state": record.get("state"),
        "terminal": record.get("terminal"),
        "progress_percent": record.get("progress_percent"),
        "command": record.get("command"),
        "request_id": record.get("request_id"),
        "result_ref": record.get("result_ref"),
        "document_id": record.get("document_id"),
        "updated_at": record.get("updated_at"),
        "completed_at": record.get("completed_at"),
    }


def build_recovery_playbook(
    task_id: str,
    workspace: str | Path = ".",
) -> dict[str, Any]:
    record = get_task_status(task_id, workspace)
    state = record.get("state") if record else "missing"
    template = RECOVERY_PLAYBOOKS.get(state, RECOVERY_PLAYBOOKS["missing"])
    playbook = dict(template)
    playbook["evidence"] = _recovery_evidence(record, task_id)
    playbook["commands"] = _recovery_commands(record)
    if record and record.get("recovery_guidance"):
        playbook["task_recovery_guidance"] = list(record["recovery_guidance"])
    else:
        playbook["task_recovery_guidance"] = []
    return playbook


def list_recovery_playbooks() -> list[dict[str, Any]]:
    return [dict(RECOVERY_PLAYBOOKS[key]) for key in sorted(RECOVERY_PLAYBOOKS)]
