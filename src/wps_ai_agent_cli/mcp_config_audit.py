from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import time
from urllib.parse import urlsplit
from queue import Empty, Full, Queue
from contextvars import ContextVar
from pathlib import Path
from threading import Event, Thread
from typing import Any

from .mcp_tool_names import audit_mcp_tool_names


DEFAULT_CONFIG_PATH = "config/mcp_client_config.example.json"
DEFAULT_SERVER_NAME = "wps-ai-agent-cli"
MCP_AUDIT_MAX_STDOUT_LINE_CHARS = 1024 * 1024
MCP_AUDIT_STDOUT_QUEUE_SIZE = 8
MCP_AUDIT_READ_CHUNK_CHARS = 8192
MCP_CONFIG_MAX_BYTES = 1024 * 1024
MCP_CONFIG_MAX_JSON_DEPTH = 64
MCP_CONFIG_AUDIT_TIMEOUT_MIN_SECONDS = 1
MCP_CONFIG_AUDIT_TIMEOUT_MAX_SECONDS = 120
MCP_CONFIG_AUDIT_MIN_EXPECTED_TOOLS = 1
MCP_CONFIG_AUDIT_MAX_EXPECTED_TOOLS = 10000
MCP_CONFIG_AUDIT_MAX_SERVER_NAME_CHARS = 256


# Set by the MCP adapter while a tool call is being served. The audit launches the configured server, so a
# caller that is itself an MCP client must not be able to turn it into arbitrary command execution.
LAUNCH_RESTRICTED: ContextVar[bool] = ContextVar("mcp_config_audit_launch_restricted", default=False)

EXPECTED_ARGS = ["-m", "wps_ai_agent_cli", "mcp-server"]
ALLOWED_ENV_KEYS = {"PYTHONPATH"}
_PACKAGE_INIT = Path(__file__).with_name("__init__.py").resolve()


def _is_python_interpreter(command: str) -> bool:
    name = Path(command).name.casefold()
    name = name[:-4] if name.endswith(".exe") else name
    return re.fullmatch(r"python(\d+(\.\d+)*)?", name) is not None


def _pythonpath_serves_this_package(pythonpath: Any, cwd: Path | None) -> bool:
    if not isinstance(pythonpath, str) or cwd is None:
        return False
    for entry in pythonpath.split(os.pathsep):
        if not entry:
            continue
        base = Path(entry) if Path(entry).is_absolute() else cwd / entry
        try:
            if (base / "wps_ai_agent_cli" / "__init__.py").resolve() == _PACKAGE_INIT:
                return True
        except OSError:
            continue
    return False


def _check(name: str, passed: bool, details: Any) -> dict[str, Any]:
    return {"name": name, "passed": passed, "details": details}


def _reject_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def _reject_nonstandard_constant(_value: str) -> None:
    raise ValueError("non-standard JSON numeric constant")


def _has_only_paired_surrogates(text: str) -> bool:
    index = 0
    while index < len(text):
        codepoint = ord(text[index])
        if 0xD800 <= codepoint <= 0xDBFF:
            if index + 1 >= len(text) or not 0xDC00 <= ord(text[index + 1]) <= 0xDFFF:
                return False
            index += 2
            continue
        if 0xDC00 <= codepoint <= 0xDFFF:
            return False
        index += 1
    return True


def _config_strings_have_valid_unicode(value: Any) -> bool:
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            if not _has_only_paired_surrogates(current):
                return False
        elif isinstance(current, dict):
            pending.extend(current.keys())
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return True


def _json_nesting_depth_within_limit(text: str, limit: int) -> bool:
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > limit:
                return False
        elif character in "]}" and depth:
            depth -= 1
    return True


