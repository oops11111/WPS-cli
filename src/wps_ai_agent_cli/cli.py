from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from typing import TextIO
from uuid import uuid4

from .artifacts import write_json_artifact
from .cli_parser import build_parser
from .artifact_retention import build_artifact_retention_summary
from .backups import create_backup, list_backups, restore_backup
from .batch_report import build_batch_report
from .batch_conversion import convert_html_batch, inspect_batch_request
from .capabilities import probe_wps_capabilities
from .cleanup_approval import build_cleanup_approval_manifest
from .cleanup_plan import build_cleanup_plan
from .cloud_sync import build_cloud_sync_package
from .com_backend import run_com_smoke, run_conversion_smoke, run_spreadsheet_calc_smoke
from .documentation_freshness import build_documentation_freshness_report
from .file_scan import scan_directory
from .jsonio import dumps_json
from .local_handoff import build_local_handoff_summary
from .html_render import render_html
from .html_editable import convert_html_editable
from .html_roundtrip import build_html_roundtrip_mapping, export_controlled_html, import_controlled_html, verify_controlled_document
from .mcp_adapter import call_mcp_tool
from .mcp_catalog_drift import DEFAULT_MCP_CATALOG_GUARD, build_mcp_catalog_drift_report
from .mcp_catalog import build_mcp_catalog_snapshot
from .mcp_config_audit import audit_mcp_client_config
from .mcp_schema import get_mcp_tool_schema, list_mcp_tool_categories, list_mcp_tool_schemas
from .mcp_server import handle_mcp_json, serve_stdio
from .mcp_smoke import run_mcp_server_smoke
from .models import CommandResponse, ValidationResult
from .operations import get_operation, inspect_mutation_request, list_operations
from .phases import list_phases
from .performance import capture_performance_baseline
from .process_audit import audit_wps_processes
from .project_status import build_project_status
from .presentation_ops import presentation_replace
from .regression import load_regression_manifest, list_regression_scenarios, run_regression_manifest
from .regression_evidence import build_regression_evidence
from .regression_history import build_regression_history
from .security_audit import build_security_boundary_audit
from .sessions import list_documents, register_document
from .ooxml import OoxmlTooLargeError
from .state_store import StateCorruptError
from .snapshots import snapshot_document
from .spreadsheet_ops import copy_spreadsheet_sheet, create_spreadsheet_sheet, delete_spreadsheet_sheet, list_spreadsheet_sheets, read_spreadsheet_range, rename_spreadsheet_sheet, set_spreadsheet_sheet_tab_color, set_spreadsheet_sheet_visibility, write_spreadsheet_formulas, write_spreadsheet_range
from .spreadsheet_inspect import inspect_spreadsheet_range
from .sync_package_coverage import build_sync_package_coverage
from .sync_package_inspect import DEFAULT_SYNC_PACKAGE, inspect_sync_package
from .sync_package_manifest import build_sync_package_manifest
from .sync_package_readiness import build_sync_package_readiness
from .sync_package_summary import summarize_sync_package
from .task_status import (
    build_recovery_playbook,
    create_task_status,
    get_task_status,
    list_recovery_playbooks,
    list_task_statuses,
    update_task_status,
)
from .template_report import render_batch_template_report
from .tasks import list_tasks
from .validators import validate_document
from .validation_runbook import build_validation_runbook
from .workspace_health import build_workspace_health
from .open_documents import (
    export_open_document_html,
    list_open_documents,
    read_writer_selection,
    replace_writer_selection,
)
from .writer_ops import writer_fill_bookmark, writer_replace, writer_table_write
from .writer_inspect import inspect_writer_structure
from .writer_structure_parity import run_writer_structure_parity
from .writer_table_smoke import run_writer_table_smoke


BACKEND = "local-python"


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


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


def inspect_env_response(request_id: str) -> CommandResponse:
    data = probe_wps_capabilities()
    checks = [
        {
            "name": "windows_host",
            "passed": data["platform"]["is_windows"],
            "details": data["platform"]["system"],
        },
        {
            "name": "pywin32_available",
            "passed": data["dependencies"]["pywin32_available"],
            "details": "required for COM integration",
        },
    ]
    for name, component in data["components"].items():
        checks.append(
            {
                "name": f"{name}_prog_id_registered",
                "passed": component["detected"],
                "details": component["selected_prog_id"],
            }
        )

    passed_count = sum(1 for check in checks if check["passed"])
    status = "passed" if passed_count == len(checks) else "warning"
    return CommandResponse(
        ok=True,
        command="inspect-env",
        request_id=request_id,
        backend=BACKEND,
        summary="Environment capability probe completed.",
        data=data,
        validation=ValidationResult(status=status, checks=checks),
    )


def wps_process_audit_response(request_id: str, timeout_seconds: int) -> CommandResponse:
    ok, result, errors = audit_wps_processes(timeout_seconds=timeout_seconds)
    return CommandResponse(
        ok=ok,
        command="wps-process-audit",
        request_id=request_id,
        backend=BACKEND,
        summary="WPS process audit completed." if ok else "WPS process audit failed.",
        data={"wps_process_audit": result},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "process_scan_completed",
                    "passed": ok,
                    "details": result.get("process_count"),
                },
                {
                    "name": "no_automatic_process_kill",
                    "passed": True,
                    "details": "Read-only process audit.",
                },
            ],
    ),
        errors=errors,
    )


def cleanup_plan_response(request_id: str, workspace: str) -> CommandResponse:
    plan = build_cleanup_plan(workspace=workspace)
    return CommandResponse(
        ok=True,
        command="cleanup-plan",
        request_id=request_id,
        backend=BACKEND,
        summary="Read-only local cleanup plan generated; no files were deleted.",
        data={"cleanup_plan": plan},
        validation=ValidationResult(
            status="passed",
            checks=[
                {
                    "name": "read_only_plan",
                    "passed": plan["read_only"] and not plan["deletion_performed"],
                    "details": "No removal operation is performed by cleanup-plan.",
                },
                {
                    "name": "approval_required",
                    "passed": plan["approval_required"],
                    "details": f"{plan['candidate_count']} candidate groups require explicit approval.",
                },
            ],
        ),
    )


def cleanup_approval_manifest_response(request_id: str, workspace: str) -> CommandResponse:
    manifest = build_cleanup_approval_manifest(workspace=workspace)
    return CommandResponse(
        ok=True,
        command="cleanup-approval-manifest",
        request_id=request_id,
        backend=BACKEND,
        summary="Read-only cleanup approval manifest generated; no files were deleted.",
        data={"cleanup_approval_manifest": manifest},
        validation=ValidationResult(
            status="passed",
            checks=[
                {
                    "name": "read_only_manifest",
                    "passed": manifest["read_only"] and not manifest["deletion_performed"],
                    "details": "No removal operation is performed by cleanup-approval-manifest.",
                },
                {
                    "name": "approval_categories_available",
                    "passed": len(manifest["categories"]) >= 1,
                    "details": [category["category"] for category in manifest["categories"]],
                },
            ],
        ),
    )


def artifact_retention_summary_response(request_id: str, workspace: str) -> CommandResponse:
    summary = build_artifact_retention_summary(workspace=workspace)
    ok = summary["retention_status"] == "passed"
    return CommandResponse(
        ok=ok,
        command="artifact-retention-summary",
        request_id=request_id,
        backend=BACKEND,
        summary="Artifact retention summary is passed." if ok else "Artifact retention summary needs review.",
        data={"artifact_retention_summary": summary},
        validation=ValidationResult(status=summary["retention_status"], checks=summary["checks"]),
    )


def plan_response(request_id: str) -> CommandResponse:
    return CommandResponse(
        ok=True,
        command="plan",
        request_id=request_id,
        backend=BACKEND,
        summary="Development roadmap loaded from PRD v1.1 phase goals.",
        data={"phases": list_phases()},
        validation=ValidationResult(status="not_applicable"),
    )


def project_status_response(request_id: str, workspace: str) -> CommandResponse:
    status = build_project_status(workspace=workspace)
    next_count = len(status["next_tasks"])
    return CommandResponse(
        ok=True,
        command="project-status",
        request_id=request_id,
        backend=BACKEND,
        summary=f"Local project status returned with {next_count} next task(s).",
        data={"project_status": status},
        validation=ValidationResult(
            status="passed",
            checks=[
                {
                    "name": "next_task_available",
                    "passed": next_count >= 1,
                    "details": [task["id"] for task in status["next_tasks"]],
                },
                {
                    "name": "cleanup_is_read_only",
                    "passed": status["cleanup"]["read_only"] and not status["cleanup"]["deletion_performed"],
                    "details": status["cleanup"],
                },
                {
                    "name": "remote_git_not_required",
                    "passed": status["remote_git_required"] is False,
                    "details": "Local-only continuation mode.",
                },
            ],
        ),
    )


def workspace_health_response(request_id: str, workspace: str) -> CommandResponse:
    health = build_workspace_health(workspace=workspace)
    return CommandResponse(
        ok=health["health_status"] == "passed",
        command="workspace-health",
        request_id=request_id,
        backend=BACKEND,
        summary=f"Local workspace health is {health['health_status']}.",
        data={"workspace_health": health},
        validation=ValidationResult(
            status=health["health_status"],
            checks=health["checks"],
        ),
    )


def local_handoff_summary_response(request_id: str, workspace: str) -> CommandResponse:
    ok, handoff, errors = build_local_handoff_summary(workspace)
    return CommandResponse(
        ok=ok,
        command="local-handoff-summary",
        request_id=request_id,
        backend=BACKEND,
        summary="Local handoff summary is passed." if ok else "Local handoff summary needs review.",
        data={"local_handoff_summary": handoff},
        validation=ValidationResult(status="passed" if ok else "warning", checks=handoff.get("checks", [])),
        errors=errors,
    )


