from __future__ import annotations

import json
import os
import shutil
import subprocess
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
        request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        command_line = [command_resolved, *[str(arg) for arg in args], "--once-json", request]
        env = os.environ.copy()
        if isinstance(env_overrides, dict):
            env.update({str(key): str(value) for key, value in env_overrides.items()})
        try:
            completed = subprocess.run(
                command_line,
                cwd=str(cwd_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            stdout = completed.stdout.strip()
            response = json.loads(stdout) if stdout else {}
            tools = response.get("result", {}).get("tools", [])
            tool_count = len(tools) if isinstance(tools, list) else None
            smoke = {
                "command_line": command_line,
                "exit_code": completed.returncode,
                "tool_count": tool_count,
                "stderr": completed.stderr.strip(),
            }
            checks.append(
                _check(
                    "configured_tools_list_smoke",
                    completed.returncode == 0 and tool_count is not None and tool_count >= expected_min_tools,
                    smoke,
                )
            )
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            smoke = {"error": str(exc)}
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
