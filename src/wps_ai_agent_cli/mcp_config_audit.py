from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


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
        try:
            deadline = time.monotonic() + timeout_seconds
            tools = []
            cursor = None
            seen_cursors = set()
            stderr_lines = []
            last_command = base_command
            exit_code = 0
            while page_count < 1000:
                params = {"cursor": cursor} if cursor is not None else {}
                request = json.dumps({
                    "jsonrpc": "2.0", "id": page_count + 1,
                    "method": "tools/list", "params": params,
                })
                last_command = [*base_command, "--once-json", request]
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(last_command, timeout_seconds)
                completed = subprocess.run(
                    last_command,
                    cwd=str(cwd_path),
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=remaining,
                    check=False,
                )
                exit_code = completed.returncode
                if completed.stderr.strip():
                    stderr_lines.append(completed.stderr.strip())
                stdout = completed.stdout.strip()
                response = json.loads(stdout) if stdout else {}
                if not isinstance(response, dict):
                    raise ValueError("Configured server returned an invalid JSON-RPC response.")
                if exit_code != 0 or isinstance(response.get("error"), dict):
                    raise ValueError("Configured server returned an error for tools/list.")
                page = response.get("result")
                page_tools = page.get("tools") if isinstance(page, dict) else None
                if not isinstance(page_tools, list):
                    raise ValueError("Configured server returned an invalid tools/list page.")
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

            names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
            invalid_tool_count = len(tools) - sum(
                isinstance(tool, dict) and isinstance(tool.get("name"), str) for tool in tools
            )
            duplicate_tool_count = len(names) - len(set(names)) if not invalid_tool_count else 0
            tool_count = len(tools)
            smoke = {
                "command_line": last_command,
                "exit_code": exit_code,
                "tool_count": tool_count,
                "page_count": page_count,
                "invalid_tool_count": invalid_tool_count,
                "duplicate_tool_count": duplicate_tool_count,
                "stderr": "\n".join(stderr_lines),
            }
            checks.append(
                _check(
                    "configured_tools_list_smoke",
                    exit_code == 0 and tool_count >= expected_min_tools
                    and invalid_tool_count == 0 and duplicate_tool_count == 0,
                    smoke,
                )
            )
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError, ValueError) as exc:
            smoke = {"error": str(exc), "page_count": page_count}
            checks.append(_check("configured_tools_list_smoke", False, smoke))
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
