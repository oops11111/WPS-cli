"""Start the wps-agent MCP server as Claude Desktop would, then read and write a workbook through it (P14-005).

    python scripts/windows_check/mcp_client_smoke.py --out DIR [--config PATH] [--name wps-agent]

The installer writes a ``wps-agent`` entry into Claude Desktop's config. This reads that entry, starts its command
with its arguments and environment (as Claude Desktop does: from a folder that is not the data folder), and over
stdio:

1. ``initialize`` and ``tools/list`` (the server's version and its tools);
2. copies ``fixtures/fidelity/book.xlsx`` into a new folder and registers it;
3. reads ``sales_gbk!A1:F3``, writes one cell (``sales_gbk!F2``), and reads it back;
4. lists the document's backups, and checks the backup file is under ``WPS_AGENT_WORKSPACE`` and that nothing was
   written into the folder the server was started in.

It writes DIR/mcp-client-smoke.json and DIR/MCP_CLIENT_SMOKE.md, and exits 1 when a step fails. Only the standard
library is used, so any Python 3.10+ runs it.
"""

from __future__ import annotations

import argparse
import json
import os
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


def _default_config() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Claude" / "claude_desktop_config.json"


class Server:
    """A stdio MCP server: one JSON message per line each way."""

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
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self._next_id = 0

    def _drain_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self.stderr.append(line.rstrip("\n"))

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def request(self, method: str, params: dict[str, Any] | None = None, timeout: float = 120) -> dict[str, Any]:
        self._next_id += 1
        request_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        deadline = time.monotonic() + timeout
        assert self.process.stdout is not None
        while time.monotonic() < deadline:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError(f"the server exited during {method}: {' | '.join(self.stderr[-5:])}")
            message = json.loads(line)
            if message.get("id") == request_id:
                return message
        raise TimeoutError(f"no answer to {method} in {timeout} s")

    def call(self, tool: str, arguments: dict[str, Any]) -> tuple[bool, dict[str, Any], list[Any]]:
        """tools/call; returns (ok, data, errors) from the tool's structured result."""
        message = self.request("tools/call", {"name": tool, "arguments": arguments})
        if "error" in message:
            return False, {}, [message["error"]]
        result = message["result"]
        structured = result.get("structuredContent") or {}
        response = (structured.get("mcp_call") or {}).get("response") or {}
        return not result.get("isError"), response.get("data") or {}, structured.get("errors") or []

    def _send(self, message: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def close(self) -> None:
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.kill()


def _cell(data: dict[str, Any], row: int, column: int) -> Any:
    values = data.get("values")
    if isinstance(values, list) and len(values) > row and isinstance(values[row], list) and len(values[row]) > column:
        return values[row][column]
    return None


def run(config_path: Path, name: str, work: Path) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []

    def step(label: str, ok: bool, detail: Any = None) -> bool:
        steps.append({"step": label, "ok": bool(ok), "detail": detail})
        print(f"{'ok' if ok else 'FAIL'}: {label}" + (f" ({detail})" if detail not in (None, "") else ""))
        return bool(ok)

    report: dict[str, Any] = {"config": str(config_path), "name": name, "steps": steps}
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        entry = config["mcpServers"][name]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        step("read the client config", False, f"{type(exc).__name__}: {exc}")
        return report
    env_extra = entry.get("env") or {}
    report["entry"] = entry
    step("read the client config", True, entry.get("command"))
    workspace = env_extra.get("WPS_AGENT_WORKSPACE")
    if not step("the entry sets WPS_AGENT_WORKSPACE", bool(workspace), workspace):
        return report
    start_dir = work / "client-start-dir"
    documents = work / "documents"
    start_dir.mkdir()
    documents.mkdir()
    document = documents / "book.xlsx"
    shutil.copyfile(FIXTURE, document)
    env = {**os.environ, **{str(k): str(v) for k, v in env_extra.items()}}
    server = Server([entry["command"], *entry.get("args", [])], env, start_dir)
    try:
        init = server.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "wps-agent-mcp-client-smoke", "version": "1"},
            },
        )
        info = (init.get("result") or {}).get("serverInfo") or {}
        report["server_info"] = info
        if not step("initialize", "result" in init, info):
            return report
        server.notify("notifications/initialized")
        tools: list[str] = []
        cursor = None
        while True:
            page = server.request("tools/list", {"cursor": cursor} if cursor else {}).get("result") or {}
            tools += [tool["name"] for tool in page.get("tools", [])]
            cursor = page.get("nextCursor")
            if not cursor:
                break
        report["tool_count"] = len(tools)
        needed = ["wps_agent_register_document", "wps_agent_spreadsheet_read", "wps_agent_spreadsheet_write"]
        missing = [tool for tool in needed if tool not in tools]
        if not step(
            "tools/list", tools and not missing, f"{len(tools)} tools" + (f", missing {missing}" if missing else "")
        ):
            return report
        ok, data, errors = server.call(
            "wps_agent_register_document", {"component": "spreadsheets", "path": str(document)}
        )
        document_id = (data.get("document") or {}).get("document_id")
        if not step("register the workbook", ok and document_id, document_id or errors):
            return report
        cells = "A1:F3"
        ok, data, errors = server.call(
            "wps_agent_spreadsheet_read", {"document_id": document_id, "sheet": SHEET, "range": cells}
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
        )
        report["write"] = data
        if not step(f"write {SHEET}!{WRITE_CELL}", ok, errors or None):
            return report
        ok, data, errors = server.call(
            "wps_agent_spreadsheet_read", {"document_id": document_id, "sheet": SHEET, "range": WRITE_CELL}
        )
        step("read the written cell back", ok and _cell(data, 0, 0) == WRITE_VALUE, data.get("values") or errors)
        ok, data, errors = server.call("wps_agent_list_backups", {"document_id": document_id})
        backups = data.get("backups") or []
        report["backups"] = backups
        step("the write left a backup", ok and bool(backups), len(backups) if ok else errors)
        paths = [str(item.get("backup_path") or item.get("path") or "") for item in backups if isinstance(item, dict)]
        under = [p for p in paths if p and Path(p).resolve().is_relative_to(Path(workspace).expanduser().resolve())]
        step("the backup is under WPS_AGENT_WORKSPACE", bool(under), under[0] if under else paths)
        stray = sorted(str(p.relative_to(start_dir)) for p in start_dir.rglob("*"))
        step("nothing was written where the server was started", not stray, stray or None)
    except (RuntimeError, TimeoutError, ValueError, KeyError) as exc:
        step("talk to the server", False, f"{type(exc).__name__}: {exc}")
    finally:
        server.close()
        report["server_stderr_tail"] = server.stderr[-20:]
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=None, help="Claude Desktop config (default: its usual place)")
    parser.add_argument("--name", default="wps-agent", help="server name under mcpServers")
    args = parser.parse_args()
    config = args.config or _default_config()
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wps-agent-mcp-smoke-") as tmp:
        report = run(config, args.name, Path(tmp))
    passed = bool(report["steps"]) and all(item["ok"] for item in report["steps"])
    report["passed"] = passed
    (args.out / "mcp-client-smoke.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    lines = [
        "# MCP client smoke",
        "",
        f"- Config: `{report['config']}`, server `{report['name']}`",
        f"- Server: {report.get('server_info')}",
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
    (args.out / "MCP_CLIENT_SMOKE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{'passed' if passed else 'FAILED'}; results: {args.out / 'MCP_CLIENT_SMOKE.md'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