def validation_runbook_response(request_id: str, workspace: str) -> CommandResponse:
    runbook = build_validation_runbook(workspace=workspace)
    ok = runbook["runbook_status"] == "passed"
    return CommandResponse(
        ok=ok,
        command="validation-runbook",
        request_id=request_id,
        backend=BACKEND,
        summary="Validation runbook is passed." if ok else "Validation runbook needs review.",
        data={"validation_runbook": runbook},
        validation=ValidationResult(status=runbook["runbook_status"], checks=runbook["checks"]),
    )


def documentation_freshness_response(request_id: str, workspace: str) -> CommandResponse:
    report = build_documentation_freshness_report(workspace=workspace)
    ok = report["freshness_status"] == "passed"
    return CommandResponse(
        ok=ok,
        command="documentation-freshness",
        request_id=request_id,
        backend=BACKEND,
        summary="Documentation freshness is passed." if ok else "Documentation freshness needs review.",
        data={"documentation_freshness": report},
        validation=ValidationResult(status=report["freshness_status"], checks=report["checks"]),
    )


def regression_history_response(request_id: str, workspace: str, limit: int) -> CommandResponse:
    history = build_regression_history(workspace=workspace, limit=limit)
    ok = history["history_status"] == "passed"
    return CommandResponse(
        ok=ok,
        command="regression-history",
        request_id=request_id,
        backend=BACKEND,
        summary="Regression history is passed." if ok else "Regression history needs review.",
        data={"regression_history": history},
        validation=ValidationResult(status=history["history_status"], checks=history["checks"]),
    )


def tasks_response(request_id: str, phase: str | None, status: str | None) -> CommandResponse:
    tasks = list_tasks(phase=phase, status=status)
    return CommandResponse(
        ok=True,
        command="tasks",
        request_id=request_id,
        backend=BACKEND,
        summary=f"Returned {len(tasks)} development tasks.",
        data={"tasks": tasks, "filters": {"phase": phase, "status": status}},
        validation=ValidationResult(status="not_applicable"),
    )


def com_smoke_response(
    request_id: str,
    component: str,
    input_path: str,
    output_path: str,
    visible: bool,
) -> CommandResponse:
    result = run_com_smoke(
        component=component,
        input_path=input_path,
        output_path=output_path,
        visible=visible,
    )
    return CommandResponse(
        ok=result["ok"],
        command="com-smoke",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Minimal COM smoke run completed."
            if result["ok"]
            else "Minimal COM smoke run could not complete."
        ),
        data=result["data"],
        validation=ValidationResult(
            status="passed" if result["ok"] else "failed",
            checks=[
                {
                    "name": "open_save_close",
                    "passed": result["ok"],
                    "details": component,
                }
            ],
        ),
        errors=result["errors"],
    )


def calc_smoke_response(request_id: str, input_path: str, output_path: str, timeout_seconds: int = 120) -> CommandResponse:
    result = run_spreadsheet_calc_smoke(
        input_path=input_path,
        output_path=output_path,
        timeout_seconds=timeout_seconds,
    )
    checks = [
        {
            "name": "formula_raw_value",
            "passed": result["ok"],
            "details": result["data"].get("raw_value") if result["data"] else None,
        },
        {
            "name": "formula_display_text",
            "passed": result["ok"],
            "details": result["data"].get("display_text") if result["data"] else None,
        },
    ]
    return CommandResponse(
        ok=result["ok"],
        command="calc-smoke",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Spreadsheet calculation smoke run completed."
            if result["ok"]
            else "Spreadsheet calculation smoke run could not complete."
        ),
        data=result["data"],
        validation=ValidationResult(status="passed" if result["ok"] else "failed", checks=checks),
        errors=result["errors"],
    )


def convert_smoke_response(
    request_id: str,
    component: str,
    input_path: str,
    output_path: str,
    output_format: str,
) -> CommandResponse:
    result = run_conversion_smoke(
        component=component,
        input_path=input_path,
        output_path=output_path,
        output_format=output_format,
    )


def html_render_response(request_id: str, input_path: str, output_path: str, output_format: str,
                         page_size: str, viewport_width: int, viewport_height: int,
                         timeout_seconds: int, allow_javascript: bool) -> CommandResponse:
    ok, data, errors = render_html(
        input_path, output_path, output_format, page_size=page_size,
        viewport_width=viewport_width, viewport_height=viewport_height,
        timeout_seconds=timeout_seconds, allow_javascript=allow_javascript,
    )


def html_editable_response(request_id: str, input_path: str, output_path: str) -> CommandResponse:
    ok, data, errors = convert_html_editable(input_path, output_path)
    return CommandResponse(
        ok=ok, command="html-editable", request_id=request_id, backend="python-docx",
        summary="HTML mapped to editable Writer content." if ok else "Editable HTML conversion could not complete.",
        data=data, validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {"name": "output_docx_created", "passed": ok, "details": data.get("output_path")},
                {"name": "editable_native_objects_reported", "passed": ok and bool(data.get("mapped_objects")), "details": data.get("mapped_objects")},
            ],
        ), errors=errors,
    )


def html_batch_convert_response(request_id: str, input_directory: str, output_directory: str,
                                mode: str, recursive: bool, progress_callback=None) -> CommandResponse:
    ok, data, errors = convert_html_batch(
        input_directory, output_directory, mode, recursive=recursive,
        request_id=request_id,
        progress_callback=progress_callback,
    )
    summary = data.get("summary", {})
    cancelled = bool(data.get("cancelled"))
    return CommandResponse(
        ok=ok, command="html-batch-convert", request_id=request_id, backend="local-python",
        summary=(f"Batch conversion cancelled after {summary.get('processed', 0)} of {summary.get('total', 0)} files."
                 if cancelled else f"Batch conversion finished: {summary.get('passed', 0)} passed, {summary.get('failed', 0)} failed."),
        data=data, validation=ValidationResult(status="passed" if ok else "partial" if data else "failed", checks=[
            {"name": "per_file_results_recorded", "passed": bool(data.get("files")), "details": summary},
            {"name": "provenance_manifest_created", "passed": bool(data.get("manifest_path")), "details": data.get("manifest_path")},
            {"name": "cancelled_with_partial_manifest", "passed": not cancelled or bool(data.get("manifest_path")), "details": cancelled},
        ]), errors=errors,
    )


def html_batch_request_response(request_id: str, batch_request_id: str, verify: bool = False) -> CommandResponse:
    ok, record, errors = inspect_batch_request(batch_request_id, verify=verify)
    validation_status = "failed" if not ok else "warning" if record["evidence_status"] == "failed" else "passed"
    return CommandResponse(
        ok=ok, command="html-batch-request", request_id=request_id, backend="local-python",
        summary="Batch request returned." if ok else "Batch request inspection failed.",
        data={"batch_request": record} if ok else {},
        validation=ValidationResult(status=validation_status, checks=[
            {"name": "batch_request_record_valid", "passed": ok, "details": batch_request_id},
            {"name": "batch_request_evidence_valid", "passed": record.get("evidence_status") != "failed", "details": record.get("evidence_status")},
        ]), errors=errors,
    )


def batch_template_report_response(request_id: str, manifest_path: str, template_path: str,
                                   output_path: str) -> CommandResponse:
    ok, data, errors = render_batch_template_report(manifest_path, template_path, output_path)
    return CommandResponse(
        ok=ok, command="batch-template-report", request_id=request_id, backend=BACKEND,
        summary="Batch template report created." if ok else "Batch template report was rejected.",
        data=data, validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "manifest_and_template_verified", "passed": ok, "details": data.get("manifest_sha256")},
            {"name": "report_created_without_overwrite", "passed": ok, "details": data.get("output_path")},
        ]), errors=errors,
    )


def html_roundtrip_plan_response(request_id: str, input_path: str) -> CommandResponse:
    ok, data, errors = build_html_roundtrip_mapping(input_path)
    return CommandResponse(
        ok=ok, command="html-roundtrip-plan", request_id=request_id, backend=BACKEND,
        summary="Owned HTML identity mapping is valid." if ok else "Owned HTML identity mapping was rejected.",
        data={"roundtrip_mapping": data},
        validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "versioned_schema_valid", "passed": ok, "details": data.get("schema_version")},
            {"name": "object_ids_unambiguous", "passed": ok, "details": data.get("mapping_count", 0)},
        ]), errors=errors,
    )


def html_controlled_import_response(request_id: str, input_path: str, output_path: str) -> CommandResponse:
    ok, data, errors = import_controlled_html(input_path, output_path)
    return CommandResponse(
        ok=ok, command="html-controlled-import", request_id=request_id, backend="python-docx",
        summary="Owned HTML imported with stable document bookmarks." if ok else "Controlled HTML import could not complete.",
        data=data, validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "docx_and_mapping_created", "passed": ok, "details": data.get("mapping_path")},
            {"name": "all_object_bookmarks_written", "passed": ok, "details": data.get("bookmark_count")},
        ]), errors=errors,
    )


def html_roundtrip_verify_response(request_id: str, document_path: str, mapping_path: str) -> CommandResponse:
    ok, data, errors = verify_controlled_document(document_path, mapping_path)
    return CommandResponse(
        ok=ok, command="html-roundtrip-verify", request_id=request_id, backend=BACKEND,
        summary="Controlled document identity is verified." if ok else "Controlled document identity needs review.",
        data=data, validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "mapped_bookmarks_unique_and_ordered", "passed": ok, "details": data.get("object_count")},
        ]), errors=errors,
    )


