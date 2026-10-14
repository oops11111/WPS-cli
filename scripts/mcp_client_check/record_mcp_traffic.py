"""Record the stdio traffic between an MCP client and the wps-agent server (P4-008).

The client starts this script instead of the server. The script starts the server, passes every line
through unchanged in both directions, and appends each line to a JSONL log:

    python scripts/mcp_client_check/record_mcp_traffic.py --log traffic.jsonl -- python -m wps_ai_agent_cli mcp-server

Afterwards, summarize what the client and the server exchanged:

    python scripts/mcp_client_check/record_mcp_traffic.py --summarize traffic.jsonl

The summary reports the client name and version, the requested and negotiated protocol versions, every
tools/list page with its cursor, the number of tools in the last complete listing, and every tools/call
with its result.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, BinaryIO


def _record(log: BinaryIO, lock: threading.Lock, direction: str, line: bytes) -> None:
    text = line.decode("utf-8", errors="replace").rstrip("\r\n")
    entry = {"t": round(time.time(), 3), "dir": direction, "line": text}
    with lock:
        log.write((json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8"))
        log.flush()


def _pump(source: BinaryIO, sink: BinaryIO, log: BinaryIO, lock: threading.Lock, direction: str) -> None:
    try:
        for line in iter(source.readline, b""):
            _record(log, lock, direction, line)
            sink.write(line)
            sink.flush()
    except (BrokenPipeError, OSError, ValueError):
        pass
    finally:
        try:
            sink.close()
        except OSError:
            pass


def relay(command: list[str], log_path: Path) -> int:
    lock = threading.Lock()
    with log_path.open("ab") as log:
        server = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        to_server = threading.Thread(
            target=_pump, args=(sys.stdin.buffer, server.stdin, log, lock, "client->server"), daemon=True
        )
        to_client = threading.Thread(
            target=_pump, args=(server.stdout, sys.stdout.buffer, log, lock, "server->client"), daemon=True
        )
        to_server.start()
        to_client.start()
        code = server.wait()
        to_client.join(timeout=5)
    return code


def _messages(log_path: Path) -> list[tuple[str, Any]]:
    messages = []
    for raw in log_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        entry = json.loads(raw)
        try:
            payload = json.loads(entry["line"])
        except json.JSONDecodeError:
            continue
        for message in payload if isinstance(payload, list) else [payload]:
            if isinstance(message, dict):
                messages.append((entry["dir"], message))
    return messages


def summarize(log_path: Path) -> dict[str, Any]:
    requests: dict[Any, dict[str, Any]] = {}
    responses: dict[Any, dict[str, Any]] = {}
    order: list[Any] = []
    initialized_notification = False
    for direction, message in _messages(log_path):
        if direction == "client->server" and "method" in message:
            if "id" in message:
                requests[message["id"]] = message
                order.append(message["id"])
            elif message["method"] == "notifications/initialized":
                initialized_notification = True
        elif direction == "server->client" and "id" in message:
            responses[message["id"]] = message

    summary: dict[str, Any] = {
        "client_info": None,
        "requested_protocol": None,
        "negotiated_protocol": None,
        "server_info": None,
        "initialized_notification": initialized_notification,
        "tools_list_pages": [],
        "tools_listed": 0,
        "all_pages_read": False,
        "tool_calls": [],
        "errors": [],
    }
    for request_id in order:
        request = requests[request_id]
        response = responses.get(request_id, {})
        method = request["method"]
        params = request.get("params") or {}
        result = response.get("result") or {}
        if "error" in response:
            summary["errors"].append({"method": method, "error": response["error"]})
        if method == "initialize":
            summary["client_info"] = params.get("clientInfo")
            summary["requested_protocol"] = params.get("protocolVersion")
            summary["negotiated_protocol"] = result.get("protocolVersion")
            summary["server_info"] = result.get("serverInfo")
        elif method == "tools/list":
            tools = result.get("tools") or []
            summary["tools_list_pages"].append(
                {"cursor": params.get("cursor"), "tools": len(tools), "next_cursor": result.get("nextCursor")}
            )
        elif method == "tools/call":
            summary["tool_calls"].append(
                {"name": params.get("name"), "answered": bool(response), "is_error": result.get("isError")}
            )
    # A page without a cursor starts a new listing; a client may list more than once.
    listing: list[dict[str, Any]] = []
    for page in summary["tools_list_pages"]:
        if page["cursor"] is None:
            listing = []
        listing.append(page)
    summary["all_pages_read"] = bool(listing) and listing[0]["cursor"] is None and listing[-1]["next_cursor"] is None
    summary["tools_listed"] = sum(page["tools"] for page in listing)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--log", type=Path, help="JSONL file to append the traffic to.")
    parser.add_argument("--summarize", type=Path, help="Summarize a recorded log and exit.")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Server command, after --.")
    args = parser.parse_args(argv)

    if args.summarize:
        print(json.dumps(summarize(args.summarize), indent=2, ensure_ascii=False))
        return 0
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not args.log or not command:
        parser.error("relay mode needs --log and a server command after --")
    return relay(command, args.log)


if __name__ == "__main__":
    sys.exit(main())
