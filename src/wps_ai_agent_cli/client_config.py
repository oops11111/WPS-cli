"""MCP client configuration for an installed wps-agent (P14-002): what to add to Claude Desktop, Claude Code or any
other MCP client so that it starts ``wps-agent mcp-server``.

    python -m wps_ai_agent_cli.client_config --client claude-desktop --command C:\\...\\wps-agent.exe [--write]
    python -m wps_ai_agent_cli.client_config --client claude-code --command C:\\...\\wps-agent.exe
    python -m wps_ai_agent_cli.client_config --client json --command C:\\...\\wps-agent.exe

The installer (``scripts/install/install.ps1``) runs it after installing. Without ``--write`` nothing is changed: the
entry is printed. With ``--write`` (Claude Desktop only) the server is added to the client's config file, which is
first copied to ``<name>.bak-<time>.json``; other servers in the file are kept. This is a module, not a CLI command, so
the public CLI and MCP interface do not change.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

SERVER_NAME = "wps-agent"


def server_entry(command: str, env: dict[str, str] | None = None) -> dict[str, Any]:
    """The ``mcpServers`` entry that starts the stdio MCP server."""
    entry: dict[str, Any] = {"command": command, "args": ["mcp-server"]}
    if env:
        entry["env"] = dict(sorted(env.items()))
    return entry


def claude_desktop_config_path() -> Path:
    """Where Claude Desktop keeps its config on this system."""
    if sys.platform == "win32":
        return (
            Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            / "Claude"
            / "claude_desktop_config.json"
        )
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def write_claude_desktop(path: Path, name: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Add or replace one server in a Claude Desktop config, keeping the rest; back the file up first."""
    config: dict[str, Any] = {}
    backup = None
    if path.is_file():
        text = path.read_text(encoding="utf-8-sig")
        config = json.loads(text) if text.strip() else {}
        if not isinstance(config, dict):
            raise ValueError(f"{path} does not hold a JSON object")
        backup = path.with_name(f"{path.stem}.bak-{time.strftime('%Y%m%dT%H%M%S')}{path.suffix}")
        shutil.copyfile(path, backup)
    servers = config.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError(f"mcpServers in {path} is not a JSON object")
    replaced = name in servers
    servers[name] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(path), "backup": str(backup) if backup else None, "replaced": replaced}


def claude_code_command(name: str, entry: dict[str, Any]) -> list[str]:
    """The ``claude mcp add`` command that registers the server for the current user in Claude Code."""
    argv = ["claude", "mcp", "add", "--scope", "user"]
    for key, value in entry.get("env", {}).items():
        argv += ["-e", f"{key}={value}"]
    return argv + [name, "--", entry["command"], *entry["args"]]


def _env_pairs(values: list[str]) -> dict[str, str]:
    pairs = {}
    for value in values:
        key, sep, rest = value.partition("=")
        if not sep or not key:
            raise argparse.ArgumentTypeError(f"--env expects KEY=VALUE, got {value!r}")
        pairs[key] = rest
    return pairs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--client", choices=["claude-desktop", "claude-code", "json"], default="json")
    parser.add_argument("--command", required=True, help="Path to the installed wps-agent executable.")
    parser.add_argument("--env", action="append", default=[], help="KEY=VALUE for the server's environment.")
    parser.add_argument("--name", default=SERVER_NAME, help="Server name in the client (default wps-agent).")
    parser.add_argument("--write", action="store_true", help="Claude Desktop: write the entry into its config.")
    parser.add_argument("--config-path", type=Path, help="Claude Desktop config file (default: its usual place).")
    args = parser.parse_args(argv)
    entry = server_entry(args.command, _env_pairs(args.env))
    result: dict[str, Any] = {"client": args.client, "name": args.name}
    if args.client == "claude-desktop":
        path = args.config_path or claude_desktop_config_path()
        result["config_path"] = str(path)
        if args.write:
            try:
                result["written"] = write_claude_desktop(path, args.name, entry)
            except (OSError, ValueError) as exc:
                result["error"] = str(exc)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 1
        result["entry"] = {"mcpServers": {args.name: entry}}
    elif args.client == "claude-code":
        result["command"] = claude_code_command(args.name, entry)
    else:
        result["entry"] = {"mcpServers": {args.name: entry}}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