def html_roundtrip_export_response(request_id: str, document_path: str, mapping_path: str, output_path: str) -> CommandResponse:
    ok, data, errors = export_controlled_html(document_path, mapping_path, output_path)
    return CommandResponse(
        ok=ok, command="html-roundtrip-export", request_id=request_id, backend="python-docx",
        summary="Controlled DOCX exported to owned HTML." if ok else "Controlled HTML export was rejected.",
        data=data, validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "owned_html_v1_created", "passed": ok, "details": data.get("output_path")},
            {"name": "all_mapped_object_ids_exported", "passed": ok, "details": data.get("exported_object_count")},
        ]), errors=errors,
    )
    return CommandResponse(
        ok=ok, command="html-render", request_id=request_id, backend="playwright-edge",
        summary="HTML rendered successfully." if ok else "HTML rendering could not complete.",
        data=data, validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[{"name": "output_artifact_verified", "passed": ok, "details": data.get("output_path")}],
        ), errors=errors,
    )
    return CommandResponse(
        ok=result["ok"],
        command="convert-smoke",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Conversion smoke run completed."
            if result["ok"]
            else "Conversion smoke run could not complete."
        ),
        data=result["data"],
        validation=ValidationResult(
            status="passed" if result["ok"] else "failed",
            checks=[
                {
                    "name": "output_file_created",
                    "passed": result["ok"],
                    "details": result["data"].get("output_path") if result["data"] else None,
                },
                {
                    "name": "output_file_non_empty",
                    "passed": result["ok"],
                    "details": result["data"].get("output_bytes") if result["data"] else None,
                },
            ],
        ),
        errors=result["errors"],
    )


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


def open_documents_response(request_id: str, component: str | None, register: bool) -> CommandResponse:
    ok, result, errors = list_open_documents(component=component, register=register)
    documents = result.get("documents", [])
    return CommandResponse(
        ok=ok,
        command="open-documents",
        request_id=request_id,
        backend="wps-com",
        summary=(
            f"Attached to running WPS and found {len(documents)} open documents."
            if ok
            else "Could not list open WPS documents."
        ),
        data=result,
        validation=ValidationResult(status="not_applicable"),
        errors=errors,
    )


def writer_selection_read_response(request_id: str, document_id: str) -> CommandResponse:
    ok, result, errors = read_writer_selection(document_id)
    return CommandResponse(
        ok=ok,
        command="writer-selection-read",
        request_id=request_id,
        backend="wps-com",
        summary="Writer selection read." if ok else "Writer selection could not be read.",
        data=result,
        validation=ValidationResult(status="not_applicable"),
        errors=errors,
    )


def writer_selection_replace_response(
    request_id: str,
    document_id: str,
    text: str,
    expected_selection_text: str | None,
    dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = replace_writer_selection(
        document_id=document_id,
        text=text,
        request_id=request_id,
        expected_selection_text=expected_selection_text,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="writer-selection-replace",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Writer selection replace request replayed from idempotency record."
            if replayed
            else "Writer selection replace dry-run completed."
            if dry_run and ok
            else "Writer selection replace completed."
            if ok
            else "Writer selection replace could not complete."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "selection_write_validated",
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


def export_open_document_response(request_id: str, document_id: str, output: str) -> CommandResponse:
    ok, result, errors, replayed = export_open_document_html(
        document_id=document_id, output=output, request_id=request_id,
    )
    return CommandResponse(
        ok=ok,
        command="export-open-document",
        request_id=request_id,
        backend="wps-com",
        summary=(
            "Open document export request replayed from idempotency record."
            if replayed
            else "Open document exported to HTML."
            if ok
            else "Open document could not be exported."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {"name": "output_created", "passed": bool(ok), "details": result.get("output")},
                {"name": "source_unchanged", "passed": bool(result.get("source_unchanged")), "details": result.get("source_path")},
            ],
        ),
        errors=errors,
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
) -> CommandResponse:
    ok, result, errors, replayed = restore_backup(
        document_id=document_id,
        request_id=request_id,
        backup_name=backup_name,
        backup_path=backup_path,
        dry_run=dry_run,
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
) -> CommandResponse:
    ok, result, errors, replayed = writer_table_write(
        document_id=document_id,
        table_index=table_index,
        row=row,
        column=column,
        text=text,
        request_id=request_id,
        dry_run=dry_run,
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


def mcp_tools_response(
    request_id: str,
    category: str | None = None,
    mutates_document: str | None = None,
) -> CommandResponse:
    mutates_filter = None
    if mutates_document == "true":
        mutates_filter = True
    elif mutates_document == "false":
        mutates_filter = False
    tools = list_mcp_tool_schemas(category=category, mutates_document=mutates_filter)
    return CommandResponse(
        ok=True,
        command="mcp-tools",
        request_id=request_id,
        backend=BACKEND,
        summary=f"Returned {len(tools)} draft MCP tool schemas.",
        data={
            "schema_version": tools[0]["schema_version"] if tools else None,
            "categories": list_mcp_tool_categories(),
            "filters": {
                "category": category,
                "mutates_document": mutates_filter,
            },
            "tools": tools,
        },
        validation=ValidationResult(status="not_applicable"),
    )


def mcp_catalog_snapshot_response(request_id: str) -> CommandResponse:
    snapshot = build_mcp_catalog_snapshot()
    safety_complete = snapshot["safety_notes_missing_count"] == 0
    return CommandResponse(
        ok=safety_complete,
        command="mcp-catalog-snapshot",
        request_id=request_id,
        backend=BACKEND,
        summary=f"MCP catalog snapshot returned {snapshot['tool_count']} tools.",
        data={"mcp_catalog_snapshot": snapshot},
        validation=ValidationResult(
            status="passed" if safety_complete else "warning",
            checks=[
                {
                    "name": "tools_present",
                    "passed": snapshot["tool_count"] > 0,
                    "details": snapshot["tool_count"],
                },
                {
                    "name": "categories_present",
                    "passed": bool(snapshot["category_counts"]),
                    "details": snapshot["category_counts"],
                },
                {
                    "name": "mutating_tools_have_safety_notes",
                    "passed": safety_complete,
                    "details": snapshot["safety_notes_missing_tools"],
                },
            ],
        ),
    )


def mcp_catalog_drift_response(request_id: str, guard_path: str = DEFAULT_MCP_CATALOG_GUARD) -> CommandResponse:
    ok, report, errors = build_mcp_catalog_drift_report(guard_path)
    return CommandResponse(
        ok=ok,
        command="mcp-catalog-drift",
        request_id=request_id,
        backend=BACKEND,
        summary="MCP catalog matches guard baseline." if ok else "MCP catalog drift requires review.",
        data={"mcp_catalog_drift": report} if report else {},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "catalog_guard_loaded",
                    "passed": not any(error.get("code", "").endswith("NOT_FOUND") for error in errors),
                    "details": guard_path,
                },
                {
                    "name": "no_catalog_drift",
                    "passed": ok,
                    "details": report.get("drifts", []) if report else errors,
                },
            ],
        ),
        errors=errors,
    )


def mcp_tool_schema_response(request_id: str, name: str) -> CommandResponse:
    schema = get_mcp_tool_schema(name)
    ok = schema is not None
    return CommandResponse(
        ok=ok,
        command="mcp-tool-schema",
        request_id=request_id,
        backend=BACKEND,
        summary="MCP tool schema returned." if ok else "MCP tool schema not found.",
        data={"tool": schema} if schema else {},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[{"name": "mcp_tool_schema_exists", "passed": ok, "details": name}],
        ),
        errors=[] if ok else [{"code": "MCP_TOOL_SCHEMA_NOT_FOUND", "message": f"MCP tool schema not found: {name}"}],
    )


def mcp_call_response(request_id: str, name: str, arguments_json: str) -> CommandResponse:
    try:
        arguments = json.loads(arguments_json)
    except json.JSONDecodeError as exc:
        return CommandResponse(
            ok=False,
            command="mcp-call",
            request_id=request_id,
            backend=BACKEND,
            summary="MCP call failed because arguments_json was not valid JSON.",
            data={"tool_name": name},
            validation=ValidationResult(
                status="failed",
                checks=[{"name": "arguments_json_valid", "passed": False, "details": str(exc)}],
            ),
            errors=[{"code": "INVALID_ARGUMENTS_JSON", "message": str(exc)}],
        )
    if not isinstance(arguments, dict):
        return CommandResponse(
            ok=False,
            command="mcp-call",
            request_id=request_id,
            backend=BACKEND,
            summary="MCP call failed because arguments_json must be an object.",
            data={"tool_name": name},
            validation=ValidationResult(
                status="failed",
                checks=[{"name": "arguments_json_object", "passed": False, "details": type(arguments).__name__}],
            ),
            errors=[{"code": "INVALID_ARGUMENTS_JSON_TYPE", "message": "arguments_json must decode to an object."}],
        )

    ok, result, errors = call_mcp_tool(name, arguments)
    return CommandResponse(
        ok=ok,
        command="mcp-call",
        request_id=request_id,
        backend=BACKEND,
        summary="MCP adapter call completed." if ok else "MCP adapter call failed.",
        data={"mcp_call": result},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "mcp_adapter_call",
                    "passed": ok,
                    "details": {
                        "tool_name": name,
                        "cli_command": result.get("cli_command"),
                        "exit_code": result.get("exit_code"),
                    },
                }
            ],
        ),
        errors=errors,
    )


def mcp_smoke_response(request_id: str, expected_min_tools: int, tool_name: str,
                       arguments_json: str | None = None) -> CommandResponse:
    try:
        tool_arguments = json.loads(arguments_json) if arguments_json is not None else None
    except json.JSONDecodeError:
        tool_arguments = None
        argument_error = {"code": "MCP_SMOKE_ARGUMENTS_INVALID_JSON", "message": "--arguments-json must be valid JSON."}
    else:
        argument_error = None if arguments_json is None or isinstance(tool_arguments, dict) else {
            "code": "MCP_SMOKE_ARGUMENTS_INVALID_OBJECT", "message": "--arguments-json must contain an object.",
        }
    if argument_error:
        ok, result, errors = False, {}, [argument_error]
    else:
        ok, result, errors = run_mcp_server_smoke(
            expected_min_tools=expected_min_tools, tool_name=tool_name, tool_arguments=tool_arguments,
        )
    return CommandResponse(
        ok=ok,
        command="mcp-smoke",
        request_id=request_id,
        backend=BACKEND,
        summary="MCP server smoke checks passed." if ok else "MCP server smoke checks failed.",
        data={"mcp_smoke": result},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=result.get("checks", []),
        ),
        errors=errors,
    )


