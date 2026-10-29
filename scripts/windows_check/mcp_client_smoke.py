"""Start the wps-agent MCP server as Claude Desktop would, then read and write a workbook through it (P14-005).

    python scripts/windows_check/mcp_client_smoke.py --out DIR [--config PATH] [--name wps-agent]
        [--timeout 180] [--inherit-env] [--keep-backup]

The installer writes a ``wps-agent`` entry into Claude Desktop's config. This reads that entry and starts its command
with its arguments from a folder that is not the data folder. Like Claude Desktop (the MCP SDK's stdio transport), it
passes only the SDK's default set of environment variables plus the entry's ``env``; ``--inherit-env`` passes this
shell's whole environment instead. Over stdio it then:

1. sends ``initialize`` and lists every ``tools/list`` page (the server's version, protocol version and tools);
2. copies ``fixtures/fidelity/book.xlsx`` into a new folder and registers it;
3. reads ``sales_gbk!A1:F3``, writes one cell (``sales_gbk!F2``), and reads it back;
4. lists the document's backups, and checks the backup file is under ``WPS_AGENT_WORKSPACE`` and that nothing was
   written into the folder the server was started in.

Afterwards it deletes that document's backup folder from the data folder (not with ``--keep-backup``). The
registration stays in the data folder's registry, pointing at the deleted copy: no tool removes one.

It writes DIR/mcp-client-smoke.json and DIR/MCP_CLIENT_SMOKE.md, also when a step fails or the server cannot be
started, and exits 1 when a step fails. The report records the entry's command, arguments and env names, not its
env values. Only the standard library is used, so any Python 3.10+ runs it.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "fidelity" / "book.xlsx"
SHEET = "sales_gbk"
WRITE_CELL = "F2"
WRITE_VALUE = "wps-agent MCP smoke"
PROTOCOL_VERSION = "2025-11-25"
MAX_TOOL_PAGES = 100
# The variables the MCP SDK's stdio transport passes to a server when the client gives no full environment.
SDK_DEFAULT_ENV = {
    "win32": (
        "APPDATA",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "PATH",
        "PROCESSOR_ARCHITECTURE",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "USERNAME",
        "USERPROFILE",
        "PROGRAMFILES",
    ),
    "posix": ("HOME", "LOGNAME", "PATH", "SHELL", "TERM", "USER"),
}
DOCUMENT_ID = re.compile(r"^doc_[0-9a-f]+$")


def _default_config() -> Path:
    """Where Claude Desktop keeps its config (as wps_ai_agent_cli.client_config.claude_desktop_config_path)."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def server_env(entry_env: dict[str, Any], inherit: bool) -> dict[str, str]:
    """The server's environment: the SDK's default variables (or all of this shell's) plus the entry's env."""
    if inherit:
        base = dict(os.environ)
    else:
        names = SDK_DEFAULT_ENV["win32" if sys.platform == "win32" else "posix"]
        base = {
            name: os.environ[name] for name in names if os.environ.get(name) and not os.environ[name].startswith("()")
        }
    return {**base, **{str(key): str(value) for key, value in entry_env.items()}}


def backup_under_workspace(backup_path: str, workspace: str) -> bool:
    """Whether a backup path the server reported lies in the workspace; relative paths are relative to it."""
    root = Path(workspace).expanduser().resolve()
    path = Path(backup_path)
    if not path.is_absolute():
        path = root / path
    return path.resolve().is_relative_to(root)


