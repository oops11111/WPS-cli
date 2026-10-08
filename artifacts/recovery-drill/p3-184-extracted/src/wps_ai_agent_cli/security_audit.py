from __future__ import annotations

from typing import Any

from .mcp_schema import list_mcp_tool_schemas


def _has_text(value: Any, needle: str) -> bool:
    if isinstance(value, str):
        return needle.lower() in value.lower()
    if isinstance(value, list):
        return any(_has_text(item, needle) for item in value)
    return False


def _check(name: str, passed: bool, details: Any) -> dict[str, Any]:
    return {"name": name, "passed": passed, "details": details}


def _tool_checks(schema: dict[str, Any]) -> list[dict[str, Any]]:
    properties = schema.get("input_schema", {}).get("properties", {})
    safety_notes = schema.get("safety_notes", [])
    idempotency = schema.get("idempotency", "")
    text_surface = [
        schema.get("description", ""),
        idempotency,
        *safety_notes,
    ]
    creates_or_protects_backup = _has_text(text_surface, "backup") or _has_text(text_surface, "protect")
    file_system_boundary = _has_text(text_surface, "file") or _has_text(text_surface, "backup") or _has_text(text_surface, "restore")
    artifact_creation = (
        schema.get("category") == "conversion"
        and _has_text(text_surface, "artifact")
        and _has_text(text_surface, "overwrit")
    )
    creates_or_protects_backup = creates_or_protects_backup or artifact_creation
    file_system_boundary = file_system_boundary or artifact_creation
    wps_boundary = not schema.get("requires_wps") or _has_text(text_surface, "wps")

    return [
        _check("request_id_available", "request_id" in properties, sorted(properties)),
        _check("idempotency_mentions_request_id", _has_text(idempotency, "request_id"), idempotency),
        _check("task_status_recovery_available", "task_id" in properties or artifact_creation, sorted(properties)),
        _check(
            "dry_run_or_explicit_risk_boundary",
            "dry_run" in properties or bool(safety_notes),
            {"has_dry_run": "dry_run" in properties, "safety_notes": safety_notes},
        ),
        _check("backup_or_protection_boundary", creates_or_protects_backup, text_surface),
        _check("file_system_boundary_documented", file_system_boundary, text_surface),
        _check("wps_boundary_documented", wps_boundary, text_surface),
    ]


def build_security_boundary_audit() -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    schemas = list_mcp_tool_schemas()
    mutating = [schema for schema in schemas if schema.get("mutates_document")]
    tool_results = []
    for schema in mutating:
        checks = _tool_checks(schema)
        failed_checks = [check for check in checks if not check["passed"]]
        tool_results.append(
            {
                "name": schema.get("name"),
                "cli_command": schema.get("cli_command"),
                "category": schema.get("category"),
                "requires_wps": bool(schema.get("requires_wps")),
                "status": "passed" if not failed_checks else "failed",
                "checks": checks,
            }
        )

    failed_tools = [tool for tool in tool_results if tool["status"] != "passed"]
    result = {
        "schema_count": len(schemas),
        "mutating_tool_count": len(tool_results),
        "passed_tool_count": len(tool_results) - len(failed_tools),
        "failed_tool_count": len(failed_tools),
        "tools": tool_results,
    }
    errors = [] if not failed_tools else [
        {
            "code": "SECURITY_BOUNDARY_AUDIT_FAILED",
            "message": "One or more mutating tools are missing required safety boundary evidence.",
            "details": [
                {
                    "name": tool["name"],
                    "failed_checks": [check["name"] for check in tool["checks"] if not check["passed"]],
                }
                for tool in failed_tools
            ],
        }
    ]
    return not failed_tools, result, errors