def mcp_config_audit_response(
    request_id: str,
    config_path: str,
    server_name: str,
    expected_min_tools: int,
    timeout_seconds: int,
) -> CommandResponse:
    ok, result, errors = audit_mcp_client_config(
        config_path=config_path,
        server_name=server_name,
        expected_min_tools=expected_min_tools,
        timeout_seconds=timeout_seconds,
    )
    return CommandResponse(
        ok=ok,
        command="mcp-config-audit",
        request_id=request_id,
        backend=BACKEND,
        summary="MCP client config audit passed." if ok else "MCP client config audit failed.",
        data={"mcp_config_audit": result},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=result.get("checks", []),
        ),
        errors=errors,
    )


def regression_manifest_response(
    request_id: str,
    manifest_path: str,
    profile: str | None,
    include_wps: bool,
) -> CommandResponse:
    ok, manifest, errors = load_regression_manifest(manifest_path)
    scenarios = list_regression_scenarios(manifest, profile=profile, include_wps=include_wps) if ok else []
    return CommandResponse(
        ok=ok,
        command="regression-manifest",
        request_id=request_id,
        backend=BACKEND,
        summary=f"Returned {len(scenarios)} regression scenarios." if ok else "Regression manifest could not be loaded.",
        data={
            "manifest_path": manifest_path,
            "version": manifest.get("version") if ok else None,
            "default_profile": manifest.get("default_profile") if ok else None,
            "filters": {"profile": profile, "include_wps": include_wps},
            "scenarios": scenarios,
        },
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[{"name": "manifest_loaded", "passed": ok, "details": manifest_path}],
        ),
        errors=errors,
    )


def regression_run_response(
    request_id: str,
    manifest_path: str,
    profile: str | None,
    include_wps: bool,
    artifact_dir: str | None = None,
) -> CommandResponse:
    ok, result, errors = run_regression_manifest(
        manifest_path=manifest_path,
        profile=profile,
        include_wps=include_wps,
    )
    response = CommandResponse(
        ok=ok,
        command="regression-run",
        request_id=request_id,
        backend=BACKEND,
        summary="Regression scenarios passed." if ok else "Regression scenarios failed.",
        data={"regression": result},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "regression_scenarios_passed",
                    "passed": ok,
                    "details": {
                        "scenario_count": result.get("scenario_count"),
                        "passed_count": result.get("passed_count"),
                        "failed_count": result.get("failed_count"),
                    },
                }
            ],
        ),
        errors=errors,
    )
    if artifact_dir:
        response_payload = response.to_dict()
        artifact = write_json_artifact(
            response_payload,
            artifact_dir=artifact_dir,
            prefix="regression-run",
            request_id=request_id,
        )
        response_payload["data"]["artifact"] = artifact
        return CommandResponse(
            ok=response.ok,
            command=response.command,
            request_id=response.request_id,
            backend=response.backend,
            summary=f"{response.summary} Artifact written.",
            data=response_payload["data"],
            validation=response.validation,
            errors=response.errors,
        )
    return response


def regression_evidence_response(request_id: str, workspace: str = ".") -> CommandResponse:
    ok, evidence, errors = build_regression_evidence(workspace)
    return CommandResponse(
        ok=ok,
        command="regression-evidence",
        request_id=request_id,
        backend=BACKEND,
        summary="Regression evidence is passed." if ok else "Regression evidence needs review.",
        data={"regression_evidence": evidence},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "safe_regression_artifact_available",
                    "passed": evidence.get("profiles", {}).get("safe", {}).get("available", False),
                    "details": evidence.get("profiles", {}).get("safe", {}).get("artifact"),
                },
                {
                    "name": "wps_regression_artifact_available",
                    "passed": evidence.get("profiles", {}).get("wps", {}).get("available", False),
                    "details": evidence.get("profiles", {}).get("wps", {}).get("artifact"),
                },
                {
                    "name": "regression_profiles_passed",
                    "passed": ok,
                    "details": {
                        "missing_profiles": evidence.get("missing_profiles", []),
                        "failed_profiles": evidence.get("failed_profiles", []),
                    },
                },
            ],
        ),
        errors=errors,
    )


def local_release_gates_response(request_id: str) -> CommandResponse:
    steps: list[dict] = []
    manifest_ok, manifest, manifest_errors = load_regression_manifest()
    safe = list_regression_scenarios(manifest, profile="safe", include_wps=True) if manifest_ok else []
    release = list_regression_scenarios(manifest, profile="release", include_wps=True) if manifest_ok else []
    expected_release = {"local-handoff-summary", "regression-evidence", "regression-history"}
    profiles_valid = (
        manifest_ok and bool(safe) and {item.get("id") for item in release} == expected_release
        and not any(item.get("requires_wps") for item in safe + release)
        and not ({item.get("id") for item in safe} & expected_release)
    )
    if not profiles_valid:
        return CommandResponse(
            ok=False, command="local-release-gates", request_id=request_id, backend=BACKEND,
            summary="Local release profile preflight failed; no gates were run.",
            data={"local_release_gates": {"steps": [], "completed_count": 0, "total_count": 5}},
            validation=ValidationResult(status="failed"),
            errors=manifest_errors or [{"code": "LOCAL_RELEASE_PROFILE_INVALID", "message": "Expected non-WPS safe baseline and three release gates."}],
        )
    sequence = (
        ("initial_package", lambda: cloud_sync_package_response(f"{request_id}-package-initial", DEFAULT_SYNC_PACKAGE, True)),
        ("safe_baseline", lambda: regression_run_response(f"{request_id}-safe", "config/regression_manifest.json", "safe", False, "artifacts/regression/safe")),
        ("refreshed_package", lambda: cloud_sync_package_response(f"{request_id}-package-refreshed", DEFAULT_SYNC_PACKAGE, True)),
        ("package_readiness", lambda: sync_package_readiness_response(f"{request_id}-readiness", ".", DEFAULT_SYNC_PACKAGE, 10)),
        ("release_gates", lambda: regression_run_response(f"{request_id}-release", "config/regression_manifest.json", "release", False, "artifacts/regression/release")),
    )
    errors: list[dict] = []
    for name, action in sequence:
        try:
            response = action()
        except Exception as exc:
            errors = [{"code": "LOCAL_RELEASE_GATE_EXCEPTION", "message": f"{name}: {exc}"}]
            steps.append({"name": name, "ok": False, "errors": errors})
            break
        steps.append({
            "name": name,
            "ok": response.ok,
            "validation_status": response.validation.status,
            "artifact": response.data.get("artifact"),
            "package": response.data.get("cloud_sync_package", {}).get("output_path"),
            "errors": response.errors,
        })
        if not response.ok or response.validation.status != "passed":
            errors = response.errors or [{"code": "LOCAL_RELEASE_GATE_FAILED", "message": f"{name} did not pass."}]
            break
    ok = len(steps) == len(sequence) and not errors
    return CommandResponse(
        ok=ok,
        command="local-release-gates",
        request_id=request_id,
        backend=BACKEND,
        summary="Local release gates passed." if ok else "Local release gates stopped at a failed step.",
        data={"local_release_gates": {"steps": steps, "completed_count": len(steps), "total_count": len(sequence), "wps_launched": False, "remote_git_used": False}},
        validation=ValidationResult(status="passed" if ok else "failed", checks=[{"name": "all_gates_passed", "passed": ok, "details": {"completed_count": len(steps), "total_count": len(sequence)}}]),
        errors=errors,
    )


def cloud_sync_package_response(
    request_id: str,
    output_path: str,
    include_latest_artifacts: bool,
) -> CommandResponse:
    ok, result, errors = build_cloud_sync_package(
        output_path=output_path,
        include_latest_artifacts=include_latest_artifacts,
    )
    return CommandResponse(
        ok=ok,
        command="cloud-sync-package",
        request_id=request_id,
        backend=BACKEND,
        summary="Cloud sync package created." if ok else "Cloud sync package could not be created.",
        data={"cloud_sync_package": result},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "package_created",
                    "passed": bool(result.get("created")),
                    "details": result.get("output_path"),
                },
                {
                    "name": "package_has_entries",
                    "passed": bool(result.get("entry_count")),
                    "details": result.get("entry_count"),
                },
                {
                    "name": "package_hash_available",
                    "passed": bool(result.get("sha256")),
                    "details": result.get("sha256"),
                },
                {
                    "name": "all_files_added",
                    "passed": not bool(result.get("failed")),
                    "details": result.get("failed"),
                },
            ],
        ),
        errors=errors,
    )


def sync_package_inspect_response(
    request_id: str,
    workspace: str,
    package_path: str,
) -> CommandResponse:
    ok, result, errors = inspect_sync_package(workspace=workspace, package_path=package_path)
    return CommandResponse(
        ok=ok,
        command="sync-package-inspect",
        request_id=request_id,
        backend=BACKEND,
        summary="Sync package inspection passed." if ok else "Sync package inspection needs review.",
        data={"sync_package_inspect": result},
        validation=ValidationResult(
            status="passed" if ok else "warning",
            checks=result.get("checks", []),
        ),
        errors=errors,
    )