class Server:
    """A stdio MCP server: one JSON message per line each way, each answer awaited with a timeout."""

    def __init__(self, argv: list[str], env: dict[str, str], cwd: Path) -> None:
        self.process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.stderr: list[str] = []
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._readers = [
            threading.Thread(target=self._drain_stderr, daemon=True),
            threading.Thread(target=self._read_stdout, daemon=True),
        ]
        for reader in self._readers:
            reader.start()
        self._next_id = 0

    def _drain_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self.stderr.append(line.rstrip("\n"))

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def request(self, method: str, params: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        self._next_id += 1
        request_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"no answer to {method} in {timeout:g} s")
            try:
                line = self._lines.get(timeout=remaining)
            except queue.Empty:
                continue
            if line is None:
                raise RuntimeError(f"the server exited during {method}: {' | '.join(self.stderr[-5:])}")
            try:
                message = json.loads(line)
            except ValueError:
                raise RuntimeError(f"the server wrote a line that is not JSON: {line[:200]!r}") from None
            # A request from the server (it has a method) can carry the same id as ours: it is not the answer.
            if isinstance(message, dict) and "method" not in message and message.get("id") == request_id:
                return message

    def call(self, tool: str, arguments: dict[str, Any], timeout: float) -> tuple[bool, dict[str, Any], list[Any]]:
        """tools/call; returns (ok, data, errors) from the tool's structured result."""
        message = self.request("tools/call", {"name": tool, "arguments": arguments}, timeout)
        if "error" in message:
            return False, {}, [message["error"]]
        result = message.get("result") or {}
        structured = result.get("structuredContent") or {}
        response = (structured.get("mcp_call") or {}).get("response") or {}
        return not result.get("isError"), response.get("data") or {}, structured.get("errors") or []

    def _send(self, message: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        try:
            self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            self.process.stdin.flush()
        except OSError as exc:
            raise RuntimeError(f"could not write to the server ({exc}): {' | '.join(self.stderr[-5:])}") from None

    def close(self) -> None:
        try:
            if self.process.stdin:
                self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.kill()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                return
        for reader in self._readers:
            reader.join(timeout=5)
        for stream in (self.process.stdout, self.process.stderr):
            if stream is not None:
                stream.close()


def _cell(data: dict[str, Any], row: int, column: int) -> Any:
    values = data.get("values")
    if isinstance(values, list) and len(values) > row and isinstance(values[row], list) and len(values[row]) > column:
        return values[row][column]
    return None


def run(
    config_path: Path,
    name: str,
    work: Path,
    timeout: float = 180,
    inherit_env: bool = False,
    keep_backup: bool = False,
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []

    def step(label: str, ok: Any, detail: Any = None) -> bool:
        steps.append({"step": label, "ok": bool(ok), "detail": detail})
        print(f"{'ok' if ok else 'FAIL'}: {label}" + (f" ({detail})" if detail not in (None, "") else ""))
        return bool(ok)

    report: dict[str, Any] = {
        "config": str(config_path),
        "name": name,
        "environment": "inherited" if inherit_env else "MCP SDK default",
        "steps": steps,
    }
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        entry = config["mcpServers"][name]
        command = entry["command"]
        args = list(entry.get("args") or [])
        entry_env = entry.get("env") or {}
        if not isinstance(command, str) or not isinstance(entry_env, dict):
            raise TypeError("command must be a string and env an object")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        step("read the client config", False, f"{type(exc).__name__}: {exc}")
        return report
    report["entry"] = {"command": command, "args": args, "env_names": sorted(entry_env)}
    step("read the client config", True, command)
    workspace = entry_env.get("WPS_AGENT_WORKSPACE")
    if not step("the entry sets WPS_AGENT_WORKSPACE", workspace, workspace):
        return report
    start_dir = work / "client-start-dir"
    documents = work / "documents"
    start_dir.mkdir()
    documents.mkdir()
    document = documents / "book.xlsx"
    shutil.copyfile(FIXTURE, document)
    try:
        server = Server([command, *args], server_env(entry_env, inherit_env), start_dir)
    except OSError as exc:
        step("start the server", False, f"{type(exc).__name__}: {exc}")
        return report
    document_id = None
    try:
        init = server.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "wps-agent-mcp-client-smoke", "version": "1"},
            },
            timeout,
        )
        result = init.get("result") or {}
        info = result.get("serverInfo") or {}
        report["server_info"] = info
        report["protocol_version"] = {"requested": PROTOCOL_VERSION, "answered": result.get("protocolVersion")}
        if not step("initialize", "result" in init, {**info, "protocolVersion": result.get("protocolVersion")}):
            return report
        server.notify("notifications/initialized")
        tools: list[str] = []
        cursor = None
        seen: set[str] = set()
        for _page in range(MAX_TOOL_PAGES):
            page = server.request("tools/list", {"cursor": cursor} if cursor else {}, timeout).get("result") or {}
            tools += [tool.get("name") for tool in page.get("tools", []) if isinstance(tool, dict)]
            cursor = page.get("nextCursor")
            if not cursor or cursor in seen:
                break
            seen.add(cursor)
        report["tool_count"] = len(tools)
        needed = ["wps_agent_register_document", "wps_agent_spreadsheet_read", "wps_agent_spreadsheet_write"]
        missing = [tool for tool in needed if tool not in tools]
        problems = [f"missing {missing}"] if missing else []
        if cursor:
            problems.append("tools/list kept returning a next page")
        if not step("tools/list", tools and not problems, ", ".join([f"{len(tools)} tools", *problems])):
            return report
        ok, data, errors = server.call(
            "wps_agent_register_document", {"component": "spreadsheets", "path": str(document)}, timeout
        )
        document_id = (data.get("document") or {}).get("document_id")
        if not step("register the workbook", ok and document_id, document_id or errors):
            return report
        cells = "A1:F3"
        ok, data, errors = server.call(
            "wps_agent_spreadsheet_read", {"document_id": document_id, "sheet": SHEET, "range": cells}, timeout
        )
        report["read"] = data.get("values")
        if not step(f"read {SHEET}!{cells}", ok and _cell(data, 0, 0) == "地区", data.get("values") or errors):
            return report
        ok, data, errors = server.call(
            "wps_agent_spreadsheet_write",
            {
                "document_id": document_id,
                "sheet": SHEET,
                "range": WRITE_CELL,
                "values_json": json.dumps([[WRITE_VALUE]]),
                "request_id": f"mcp-client-smoke-{uuid.uuid4().hex[:12]}",
            },
            timeout,
        )
        report["write"] = data
        if not step(f"write {SHEET}!{WRITE_CELL}", ok, errors or None):
            return report
        ok, data, errors = server.call(
            "wps_agent_spreadsheet_read", {"document_id": document_id, "sheet": SHEET, "range": WRITE_CELL}, timeout
        )
        step("read the written cell back", ok and _cell(data, 0, 0) == WRITE_VALUE, data.get("values") or errors)
        ok, data, errors = server.call("wps_agent_list_backups", {"document_id": document_id}, timeout)
        backups = [item for item in data.get("backups") or [] if isinstance(item, dict)]
        report["backups"] = backups
        step("the write left a backup", ok and backups, len(backups) if ok else errors)
        paths = [str(item.get("backup_path") or "") for item in backups]
        under = [path for path in paths if path and backup_under_workspace(path, workspace)]
        step("the backup is under WPS_AGENT_WORKSPACE", under, under[0] if under else paths)
        stray = sorted(str(p.relative_to(start_dir)) for p in start_dir.rglob("*"))
        step("nothing was written where the server was started", not stray, stray or None)
    except Exception as exc:  # any failure is a failed step with a report, not a traceback
        step("talk to the server", False, f"{type(exc).__name__}: {exc}")
    finally:
        server.close()
        report["server_stderr_tail"] = server.stderr[-20:]
        if document_id and not keep_backup:
            report["backup_folder_removed"] = _remove_backup_folder(workspace, document_id)
    return report


