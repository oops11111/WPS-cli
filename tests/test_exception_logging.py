from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from wps_ai_agent_cli.com_backend import run_com_smoke
from wps_ai_agent_cli.mcp_server import serve_stdio


class McpServerExceptionLoggingTests(unittest.TestCase):
    def test_tool_call_exception_is_logged_and_the_protocol_error_is_unchanged(self):
        handshake = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        ]
        call = {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "wps_agent_tasks", "arguments": {}}}
        stdin = io.StringIO("".join(json.dumps(message) + "\n" for message in [*handshake, call]))
        output = io.StringIO()

        with patch("wps_ai_agent_cli.mcp_server.handle_mcp_json", side_effect=RuntimeError("boom")) as handler, \
                self.assertLogs("wps_ai_agent_cli.mcp_server", level="ERROR") as logs:
            serve_stdio(stdin, output)

        self.assertEqual(handler.call_count, 1)
        response = json.loads(output.getvalue().splitlines()[-1])
        self.assertEqual(response["error"]["code"], -32603)
        self.assertEqual(response["error"]["message"], "Tool call failed unexpectedly.")
        self.assertNotIn("boom", output.getvalue())
        self.assertIsNotNone(logs.records[0].exc_info)
        self.assertEqual(logs.records[0].exc_info[1].args, ("boom",))


class ComBackendCleanupLoggingTests(unittest.TestCase):
    def test_failed_close_and_quit_are_logged_as_warnings(self):
        document = MagicMock()
        document.SaveAs.side_effect = RuntimeError("save failed")
        document.Close.side_effect = RuntimeError("close failed")
        app = MagicMock()
        app.Documents.Open.return_value = document
        app.Quit.side_effect = RuntimeError("quit failed")
        client = MagicMock()
        client.DispatchEx.return_value = app
        capabilities = {"components": {"writer": {"selected_prog_id": "kwps.Application"}}}

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.docx"
            source.write_bytes(b"not a real document")
            target = Path(tmp) / "output.pdf"
            with patch("wps_ai_agent_cli.com_backend._load_win32com", return_value=client), \
                    patch("wps_ai_agent_cli.com_backend.probe_wps_capabilities", return_value=capabilities), \
                    self.assertLogs("wps_ai_agent_cli.com_backend", level="WARNING") as logs:
                result = run_com_smoke("writer", str(source), str(target), visible=False)

        self.assertFalse(result["ok"])
        messages = [record.getMessage() for record in logs.records]
        self.assertTrue(any("Could not close the WPS document" in message for message in messages), messages)
        self.assertTrue(any("Could not quit the WPS instance" in message for message in messages), messages)


if __name__ == "__main__":
    unittest.main()
