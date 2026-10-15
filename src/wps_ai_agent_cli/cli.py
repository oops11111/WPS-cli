from __future__ import annotations

import sys
from typing import TextIO
from uuid import uuid4

from .cli_common import BACKEND

# cli_handlers reads every command handler from this module (cli.<name>_response), and tests patch
# some of them here, so the handlers are re-exported from their modules.
from .cli_documents import (  # noqa: F401
    backup_document_response,
    documents_response,
    list_backups_response,
    mutation_request_inspect_response,
    operation_response,
    operations_response,
    register_document_response,
    restore_backup_response,
    snapshot_document_response,
    task_recovery_playbooks_response,
    task_recovery_response,
    validate_document_response,
)
from .cli_environment import (  # noqa: F401
    calc_smoke_response,
    cleanup_approval_manifest_response,
    cleanup_plan_response,
    com_smoke_response,
    convert_smoke_response,
    inspect_env_response,
    performance_baseline_response,
    plan_response,
    security_audit_response,
    tasks_response,
    wps_process_audit_response,
    wps_version_compare_response,
)
from .cli_html import (  # noqa: F401
    batch_report_response,
    batch_template_report_response,
    html_batch_convert_response,
    html_batch_request_response,
    html_controlled_import_response,
    html_editable_response,
    html_render_response,
    html_roundtrip_export_response,
    html_roundtrip_plan_response,
    html_roundtrip_verify_response,
    scan_dir_response,
)
from .cli_mcp import (  # noqa: F401
    mcp_call_response,
    mcp_catalog_drift_response,
    mcp_catalog_snapshot_response,
    mcp_config_audit_response,
    mcp_smoke_response,
    mcp_tool_schema_response,
    mcp_tools_response,
    regression_manifest_response,
    regression_run_response,
)
from .cli_open_documents import (  # noqa: F401
    export_open_document_copy_response,
    export_open_document_pdf_response,
    export_open_document_response,
    export_open_document_text_response,
    open_documents_response,
    presentation_selection_delete_response,
    presentation_selection_insert_response,
    presentation_selection_read_response,
    presentation_selection_replace_response,
    save_as_open_document_response,
    save_open_document_response,
    spreadsheet_selection_delete_response,
    spreadsheet_selection_read_response,
    spreadsheet_selection_replace_response,
    writer_selection_delete_response,
    writer_selection_insert_response,
    writer_selection_read_response,
    writer_selection_replace_response,
)
from .cli_parser import build_parser
from .cli_presentation import (  # noqa: F401
    presentation_replace_response,
)
from .cli_spreadsheet import (  # noqa: F401
    spreadsheet_copy_sheet_response,
    spreadsheet_create_sheet_response,
    spreadsheet_delete_sheet_response,
    spreadsheet_formula_write_response,
    spreadsheet_inspect_response,
    spreadsheet_read_response,
    spreadsheet_rename_sheet_response,
    spreadsheet_set_sheet_tab_color_response,
    spreadsheet_set_sheet_visibility_response,
    spreadsheet_sheets_response,
    spreadsheet_write_response,
)
from .cli_writer import (  # noqa: F401
    writer_fill_bookmark_response,
    writer_replace_response,
    writer_structure_parity_response,
    writer_structure_response,
    writer_table_smoke_response,
    writer_table_write_response,
)
from .errors import DOCUMENT_HELD_OPEN
from .file_hold import is_share_conflict
from .jsonio import dumps_json

# cli_handlers reaches these through this module (cli.handle_mcp_json, cli.serve_stdio).
from .mcp_server import handle_mcp_json, serve_stdio  # noqa: F401
from .models import CommandResponse, ValidationResult
from .ooxml import OoxmlTooLargeError
from .state_store import StateCorruptError
from .task_status import (
    create_task_status,
    get_task_status,
    list_task_statuses,
    update_task_status,
)