def _remove_backup_folder(workspace: str, document_id: str) -> str | None:
    """Delete the backups of the workbook this run registered; nothing else in the data folder is touched."""
    if not DOCUMENT_ID.match(str(document_id)):
        return None
    folder = Path(workspace).expanduser() / ".wps-agent" / "backups" / document_id
    if not folder.is_dir():
        return None
    shutil.rmtree(folder, ignore_errors=True)
    return str(folder)


def write_report(out: Path, report: dict[str, Any]) -> bool:
    passed = bool(report["steps"]) and all(item["ok"] for item in report["steps"])
    report["passed"] = passed
    (out / "mcp-client-smoke.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    protocol = report.get("protocol_version") or {}
    lines = [
        "# MCP client smoke",
        "",
        f"- Config: `{report['config']}`, server `{report['name']}`",
        f"- Server: {report.get('server_info')}; protocol {protocol.get('answered')} "
        f"(asked for {protocol.get('requested')})",
        f"- Server environment: {report['environment']} variables plus the entry's env "
        f"({', '.join((report.get('entry') or {}).get('env_names', [])) or 'none'})",
        f"- Python running this script: {sys.version.split()[0]}",
        "- Written by `scripts/windows_check/mcp_client_smoke.py`; nothing in this file was typed by hand.",
        "",
        f"**{'Passed' if passed else 'Failed'}.**",
        "",
        "| Step | Result | Detail |",
        "| --- | --- | --- |",
    ]
    for item in report["steps"]:
        detail = json.dumps(item["detail"], ensure_ascii=False, default=str) if item["detail"] is not None else ""
        lines.append(f"| {item['step']} | {'ok' if item['ok'] else 'FAIL'} | {detail.replace('|', '/')} |")
    if report.get("backup_folder_removed"):
        lines += ["", f"Removed this run's backup folder `{report['backup_folder_removed']}`."]
    (out / "MCP_CLIENT_SMOKE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return passed


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=None, help="Claude Desktop config (default: its usual place)")
    parser.add_argument("--name", default="wps-agent", help="server name under mcpServers")
    parser.add_argument("--timeout", type=float, default=180, help="seconds to wait for each answer (default 180)")
    parser.add_argument("--inherit-env", action="store_true", help="pass this shell's whole environment")
    parser.add_argument("--keep-backup", action="store_true", help="leave this run's backup in the data folder")
    args = parser.parse_args(argv)
    config = args.config or _default_config()
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wps-agent-mcp-smoke-", ignore_cleanup_errors=True) as tmp:
        report = run(config, args.name, Path(tmp), args.timeout, args.inherit_env, args.keep_backup)
        # Written before the temporary folder goes, so a file WPS still holds there cannot lose the report.
        passed = write_report(args.out, report)
    print(f"{'passed' if passed else 'FAILED'}; results: {args.out / 'MCP_CLIENT_SMOKE.md'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