def sync_package_summary_response(
    request_id: str,
    workspace: str,
    package_path: str,
    limit: int,
) -> CommandResponse:
    ok, result, errors = summarize_sync_package(workspace=workspace, package_path=package_path, limit=limit)
    return CommandResponse(
        ok=ok,
        command="sync-package-summary",
        request_id=request_id,
        backend=BACKEND,
        summary="Sync package summary passed." if ok else "Sync package summary needs review.",
        data={"sync_package_summary": result},
        validation=ValidationResult(
            status="passed" if ok else "warning",
            checks=result.get("checks", []),
        ),
        errors=errors,
    )


def sync_package_manifest_response(
    request_id: str,
    workspace: str,
    package_path: str,
    prefix: str | None,
    limit: int,
) -> CommandResponse:
    ok, result, errors = build_sync_package_manifest(
        workspace=workspace,
        package_path=package_path,
        prefix=prefix,
        limit=limit,
    )
    return CommandResponse(
        ok=ok,
        command="sync-package-manifest",
        request_id=request_id,
        backend=BACKEND,
        summary="Sync package manifest passed." if ok else "Sync package manifest needs review.",
        data={"sync_package_manifest": result},
        validation=ValidationResult(
            status="passed" if ok else "warning",
            checks=result.get("checks", []),
        ),
        errors=errors,
    )


def sync_package_coverage_response(
    request_id: str,
    workspace: str,
    package_path: str,
    limit: int,
) -> CommandResponse:
    ok, result, errors = build_sync_package_coverage(workspace=workspace, package_path=package_path, limit=limit)
    return CommandResponse(
        ok=ok,
        command="sync-package-coverage",
        request_id=request_id,
        backend=BACKEND,
        summary="Sync package coverage passed." if ok else "Sync package coverage needs review.",
        data={"sync_package_coverage": result},
        validation=ValidationResult(
            status="passed" if ok else "warning",
            checks=result.get("checks", []),
        ),
        errors=errors,
    )


def sync_package_readiness_response(
    request_id: str,
    workspace: str,
    package_path: str,
    limit: int,
) -> CommandResponse:
    ok, result, errors = build_sync_package_readiness(workspace=workspace, package_path=package_path, limit=limit)
    return CommandResponse(
        ok=ok,
        command="sync-package-readiness",
        request_id=request_id,
        backend=BACKEND,
        summary="Sync package readiness passed." if ok else "Sync package readiness needs review.",
        data={"sync_package_readiness": result},
        validation=ValidationResult(
            status="passed" if ok else "warning",
            checks=result.get("checks", []),
        ),
        errors=errors,
    )


def security_audit_response(request_id: str) -> CommandResponse:
    ok, result, errors = build_security_boundary_audit()
    return CommandResponse(
        ok=ok,
        command="security-audit",
        request_id=request_id,
        backend=BACKEND,
        summary="Schema text and parser consistency audit passed (not a behavioral security test)." if ok else "Schema text and parser consistency audit failed.",
        data={"security_audit": result},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "mutating_tool_boundaries",
                    "passed": ok,
                    "details": {
                        "mutating_tool_count": result.get("mutating_tool_count"),
                        "passed_tool_count": result.get("passed_tool_count"),
                        "failed_tool_count": result.get("failed_tool_count"),
                    },
                }
            ],
        ),
        errors=errors,
    )


def performance_baseline_response(request_id: str) -> CommandResponse:
    ok, result, errors = capture_performance_baseline()
    return CommandResponse(
        ok=ok,
        command="performance-baseline",
        request_id=request_id,
        backend=BACKEND,
        summary="Performance baseline captured." if ok else "Performance baseline failed.",
        data={"performance_baseline": result},
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "baseline_commands_passed",
                    "passed": ok,
                    "details": {
                        "scenario_count": result.get("scenario_count"),
                        "passed_count": result.get("passed_count"),
                        "failed_count": result.get("failed_count"),
                    },
                },
                {
                    "name": "wps_not_launched",
                    "passed": not result.get("launches_wps", True),
                    "details": {"launches_wps": result.get("launches_wps")},
                },
            ],
        ),
        errors=errors,
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
        _errors = [{"code": "TASK_ALREADY_TERMINAL", "message": "Use a new task ID after reviewing the failed or cancelled operation."}]
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
            message=(
                f"{tracked_command} completed."
                if response.ok
                else f"{tracked_command} failed."
            ),
            recovery_guidance=[] if response.ok else [
                "Inspect response errors before retrying.",
                "Run task-status with this task_id to avoid duplicate work.",
            ],
            result_ref=operation_request_id,
        )
        current_status = get_task_status(task_id)
    if current_status:
        response.data["task_status"] = current_status
    return response


def scan_dir_response(request_id: str, path: str, recursive: bool) -> CommandResponse:
    ok, result, errors = scan_directory(path, recursive=recursive)
    return CommandResponse(
        ok=ok,
        command="scan-dir",
        request_id=request_id,
        backend=BACKEND,
        summary=(
            f"Returned {result.get('count', 0)} supported files."
            if ok
            else "Directory scan failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "directory_scanned",
                    "passed": ok,
                    "details": path,
                }
            ],
        ),
        errors=errors,
    )


def batch_report_response(
    request_id: str,
    path: str,
    recursive: bool,
    include_snapshots: bool,
) -> CommandResponse:
    ok, result, errors = build_batch_report(
        directory=path,
        recursive=recursive,
        include_snapshots=include_snapshots,
    )
    summary = result.get("summary", {})
    return CommandResponse(
        ok=ok,
        command="batch-report",
        request_id=request_id,
        backend=BACKEND,
        summary=(
            f"Batch report returned {summary.get('total_files', 0)} supported files."
            if ok
            else "Batch report failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok and not summary.get("snapshot_failed") else "failed",
            checks=[
                {
                    "name": "directory_scanned",
                    "passed": ok,
                    "details": path,
                },
                {
                    "name": "registration_status_included",
                    "passed": ok,
                    "details": {
                        "registered_files": summary.get("registered_files"),
                        "unregistered_files": summary.get("unregistered_files"),
                    },
                },
                {
                    "name": "snapshots_collected",
                    "passed": bool(ok and (not include_snapshots or summary.get("snapshot_failed") == 0)),
                    "details": {
                        "enabled": include_snapshots,
                        "passed": summary.get("snapshot_passed"),
                        "failed": summary.get("snapshot_failed"),
                        "skipped": summary.get("snapshot_skipped"),
                    },
                },
            ],
        ),
        errors=errors,
    )


def spreadsheet_read_response(
    request_id: str,
    document_id: str,
    range_address: str,
    sheet_name: str | None,
) -> CommandResponse:
    ok, result, errors = read_spreadsheet_range(
        document_id=document_id,
        range_address=range_address,
        sheet_name=sheet_name,
    )


def spreadsheet_sheets_response(request_id: str, document_id: str) -> CommandResponse:
    ok, result, errors = list_spreadsheet_sheets(document_id)
    return CommandResponse(
        ok=ok,
        command="spreadsheet-sheets",
        request_id=request_id,
        backend=BACKEND,
        summary="Spreadsheet worksheets listed." if ok else "Spreadsheet worksheet listing failed.",
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[{
                "name": "worksheet_inventory_read_only",
                "passed": bool(ok and result.get("read_only") and not result.get("saved")),
                "details": result.get("sheet_count"),
            }],
        ),
        errors=errors,
    )


def spreadsheet_rename_sheet_response(
    request_id: str, document_id: str, old_name: str, new_name: str, dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = rename_spreadsheet_sheet(
        document_id, old_name, new_name, request_id, dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="spreadsheet-rename-sheet",
        request_id=request_id,
        backend="wps-com" if not dry_run and ok and result.get("saved") else BACKEND,
        summary=("Worksheet rename request replayed." if replayed else "Worksheet rename preview completed." if dry_run and ok else "Worksheet renamed." if ok else "Worksheet rename failed."),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[{"name": "ordered_sheet_names_read_back", "passed": bool(ok and (dry_run or result.get("validation_passed"))), "details": result.get("sheet_names_read_back", result.get("sheet_names_after"))}],
        ),
        errors=errors,
    )


def spreadsheet_create_sheet_response(
    request_id: str, document_id: str, name: str, index: int | None, dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = create_spreadsheet_sheet(document_id, name, request_id, index, dry_run)
    return CommandResponse(
        ok=ok, command="spreadsheet-create-sheet", request_id=request_id,
        backend="wps-com" if not dry_run and ok else BACKEND,
        summary=("Worksheet creation request replayed." if replayed else "Worksheet creation preview completed." if dry_run and ok else "Worksheet created." if ok else "Worksheet creation failed."),
        data=result,
        validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "ordered_sheet_names_read_back", "passed": bool(ok and (dry_run or result.get("validation_passed"))), "details": result.get("sheet_names_read_back", result.get("sheet_names_after"))},
        ]),
        errors=errors,
    )


def spreadsheet_set_sheet_visibility_response(
    request_id: str, document_id: str, sheet_name: str, visible: bool, dry_run: bool,
) -> CommandResponse:
    ok, result, errors, replayed = set_spreadsheet_sheet_visibility(document_id, sheet_name, visible, request_id, dry_run)
    return CommandResponse(
        ok=ok, command="spreadsheet-set-sheet-visibility", request_id=request_id,
        backend="wps-com" if ok and result.get("saved") else BACKEND,
        summary=("Worksheet visibility request replayed." if replayed else "Worksheet visibility preview completed." if dry_run and ok else "Worksheet visibility updated." if ok else "Worksheet visibility update failed."),
        data=result,
        validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "ordered_sheet_visibility_read_back", "passed": bool(ok and (dry_run or result.get("validation_passed"))), "details": result.get("sheet_states_read_back", result.get("sheet_states_after"))},
        ]),
        errors=errors,
    )


