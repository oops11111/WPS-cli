from __future__ import annotations

import io
import json
import math
import re
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


def _constraint_error(argument_name: str, constraint: str) -> dict[str, Any]:
    return _error(
        "MCP_SCHEMA_CONSTRAINT_INVALID",
        "Tool input schema contains invalid constraint metadata.",
        {"argument": argument_name, "constraint": constraint},
    )


def _validate_property_schema(argument_name: str, property_schema: Any) -> list[dict[str, Any]]:
    if not isinstance(property_schema, dict):
        return [_constraint_error(argument_name, "property")]

    expected = property_schema.get("type")
    supported_types = {"string", "integer", "number", "boolean", "array", "object"}
    if expected not in supported_types:
        return [_error(
            "MCP_SCHEMA_TYPE_UNSUPPORTED",
            "Tool input schema uses an unsupported JSON type.",
            argument_name,
        )]

    errors: list[dict[str, Any]] = []
    for keyword in ("minimum", "maximum"):
        if keyword not in property_schema:
            continue
        value = property_schema[keyword]
        numeric = type(value) is int or (type(value) is float and math.isfinite(value))
        compatible = (
            expected in {"integer", "number"}
            and numeric
            and (expected != "integer" or type(value) is int)
        )
        if not compatible:
            errors.append(_constraint_error(argument_name, keyword))
    if (
        "minimum" in property_schema and "maximum" in property_schema
        and not any(error["details"]["constraint"] in {"minimum", "maximum"} for error in errors)
        and property_schema["minimum"] > property_schema["maximum"]
    ):
        errors.append(_constraint_error(argument_name, "minimum/maximum"))

    for keyword in ("minLength", "maxLength"):
        if keyword not in property_schema:
            continue
        value = property_schema[keyword]
        if expected != "string" or type(value) is not int or value < 0:
            errors.append(_constraint_error(argument_name, keyword))
    if (
        "minLength" in property_schema and "maxLength" in property_schema
        and type(property_schema["minLength"]) is int
        and type(property_schema["maxLength"]) is int
        and property_schema["minLength"] > property_schema["maxLength"]
    ):
        errors.append(_constraint_error(argument_name, "minLength/maxLength"))

    if "enum" in property_schema:
        values = property_schema["enum"]
        if not isinstance(values, list) or not values:
            errors.append(_constraint_error(argument_name, "enum"))
        else:
            enum_validators = {
                "string": lambda item: isinstance(item, str),
                "integer": lambda item: type(item) is int,
                "number": lambda item: type(item) is int or (type(item) is float and math.isfinite(item)),
                "boolean": lambda item: isinstance(item, bool),
                "array": lambda item: isinstance(item, list),
                "object": lambda item: isinstance(item, dict),
            }
            if any(not enum_validators[expected](item) for item in values):
                errors.append(_constraint_error(argument_name, "enum"))
    if "pattern" in property_schema:
        pattern = property_schema["pattern"]
        if expected != "string" or not isinstance(pattern, str):
            errors.append(_constraint_error(argument_name, "pattern"))
        else:
            try:
                re.compile(pattern)
            except re.error:
                errors.append(_constraint_error(argument_name, "pattern"))

    if "items" in property_schema:
        item_schema = property_schema["items"]
        if (
            expected != "array"
            or not isinstance(item_schema, dict)
            or item_schema.get("type") not in supported_types
        ):
            errors.append(_constraint_error(argument_name, "items"))
    return errors


