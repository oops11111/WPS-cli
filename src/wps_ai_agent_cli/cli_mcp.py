"""MCP catalog, call, smoke and config commands, and the regression runner."""

from __future__ import annotations

import json

from .artifacts import write_json_artifact
from .cli_common import BACKEND
from .mcp_adapter import call_mcp_tool
from .mcp_catalog import build_mcp_catalog_snapshot
from .mcp_catalog_drift import DEFAULT_MCP_CATALOG_GUARD, build_mcp_catalog_drift_report
from .mcp_config_audit import audit_mcp_client_config
from .mcp_schema import (
    get_mcp_tool_schema,
    list_mcp_tool_categories,
    list_mcp_tool_schemas,
)
from .mcp_smoke import run_mcp_server_smoke
from .models import CommandResponse, ValidationResult
from .regression import (
    list_regression_scenarios,
    load_regression_manifest,
    run_regression_manifest,
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