def spreadsheet_delete_sheet_response(request_id: str, document_id: str, sheet_name: str, dry_run: bool) -> CommandResponse:
    ok, result, errors, replayed = delete_spreadsheet_sheet(document_id, sheet_name, request_id, dry_run)
    return CommandResponse(
        ok=ok, command="spreadsheet-delete-sheet", request_id=request_id,
        backend="wps-com" if ok and result.get("saved") else BACKEND,
        summary=("Worksheet deletion request replayed." if replayed else "Worksheet deletion preview completed." if dry_run and ok else "Worksheet deleted." if ok else "Worksheet deletion failed."),
        data=result,
        validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "ordered_sheet_names_read_back", "passed": bool(ok and (dry_run or result.get("validation_passed"))), "details": result.get("sheet_names_read_back", result.get("sheet_names_after"))},
        ]),
        errors=errors,
    )


def spreadsheet_copy_sheet_response(request_id: str, document_id: str, source_name: str, new_name: str, index: int | None, dry_run: bool) -> CommandResponse:
    ok, result, errors, replayed = copy_spreadsheet_sheet(document_id, source_name, new_name, request_id, index, dry_run)
    return CommandResponse(
        ok=ok, command="spreadsheet-copy-sheet", request_id=request_id,
        backend="wps-com" if ok and result.get("saved") else BACKEND,
        summary=("Worksheet copy request replayed." if replayed else "Worksheet copy preview completed." if dry_run and ok else "Worksheet copied." if ok else "Worksheet copy failed."),
        data=result,
        validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "ordered_copy_and_cell_read_back", "passed": bool(ok and (dry_run or result.get("validation_passed"))), "details": result.get("sheet_names_read_back", result.get("sheet_names_after"))},
        ]),
        errors=errors,
    )


def spreadsheet_set_sheet_tab_color_response(request_id: str, document_id: str, sheet_name: str, color: str, dry_run: bool) -> CommandResponse:
    ok, result, errors, replayed = set_spreadsheet_sheet_tab_color(document_id, sheet_name, color, request_id, dry_run)
    return CommandResponse(
        ok=ok, command="spreadsheet-set-sheet-tab-color", request_id=request_id,
        backend="wps-com" if ok and result.get("saved") else BACKEND,
        summary=("Worksheet tab color request replayed." if replayed else "Worksheet tab color preview completed." if dry_run and ok else "Worksheet tab color updated." if ok else "Worksheet tab color update failed."),
        data=result,
        validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "tab_color_read_back", "passed": bool(ok and (dry_run or result.get("validation_passed"))), "details": result.get("tab_color_read_back", result.get("color"))},
        ]),
        errors=errors,
    )


def spreadsheet_inspect_response(request_id: str, document_id: str, range_address: str, sheet_name: str | None) -> CommandResponse:
    ok, result, errors = inspect_spreadsheet_range(document_id, range_address, sheet_name)
    return CommandResponse(
        ok=ok, command="spreadsheet-inspect", request_id=request_id, backend="wps-com",
        summary="Spreadsheet calculation and display inspection completed without saving." if ok else "Spreadsheet inspection failed.",
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {"name": "read_only", "passed": bool(result.get("read_only")), "details": result.get("saved")},
                {"name": "formula_cache_display_fields", "passed": bool(ok and all("formula" in cell and "saved_cached_value" in cell and "recalculated_value" in cell and "displayed_text" in cell for cell in result.get("cells", []))), "details": len(result.get("cells", []))},
            ],
        ),
        errors=errors,
    )


def spreadsheet_write_response(
    request_id: str,
    document_id: str,
    range_address: str,
    values_json: str,
    sheet_name: str | None,
    dry_run: bool,
) -> CommandResponse:
    try:
        values = json.loads(values_json)
    except json.JSONDecodeError as exc:
        return CommandResponse(
            ok=False,
            command="spreadsheet-write",
            request_id=request_id,
            backend=BACKEND,
            summary="Spreadsheet write could not parse values_json.",
            data={},
            validation=ValidationResult(status="failed"),
            errors=[{"code": "INVALID_JSON", "message": str(exc)}],
        )
    ok, result, errors, replayed = write_spreadsheet_range(
        document_id=document_id,
        range_address=range_address,
        values=values,
        request_id=request_id,
        sheet_name=sheet_name,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="spreadsheet-write",
        request_id=request_id,
        backend="wps-com" if not dry_run else BACKEND,
        summary=(
            "Spreadsheet write request replayed from idempotency record."
            if replayed
            else "Spreadsheet write dry-run completed."
            if dry_run and ok
            else "Spreadsheet write completed."
            if ok
            else "Spreadsheet write failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "range_shape_valid",
                    "passed": ok,
                    "details": {
                        "range": range_address,
                        "row_count": result.get("row_count"),
                        "column_count": result.get("column_count"),
                    },
                },
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "write_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": result.get("read_back_values"),
                },
            ],
        ),
        errors=errors,
    )


def spreadsheet_formula_write_response(
    request_id: str,
    document_id: str,
    range_address: str,
    formulas_json: str,
    expected_values_json: str,
    sheet_name: str | None,
    dry_run: bool,
) -> CommandResponse:
    try:
        formulas = json.loads(formulas_json)
        expected_values = json.loads(expected_values_json)
    except json.JSONDecodeError as exc:
        return CommandResponse(
            ok=False,
            command="spreadsheet-formula-write",
            request_id=request_id,
            backend=BACKEND,
            summary="Spreadsheet formula write could not parse JSON arguments.",
            data={},
            validation=ValidationResult(status="failed"),
            errors=[{"code": "INVALID_JSON", "message": str(exc)}],
        )
    ok, result, errors, replayed = write_spreadsheet_formulas(
        document_id=document_id,
        range_address=range_address,
        formulas=formulas,
        expected_values=expected_values,
        request_id=request_id,
        sheet_name=sheet_name,
        dry_run=dry_run,
    )
    return CommandResponse(
        ok=ok,
        command="spreadsheet-formula-write",
        request_id=request_id,
        backend="wps-com" if not dry_run else BACKEND,
        summary=(
            "Spreadsheet formula write request replayed from idempotency record."
            if replayed
            else "Spreadsheet formula write dry-run completed."
            if dry_run and ok
            else "Spreadsheet formula write completed."
            if ok
            else "Spreadsheet formula write failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "formula_range_shape_valid",
                    "passed": ok,
                    "details": {
                        "range": range_address,
                        "row_count": result.get("row_count"),
                        "column_count": result.get("column_count"),
                    },
                },
                {
                    "name": "backup_created",
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "calculation_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": result.get("read_back_values"),
                },
            ],
        ),
        errors=errors,
    )


def presentation_replace_response(
    request_id: str,
    document_id: str,
    find_text: str,
    replace_text: str,
    dry_run: bool,
    slide_index: int | None,
) -> CommandResponse:
    ok, result, errors, replayed = presentation_replace(
        document_id=document_id,
        find_text=find_text,
        replace_text=replace_text,
        request_id=request_id,
        dry_run=dry_run,
        slide_index=slide_index,
    )
    return CommandResponse(
        ok=ok,
        command="presentation-replace",
        request_id=request_id,
        backend="wps-com" if not dry_run else BACKEND,
        summary=(
            "Presentation replace request replayed from idempotency record."
            if replayed
            else "Presentation replace dry-run completed."
            if dry_run and ok
            else "Presentation replace completed."
            if ok
            else "Presentation replace could not complete."
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
                    "passed": bool(dry_run or result.get("backup", {}).get("created") or replayed),
                    "details": result.get("backup", {}).get("backup_path"),
                },
                {
                    "name": "replacement_validated",
                    "passed": bool(dry_run or result.get("validation_passed") or replayed),
                    "details": {
                        "remaining_find_count": result.get("remaining_find_count"),
                        "replace_count_delta": result.get("replace_count_delta"),
                    },
                },
            ],
        ),
        errors=errors,
    )


