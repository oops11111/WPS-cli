from __future__ import annotations

import io
import json
from typing import Any

from .mcp_schema import get_mcp_tool_schema


ADAPTER_BLOCKED_TOOL_NAMES = {"wps_agent_mcp_call", "mcp-call", "wps_agent_mcp_server", "mcp-server"}


def _error(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return error


def _flag_name(argument_name: str) -> str:
    return f"--{argument_name.replace('_', '-')}"


def _validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> list[dict[str, Any]]:
    input_schema = schema["input_schema"]
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])
    missing = [name for name in required if name not in arguments or arguments[name] is None]
    unknown = sorted(set(arguments) - set(properties))
    errors: list[dict[str, Any]] = []
    if missing:
        errors.append(_error("MCP_ARGUMENTS_MISSING_REQUIRED", "Required arguments are missing.", missing))
    if unknown:
        errors.append(_error("MCP_ARGUMENTS_UNKNOWN", "Unknown arguments were supplied.", unknown))
    invalid = [
        problem
        for name, value in arguments.items()
        if name in properties and value is not None and (problem := _type_problem(name, properties[name], value))
    ]
    if invalid:
        errors.append(_error("MCP_ARGUMENTS_INVALID", "Arguments do not match the tool input schema.", invalid))
    return errors


def _type_problem(name: str, spec: dict[str, Any], value: Any) -> str | None:
    kind = spec.get("type")
    if kind == "string":
        if not isinstance(value, str):
            return f"{name} must be a string"
    elif kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return f"{name} must be an integer"
        if "minimum" in spec and value < spec["minimum"]:
            return f"{name} must be at least {spec['minimum']}"
        if "maximum" in spec and value > spec["maximum"]:
            return f"{name} must be at most {spec['maximum']}"
    elif kind == "boolean":
        if not isinstance(value, bool):
            return f"{name} must be a boolean"
    elif kind == "array":
        if not isinstance(value, list) or not all(isinstance(item, (str, int)) and not isinstance(item, bool) for item in value):
            return f"{name} must be an array of strings or integers"
    if "enum" in spec and value not in spec["enum"]:
        return f"{name} must be one of {spec['enum']}"
    return None


def build_cli_argv(tool_name: str, arguments: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any] | None, list[dict[str, Any]]]:
    schema = get_mcp_tool_schema(tool_name)
    if not schema:
        return (
            False,
            [],
            None,
            [_error("MCP_TOOL_SCHEMA_NOT_FOUND", f"MCP tool schema not found: {tool_name}")],
        )
    if schema["name"] in ADAPTER_BLOCKED_TOOL_NAMES or schema["cli_command"] in ADAPTER_BLOCKED_TOOL_NAMES:
        return (
            False,
            [],
            schema,
            [_error("MCP_ADAPTER_CALL_REJECTED", "mcp-call cannot invoke adapter or server entrypoint tools.")],
        )

    errors = _validate_arguments(schema, arguments)
    if errors:
        return False, [], schema, errors

    argv = [schema["cli_command"]]
    request_id = arguments.get("request_id")
    for name, value in arguments.items():
        if name == "request_id" or value is None:
            continue
        property_schema = schema["input_schema"]["properties"].get(name, {})
        if property_schema.get("type") == "boolean":
            if value:
                argv.append(_flag_name(name))
            continue
        if property_schema.get("type") == "array":
            for item in value:
                argv.extend([_flag_name(name), str(item)])
            continue
        if str(value).startswith("-"):
            argv.append(f"{_flag_name(name)}={value}")
        else:
            argv.extend([_flag_name(name), str(value)])

    if request_id:
        if str(request_id).startswith("-"):
            argv.append(f"--request-id={request_id}")
        else:
            argv.extend(["--request-id", str(request_id)])
    return True, argv, schema, []


def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    ok, argv, schema, errors = build_cli_argv(tool_name, arguments)
    if not ok:
        return (
            False,
            {
                "tool_name": tool_name,
                "schema": schema,
                "cli_argv": argv,
                "response": None,
            },
            errors,
        )

    from .cli import run

    output = io.StringIO()
    try:
        exit_code = run(argv, output_stream=output)
    except SystemExit as exc:
        return (
            False,
            {
                "tool_name": schema["name"] if schema else tool_name,
                "cli_command": schema["cli_command"] if schema else None,
                "cli_argv": argv,
                "response": None,
                "exit_code": exc.code,
            },
            [_error("MCP_CLI_ARGUMENTS_REJECTED", "The CLI parser rejected the arguments; see the server's stderr for the usage message.", {"exit_code": exc.code})],
        )
    except Exception as exc:  # noqa: BLE001
        return (
            False,
            {
                "tool_name": schema["name"] if schema else tool_name,
                "cli_command": schema["cli_command"] if schema else None,
                "cli_argv": argv,
                "response": None,
            },
            [_error("MCP_TOOL_EXECUTION_FAILED", f"{type(exc).__name__}: {exc}"[:500])],
        )
    raw_output = output.getvalue().strip()
    try:
        response = json.loads(raw_output) if raw_output else {}
    except json.JSONDecodeError as exc:
        return (
            False,
            {
                "tool_name": schema["name"] if schema else tool_name,
                "cli_command": schema["cli_command"] if schema else None,
                "cli_argv": argv,
                "response": None,
                "raw_output": raw_output,
            },
            [_error("MCP_RESPONSE_PARSE_FAILED", "CLI response was not valid JSON.", str(exc))],
        )

    return (
        exit_code == 0 and bool(response.get("ok")),
        {
            "tool_name": schema["name"] if schema else tool_name,
            "cli_command": schema["cli_command"] if schema else None,
            "cli_argv": argv,
            "exit_code": exit_code,
            "response": response,
        },
        [],
    )
