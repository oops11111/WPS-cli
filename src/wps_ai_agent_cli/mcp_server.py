from __future__ import annotations

import base64
import hashlib
import json
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Any, TextIO

from .mcp_adapter import call_mcp_tool, validate_mcp_tool_arguments
from .mcp_schema import list_mcp_tool_schemas


MCP_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_MCP_PROTOCOL_VERSIONS = (MCP_PROTOCOL_VERSION,)
SERVER_INFO = {"name": "wps-ai-agent-cli", "version": "phase2-prototype"}
MCP_TOOLS_PAGE_SIZE = 50
MCP_TOOLS_CURSOR_MAX_LENGTH = 128
MCP_STDIO_MAX_LINE_CHARS = 1024 * 1024
MCP_STDIO_DRAIN_CHUNK_CHARS = 8192
_CURSOR_OMITTED = object()


class _DuplicateJsonKeyError(ValueError):
    pass


class _NonstandardJsonConstantError(ValueError):
    pass


def _object_from_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError
        result[key] = value
    return result


def _reject_nonstandard_json_constant(value: str) -> None:
    raise _NonstandardJsonConstantError


def _loads_mcp_json(raw_json: str) -> Any:
    return json.loads(
        raw_json,
        object_pairs_hook=_object_from_pairs,
        parse_constant=_reject_nonstandard_json_constant,
    )


def _iter_bounded_mcp_lines(input_stream: TextIO):
    readline = getattr(input_stream, "readline", None)
    if not callable(readline):
        for line in input_stream:
            yield line if len(line) <= MCP_STDIO_MAX_LINE_CHARS else None, len(line) > MCP_STDIO_MAX_LINE_CHARS
        return

    while True:
        line = readline(MCP_STDIO_MAX_LINE_CHARS + 1)
        if not line:
            return
        if len(line) <= MCP_STDIO_MAX_LINE_CHARS:
            yield line, False
            continue
        while line and not line.endswith("\n"):
            line = readline(MCP_STDIO_DRAIN_CHUNK_CHARS)
        yield None, True


def _response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id: Any, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _validate_mcp_envelope(message: Any) -> tuple[dict[str, Any] | None, bool]:
    if not isinstance(message, dict):
        return _error_response(None, -32600, "Invalid JSON-RPC request."), False
    method = message.get("method")
    if message.get("jsonrpc") != "2.0" or not isinstance(method, str) or not method:
        return _error_response(None, -32600, "Invalid JSON-RPC request."), False

    is_notification = "id" not in message
    if is_notification:
        if method.startswith("notifications/"):
            if "params" in message and not isinstance(message["params"], dict):
                return None, True
            return None, True
        return _error_response(None, -32600, "MCP requests require a string or integer ID."), False

    request_id = message["id"]
    if (method.startswith("notifications/") or isinstance(request_id, bool)
            or not isinstance(request_id, (str, int))):
        return _error_response(None, -32600, "Invalid JSON-RPC request."), False
    if "params" in message and not isinstance(message["params"], dict):
        return _error_response(None, -32600, "MCP request params must be an object."), False
    return None, False


def _tool_from_schema(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": schema["name"],
        "title": schema["title"],
        "description": schema["description"],
        "inputSchema": schema["input_schema"],
        "outputSchema": schema["output_contract"],
        "annotations": {
            "readOnlyHint": not schema["mutates_document"],
            "destructiveHint": schema["mutates_document"],
            "openWorldHint": schema["requires_wps"],
        },
        "_meta": {
            "cliCommand": schema["cli_command"],
            "category": schema["category"],
            "requiresWps": schema["requires_wps"],
            "idempotency": schema["idempotency"],
        },
    }


def _initialize_result(protocol_version: str = MCP_PROTOCOL_VERSION) -> dict[str, Any]:
    return {
        "protocolVersion": protocol_version,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": SERVER_INFO,
    }


