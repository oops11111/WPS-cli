from __future__ import annotations

import argparse
from typing import Any

from .mcp_schema import list_mcp_tool_schemas


SCOPE_NOTE = (
    "Text checks only confirm that tool schemas mention request_id, backup and WPS/file boundaries. "
    "They do not prove behavior; the schema_matches_cli_parser check is the only structural check. "
    "Failure modes (timeouts, restore, corruption) are verified by the unit tests, not by this audit."
)


def _parses_integer(parser_type: Any) -> bool:
    if parser_type is int:
        return True
    returns = getattr(parser_type, "__annotations__", {}).get("return")
    return returns in (int, "int")


def cli_parser_options() -> dict[str, dict[str, dict[str, Any]]]:
    from .cli import build_parser

    parser = build_parser()
    subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    commands: dict[str, dict[str, dict[str, Any]]] = {}
    for name, subparser in subparsers.choices.items():
        options: dict[str, dict[str, Any]] = {}
        for action in subparser._actions:
            for flag in action.option_strings:
                if flag.startswith("--") and flag != "--help":
                    options[flag] = {
                        "required": bool(action.required),
                        "flag": isinstance(action, argparse._StoreTrueAction),
                        "integer": _parses_integer(action.type),
                        "append": isinstance(action, argparse._AppendAction),
                    }
        commands[name] = options
    return commands


def schema_parser_mismatches(schema: dict[str, Any], commands: dict[str, dict[str, dict[str, Any]]]) -> list[str]:
    options = commands.get(schema.get("cli_command", ""))
    if options is None:
        return [f"no CLI subcommand named {schema.get('cli_command')}"]
    input_schema = schema.get("input_schema", {})
    properties = {name: spec for name, spec in input_schema.get("properties", {}).items() if name != "request_id"}
    required = set(input_schema.get("required", []))
    problems: list[str] = []
    for name, spec in properties.items():
        flag = "--" + name.replace("_", "-")
        option = options.get(flag)
        if option is None:
            problems.append(f"schema property {name} has no CLI flag {flag}")
            continue
        kind = spec.get("type")
        if (kind == "boolean") != option["flag"]:
            problems.append(f"{name}: boolean schema/flag mismatch")
        if kind == "integer" and not option["integer"]:
            problems.append(f"{name}: integer schema but CLI does not parse an int")
        if kind == "array" and not option["append"]:
            problems.append(f"{name}: array schema but CLI flag is not repeatable")
        if option["required"] != (name in required):
            problems.append(f"{name}: required mismatch between schema and CLI")
    for flag, option in options.items():
        name = flag[2:].replace("-", "_")
        if option["required"] and name not in properties:
            problems.append(f"CLI requires {flag} but the schema does not declare it")
    return problems


def _has_text(value: Any, needle: str) -> bool:
    if isinstance(value, str):
        return needle.lower() in value.lower()
    if isinstance(value, list):
        return any(_has_text(item, needle) for item in value)
    return False


def _check(name: str, passed: bool, details: Any) -> dict[str, Any]:
    return {"name": name, "passed": passed, "details": details}


def _tool_checks(schema: dict[str, Any], commands: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
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
        _check("schema_matches_cli_parser", not (mismatches := schema_parser_mismatches(schema, commands)), mismatches),
    ]


def build_security_boundary_audit() -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    schemas = list_mcp_tool_schemas()
    mutating = [schema for schema in schemas if schema.get("mutates_document")]
    commands = cli_parser_options()
    tool_results = []
    for schema in mutating:
        checks = _tool_checks(schema, commands)
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
    all_mismatches = {
        schema["name"]: problems
        for schema in schemas
        if (problems := schema_parser_mismatches(schema, commands))
    }
    result = {
        "scope": "schema_text_and_parser_consistency",
        "behavioral_verification": False,
        "scope_note": SCOPE_NOTE,
        "schema_parser_mismatches": all_mismatches,
        "schema_count": len(schemas),
        "mutating_tool_count": len(tool_results),
        "passed_tool_count": len(tool_results) - len(failed_tools),
        "failed_tool_count": len(failed_tools),
        "tools": tool_results,
    }
    ok_overall = not failed_tools and not all_mismatches
    errors = [] if ok_overall else [
        {
            "code": "SECURITY_BOUNDARY_AUDIT_FAILED",
            "message": "One or more mutating tools are missing required safety boundary evidence, or a tool schema disagrees with its CLI parser.",
            "details": [
                {
                    "name": tool["name"],
                    "failed_checks": [check["name"] for check in tool["checks"] if not check["passed"]],
                }
                for tool in failed_tools
            ] + [{"name": name, "schema_parser_mismatches": problems} for name, problems in all_mismatches.items()],
        }
    ]
    return ok_overall, result, errors
