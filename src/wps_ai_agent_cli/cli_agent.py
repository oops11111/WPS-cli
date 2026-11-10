"""Agent convenience commands: batch (C-07), get by path (C-08), document-view and document-check (C-09)."""

from __future__ import annotations

from .agent_tools import document_check, document_view, get_by_path, load_commands, run_batch
from .cli_common import BACKEND
from .models import CommandResponse


def batch_response(
    request_id: str, commands_json: str | None, commands_file: str | None, continue_on_error: bool
) -> CommandResponse:
    commands, problem = load_commands(commands_json, commands_file)
    if problem:
        ok, data, errors = False, {}, [{"code": "INVALID_ARGUMENT", "message": problem}]
    else:
        ok, data, errors = run_batch(commands, request_id, continue_on_error)
    if ok:
        summary = f"Ran {data['ran']} commands; all succeeded."
    elif data.get("results") is not None:
        summary = f"Ran {data['ran']} of {data['commands']} commands; {len(data['failed'])} failed."
    else:
        summary = "Batch could not start."
    return CommandResponse(
        ok=ok, command="batch", request_id=request_id, backend=BACKEND, summary=summary, data=data, errors=errors
    )


def get_response(request_id: str, document_id: str, path: str) -> CommandResponse:
    ok, data, errors = get_by_path(document_id, path)
    return CommandResponse(
        ok=ok,
        command="get",
        request_id=request_id,
        backend="python",
        summary=f"Read {path}." if ok else f"Could not read {path}.",
        data=data,
        errors=errors,
    )


def document_view_response(request_id: str, document_id: str) -> CommandResponse:
    ok, data, errors = document_view(document_id)
    return CommandResponse(
        ok=ok,
        command="document-view",
        request_id=request_id,
        backend="python",
        summary=f"Summarised the {data.get('component')} document." if ok else "Could not read the document.",
        data=data,
        errors=errors,
    )


def document_check_response(request_id: str, document_id: str) -> CommandResponse:
    ok, data, errors = document_check(document_id)
    if ok:
        counts = data["counts"]
        summary = (
            f"Found {counts['error']} errors, {counts['warning']} warnings, {counts['info']} notes."
            if any(counts.values())
            else "No problems found."
        )
    else:
        summary = "Could not check the document."
    return CommandResponse(
        ok=ok,
        command="document-check",
        request_id=request_id,
        backend="python",
        summary=summary,
        data=data,
        errors=errors,
    )
