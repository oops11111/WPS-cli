"""Environment, planning, smoke-test, audit and baseline commands."""

from __future__ import annotations

from .capabilities import probe_wps_capabilities
from .cleanup_approval import build_cleanup_approval_manifest
from .cleanup_plan import build_cleanup_plan
from .cli_common import BACKEND
from .com_backend import run_com_smoke, run_conversion_smoke, run_spreadsheet_calc_smoke
from .models import CommandResponse, ValidationResult
from .performance import capture_performance_baseline
from .phases import list_phases
from .process_audit import audit_wps_processes
from .security_audit import build_security_boundary_audit
from .tasks import list_tasks
from .wps_versions import compare_wps_versions


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


def wps_version_compare_response(
    request_id: str,
    workspace: str,
    record: bool,
    writer_version: str | None,
    spreadsheets_version: str | None,
    presentation_version: str | None,
) -> CommandResponse:
    ok, result, errors = compare_wps_versions(
        workspace,
        {
            "writer": writer_version,
            "spreadsheets": spreadsheets_version,
            "presentation": presentation_version,
        },
        record=record,
    )
    comparisons = result.get("comparisons", [])
    unparsable = any(item.get("relation", "").startswith("unparsable") for item in comparisons)
    if not ok:
        status = "failed"
    elif unparsable:
        status = "warning"
    else:
        status = "passed"
    return CommandResponse(
        ok=ok,
        command="wps-version-compare",
        request_id=request_id,
        backend=BACKEND,
        summary="WPS version comparison completed." if ok else "WPS version comparison failed.",
        data={"wps_version_compare": result},
        validation=ValidationResult(
            status=status,
            checks=[
                {
                    "name": "baseline_compared",
                    "passed": ok,
                    "details": result.get("state_path"),
                },
                {
                    "name": "versions_recorded",
                    "passed": (not record) or bool(result.get("persisted")),
                    "details": {"record_requested": record, "persisted": result.get("persisted", False)},
                },
            ],
        ),
        errors=errors,
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
