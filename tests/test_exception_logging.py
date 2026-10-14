from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