def _tools_list_result(cursor: Any = _CURSOR_OMITTED) -> dict[str, Any]:
    tools = [_tool_from_schema(schema) for schema in list_mcp_tool_schemas()]
    fingerprint = hashlib.sha256(
        json.dumps(tools, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    offset = 0
    if cursor is not _CURSOR_OMITTED:
        if (not isinstance(cursor, str) or not cursor
                or len(cursor) > MCP_TOOLS_CURSOR_MAX_LENGTH):
            raise ValueError("Invalid tools/list cursor.")
        try:
            encoded = cursor.encode("ascii")
            padded = encoded + b"=" * (-len(encoded) % 4)
            decoded = base64.b64decode(padded, altchars=b"-_", validate=True).decode("ascii")
        except (UnicodeEncodeError, UnicodeDecodeError, ValueError):
            raise ValueError("Invalid tools/list cursor.") from None
        prefix, separator, offset_text = decoded.rpartition(":")
        if (prefix != fingerprint or not separator or not offset_text.isdecimal()
                or (len(offset_text) > 1 and offset_text.startswith("0"))):
            raise ValueError("Invalid tools/list cursor.")
        offset = int(offset_text)
        if offset <= 0 or offset >= len(tools) or offset % MCP_TOOLS_PAGE_SIZE:
            raise ValueError("Invalid tools/list cursor.")

    page = tools[offset:offset + MCP_TOOLS_PAGE_SIZE]
    result = {
        "resultType": "complete",
        "tools": page,
        "ttlMs": 300000,
        "cacheScope": "public",
    }
    next_offset = offset + len(page)
    if next_offset < len(tools):
        cursor_payload = f"{fingerprint}:{next_offset}".encode("ascii")
        result["nextCursor"] = base64.urlsafe_b64encode(cursor_payload).rstrip(b"=").decode("ascii")
    return result


def _tools_call_result(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    ok, result, errors = call_mcp_tool(name, arguments)
    summary = None
    response = result.get("response") if result else None
    if response:
        summary = response.get("summary")
    payload = {
        "ok": ok,
        "summary": summary or ("MCP tool call completed." if ok else "MCP tool call failed."),
        "errors": errors,
    }
    return {
        "resultType": "complete",
        "isError": not ok,
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            }
        ],
        "structuredContent": {
            "mcp_call": result,
            "errors": errors,
        },
    }


def handle_mcp_request(message: dict[str, Any]) -> dict[str, Any] | None:
    validation_error, is_notification = _validate_mcp_envelope(message)
    if validation_error is not None:
        return validation_error
    if is_notification:
        return None

    request_id = message.get("id")
    method = message.get("method")
    if method == "initialize":
        params = message.get("params")
        if not isinstance(params, dict):
            return _error_response(request_id, -32602, "initialize params must be an object.")
        requested_version = params.get("protocolVersion")
        capabilities = params.get("capabilities")
        client_info = params.get("clientInfo")
        if (not isinstance(requested_version, str) or not requested_version
                or not isinstance(capabilities, dict)
                or not isinstance(client_info, dict)
                or not isinstance(client_info.get("name"), str) or not client_info["name"]
                or not isinstance(client_info.get("version"), str) or not client_info["version"]):
            return _error_response(request_id, -32602, "initialize requires protocolVersion, capabilities, and clientInfo name/version.")
        selected_version = (
            requested_version if requested_version in SUPPORTED_MCP_PROTOCOL_VERSIONS
            else SUPPORTED_MCP_PROTOCOL_VERSIONS[0]
        )
        return _response(request_id, _initialize_result(selected_version))
    if method == "ping":
        params = message.get("params", {})
        if not isinstance(params, dict) or params:
            return _error_response(request_id, -32602, "ping params must be empty.")
        return _response(request_id, {})
    if method == "tools/list":
        params = message.get("params", {})
        if not isinstance(params, dict):
            return _error_response(request_id, -32602, "tools/list params must be an object.")
        try:
            cursor = params["cursor"] if "cursor" in params else _CURSOR_OMITTED
            return _response(request_id, _tools_list_result(cursor))
        except ValueError:
            return _error_response(request_id, -32602, "Invalid tools/list cursor.")
    if method == "tools/call":
        params = message.get("params", {})
        if not isinstance(params, dict):
            return _error_response(request_id, -32602, "tools/call params must be an object.")
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not name:
            return _error_response(request_id, -32602, "tools/call requires a tool name.")
        if not isinstance(arguments, dict):
            return _error_response(request_id, -32602, "tools/call arguments must be an object.")
        if name not in {schema["name"] for schema in list_mcp_tool_schemas()}:
            return _error_response(request_id, -32602, f"Unknown tool: {name}")
        argument_errors = validate_mcp_tool_arguments(name, arguments)
        if argument_errors:
            return _error_response(request_id, -32602, "Invalid tool arguments.", argument_errors)
        return _response(request_id, _tools_call_result(name, arguments))

    return _error_response(request_id, -32601, f"Method not found: {method}")


def handle_mcp_json(raw_json: str) -> dict[str, Any] | None:
    try:
        message = _loads_mcp_json(raw_json)
    except _DuplicateJsonKeyError:
        return _error_response(None, -32600, "Invalid JSON-RPC request.")
    except _NonstandardJsonConstantError:
        return _error_response(None, -32700, "Parse error.")
    except json.JSONDecodeError as exc:
        return _error_response(None, -32700, "Parse error.", str(exc))
    if not isinstance(message, dict):
        return _error_response(None, -32600, "Invalid JSON-RPC request.")
    return handle_mcp_request(message)


def serve_stdio(input_stream: TextIO | None = None, output_stream: TextIO | None = None) -> int:
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    output_lock = Lock()

    def write_response(response: dict[str, Any] | None) -> None:
        if response is None:
            return
        encoded = json.dumps(response, ensure_ascii=False, sort_keys=True) + "\n"
        with output_lock:
            output_stream.write(encoded)
            output_stream.flush()

    def run_batch(raw_json: str, request_id: Any) -> None:
        try:
            response = handle_mcp_json(raw_json)
        except Exception:
            response = _error_response(request_id, -32603, "Batch conversion failed unexpectedly.")
        # Deliver completion even while the main thread is blocked reading stdin.
        write_response(response)

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="mcp-html-batch") as executor:
        pending: Future[None] | None = None
        lifecycle = "awaiting_initialize"
        seen_request_ids: set[tuple[type, str | int]] = set()
        for line, oversized in _iter_bounded_mcp_lines(input_stream):
            if oversized:
                write_response(_error_response(None, -32600, "MCP stdio message exceeds the maximum line length."))
                continue
            if line is None:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                message = _loads_mcp_json(line)
            except _DuplicateJsonKeyError:
                write_response(_error_response(None, -32600, "Invalid JSON-RPC request."))
                continue
            except _NonstandardJsonConstantError:
                write_response(_error_response(None, -32700, "Parse error."))
                continue
            except json.JSONDecodeError:
                write_response(handle_mcp_json(line))
                continue
            validation_error, is_notification = _validate_mcp_envelope(message)
            if validation_error is not None:
                write_response(validation_error)
                continue
            if is_notification:
                initialized_params_valid = (
                    "params" not in message or isinstance(message["params"], dict)
                )
                if (message.get("method") == "notifications/initialized"
                        and lifecycle == "awaiting_initialized" and initialized_params_valid):
                    lifecycle = "ready"
                handle_mcp_request(message)
                continue
            request_id = message["id"]
            request_id_key = (type(request_id), request_id)
            if request_id_key in seen_request_ids:
                write_response(_error_response(request_id, -32600, "Request ID has already been used in this MCP session."))
                continue
            seen_request_ids.add(request_id_key)
            method = message["method"]
            if lifecycle == "awaiting_initialize":
                if method != "initialize":
                    write_response(_error_response(message["id"], -32600, "MCP session must be initialized first."))
                    continue
                response = handle_mcp_request(message)
                write_response(response)
                if response is not None and "result" in response:
                    lifecycle = "awaiting_initialized"
                continue
            if lifecycle == "awaiting_initialized":
                write_response(_error_response(message["id"], -32600, "MCP session is awaiting notifications/initialized."))
                continue
            if method == "initialize":
                write_response(_error_response(message["id"], -32600, "MCP session is already initialized."))
                continue
            params = message.get("params") if isinstance(message, dict) else None
            if (
                isinstance(message, dict)
                and message.get("method") == "tools/call"
                and isinstance(params, dict)
                and params.get("name") == "wps_agent_html_batch_convert"
            ):
                if pending is not None and not pending.done():
                    write_response(_error_response(message.get("id"), -32000, "An HTML batch conversion is already in progress."))
                else:
                    if pending is not None:
                        pending.result()
                    pending = executor.submit(run_batch, line, message.get("id"))
            else:
                write_response(handle_mcp_request(message) if isinstance(message, dict) else handle_mcp_json(line))
            if pending is not None and pending.done():
                pending.result()
                pending = None
        if pending is not None:
            pending.result()
    return 0
