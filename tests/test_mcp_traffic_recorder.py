import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "mcp_client_check" / "record_mcp_traffic.py"

_spec = importlib.util.spec_from_file_location("record_mcp_traffic", SCRIPT)
recorder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recorder)

PROTOCOL = "2025-11-25"


def _line(message):
    return json.dumps(message) + "\n"


class RecorderRelayTests(unittest.TestCase):
    def test_a_full_session_through_the_recorder_is_relayed_and_summarized(self):
        env = dict(os.environ, PYTHONPATH=str(REPO_ROOT / "src"))
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "traffic.jsonl"
            recorder_process = subprocess.Popen(
                [sys.executable, str(SCRIPT), "--log", str(log), "--",
                 sys.executable, "-m", "wps_ai_agent_cli", "mcp-server"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, cwd=tmp, text=True,
            )

            def ask(message):
                recorder_process.stdin.write(_line(message))
                recorder_process.stdin.flush()
                return json.loads(recorder_process.stdout.readline())

            initialize = ask({
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": PROTOCOL, "capabilities": {},
                           "clientInfo": {"name": "stand-in-client", "version": "9.9"}},
            })
            self.assertEqual(initialize["result"]["protocolVersion"], PROTOCOL)
            recorder_process.stdin.write(_line({"jsonrpc": "2.0", "method": "notifications/initialized"}))
            first = ask({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            cursor = first["result"]["nextCursor"]
            second = ask({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {"cursor": cursor}})
            call = ask({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                        "params": {"name": "wps_agent_tasks", "arguments": {"phase": "phase4"}}})
            recorder_process.stdin.close()
            self.assertEqual(recorder_process.wait(timeout=30), 0)
            recorder_process.stdout.close()

            summary = recorder.summarize(log)

        self.assertEqual(summary["client_info"], {"name": "stand-in-client", "version": "9.9"})
        self.assertEqual(summary["requested_protocol"], PROTOCOL)
        self.assertEqual(summary["negotiated_protocol"], PROTOCOL)
        self.assertEqual(summary["server_info"]["name"], "wps-ai-agent-cli")
        self.assertTrue(summary["initialized_notification"])
        self.assertEqual(len(summary["tools_list_pages"]), 2)
        self.assertEqual(summary["tools_listed"], len(first["result"]["tools"]) + len(second["result"]["tools"]))
        self.assertTrue(summary["all_pages_read"])
        self.assertEqual(summary["tool_calls"], [
            {"name": "wps_agent_tasks", "answered": True, "is_error": call["result"].get("isError")}
        ])
        self.assertFalse(call["result"].get("isError"))
        self.assertEqual(summary["errors"], [])


class SummaryTests(unittest.TestCase):
    def write_log(self, entries):
        handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        with handle:
            for direction, message in entries:
                handle.write(json.dumps({"t": 0, "dir": direction, "line": json.dumps(message)}) + "\n")
        self.addCleanup(os.unlink, handle.name)
        return Path(handle.name)

    def test_only_the_last_complete_listing_is_counted(self):
        log = self.write_log([
            ("client->server", {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}),
            ("server->client", {"jsonrpc": "2.0", "id": 1, "result": {"tools": [{}] * 50, "nextCursor": "c"}}),
            ("client->server", {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"cursor": "c"}}),
            ("server->client", {"jsonrpc": "2.0", "id": 2, "result": {"tools": [{}] * 35}}),
            ("client->server", {"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}}),
            ("server->client", {"jsonrpc": "2.0", "id": 3, "result": {"tools": [{}] * 50, "nextCursor": "c"}}),
        ])

        summary = recorder.summarize(log)

        self.assertEqual(len(summary["tools_list_pages"]), 3)
        self.assertFalse(summary["all_pages_read"])
        self.assertEqual(summary["tools_listed"], 50)

    def test_error_responses_and_unparsable_lines_are_reported_or_skipped(self):
        log = self.write_log([
            ("client->server", {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "nope"}}),
            ("server->client", {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Unknown tool"}}),
        ])
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"t": 0, "dir": "server->client", "line": "not json"}) + "\n")

        summary = recorder.summarize(log)

        self.assertEqual(summary["errors"], [{"method": "tools/call", "error": {"code": -32602, "message": "Unknown tool"}}])
        self.assertEqual(summary["tool_calls"], [{"name": "nope", "answered": True, "is_error": None}])


if __name__ == "__main__":
    unittest.main()
