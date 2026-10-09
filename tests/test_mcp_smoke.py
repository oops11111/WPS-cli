import unittest
import json
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from wps_ai_agent_cli.mcp_smoke import run_mcp_server_smoke
from wps_ai_agent_cli.cli import mcp_smoke_response, run
from wps_ai_agent_cli.batch_conversion import _request_record_path


class McpSmokeTests(unittest.TestCase):
    def test_parameterized_smoke_exercises_read_only_batch_request(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"):
                record_path = _request_record_path("inspect")
                record_path.parent.mkdir()
                record_path.write_text(json.dumps({
                    "request_id": "inspect", "state": "succeeded",
                    "arguments": {"output_directory": str(root / "output")},
                }), encoding="utf-8")
                response = mcp_smoke_response("smoke", 70, "wps_agent_html_batch_request",
                                              arguments_json='{"batch_request_id":"inspect"}')
                self.assertTrue(response.ok, response.errors)
                self.assertEqual(response.data["mcp_smoke"]["responses"]["tools_call"]["result"]
                                 ["structuredContent"]["mcp_call"]["response"]["data"]["batch_request"]["state"], "succeeded")

                output = io.StringIO()
                self.assertEqual(run(["mcp-smoke", "--expected-min-tools", "70",
                                      "--tool-name", "wps_agent_html_batch_request",
                                      "--arguments-json", '{"batch_request_id":"inspect"}'], output_stream=output), 0)
                self.assertTrue(json.loads(output.getvalue())["ok"])

    def test_parameterized_smoke_rejects_invalid_json_and_mutating_tool(self):
        for arguments, code in (("{bad", "MCP_SMOKE_ARGUMENTS_INVALID_JSON"),
                                ("[]", "MCP_SMOKE_ARGUMENTS_INVALID_OBJECT"),
                                ("null", "MCP_SMOKE_ARGUMENTS_INVALID_OBJECT")):
            with self.subTest(arguments=arguments):
                response = mcp_smoke_response("smoke", 1, "wps_agent_tasks", arguments_json=arguments)
                self.assertFalse(response.ok)
                self.assertEqual(response.errors[0]["code"], code)
        ok, _, errors = run_mcp_server_smoke(1, "wps_agent_html_batch_convert", tool_arguments={})
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_SMOKE_TOOL_NOT_READ_ONLY")
        ok, _, errors = run_mcp_server_smoke(1, "wps_agent_cloud_sync_package", tool_arguments={})
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_SMOKE_TOOL_NOT_READ_ONLY")

    def test_mcp_server_smoke_passes_for_tasks_tool(self):
        ok, result, errors = run_mcp_server_smoke(
            expected_min_tools=1,
            tool_name="wps_agent_tasks",
        )

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertTrue(all(check["passed"] for check in result["checks"]))
        self.assertEqual(
            result["responses"]["tools_call"]["result"]["structuredContent"]["mcp_call"]["response"]["command"],
            "tasks",
        )

    def test_mcp_server_smoke_fails_when_tool_count_expectation_is_too_high(self):
        ok, result, errors = run_mcp_server_smoke(expected_min_tools=10_000)

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_SMOKE_FAILED")
        self.assertFalse(result["checks"][1]["passed"])

    def test_mcp_server_smoke_passes_for_no_argument_tool(self):
        ok, result, errors = run_mcp_server_smoke(
            expected_min_tools=1,
            tool_name="wps_agent_security_audit",
        )

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(
            result["responses"]["tools_call"]["result"]["structuredContent"]["mcp_call"]["response"]["command"],
            "security-audit",
        )


if __name__ == "__main__":
    unittest.main()
