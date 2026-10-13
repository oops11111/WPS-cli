"""Writer document commands."""

from __future__ import annotations

from .artifacts import write_json_artifact
from .models import CommandResponse, ValidationResult
from .writer_ops import writer_fill_bookmark, writer_replace, writer_table_write
from .writer_inspect import inspect_writer_structure
from .writer_structure_parity import run_writer_structure_parity
from .writer_table_smoke import run_writer_table_smoke
from .cli_common import BACKEND


def writer_table_smoke_response(
    request_id: str,
    input_path: str,
    output_path: str,
    table_index: int,
    row: int,
    column: int,
    text: str,
) -> CommandResponse:
    result = run_writer_table_smoke(
        input_path=input_path,
        output_path=output_path,
        table_index=table_index,
        row=row,
        column=column,
        text=text,
        request_id=request_id,
    )
    data = result["data"]
    return CommandResponse(
        ok=result["ok"],
        command="writer-table-smoke",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Writer table smoke run completed."
            if result["ok"]
            else "Writer table smoke run could not complete."
        ),
        data=data,
        validation=ValidationResult(
            status="passed" if result["ok"] else "failed",
            checks=[
                {
                    "name": "output_file_created",
                    "passed": bool(data.get("output_bytes")),
                    "details": data.get("output_path"),
                },
                {
                    "name": "writer_table_validated",
                    "passed": bool(data.get("writer_table", {}).get("validation_passed")),
                    "details": data.get("writer_table", {}).get("read_back_text"),
                },
                {
                    "name": "backup_available",
                    "passed": bool(data.get("backup_exists")),
                    "details": data.get("writer_table", {}).get("backup", {}).get("backup_path"),
                },
                {
                    "name": "restore_dry_run_available",
                    "passed": bool(data.get("restore_check", {}).get("ok")),
                    "details": data.get("restore_check", {}).get("result", {}).get("backup_name"),
                },
            ],
        ),
        errors=result["errors"],
    )


def writer_replace_response(
    request_id: str,
    document_id: str,
    find_text: str,
    replace_text: str,
    dry_run: bool,
    paragraph_index: int | None,
) -> CommandResponse:
    ok, result, errors, replayed = writer_replace(
        document_id=document_id,
        find_text=find_text,
        replace_text=replace_text,
        request_id=request_id,
        dry_run=dry_run,
        paragraph_index=paragraph_index,
    )
    return CommandResponse(
        ok=ok,
        command="writer-replace",
        request_id=request_id,
        backend="wps-com" if not dry_run else BACKEND,
        summary=(
            "Writer replace request replayed from idempotency record."
            if replayed
            else "Writer replace dry-run completed."
            if dry_run and ok
            else "Writer replace completed."
            if ok
            else "Writer replace could not complete."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "matches_found",
                    "passed": bool(result.get("matches", 0) > 0),
                    "details": result.get("matches"),
                },
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created")),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "replacement_validated",
                    "passed": bool(dry_run or result.get("validation_passed")),
                    "details": {
                        "remaining_find_count": result.get("remaining_find_count"),
                        "replace_count_delta": result.get("replace_count_delta"),
                    },
                },
            ],
        ),
        errors=errors,
    )


def writer_fill_bookmark_response(
    request_id: str, document_id: str, bookmark_name: str, text: str, dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = writer_fill_bookmark(
        document_id=document_id, bookmark_name=bookmark_name, value=text,
        request_id=request_id, dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok, command="writer-fill-bookmark", request_id=request_id,
        backend="local-python" if dry_run else "wps-com",
        summary=("Writer bookmark fill request replayed." if replayed else
                 "Writer bookmark fill dry-run completed." if ok and dry_run else
                 "Writer bookmark fill completed." if ok else "Writer bookmark fill could not complete."),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {"name": "unique_supported_bookmark", "passed": not errors or errors[0]["code"] not in {"BOOKMARK_NOT_FOUND", "BOOKMARK_AMBIGUOUS", "BOOKMARK_SCOPE_UNSUPPORTED"}, "details": result.get("bookmark_name")},
                {"name": "backup_created", "passed": dry_run or bool(result.get("backup", {}).get("created")), "details": result.get("backup", {}).get("backup_path")},
                {"name": "bookmark_readback_matches", "passed": dry_run or bool(result.get("readback_passed")), "details": result.get("readback_passed")},
            ],
        ),
        errors=errors,
    )


def writer_table_write_response(
    request_id: str,
    document_id: str,
    table_index: int,
    row: int,
    column: int,
    text: str,
    dry_run: bool,
    allow_rich_content: bool = False,
) -> CommandResponse:
    ok, result, errors, replayed = writer_table_write(
        document_id=document_id,
        table_index=table_index,
        row=row,
        column=column,
        text=text,
        request_id=request_id,
        dry_run=dry_run,
        allow_rich_content=allow_rich_content,
    )
    return CommandResponse(
        ok=ok,
        command="writer-table-write",
        request_id=request_id,
        backend="wps-com" if not dry_run else BACKEND,
        summary=(
            "Writer table write request replayed from idempotency record."
            if replayed
            else "Writer table write dry-run completed."
            if dry_run and ok
            else "Writer table write completed."
            if ok
            else "Writer table write could not complete."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "table_cell_found",
                    "passed": ok,
                    "details": {
                        "table_index": table_index,
                        "row": row,
                        "column": column,
                        "current_text": result.get("current_text"),
                    },
                },
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "cell_write_validated",
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


def writer_structure_response(request_id: str, document_id: str, limit: int, section: str = "all",
                              offset: int = 0, bookmark_name: str | None = None,
                              expected_sha256: str | None = None, include_text: bool = False,
                              text_limit: int = 200) -> CommandResponse:
    ok, result, errors = inspect_writer_structure(
        document_id, limit, section=section, offset=offset, bookmark_name=bookmark_name,
        expected_sha256=expected_sha256, include_text=include_text, text_limit=text_limit,
    )
    return CommandResponse(
        ok=ok, command="writer-structure", request_id=request_id, backend=BACKEND,
        summary="Writer structure inspected from OOXML." if ok else "Writer structure inspection failed.",
        data={"writer_structure": result},
        validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "offline_structure_available", "passed": ok, "details": result.get("path")},
        ]), errors=errors,
    )


def writer_structure_parity_response(request_id: str, run_wps: bool, timeout_seconds: int,
                                     artifact_dir: str | None, scope: str = "structure") -> CommandResponse:
    ok, report, errors = run_writer_structure_parity(run_wps=run_wps, timeout_seconds=timeout_seconds, scope=scope)
    response = CommandResponse(
        ok=ok, command="writer-structure-parity", request_id=request_id, backend=BACKEND,
        summary="Writer structure parity passed." if ok else "Writer structure parity did not pass.",
        data={"writer_structure_parity": report},
        validation=ValidationResult(status="passed" if ok else "failed", checks=report.get("checks", [])),
        errors=errors,
    )
    if not run_wps:
        return response
    prefix = "writer-nested-parity" if scope == "nested" else "writer-structure-parity"
    artifact = write_json_artifact(response.to_dict(), artifact_dir or f"artifacts/{prefix}", prefix, request_id)
    return CommandResponse(
        ok=response.ok, command=response.command, request_id=response.request_id,
        backend=response.backend, summary=response.summary, data={**response.data, "artifact": artifact},
        validation=response.validation, errors=response.errors,
    )