def _configure_stdout() -> None:
    """Read and write UTF-8 on the standard streams, whatever the console code page.

    stdin matters for mcp-server: an MCP client sends its JSON-RPC requests as UTF-8, and Python on a Chinese
    Windows reads stdin as GBK by default, so every non-ASCII argument reached the tools garbled; the untitled
    document name 文字文稿1 could not be found (P7-007).
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")


def _request_id(value: str | None) -> str:
    return value or str(uuid4())


def _extract_request_id(argv: list[str]) -> tuple[list[str], str | None]:
    cleaned: list[str] = []
    request_id = None
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--request-id":
            if index + 1 >= len(argv):
                cleaned.append(item)
            else:
                request_id = argv[index + 1]
                index += 1
        elif item.startswith("--request-id="):
            request_id = item.split("=", 1)[1]
        else:
            cleaned.append(item)
        index += 1
    return cleaned, request_id


def task_status_create_response(
    request_id: str,
    task_id: str | None,
    command: str,
    operation_request_id: str,
    document_id: str | None,
    message: str | None,
    recovery_guidance: list[str],
) -> CommandResponse:
    ok, result, errors, replayed = create_task_status(
        task_id=task_id,
        command=command,
        request_id=operation_request_id,
        document_id=document_id,
        message=message,
        recovery_guidance=recovery_guidance,
    )
    return CommandResponse(
        ok=ok,
        command="task-status-create",
        request_id=request_id,
        backend=BACKEND,
        summary=(
            "Task status replayed from existing task_id."
            if replayed
            else "Task status created."
            if ok
            else "Task status create failed."
        ),
        data={"task_status": result},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "task_status_created",
                    "passed": ok,
                    "details": {
                        "task_id": result.get("task_id"),
                        "state": result.get("state"),
                        "terminal": result.get("terminal"),
                    },
                }
            ],
        ),
        errors=errors,
    )


def task_status_update_response(
    request_id: str,
    task_id: str,
    state: str,
    progress_percent: int | None,
    message: str | None,
    recovery_guidance: list[str] | None,
    result_ref: str | None,
) -> CommandResponse:
    ok, result, errors = update_task_status(
        task_id=task_id,
        state_value=state,
        progress_percent=progress_percent,
        message=message,
        recovery_guidance=recovery_guidance,
        result_ref=result_ref,
    )
    return CommandResponse(
        ok=ok,
        command="task-status-update",
        request_id=request_id,
        backend=BACKEND,
        summary="Task status updated." if ok else "Task status update failed.",
        data={"task_status": result},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "task_status_updated",
                    "passed": ok,
                    "details": {
                        "task_id": result.get("task_id"),
                        "state": result.get("state"),
                        "progress_percent": result.get("progress_percent"),
                        "terminal": result.get("terminal"),
                    },
                }
            ],
        ),
        errors=errors,
    )


def task_status_response(request_id: str, task_id: str) -> CommandResponse:
    result = get_task_status(task_id)
    ok = result is not None
    return CommandResponse(
        ok=ok,
        command="task-status",
        request_id=request_id,
        backend=BACKEND,
        summary="Task status returned." if ok else "Task status not found.",
        data={"task_status": result} if result else {},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[{"name": "task_status_exists", "passed": ok, "details": task_id}],
        ),
        errors=[] if ok else [{"code": "TASK_STATUS_NOT_FOUND", "message": f"Task status not found: {task_id}"}],
    )


def task_statuses_response(request_id: str) -> CommandResponse:
    statuses = list_task_statuses()
    return CommandResponse(
        ok=True,
        command="task-statuses",
        request_id=request_id,
        backend=BACKEND,
        summary=f"Returned {len(statuses)} task statuses.",
        data={"task_statuses": statuses},
        validation=ValidationResult(status="not_applicable"),
    )


def _with_optional_task_status(
    response_factory,
    task_id: str | None,
    tracked_command: str,
    operation_request_id: str,
    document_id: str | None = None,
) -> CommandResponse:
    if not task_id:
        return response_factory()

    _ok, status, _errors, _replayed = create_task_status(
        task_id=task_id,
        command=tracked_command,
        request_id=operation_request_id,
        document_id=document_id,
        message=f"{tracked_command} queued.",
        recovery_guidance=[
            "Run task-status with this task_id before retrying.",
            "Check operation by request_id if the command reached a terminal state.",
        ],
    )
    if _ok and status.get("state") in {"cancelled", "failed"}:
        _ok = False
        _errors = [
            {
                "code": "TASK_ALREADY_TERMINAL",
                "message": "Use a new task ID after reviewing the failed or cancelled operation.",
            }
        ]
    if _ok and not status.get("terminal"):
        _ok, status, _errors = update_task_status(
            task_id,
            "running",
            progress_percent=10,
            message=f"{tracked_command} running.",
        )
    if not _ok:
        return CommandResponse(
            ok=False,
            command=tracked_command,
            request_id=operation_request_id,
            backend=BACKEND,
            summary="Task tracking preflight failed; operation was not started.",
            data={"task_status": status},
            validation=ValidationResult(status="failed"),
            errors=_errors,
        )
    try:
        response = response_factory()
    except BaseException as exc:
        current_status = get_task_status(task_id)
        if current_status and not current_status.get("terminal"):
            update_task_status(
                task_id,
                "failed",
                message=f"{tracked_command} raised {type(exc).__name__}: {exc}",
                recovery_guidance=[
                    "The operation raised an unexpected exception; run mutation-request-inspect with the request_id before retrying.",
                ],
                result_ref=operation_request_id,
            )
        raise
    current_status = get_task_status(task_id)
    if current_status and not current_status.get("terminal"):
        update_task_status(
            task_id,
            "succeeded" if response.ok else "failed",
            message=(f"{tracked_command} completed." if response.ok else f"{tracked_command} failed."),
            recovery_guidance=[]
            if response.ok
            else [
                "Inspect response errors before retrying.",
                "Run task-status with this task_id to avoid duplicate work.",
            ],
            result_ref=operation_request_id,
        )
        current_status = get_task_status(task_id)
    if current_status:
        response.data["task_status"] = current_status
    return response


# Imported last: cli_handlers reads the handler functions defined above from this module.
from .cli_handlers import build_command_handlers  # noqa: E402

COMMAND_HANDLERS = build_command_handlers(sys.modules[__name__])


def _run_command(argv: list[str], output_stream: TextIO | None = None, strict_exit: bool = False) -> int:
    if output_stream is None:
        _configure_stdout()
    argv, extracted_request_id = _extract_request_id(list(argv))
    parser = build_parser()
    args = parser.parse_args(argv)
    request_id = _request_id(extracted_request_id or args.request_id)

    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:  # pragma: no cover - argparse enforces valid commands
        parser.error(f"Unsupported command: {args.command}")
    response = handler(args, request_id, output_stream)
    if isinstance(response, int):
        return response

    print(dumps_json(response.to_dict()), file=output_stream or sys.stdout)
    return 0 if response.ok or not strict_exit else 1


def run(argv: list[str] | None = None, output_stream: TextIO | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    strict_exit = "--strict-exit" in argv
    argv = [item for item in argv if item != "--strict-exit"]
    try:
        return _run_command(argv, output_stream, strict_exit)
    except (StateCorruptError, OoxmlTooLargeError) as exc:
        command = next((item for item in argv if not item.startswith("-")), "unknown")
        _, request_id = _extract_request_id(argv)
        response = CommandResponse(
            ok=False,
            command=command,
            request_id=request_id or "unknown",
            backend=BACKEND,
            summary=(
                "Workspace state file is corrupt and was quarantined; the command stopped. If it modifies documents, "
                "it may already have been applied before the state was read again - run mutation-request-inspect before retrying."
                if isinstance(exc, StateCorruptError)
                else "Input document exceeds the supported size limits; the command was not executed."
            ),
            data=dict(exc.details),
            validation=ValidationResult(status="failed"),
            errors=[{"code": exc.code, "message": str(exc)}],
        )
        print(dumps_json(response.to_dict()), file=output_stream or sys.stdout)
        return 1 if strict_exit else 0
    except OSError as exc:
        # A command that does not check for a held file itself (for example spreadsheet-read or batch-report)
        # still answers with a DOCUMENT_HELD_OPEN envelope, not an uncaught PermissionError.
        if not is_share_conflict(exc):
            raise
        command = next((item for item in argv if not item.startswith("-")), "unknown")
        _, request_id = _extract_request_id(argv)
        mutating = _command_mutates_document(command)
        response = CommandResponse(
            ok=False,
            command=command,
            request_id=request_id or "unknown",
            backend=BACKEND,
            summary="A file the command needed is held open by another handle; the command stopped.",
            data={"path": getattr(exc, "filename", None), "mutates_document": mutating},
            validation=ValidationResult(status="failed"),
            errors=[{"code": DOCUMENT_HELD_OPEN, "message": _held_during_command_message(exc, mutating)}],
        )
        print(dumps_json(response.to_dict()), file=output_stream or sys.stdout)
        return 1 if strict_exit else 0


def _command_mutates_document(command: str) -> bool:
    """True unless the MCP catalog marks the command as read-only; unknown commands count as mutating."""
    from .mcp_schema import list_mcp_tool_schemas

    for schema in list_mcp_tool_schemas():
        if schema["cli_command"] == command:
            return bool(schema.get("mutates_document"))
    return True


def _held_during_command_message(exc: OSError, mutating: bool) -> str:
    message = (
        f"A file the command needed is held open by another handle ({exc}), most likely because it is open in WPS. "
        "Save or close the document in WPS (or the program that holds the file) and retry."
    )
    if mutating:
        return message + (
            " This command can change documents and stopped part way, so check what was applied with "
            "mutation-request-inspect before retrying."
        )
    return message + " This command does not change documents, so no document was changed."


def main() -> int:
    return run(sys.argv[1:])