def _validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> list[dict[str, Any]]:
    input_schema = schema["input_schema"]
    properties = input_schema.get("properties", {})
    required = input_schema.get("required", [])
    if not isinstance(properties, dict):
        return [_constraint_error("input_schema", "properties")]
    schema_errors = [
        error
        for name, property_schema in properties.items()
        for error in _validate_property_schema(name, property_schema)
    ]
    if schema_errors:
        return schema_errors
    missing = [name for name in required if name not in arguments]
    unknown = sorted(set(arguments) - set(properties)) if input_schema.get("additionalProperties", True) is False else []
    errors: list[dict[str, Any]] = []
    if missing:
        errors.append(_error("MCP_ARGUMENTS_MISSING_REQUIRED", "Required arguments are missing.", missing))
    if unknown:
        errors.append(_error("MCP_ARGUMENTS_UNKNOWN", "Unknown arguments were supplied.", unknown))
    for name in sorted(set(arguments) & set(properties)):
        value = arguments[name]
        property_schema = properties[name]
        expected = property_schema.get("type")
        valid_type = {
            "string": lambda item: isinstance(item, str),
            "integer": lambda item: type(item) is int,
            "number": lambda item: type(item) in (int, float) and math.isfinite(item),
            "boolean": lambda item: isinstance(item, bool),
            "array": lambda item: isinstance(item, list),
            "object": lambda item: isinstance(item, dict),
        }.get(expected)
        if valid_type is None:
            errors.append(_error("MCP_SCHEMA_TYPE_UNSUPPORTED", "Tool input schema uses an unsupported JSON type.", name))
            continue
        if not valid_type(value):
            errors.append(_error("MCP_ARGUMENT_TYPE_INVALID", "Argument has an invalid JSON type.", name))
            continue
        if "enum" in property_schema and value not in property_schema["enum"]:
            errors.append(_error("MCP_ARGUMENT_ENUM_INVALID", "Argument is not one of the permitted values.", name))
        if expected == "string":
            if "minLength" in property_schema and len(value) < property_schema["minLength"]:
                errors.append(_error("MCP_ARGUMENT_STRING_TOO_SHORT", "Argument is shorter than its minimum length.", name))
            if "maxLength" in property_schema and len(value) > property_schema["maxLength"]:
                errors.append(_error("MCP_ARGUMENT_STRING_TOO_LONG", "Argument is longer than its maximum length.", name))
            if "pattern" in property_schema and re.search(property_schema["pattern"], value) is None:
                errors.append(_error("MCP_ARGUMENT_PATTERN_MISMATCH", "Argument does not match its required pattern.", name))
        if expected in {"integer", "number"}:
            if "minimum" in property_schema and value < property_schema["minimum"]:
                errors.append(_error("MCP_ARGUMENT_BELOW_MINIMUM", "Argument is below its minimum.", name))
            if "maximum" in property_schema and value > property_schema["maximum"]:
                errors.append(_error("MCP_ARGUMENT_ABOVE_MAXIMUM", "Argument is above its maximum.", name))
        item_schema = property_schema.get("items")
        if expected == "array" and isinstance(item_schema, dict):
            item_type = item_schema.get("type")
            item_validators = {
                "string": lambda item: isinstance(item, str),
                "integer": lambda item: type(item) is int,
                "number": lambda item: type(item) is int or (type(item) is float and math.isfinite(item)),
                "boolean": lambda item: isinstance(item, bool),
                "object": lambda item: isinstance(item, dict),
            }
            item_validator = item_validators.get(item_type)
            if item_validator is None:
                errors.append(_error("MCP_SCHEMA_ITEMS_UNSUPPORTED", "Tool input schema uses unsupported array item constraints.", name))
            elif any(not item_validator(item) for item in value):
                errors.append(_error("MCP_ARGUMENT_ARRAY_ITEM_INVALID", "Array contains an item with an invalid JSON type.", name))
    return errors


def validate_mcp_tool_arguments(tool_name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
    schema = get_mcp_tool_schema(tool_name)
    if schema is None:
        return [_error("MCP_TOOL_SCHEMA_NOT_FOUND", f"MCP tool schema not found: {tool_name}")]
    return _validate_arguments(schema, arguments)


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
        argv.extend([_flag_name(name), str(value)])

    if request_id:
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
    exit_code = run(argv, output_stream=output)
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
