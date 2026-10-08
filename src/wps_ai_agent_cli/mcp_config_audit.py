from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from queue import Empty, Queue
from pathlib import Path
from threading import Thread
from typing import Any

from .mcp_tool_names import audit_mcp_tool_names


DEFAULT_CONFIG_PATH = "config/mcp_client_config.example.json"
DEFAULT_SERVER_NAME = "wps-ai-agent-cli"


def _check(name: str, passed: bool, details: Any) -> dict[str, Any]:
    return {"name": name, "passed": passed, "details": details}


def _load_config(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not path.exists():
        return None, [_check("config_exists", False, str(path))]
    try:
        return json.loads(path.read_text(encoding="utf-8")), [_check("config_exists", True, str(path))]
    except json.JSONDecodeError as exc:
        return None, [
            _check("config_exists", True, str(path)),
            _check("config_json_valid", False, str(exc)),
        ]


def _resolve_command(command: str) -> str | None:
    command_path = Path(command)
    if command_path.is_absolute():
        return str(command_path) if command_path.exists() else None
    return shutil.which(command)


def _tool_descriptor_issues(tools: list[Any], page_number: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    def add(index: int, field: str) -> None:
        if len(issues) < 20:
            issues.append({"page": page_number, "index": index, "field": field})

    def valid_object_schema(schema: Any) -> bool:
        if not isinstance(schema, dict) or schema.get("type") != "object":
            return False
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        additional = schema.get("additionalProperties", True)
        return (
            isinstance(properties, dict)
            and all(isinstance(key, str) and isinstance(value, dict) for key, value in properties.items())
            and isinstance(required, list)
            and all(isinstance(item, str) for item in required)
            and isinstance(additional, (bool, dict))
        )

    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            add(index, "tool")
            continue
        for field in ("title", "description"):
            if field in tool and (not isinstance(tool[field], str) or not tool[field].strip()):
                add(index, field)
        if not valid_object_schema(tool.get("inputSchema")):
            add(index, "inputSchema")
        if "outputSchema" in tool and not valid_object_schema(tool["outputSchema"]):
            add(index, "outputSchema")
        if "annotations" in tool and not isinstance(tool["annotations"], dict):
            add(index, "annotations")
    return issues


def audit_mcp_client_config(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    server_name: str = DEFAULT_SERVER_NAME,
    expected_min_tools: int = 1,
    timeout_seconds: int = 15,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    path = Path(config_path)
    config, checks = _load_config(path)
    if config is None:
        result = {
            "config_path": str(path),
            "server_name": server_name,
            "checks": checks,
            "smoke": None,
        }
        return False, result, [{"code": "MCP_CONFIG_AUDIT_FAILED", "message": "Config could not be loaded."}]

    checks.append(_check("config_json_valid", True, str(path)))
    servers = config.get("mcpServers", {})
    server = servers.get(server_name) if isinstance(servers, dict) else None
    checks.append(_check("server_found", isinstance(server, dict), server_name))
    if not isinstance(server, dict):
        result = {
            "config_path": str(path),
            "server_name": server_name,
            "checks": checks,
            "smoke": None,
        }
        return False, result, [{"code": "MCP_CONFIG_AUDIT_FAILED", "message": "Server entry was not found."}]

    command = server.get("command")
    args = server.get("args", [])
    cwd = server.get("cwd")
    env_overrides = server.get("env", {})
    cwd_path = Path(cwd) if isinstance(cwd, str) else None
    cwd_ok = bool(cwd_path and cwd_path.exists())
    checks.append(_check("cwd_exists", cwd_ok, cwd))
    command_resolved = _resolve_command(command) if isinstance(command, str) else None
    checks.append(_check("command_resolves", command_resolved is not None, command))
    checks.append(_check("args_include_mcp_server", isinstance(args, list) and "mcp-server" in args, args))
    checks.append(
        _check(
            "env_pythonpath_present",
            isinstance(env_overrides, dict) and bool(env_overrides.get("PYTHONPATH")),
            env_overrides.get("PYTHONPATH") if isinstance(env_overrides, dict) else None,
        )
    )

    smoke: dict[str, Any] | None = None
    if cwd_ok and command_resolved and isinstance(args, list):
        base_command = [command_resolved, *[str(arg) for arg in args]]
        env = os.environ.copy()
        if isinstance(env_overrides, dict):
            env.update({str(key): str(value) for key, value in env_overrides.items()})
        page_count = 0
        descriptor_issues: list[dict[str, Any]] = []
        descriptor_issue_count = 0
        process: subprocess.Popen[str] | None = None
        stdout_thread: Thread | None = None
        stderr_thread: Thread | None = None
        replies: Queue[str | None] = Queue()
        stderr_chunks: list[str] = []
        stderr_size = 0
        try:
            deadline = time.monotonic() + timeout_seconds
            process = subprocess.Popen(
                base_command,
                cwd=str(cwd_path),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )

            def collect_stdout() -> None:
                assert process is not None and process.stdout is not None
                for output_line in process.stdout:
                    replies.put(output_line)
                replies.put(None)

            def collect_stderr() -> None:
                nonlocal stderr_size
                assert process is not None and process.stderr is not None
                for error_line in process.stderr:
                    remaining = 8192 - stderr_size
                    if remaining > 0:
                        chunk = error_line[:remaining]
                        stderr_chunks.append(chunk)
                        stderr_size += len(chunk)

            stdout_thread = Thread(target=collect_stdout, name="mcp-config-audit-stdout", daemon=True)
            stderr_thread = Thread(target=collect_stderr, name="mcp-config-audit-stderr", daemon=True)
            stdout_thread.start()
            stderr_thread.start()

            def exchange(request_id: str | int, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
                assert process is not None and process.stdin is not None
                request = {"jsonrpc": "2.0", "id": request_id, "method": method}
                if params is not None:
                    request["params"] = params
                process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
                process.stdin.flush()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(base_command, timeout_seconds)
                try:
                    raw_response = replies.get(timeout=remaining)
                except Empty as exc:
                    raise subprocess.TimeoutExpired(base_command, timeout_seconds) from exc
                if raw_response is None:
                    raise ValueError("Configured server closed stdout before replying.")
                response = json.loads(raw_response)
                if (not isinstance(response, dict) or response.get("jsonrpc") != "2.0"
                        or response.get("id") != request_id):
                    raise ValueError("Configured server returned an invalid JSON-RPC response or request ID.")
                if isinstance(response.get("error"), dict):
                    raise ValueError(f"Configured server returned a JSON-RPC error for {method}.")
                if not isinstance(response.get("result"), dict):
                    raise ValueError(f"Configured server returned an invalid result for {method}.")
                return response

            initialize = exchange(
                "mcp-config-audit-init",
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "wps-ai-agent-cli-config-audit", "version": "1"},
                },
            )["result"]
            if (initialize.get("protocolVersion") != "2025-11-25"
                    or not isinstance(initialize.get("capabilities"), dict)
                    or not isinstance(initialize.get("serverInfo"), dict)):
                raise ValueError("Configured server returned an invalid initialize result.")

            assert process.stdin is not None
            process.stdin.write(json.dumps({
                "jsonrpc": "2.0", "method": "notifications/initialized",
            }) + "\n")
            process.stdin.flush()

            tools = []
            cursor = None
            seen_cursors = set()
            while page_count < 1000:
                params = {"cursor": cursor} if cursor is not None else {}
                response = exchange(page_count + 1, "tools/list", params)
                page = response["result"]
                page_tools = page.get("tools")
                if not isinstance(page_tools, list):
                    raise ValueError("Configured server returned an invalid tools/list page.")
                page_issues = _tool_descriptor_issues(page_tools, page_count + 1)
                descriptor_issue_count += len(page_issues)
                descriptor_issues.extend(page_issues[:max(0, 20 - len(descriptor_issues))])
                tools.extend(page_tools)
                page_count += 1
                next_cursor = page.get("nextCursor")
                if next_cursor is None:
                    break
                if not isinstance(next_cursor, str) or next_cursor in seen_cursors:
                    raise ValueError("Configured server returned an invalid or repeated cursor.")
                seen_cursors.add(next_cursor)
                cursor = next_cursor
            else:
                raise ValueError("Configured server exceeded the tools/list page limit.")

            assert process.stdin is not None
            process.stdin.close()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(base_command, timeout_seconds)
            try:
                exit_code = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                raise subprocess.TimeoutExpired(base_command, timeout_seconds) from None
            if exit_code != 0:
                raise ValueError(f"Configured server exited with code {exit_code}.")
            if stdout_thread is not None:
                stdout_thread.join(timeout=max(0, deadline - time.monotonic()))
            if stderr_thread is not None:
                stderr_thread.join(timeout=max(0, deadline - time.monotonic()))

            invalid_tool_count, duplicate_tool_count = audit_mcp_tool_names(tools)
            tool_count = len(tools)
            smoke = {
                "command_line": base_command,
                "exit_code": exit_code,
                "tool_count": tool_count,
                "page_count": page_count,
                "invalid_tool_count": invalid_tool_count,
                "duplicate_tool_count": duplicate_tool_count,
                "invalid_descriptor_count": descriptor_issue_count,
                "descriptor_issues": descriptor_issues,
                "stderr": "".join(stderr_chunks).strip(),
                "protocol_version": initialize["protocolVersion"],
                "persistent_session": True,
            }
            checks.append(
                _check(
                    "configured_tools_list_smoke",
                    exit_code == 0 and tool_count >= expected_min_tools
                    and invalid_tool_count == 0 and duplicate_tool_count == 0,
                    smoke,
                )
            )
            checks.append(_check(
                "configured_tool_descriptors",
                descriptor_issue_count == 0,
                {"invalid_count": descriptor_issue_count, "issues": descriptor_issues},
            ))
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError, ValueError) as exc:
            smoke = {"error": str(exc), "page_count": page_count, "stderr": "".join(stderr_chunks).strip()}
            checks.append(_check("configured_tools_list_smoke", False, smoke))
        finally:
            if process is not None:
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                if stdout_thread is not None:
                    stdout_thread.join(timeout=1)
                if stderr_thread is not None:
                    stderr_thread.join(timeout=1)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
    else:
        checks.append(_check("configured_tools_list_smoke", False, "Skipped because command or cwd check failed."))

    ok = all(check["passed"] for check in checks)
    result = {
        "config_path": str(path),
        "server_name": server_name,
        "expected_min_tools": expected_min_tools,
        "checks": checks,
        "smoke": smoke,
    }
    errors = [] if ok else [
        {
            "code": "MCP_CONFIG_AUDIT_FAILED",
            "message": "One or more MCP client configuration audit checks failed.",
            "details": [check for check in checks if not check["passed"]],
        }
    ]
    return ok, result, errors