def _load_config(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not path.exists():
        return None, [_check("config_exists", False, str(path))]
    try:
        if not path.is_file():
            return None, [
                _check("config_exists", True, str(path)),
                _check("config_is_file", False, None),
            ]
        with path.open("rb") as config_file:
            raw_config = config_file.read(MCP_CONFIG_MAX_BYTES + 1)
    except OSError:
        return None, [
            _check("config_exists", True, str(path)),
            _check("config_readable", False, None),
        ]

    checks = [_check("config_exists", True, str(path))]
    if len(raw_config) > MCP_CONFIG_MAX_BYTES:
        return None, checks + [
            _check(
                "config_size_within_limit", False,
                {"limit_bytes": MCP_CONFIG_MAX_BYTES, "observed_at_least": len(raw_config)},
            )
        ]
    checks.append(_check(
        "config_size_within_limit", True,
        {"size_bytes": len(raw_config), "limit_bytes": MCP_CONFIG_MAX_BYTES},
    ))
    try:
        config_text = raw_config.decode("utf-8")
    except UnicodeDecodeError:
        return None, checks + [_check("config_utf8_valid", False, None)]
    checks.append(_check("config_utf8_valid", True, None))
    if not _json_nesting_depth_within_limit(config_text, MCP_CONFIG_MAX_JSON_DEPTH):
        return None, checks + [
            _check("config_json_depth_within_limit", False, {"limit": MCP_CONFIG_MAX_JSON_DEPTH})
        ]
    checks.append(
        _check("config_json_depth_within_limit", True, {"limit": MCP_CONFIG_MAX_JSON_DEPTH})
    )
    try:
        config = json.loads(
            config_text,
            object_pairs_hook=_reject_duplicate_members,
            parse_constant=_reject_nonstandard_constant,
        )
    except (json.JSONDecodeError, ValueError, RecursionError):
        return None, checks + [_check("config_json_valid", False, None)]
    checks.append(_check("config_json_valid", True, str(path)))
    if not _config_strings_have_valid_unicode(config):
        return None, checks + [_check("config_unicode_valid", False, None)]
    checks.append(_check("config_unicode_valid", True, None))
    if not isinstance(config, dict):
        return None, checks + [_check("config_root_is_object", False, None)]
    checks.append(_check("config_root_is_object", True, None))
    return config, checks


def _resolve_command(command: str) -> str | None:
    command_path = Path(command)
    if command_path.is_absolute():
        return str(command_path) if command_path.exists() else None
    return shutil.which(command)


def _implementation_metadata_issue(server_info: dict[str, Any]) -> str | None:
    for field in ("title", "description"):
        if field in server_info and (
            not isinstance(server_info[field], str) or not server_info[field].strip()
        ):
            return f"serverInfo.{field}"

    if "websiteUrl" in server_info:
        website = server_info["websiteUrl"]
        if not isinstance(website, str):
            return "serverInfo.websiteUrl"
        try:
            parsed = urlsplit(website)
        except ValueError:
            return "serverInfo.websiteUrl"
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "serverInfo.websiteUrl"

    if "icons" in server_info:
        icons = server_info["icons"]
        if not isinstance(icons, list):
            return "serverInfo.icons"
        for index, icon in enumerate(icons):
            prefix = f"serverInfo.icons[{index}]"
            if not isinstance(icon, dict) or not isinstance(icon.get("src"), str):
                return f"{prefix}.src"
            src = icon["src"]
            try:
                parsed = urlsplit(src)
            except ValueError:
                return f"{prefix}.src"
            if parsed.scheme in {"http", "https"}:
                if not parsed.netloc:
                    return f"{prefix}.src"
            elif parsed.scheme == "data":
                if "," not in src:
                    return f"{prefix}.src"
            else:
                return f"{prefix}.src"
            if "mimeType" in icon and (
                not isinstance(icon["mimeType"], str) or not icon["mimeType"].strip()
            ):
                return f"{prefix}.mimeType"
            if "sizes" in icon and (
                not isinstance(icon["sizes"], list)
                or not all(isinstance(size, str) and size.strip() for size in icon["sizes"])
            ):
                return f"{prefix}.sizes"
            if "theme" in icon and (
                not isinstance(icon["theme"], str) or icon["theme"] not in {"light", "dark"}
            ):
                return f"{prefix}.theme"
    return None


def _tool_descriptor_issues(tools: list[Any], page_number: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    def add(index: int, path: str) -> None:
        if len(issues) < 20:
            issues.append({"page": page_number, "index": index, "path": path[:160]})

    def schema_paths(schema: Any, root_path: str) -> list[str]:
        found: list[str] = []
        pending = [(schema, root_path, 0)]
        allowed_types = {"array", "boolean", "integer", "null", "number", "object", "string"}
        maps = ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas")
        nested = (
            "additionalItems", "additionalProperties", "contains", "contentSchema", "else",
            "if", "items", "not", "propertyNames", "then", "unevaluatedItems", "unevaluatedProperties",
        )
        applicators = ("allOf", "anyOf", "oneOf", "prefixItems")
        number_keywords = (
            "maximum", "minimum", "exclusiveMaximum", "exclusiveMinimum", "multipleOf",
        )
        integer_keywords = (
            "maxContains", "maxItems", "maxLength", "maxProperties", "minContains",
            "minItems", "minLength", "minProperties",
        )
        string_keywords = (
            "$anchor", "$comment", "$dynamicRef", "$dynamicAnchor", "$id", "$ref", "$schema",
            "contentEncoding", "contentMediaType", "format", "pattern", "title", "description",
        )
        boolean_keywords = ("deprecated", "readOnly", "uniqueItems", "writeOnly")

        def issue(path: str) -> None:
            if len(found) < 20:
                found.append(path[:160])

        while pending and len(found) < 20:
            current, path, depth = pending.pop()
            if isinstance(current, bool):
                continue
            if not isinstance(current, dict):
                issue(path)
                continue
            if depth > 64:
                issue(path)
                continue

            value = current.get("type")
            if "type" in current:
                valid_type = (
                    value in allowed_types if isinstance(value, str)
                    else isinstance(value, list) and bool(value)
                    and all(isinstance(item, str) and item in allowed_types for item in value)
                    and len(set(value)) == len(value)
                )
                if not valid_type:
                    issue(f"{path}.type")

            if "required" in current:
                value = current["required"]
                if (not isinstance(value, list) or not all(isinstance(item, str) for item in value)
                        or len(set(value)) != len(value)):
                    issue(f"{path}.required")

            for keyword in maps:
                if keyword not in current:
                    continue
                value = current[keyword]
                if not isinstance(value, dict):
                    issue(f"{path}.{keyword}")
                    continue
                for name, child in value.items():
                    pending.append((child, f"{path}.{keyword}.{name}", depth + 1))

            for keyword in nested:
                if keyword in current:
                    pending.append((current[keyword], f"{path}.{keyword}", depth + 1))

            for keyword in applicators:
                if keyword not in current:
                    continue
                value = current[keyword]
                if not isinstance(value, list):
                    issue(f"{path}.{keyword}")
                    continue
                for item_index, child in enumerate(value):
                    pending.append((child, f"{path}.{keyword}[{item_index}]", depth + 1))

            if "enum" in current and (not isinstance(current["enum"], list) or not current["enum"]):
                issue(f"{path}.enum")
            for keyword in number_keywords:
                if keyword in current:
                    value = current[keyword]
                    if (isinstance(value, bool) or not isinstance(value, (int, float))
                            or isinstance(value, float) and not math.isfinite(value)
                            or keyword == "multipleOf" and value <= 0):
                        issue(f"{path}.{keyword}")
            for keyword in integer_keywords:
                if keyword in current:
                    value = current[keyword]
                    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                        issue(f"{path}.{keyword}")
            for keyword in string_keywords:
                if keyword in current and not isinstance(current[keyword], str):
                    issue(f"{path}.{keyword}")
            for keyword in boolean_keywords:
                if keyword in current and not isinstance(current[keyword], bool):
                    issue(f"{path}.{keyword}")
            if "dependentRequired" in current:
                value = current["dependentRequired"]
                if (not isinstance(value, dict) or any(
                    not isinstance(names, list) or not all(isinstance(name, str) for name in names)
                    or len(set(names)) != len(names)
                    for names in value.values()
                )):
                    issue(f"{path}.dependentRequired")
            if "examples" in current and not isinstance(current["examples"], list):
                issue(f"{path}.examples")
        return found

    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            add(index, "tool")
            continue
        for field in ("title", "description"):
            if field in tool and (not isinstance(tool[field], str) or not tool[field].strip()):
                add(index, field)
        input_schema = tool.get("inputSchema")
        if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
            add(index, "inputSchema.type")
        else:
            for path in schema_paths(input_schema, "inputSchema"):
                add(index, path)
        if "outputSchema" in tool:
            output_schema = tool["outputSchema"]
            if not isinstance(output_schema, dict) or output_schema.get("type") != "object":
                add(index, "outputSchema.type")
            else:
                for path in schema_paths(output_schema, "outputSchema"):
                    add(index, path)
        if "annotations" in tool and not isinstance(tool["annotations"], dict):
            add(index, "annotations")
    return issues


def audit_mcp_client_config(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    server_name: str = DEFAULT_SERVER_NAME,
    expected_min_tools: int = 1,
    timeout_seconds: int = 15,
    restrict_launch: bool | None = None,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    restricted = LAUNCH_RESTRICTED.get() if restrict_launch is None else restrict_launch
    path = Path(config_path)
    server_name_valid = (
        isinstance(server_name, str)
        and bool(server_name.strip())
        and len(server_name) <= MCP_CONFIG_AUDIT_MAX_SERVER_NAME_CHARS
    )
    server_name_check = _check(
        "server_name_within_limit",
        server_name_valid,
        {"maximum_characters": MCP_CONFIG_AUDIT_MAX_SERVER_NAME_CHARS},
    )
    if not server_name_valid:
        result = {
            "config_path": str(path),
            "server_name": None,
            "checks": [server_name_check],
            "smoke": None,
        }
        return False, result, [{"code": "MCP_CONFIG_AUDIT_FAILED", "message": "Server name must be nonempty and at most 256 characters."}]
    expected_tools_valid = (
        isinstance(expected_min_tools, int)
        and not isinstance(expected_min_tools, bool)
        and MCP_CONFIG_AUDIT_MIN_EXPECTED_TOOLS <= expected_min_tools <= MCP_CONFIG_AUDIT_MAX_EXPECTED_TOOLS
    )
    expected_tools_check = _check(
        "expected_min_tools_within_limit",
        expected_tools_valid,
        {
            "minimum": MCP_CONFIG_AUDIT_MIN_EXPECTED_TOOLS,
            "maximum": MCP_CONFIG_AUDIT_MAX_EXPECTED_TOOLS,
        },
    )
    if not expected_tools_valid:
        result = {
            "config_path": str(path),
            "server_name": server_name,
            "checks": [server_name_check, expected_tools_check],
            "smoke": None,
        }
        return False, result, [{"code": "MCP_CONFIG_AUDIT_FAILED", "message": "Expected tool count must be between 1 and 10000."}]
    timeout_valid = (
        isinstance(timeout_seconds, int)
        and not isinstance(timeout_seconds, bool)
        and MCP_CONFIG_AUDIT_TIMEOUT_MIN_SECONDS <= timeout_seconds <= MCP_CONFIG_AUDIT_TIMEOUT_MAX_SECONDS
    )
    timeout_check = _check(
        "timeout_seconds_within_limit",
        timeout_valid,
        {
            "minimum": MCP_CONFIG_AUDIT_TIMEOUT_MIN_SECONDS,
            "maximum": MCP_CONFIG_AUDIT_TIMEOUT_MAX_SECONDS,
        },
    )
    if not timeout_valid:
        result = {
            "config_path": str(path),
            "server_name": server_name,
            "checks": [server_name_check, expected_tools_check, timeout_check],
            "smoke": None,
        }
        return False, result, [{"code": "MCP_CONFIG_AUDIT_FAILED", "message": "Timeout must be between 1 and 120 seconds."}]
    config, checks = _load_config(path)
    checks[0:0] = [server_name_check, expected_tools_check, timeout_check]
    if config is None:
        result = {
            "config_path": str(path),
            "server_name": server_name,
            "checks": checks,
            "smoke": None,
        }
        return False, result, [{"code": "MCP_CONFIG_AUDIT_FAILED", "message": "Config could not be loaded."}]

    servers = config.get("mcpServers")
    if not isinstance(servers, dict):
        checks.append(_check("mcp_servers_is_object", False, None))
        result = {
            "config_path": str(path),
            "server_name": server_name,
            "checks": checks,
            "smoke": None,
        }
        return False, result, [{"code": "MCP_CONFIG_AUDIT_FAILED", "message": "mcpServers must be an object."}]
    checks.append(_check("mcp_servers_is_object", True, None))
    server = servers.get(server_name)
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
    command_valid = isinstance(command, str) and bool(command.strip()) and "\0" not in command
    args_valid = isinstance(args, list) and all(isinstance(arg, str) and "\0" not in arg for arg in args)
    env_valid = isinstance(env_overrides, dict) and all(
        isinstance(key, str) and bool(key) and "=" not in key and "\0" not in key
        and isinstance(value, str) and "\0" not in value
        for key, value in env_overrides.items()
    )
    cwd_path = Path(cwd) if isinstance(cwd, str) and cwd.strip() else None
    try:
        cwd_ok = bool(cwd_path and cwd_path.exists())
    except OSError:
        cwd_ok = False
    checks.append(_check(
        "cwd_exists", cwd_ok,
        cwd[:256] if isinstance(cwd, str) else None,
    ))
    command_resolved = _resolve_command(command) if command_valid else None
    checks.append(_check(
        "command_resolves", command_resolved is not None,
        command[:256] if isinstance(command, str) else None,
    ))
    checks.append(_check("command_characters_valid", command_valid, "NUL-free nonempty command required."))
    checks.append(_check("args_are_strings", args_valid, "Arguments must be strings without NUL."))
    checks.append(_check(
        "args_include_mcp_server", args_valid and "mcp-server" in args,
        {"argument_count": len(args) if isinstance(args, list) else None},
    ))
    checks.append(_check(
        "env_overrides_are_strings", env_valid,
        "Environment must map valid string keys to NUL-free string values.",
    ))
    checks.append(
        _check(
            "env_pythonpath_present",
            isinstance(env_overrides, dict) and bool(env_overrides.get("PYTHONPATH")),
            bool(env_overrides.get("PYTHONPATH")) if isinstance(env_overrides, dict) else False,
        )
    )

    # When the audit is reached through an MCP tool call only this package's own
    # `python -m wps_ai_agent_cli mcp-server` launch line may be executed; anything else in a config
    # written by the caller would be arbitrary code execution. Direct CLI use audits any launch line.
    safe_launch = not restricted or (
        isinstance(command, str)
        and _is_python_interpreter(command)
        and args == EXPECTED_ARGS
        and isinstance(env_overrides, dict)
        and set(env_overrides) <= ALLOWED_ENV_KEYS
        and _pythonpath_serves_this_package(env_overrides.get("PYTHONPATH"), cwd_path)
    )
    checks.append(
        _check(
            "launch_line_is_this_package",
            safe_launch,
            {
                "enforced": restricted,
                "requires": "a python interpreter, args exactly -m wps_ai_agent_cli mcp-server, env limited to PYTHONPATH that resolves to this package",
                "command": command,
                "argument_count": len(args) if isinstance(args, list) else None,
                "env_keys": sorted(env_overrides) if isinstance(env_overrides, dict) else None,
            },
        )
    )

    smoke: dict[str, Any] | None = None
    if cwd_ok and command_resolved and args_valid and env_valid and safe_launch:
        base_command = [command_resolved, *args]
        env = os.environ.copy()
        env.update(env_overrides)
        page_count = 0
        descriptor_issues: list[dict[str, Any]] = []
        descriptor_issue_count = 0
        process: subprocess.Popen[str] | None = None
        stdout_thread: Thread | None = None
        stderr_thread: Thread | None = None
        replies: Queue[Any] = Queue(maxsize=MCP_AUDIT_STDOUT_QUEUE_SIZE)
        stop_readers = Event()
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

                def enqueue(item: Any) -> bool:
                    while not stop_readers.is_set():
                        try:
                            replies.put(item, timeout=0.1)
                            return True
                        except Full:
                            continue
                    return False

                while not stop_readers.is_set():
                    try:
                        output_line = process.stdout.readline(MCP_AUDIT_MAX_STDOUT_LINE_CHARS + 1)
                    except UnicodeDecodeError:
                        enqueue(ValueError("Configured server stdout was not valid UTF-8."))
                        return
                    if not output_line:
                        enqueue(None)
                        return
                    if len(output_line) > MCP_AUDIT_MAX_STDOUT_LINE_CHARS:
                        while output_line and not output_line.endswith("\n"):
                            output_line = process.stdout.readline(MCP_AUDIT_READ_CHUNK_CHARS)
                        enqueue(ValueError("Configured server stdout line exceeded the audit limit."))
                        return
                    if not enqueue(output_line):
                        return

            def collect_stderr() -> None:
                nonlocal stderr_size
                assert process is not None and process.stderr is not None
                while True:
                    error_chunk = process.stderr.read(MCP_AUDIT_READ_CHUNK_CHARS)
                    if not error_chunk:
                        return
                    remaining = 8192 - stderr_size
                    if remaining > 0:
                        chunk = error_chunk[:remaining]
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
                if isinstance(raw_response, BaseException):
                    raise raw_response
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
                    or not isinstance(initialize.get("capabilities"), dict)):
                raise ValueError("Configured server returned an invalid initialize result.")
            server_info = initialize.get("serverInfo")
            capabilities = initialize["capabilities"]
            tools_capability = capabilities.get("tools")
            if (not isinstance(server_info, dict)
                    or not isinstance(server_info.get("name"), str) or not server_info["name"].strip()
                    or not isinstance(server_info.get("version"), str) or not server_info["version"].strip()
                    or not isinstance(tools_capability, dict)
                    or isinstance(tools_capability, dict) and "listChanged" in tools_capability
                    and not isinstance(tools_capability["listChanged"], bool)):
                raise ValueError("Configured server returned invalid initialize metadata.")
            optional_metadata_issue = _implementation_metadata_issue(server_info)
            if optional_metadata_issue is not None:
                raise ValueError(f"Configured server returned invalid metadata at {optional_metadata_issue}.")

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
        except (subprocess.SubprocessError, OSError, json.JSONDecodeError, RecursionError, ValueError) as exc:
            smoke = {"error": str(exc), "page_count": page_count, "stderr": "".join(stderr_chunks).strip()}
            checks.append(_check("configured_tools_list_smoke", False, smoke))
        finally:
            stop_readers.set()
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
        checks.append(_check(
            "configured_tools_list_smoke", False,
            "Skipped because command, cwd, args, env or launch-line checks failed; nothing was executed.",
        ))

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
