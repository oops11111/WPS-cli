from __future__ import annotations

from typing import Any

from .mcp_server import handle_mcp_request
from .mcp_schema import get_mcp_tool_schema


_PARAMETERIZED_READ_ONLY_COMMANDS = {
    "tasks", "task-status", "task-statuses", "task-recovery", "task-recovery-playbooks",
    "html-batch-request", "operation", "operations", "mutation-request-inspect", "mcp-tools", "mcp-tool-schema",
    "mcp-catalog-snapshot", "mcp-catalog-drift", "security-audit", "regression-manifest",
}


def _request(request_id: int, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }


def _check(name: str, passed: bool, details: Any) -> dict[str, Any]:
    return {"name": name, "passed": passed, "details": details}


def _tool_arguments(tool_name: str) -> dict[str, Any]:
    arguments = {"request_id": "mcp-smoke-tools-call-001"}
    if tool_name in {"wps_agent_tasks", "tasks"}:
        arguments["phase"] = "phase2"
    return arguments


def run_mcp_server_smoke(
    expected_min_tools: int = 1,
    tool_name: str = "wps_agent_tasks",
    tool_arguments: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    if tool_arguments is not None:
        schema = get_mcp_tool_schema(tool_name)
        if (schema is None or schema["mutates_document"] or schema["requires_wps"]
                or schema["cli_command"] not in _PARAMETERIZED_READ_ONLY_COMMANDS):
            return False, {}, [{"code": "MCP_SMOKE_TOOL_NOT_READ_ONLY", "message": "Parameterized smoke requires a local read-only tool."}]
    initialize_response = handle_mcp_request(_request(1, "initialize"))
    tools_list_response = handle_mcp_request(_request(2, "tools/list"))
    tools_call_response = handle_mcp_request(
        _request(
            3,
            "tools/call",
            {
                "name": tool_name,
                "arguments": _tool_arguments(tool_name) if tool_arguments is None else {
                    "request_id": "mcp-smoke-tools-call-001", **tool_arguments,
                },
            },
        )
    )

    initialize_result = (initialize_response or {}).get("result", {})
    tools_result = (tools_list_response or {}).get("result", {})
    tools = tools_result.get("tools", [])
    call_result = (tools_call_response or {}).get("result", {})
    structured = call_result.get("structuredContent", {})
    cli_response = structured.get("mcp_call", {}).get("response") or {}

    checks = [
        _check(
            "initialize_protocol",
            initialize_result.get("protocolVersion") is not None
            and initialize_result.get("capabilities", {}).get("tools") is not None,
            {
                "protocolVersion": initialize_result.get("protocolVersion"),
                "serverInfo": initialize_result.get("serverInfo"),
            },
        ),
        _check(
            "tools_list_count",
            isinstance(tools, list) and len(tools) >= expected_min_tools,
            {"tool_count": len(tools) if isinstance(tools, list) else None, "expected_min_tools": expected_min_tools},
        ),
        _check(
            "tools_call_adapter",
            call_result.get("isError") is False and cli_response.get("ok") is True,
            {
                "tool_name": tool_name,
                "cli_command": structured.get("mcp_call", {}).get("cli_command"),
                "summary": cli_response.get("summary"),
            },
        ),
    ]
    ok = all(check["passed"] for check in checks)
    result = {
        "expected_min_tools": expected_min_tools,
        "tool_name": tool_name,
        "checks": checks,
        "responses": {
            "initialize": initialize_response,
            "tools_list": tools_list_response,
            "tools_call": tools_call_response,
        },
    }
    errors = [] if ok else [
        {
            "code": "MCP_SMOKE_FAILED",
            "message": "One or more MCP server smoke checks failed.",
            "details": [check for check in checks if not check["passed"]],
        }
    ]
    return ok, result, errors