def _handle_inspect_env(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = inspect_env_response(request_id)
    return response


def _handle_wps_process_audit(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = wps_process_audit_response(
        request_id,
        timeout_seconds=args.timeout_seconds,
    )
    return response


def _handle_cleanup_plan(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = cleanup_plan_response(
        request_id,
        workspace=args.workspace,
    )
    return response


def _handle_cleanup_approval_manifest(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = cleanup_approval_manifest_response(
        request_id,
        workspace=args.workspace,
    )
    return response


def _handle_artifact_retention_summary(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = artifact_retention_summary_response(
        request_id,
        workspace=args.workspace,
    )
    return response


def _handle_plan(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = plan_response(request_id)
    return response


def _handle_project_status(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = project_status_response(
        request_id,
        workspace=args.workspace,
    )
    return response


def _handle_workspace_health(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = workspace_health_response(
        request_id,
        workspace=args.workspace,
    )
    return response


def _handle_local_handoff_summary(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = local_handoff_summary_response(
        request_id,
        workspace=args.workspace,
    )
    return response


def _handle_validation_runbook(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = validation_runbook_response(
        request_id,
        workspace=args.workspace,
    )
    return response


def _handle_documentation_freshness(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = documentation_freshness_response(
        request_id,
        workspace=args.workspace,
    )
    return response


def _handle_regression_history(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = regression_history_response(
        request_id,
        workspace=args.workspace,
        limit=args.limit,
    )
    return response


def _handle_tasks(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = tasks_response(request_id, phase=args.phase, status=args.status)
    return response


def _handle_com_smoke(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = com_smoke_response(
        request_id,
        component=args.component,
        input_path=args.input,
        output_path=args.output,
        visible=args.visible,
    )
    return response


def _handle_calc_smoke(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = calc_smoke_response(
        request_id,
        input_path=args.input,
        output_path=args.output,
        timeout_seconds=args.timeout_seconds,
    )
    return response


def _handle_convert_smoke(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = convert_smoke_response(
        request_id,
        component=args.component,
        input_path=args.input,
        output_path=args.output,
        output_format=args.format,
    )
    return response


def _handle_html_render(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: html_render_response(
            request_id, args.input, args.output, args.format, args.page_size,
            args.viewport_width, args.viewport_height, args.timeout_seconds, args.allow_javascript,
        ),
        task_id=args.task_id,
        tracked_command="html-render",
        operation_request_id=request_id,
    )
    return response


def _handle_html_batch_convert(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    progress_callback = None
    if args.task_id:
        def progress_callback(completed: int, total: int, message: str) -> bool:
            current = get_task_status(args.task_id)
            if current and current.get("state") == "cancelled":
                return False
            percent = min(95, 10 + int(85 * completed / max(1, total)))
            update_task_status(args.task_id, "running", progress_percent=percent, message=message)
            current = get_task_status(args.task_id)
            return not current or current.get("state") != "cancelled"
    response = _with_optional_task_status(
        lambda: html_batch_convert_response(request_id, args.input_dir, args.output_dir, args.mode, args.recursive, progress_callback),
        task_id=args.task_id, tracked_command="html-batch-convert", operation_request_id=request_id,
    )
    return response


def _handle_html_batch_request(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = html_batch_request_response(request_id, args.batch_request_id, args.verify)
    return response


def _handle_batch_template_report(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: batch_template_report_response(request_id, args.manifest, args.template, args.output),
        task_id=args.task_id, tracked_command="batch-template-report", operation_request_id=request_id,
    )
    return response


def _handle_html_editable(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: html_editable_response(request_id, args.input, args.output),
        task_id=args.task_id, tracked_command="html-editable", operation_request_id=request_id,
    )
    return response


def _handle_html_roundtrip_plan(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = html_roundtrip_plan_response(request_id, args.input)
    return response


def _handle_html_controlled_import(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: html_controlled_import_response(request_id, args.input, args.output),
        task_id=args.task_id, tracked_command="html-controlled-import", operation_request_id=request_id,
    )
    return response


def _handle_html_roundtrip_verify(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = html_roundtrip_verify_response(request_id, args.docx, args.mapping)
    return response


def _handle_html_roundtrip_export(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: html_roundtrip_export_response(request_id, args.docx, args.mapping, args.output),
        task_id=args.task_id, tracked_command="html-roundtrip-export", operation_request_id=request_id,
    )
    return response


def _handle_writer_table_smoke(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: writer_table_smoke_response(
            request_id,
            input_path=args.input,
            output_path=args.output,
            table_index=args.table_index,
            row=args.row,
            column=args.column,
            text=args.text,
        ),
        task_id=args.task_id,
        tracked_command="writer-table-smoke",
        operation_request_id=request_id,
    )
    return response


def _handle_register_document(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = register_document_response(
        request_id,
        component=args.component,
        path=args.path,
    )
    return response


def _handle_documents(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = documents_response(request_id)
    return response


def _handle_backup_document(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: backup_document_response(
            request_id,
            document_id=args.document_id,
            dry_run=args.dry_run,
        ),
        task_id=args.task_id,
        tracked_command="backup-document",
        operation_request_id=request_id,
        document_id=args.document_id,
    )
    return response


def _handle_list_backups(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = list_backups_response(
        request_id,
        document_id=args.document_id,
    )
    return response


def _handle_restore_backup(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: restore_backup_response(
            request_id,
            document_id=args.document_id,
            backup_name=args.backup_name,
            backup_path=args.backup_path,
            dry_run=args.dry_run,
        ),
        task_id=args.task_id,
        tracked_command="restore-backup",
        operation_request_id=request_id,
        document_id=args.document_id,
    )
    return response


def _handle_writer_replace(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: writer_replace_response(
            request_id,
            document_id=args.document_id,
            find_text=args.find,
            replace_text=args.replace,
            dry_run=args.dry_run,
            paragraph_index=args.paragraph_index,
        ),
        task_id=args.task_id,
        tracked_command="writer-replace",
        operation_request_id=request_id,
        document_id=args.document_id,
    )
    return response


def _handle_writer_fill_bookmark(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: writer_fill_bookmark_response(
            request_id, document_id=args.document_id,
            bookmark_name=args.bookmark_name, text=args.text, dry_run=args.dry_run,
        ),
        task_id=args.task_id,
        tracked_command="writer-fill-bookmark",
        operation_request_id=request_id,
        document_id=args.document_id,
    )
    return response


def _handle_writer_table_write(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: writer_table_write_response(
            request_id,
            document_id=args.document_id,
            table_index=args.table_index,
            row=args.row,
            column=args.column,
            text=args.text,
            dry_run=args.dry_run,
        ),
        task_id=args.task_id,
        tracked_command="writer-table-write",
        operation_request_id=request_id,
        document_id=args.document_id,
    )
    return response


def _handle_open_documents(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = open_documents_response(request_id, component=args.component, register=args.register)
    return response


def _handle_writer_selection_read(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = writer_selection_read_response(request_id, document_id=args.document_id)
    return response


def _handle_writer_selection_replace(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: writer_selection_replace_response(
            request_id,
            document_id=args.document_id,
            text=args.text,
            expected_selection_text=args.expected_selection_text,
            dry_run=args.dry_run,
        ),
        task_id=args.task_id,
        tracked_command="writer-selection-replace",
        operation_request_id=request_id,
        document_id=args.document_id,
    )
    return response


def _handle_export_open_document(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = export_open_document_response(request_id, document_id=args.document_id, output=args.output)
    return response


def _handle_validate_document(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = validate_document_response(
        request_id,
        document_id=args.document_id,
        contains=args.contains,
        cell=args.cell,
        equals=args.equals,
    )
    return response


def _handle_snapshot_document(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = snapshot_document_response(
        request_id,
        document_id=args.document_id,
    )
    return response


def _handle_writer_structure(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = writer_structure_response(request_id, args.document_id, args.limit, args.section,
                                         args.offset, args.bookmark_name, args.expected_sha256,
                                         args.include_text, args.text_limit)
    return response


def _handle_writer_structure_parity(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = writer_structure_parity_response(request_id, args.run_wps, args.timeout_seconds,
                                                args.artifact_dir, args.scope)
    return response


def _handle_operation(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = operation_response(
        request_id,
        operation_request_id=args.request,
    )
    return response


def _handle_operations(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = operations_response(request_id)
    return response


def _handle_mutation_request_inspect(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = mutation_request_inspect_response(request_id, args.request)
    return response


def _handle_task_status_create(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = task_status_create_response(
        request_id,
        task_id=args.task_id,
        command=args.tracked_command,
        operation_request_id=args.operation_request_id,
        document_id=args.document_id,
        message=args.message,
        recovery_guidance=args.recovery_guidance,
    )
    return response


def _handle_task_status_update(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = task_status_update_response(
        request_id,
        task_id=args.task_id,
        state=args.state,
        progress_percent=args.progress_percent,
        message=args.message,
        recovery_guidance=args.recovery_guidance,
        result_ref=args.result_ref,
    )
    return response


def _handle_task_status(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = task_status_response(
        request_id,
        task_id=args.task_id,
    )
    return response


def _handle_task_statuses(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = task_statuses_response(request_id)
    return response


def _handle_task_recovery(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = task_recovery_response(
        request_id,
        task_id=args.task_id,
    )
    return response


def _handle_task_recovery_playbooks(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = task_recovery_playbooks_response(request_id)
    return response


def _handle_mcp_tools(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = mcp_tools_response(
        request_id,
        category=args.category,
        mutates_document=args.mutates_document,
    )
    return response


def _handle_mcp_catalog_snapshot(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = mcp_catalog_snapshot_response(request_id)
    return response


def _handle_mcp_catalog_drift(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = mcp_catalog_drift_response(
        request_id,
        guard_path=args.guard,
    )
    return response


def _handle_mcp_tool_schema(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = mcp_tool_schema_response(
        request_id,
        name=args.name,
    )
    return response


def _handle_mcp_call(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = mcp_call_response(
        request_id,
        name=args.name,
        arguments_json=args.arguments_json,
    )
    return response


def _handle_mcp_server(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse | int:
    if args.once_json:
        rpc_response = handle_mcp_json(args.once_json)
        if rpc_response is not None:
            print(dumps_json(rpc_response), file=output_stream or sys.stdout)
        return 0
    return serve_stdio()


def _handle_mcp_smoke(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = mcp_smoke_response(
        request_id,
        expected_min_tools=args.expected_min_tools,
        tool_name=args.tool_name,
        arguments_json=args.arguments_json,
    )
    return response


def _handle_mcp_config_audit(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = mcp_config_audit_response(
        request_id,
        config_path=args.config,
        server_name=args.server_name,
        expected_min_tools=args.expected_min_tools,
        timeout_seconds=args.timeout_seconds,
    )
    return response


def _handle_regression_manifest(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = regression_manifest_response(
        request_id,
        manifest_path=args.manifest,
        profile=args.profile,
        include_wps=args.include_wps,
    )
    return response


def _handle_regression_run(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = regression_run_response(
        request_id,
        manifest_path=args.manifest,
        profile=args.profile,
        include_wps=args.include_wps,
        artifact_dir=args.artifact_dir,
    )
    return response


def _handle_local_release_gates(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = local_release_gates_response(request_id)
    return response


def _handle_regression_evidence(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = regression_evidence_response(
        request_id,
        workspace=args.workspace,
    )
    return response


def _handle_cloud_sync_package(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = cloud_sync_package_response(
        request_id,
        output_path=args.output,
        include_latest_artifacts=not args.no_latest_artifacts,
    )
    return response


def _handle_sync_package_inspect(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = sync_package_inspect_response(
        request_id,
        workspace=args.workspace,
        package_path=args.package,
    )
    return response


def _handle_sync_package_summary(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = sync_package_summary_response(
        request_id,
        workspace=args.workspace,
        package_path=args.package,
        limit=args.limit,
    )
    return response


def _handle_sync_package_manifest(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = sync_package_manifest_response(
        request_id,
        workspace=args.workspace,
        package_path=args.package,
        prefix=args.prefix,
        limit=args.limit,
    )
    return response


def _handle_sync_package_coverage(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = sync_package_coverage_response(
        request_id,
        workspace=args.workspace,
        package_path=args.package,
        limit=args.limit,
    )
    return response


def _handle_sync_package_readiness(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = sync_package_readiness_response(
        request_id,
        workspace=args.workspace,
        package_path=args.package,
        limit=args.limit,
    )
    return response


def _handle_security_audit(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = security_audit_response(request_id)
    return response


def _handle_performance_baseline(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = performance_baseline_response(request_id)
    return response


def _handle_scan_dir(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = scan_dir_response(
        request_id,
        path=args.path,
        recursive=args.recursive,
    )
    return response


def _handle_batch_report(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = batch_report_response(
        request_id,
        path=args.path,
        recursive=args.recursive,
        include_snapshots=not args.no_snapshots,
    )
    return response


def _handle_spreadsheet_read(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = spreadsheet_read_response(
        request_id,
        document_id=args.document_id,
        range_address=args.range,
        sheet_name=args.sheet,
    )
    return response


def _handle_spreadsheet_sheets(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = spreadsheet_sheets_response(request_id, document_id=args.document_id)
    return response


def _handle_spreadsheet_rename_sheet(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: spreadsheet_rename_sheet_response(
            request_id, document_id=args.document_id, old_name=args.old_name,
            new_name=args.new_name, dry_run=args.dry_run,
        ),
        task_id=args.task_id,
        tracked_command="spreadsheet-rename-sheet",
    )
    return response


def _handle_spreadsheet_create_sheet(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: spreadsheet_create_sheet_response(request_id, args.document_id, args.name, args.index, args.dry_run),
        task_id=args.task_id, tracked_command="spreadsheet-create-sheet",
    )
    return response


def _handle_spreadsheet_set_sheet_visibility(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: spreadsheet_set_sheet_visibility_response(request_id, args.document_id, args.sheet_name, args.visible == "true", args.dry_run),
        task_id=args.task_id, tracked_command="spreadsheet-set-sheet-visibility",
    )
    return response


def _handle_spreadsheet_delete_sheet(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: spreadsheet_delete_sheet_response(request_id, args.document_id, args.sheet_name, args.dry_run),
        task_id=args.task_id, tracked_command="spreadsheet-delete-sheet",
    )
    return response


def _handle_spreadsheet_copy_sheet(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: spreadsheet_copy_sheet_response(request_id, args.document_id, args.source_name, args.new_name, args.index, args.dry_run),
        task_id=args.task_id, tracked_command="spreadsheet-copy-sheet",
    )
    return response


def _handle_spreadsheet_set_sheet_tab_color(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: spreadsheet_set_sheet_tab_color_response(request_id, args.document_id, args.sheet_name, args.color, args.dry_run),
        task_id=args.task_id, tracked_command="spreadsheet-set-sheet-tab-color",
    )
    return response


def _handle_spreadsheet_inspect(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = spreadsheet_inspect_response(
        request_id, document_id=args.document_id, range_address=args.range, sheet_name=args.sheet,
    )
    return response


def _handle_spreadsheet_write(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: spreadsheet_write_response(
            request_id,
            document_id=args.document_id,
            range_address=args.range,
            values_json=args.values_json,
            sheet_name=args.sheet,
            dry_run=args.dry_run,
        ),
        task_id=args.task_id,
        tracked_command="spreadsheet-write",
        operation_request_id=request_id,
        document_id=args.document_id,
    )
    return response


def _handle_spreadsheet_formula_write(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: spreadsheet_formula_write_response(
            request_id,
            document_id=args.document_id,
            range_address=args.range,
            formulas_json=args.formulas_json,
            expected_values_json=args.expected_values_json,
            sheet_name=args.sheet,
            dry_run=args.dry_run,
        ),
        task_id=args.task_id,
        tracked_command="spreadsheet-formula-write",
        operation_request_id=request_id,
        document_id=args.document_id,
    )
    return response


def _handle_presentation_replace(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
    response = _with_optional_task_status(
        lambda: presentation_replace_response(
            request_id,
            document_id=args.document_id,
            find_text=args.find,
            replace_text=args.replace,
            dry_run=args.dry_run,
            slide_index=args.slide_index,
        ),
        task_id=args.task_id,
        tracked_command="presentation-replace",
        operation_request_id=request_id,
        document_id=args.document_id,
    )
    return response


COMMAND_HANDLERS: dict[str, Callable[[argparse.Namespace, str, TextIO | None], CommandResponse | int]] = {
    "inspect-env": _handle_inspect_env,
    "wps-process-audit": _handle_wps_process_audit,
    "cleanup-plan": _handle_cleanup_plan,
    "cleanup-approval-manifest": _handle_cleanup_approval_manifest,
    "artifact-retention-summary": _handle_artifact_retention_summary,
    "plan": _handle_plan,
    "project-status": _handle_project_status,
    "workspace-health": _handle_workspace_health,
    "local-handoff-summary": _handle_local_handoff_summary,
    "validation-runbook": _handle_validation_runbook,
    "documentation-freshness": _handle_documentation_freshness,
    "regression-history": _handle_regression_history,
    "tasks": _handle_tasks,
    "com-smoke": _handle_com_smoke,
    "calc-smoke": _handle_calc_smoke,
    "convert-smoke": _handle_convert_smoke,
    "html-render": _handle_html_render,
    "html-batch-convert": _handle_html_batch_convert,
    "html-batch-request": _handle_html_batch_request,
    "batch-template-report": _handle_batch_template_report,
    "html-editable": _handle_html_editable,
    "html-roundtrip-plan": _handle_html_roundtrip_plan,
    "html-controlled-import": _handle_html_controlled_import,
    "html-roundtrip-verify": _handle_html_roundtrip_verify,
    "html-roundtrip-export": _handle_html_roundtrip_export,
    "writer-table-smoke": _handle_writer_table_smoke,
    "register-document": _handle_register_document,
    "documents": _handle_documents,
    "backup-document": _handle_backup_document,
    "list-backups": _handle_list_backups,
    "restore-backup": _handle_restore_backup,
    "writer-replace": _handle_writer_replace,
    "writer-fill-bookmark": _handle_writer_fill_bookmark,
    "writer-table-write": _handle_writer_table_write,
    "open-documents": _handle_open_documents,
    "writer-selection-read": _handle_writer_selection_read,
    "writer-selection-replace": _handle_writer_selection_replace,
    "export-open-document": _handle_export_open_document,
    "validate-document": _handle_validate_document,
    "snapshot-document": _handle_snapshot_document,
    "writer-structure": _handle_writer_structure,
    "writer-structure-parity": _handle_writer_structure_parity,
    "operation": _handle_operation,
    "operations": _handle_operations,
    "mutation-request-inspect": _handle_mutation_request_inspect,
    "task-status-create": _handle_task_status_create,
    "task-status-update": _handle_task_status_update,
    "task-status": _handle_task_status,
    "task-statuses": _handle_task_statuses,
    "task-recovery": _handle_task_recovery,
    "task-recovery-playbooks": _handle_task_recovery_playbooks,
    "mcp-tools": _handle_mcp_tools,
    "mcp-catalog-snapshot": _handle_mcp_catalog_snapshot,
    "mcp-catalog-drift": _handle_mcp_catalog_drift,
    "mcp-tool-schema": _handle_mcp_tool_schema,
    "mcp-call": _handle_mcp_call,
    "mcp-server": _handle_mcp_server,
    "mcp-smoke": _handle_mcp_smoke,
    "mcp-config-audit": _handle_mcp_config_audit,
    "regression-manifest": _handle_regression_manifest,
    "regression-run": _handle_regression_run,
    "local-release-gates": _handle_local_release_gates,
    "regression-evidence": _handle_regression_evidence,
    "cloud-sync-package": _handle_cloud_sync_package,
    "sync-package-inspect": _handle_sync_package_inspect,
    "sync-package-summary": _handle_sync_package_summary,
    "sync-package-manifest": _handle_sync_package_manifest,
    "sync-package-coverage": _handle_sync_package_coverage,
    "sync-package-readiness": _handle_sync_package_readiness,
    "security-audit": _handle_security_audit,
    "performance-baseline": _handle_performance_baseline,
    "scan-dir": _handle_scan_dir,
    "batch-report": _handle_batch_report,
    "spreadsheet-read": _handle_spreadsheet_read,
    "spreadsheet-sheets": _handle_spreadsheet_sheets,
    "spreadsheet-rename-sheet": _handle_spreadsheet_rename_sheet,
    "spreadsheet-create-sheet": _handle_spreadsheet_create_sheet,
    "spreadsheet-set-sheet-visibility": _handle_spreadsheet_set_sheet_visibility,
    "spreadsheet-delete-sheet": _handle_spreadsheet_delete_sheet,
    "spreadsheet-copy-sheet": _handle_spreadsheet_copy_sheet,
    "spreadsheet-set-sheet-tab-color": _handle_spreadsheet_set_sheet_tab_color,
    "spreadsheet-inspect": _handle_spreadsheet_inspect,
    "spreadsheet-write": _handle_spreadsheet_write,
    "spreadsheet-formula-write": _handle_spreadsheet_formula_write,
    "presentation-replace": _handle_presentation_replace,
}



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
                "Workspace state file is corrupt; the command was not executed."
                if isinstance(exc, StateCorruptError)
                else "Input document exceeds the supported size limits; the command was not executed."
            ),
            data=dict(exc.details),
            validation=ValidationResult(status="failed"),
            errors=[{"code": exc.code, "message": str(exc)}],
        )
        print(dumps_json(response.to_dict()), file=output_stream or sys.stdout)
        return 1 if strict_exit else 0


def main() -> int:
    return run(sys.argv[1:])
