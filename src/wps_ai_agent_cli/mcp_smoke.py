from __future__ import annotations

from typing import Any

from .mcp_server import handle_mcp_request
from .mcp_schema import get_mcp_tool_schema
from .mcp_tool_names import audit_mcp_tool_names


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


def _response_result(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict):
        return {}
    result = response.get("result")
    return result if isinstance(result, dict) else {}


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
    tools_list_pages = []
    tools = []
    cursor = None
    seen_cursors = set()
    tools_list_error = None
    for page_index in range(1000):
        params = {"cursor": cursor} if cursor is not None else {}
        page_response = handle_mcp_request(_request(2 + page_index, "tools/list", params))
        tools_list_pages.append(page_response)
        page_result = _response_result(page_response)
        if not isinstance(page_result.get("tools"), list):
            response_object = page_response if isinstance(page_response, dict) else {}
            tools_list_error = response_object.get("error") or "Invalid tools/list page."
            break
        tools.extend(page_result["tools"])
        next_cursor = page_result.get("nextCursor")
        if next_cursor is None:
            break
        if not isinstance(next_cursor, str) or next_cursor in seen_cursors:
            tools_list_error = "Invalid or repeated tools/list cursor."
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    else:
        tools_list_error = "MCP tools/list exceeded the page limit."

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

    initialize_result = _response_result(initialize_response)
    call_result = _response_result(tools_call_response)
    structured = call_result.get("structuredContent")
    if not isinstance(structured, dict):
        structured = {}
    mcp_call = structured.get("mcp_call")
    if not isinstance(mcp_call, dict):
        mcp_call = {}
    cli_response = mcp_call.get("response")
    if not isinstance(cli_response, dict):
        cli_response = {}
    invalid_tool_count, duplicate_tool_count = audit_mcp_tool_names(tools)
    page_summaries = []
    for index, response in enumerate(tools_list_pages):
        page_result = _response_result(response)
        page_tools = page_result.get("tools")
        page_summaries.append({
            "page": index + 1,
            "tool_count": len(page_tools) if isinstance(page_tools, list) else 0,
            "has_next_page": "nextCursor" in page_result,
            "ttlMs": page_result.get("ttlMs"),
            "cacheScope": page_result.get("cacheScope"),
        })
    tools_list_summary = {
        "tool_count": len(tools),
        "page_count": len(tools_list_pages),
        "pages": page_summaries,
    }
    capabilities = initialize_result.get("capabilities")
    tool_capabilities = capabilities.get("tools") if isinstance(capabilities, dict) else None

    checks = [
        _check(
            "initialize_protocol",
            initialize_result.get("protocolVersion") is not None
            and tool_capabilities is not None,
            {
                "protocolVersion": initialize_result.get("protocolVersion"),
                "serverInfo": initialize_result.get("serverInfo"),
            },
        ),
        _check(
            "tools_list_count",
            tools_list_error is None and len(tools) >= expected_min_tools
            and invalid_tool_count == 0 and duplicate_tool_count == 0,
            {
                "tool_count": len(tools),
                "page_count": len(tools_list_pages),
                "invalid_tool_count": invalid_tool_count,
                "duplicate_tool_count": duplicate_tool_count,
                "expected_min_tools": expected_min_tools,
                "error": tools_list_error,
            },
        ),
        _check(
            "tools_call_adapter",
            call_result.get("isError") is False and cli_response.get("ok") is True,
            {
                "tool_name": tool_name,
                "cli_command": mcp_call.get("cli_command"),
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
            "tools_list": tools_list_summary,
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
