import unittest
import json
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from wps_ai_agent_cli.mcp_smoke import run_mcp_server_smoke
from wps_ai_agent_cli.cli import mcp_smoke_response, run
from wps_ai_agent_cli.batch_conversion import _request_record_path
from wps_ai_agent_cli.mcp_schema import list_mcp_tool_schemas
from wps_ai_agent_cli.mcp_server import handle_mcp_request as real_handle_mcp_request


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
            expected_min_tools=len(list_mcp_tool_schemas()),
            tool_name="wps_agent_tasks",
        )

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertTrue(all(check["passed"] for check in result["checks"]))
        self.assertEqual(
            result["checks"][1]["details"]["tool_count"], len(list_mcp_tool_schemas()),
        )
        self.assertGreater(result["checks"][1]["details"]["page_count"], 1)
        self.assertEqual(result["responses"]["tools_list"]["page_count"], 2)
        self.assertEqual(
            result["responses"]["tools_list"]["pages"][0]["tool_count"], 50,
        )
        self.assertEqual(
            result["responses"]["tools_list"]["pages"][1]["tool_count"], 20,
        )
        self.assertEqual(
            result["responses"]["tools_call"]["result"]["structuredContent"]["mcp_call"]["response"]["command"],
            "tasks",
        )

    def test_mcp_server_smoke_fails_when_tool_count_expectation_is_too_high(self):
        ok, result, errors = run_mcp_server_smoke(expected_min_tools=10_000)

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_SMOKE_FAILED")
        self.assertFalse(result["checks"][1]["passed"])

    def test_mcp_server_smoke_reports_malformed_json_rpc_results_without_raising(self):
        malformed_results = {
            "missing": {},
            "null": {"result": None},
            "non_object": {"result": []},
        }
        for shape, result_fields in malformed_results.items():
            with self.subTest(shape=shape):
                def malformed_response(request):
                    return {"jsonrpc": "2.0", "id": request["id"], **result_fields}

                with patch("wps_ai_agent_cli.mcp_smoke.handle_mcp_request", side_effect=malformed_response):
                    ok, result, errors = run_mcp_server_smoke(expected_min_tools=1)

                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "MCP_SMOKE_FAILED")
                self.assertTrue(all(not check["passed"] for check in result["checks"]))
                self.assertEqual(result["responses"]["tools_list"]["tool_count"], 0)
                self.assertEqual(result["responses"]["tools_list"]["page_count"], 1)
                self.assertEqual(result["responses"]["tools_list"]["pages"][0]["tool_count"], 0)
                self.assertFalse(result["responses"]["tools_list"]["pages"][0]["has_next_page"])

    def test_mcp_server_smoke_rejects_nonconforming_tool_names(self):
        for name in ("", "   ", "tool name", "tool/name", "naïve", "a" * 129):
            with self.subTest(name=repr(name)):
                def response(request):
                    if request["method"] == "tools/list":
                        return {"jsonrpc": "2.0", "id": request["id"], "result": {
                            "tools": [{"name": name}], "resultType": "complete",
                        }}
                    return real_handle_mcp_request(request)

                with patch("wps_ai_agent_cli.mcp_smoke.handle_mcp_request", side_effect=response):
                    ok, result, errors = run_mcp_server_smoke(expected_min_tools=1)

                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "MCP_SMOKE_FAILED")
                details = result["checks"][1]["details"]
                self.assertEqual(details["tool_count"], 1)
                self.assertEqual(details["invalid_tool_count"], 1)

    def test_mcp_server_smoke_accepts_mcp_tool_name_boundaries(self):
        for name in ("a", "A" * 128, "tool.name_v2-3"):
            with self.subTest(name=name[:20]):
                def response(request):
                    if request["method"] == "tools/list":
                        return {"jsonrpc": "2.0", "id": request["id"], "result": {
                            "tools": [{"name": name}], "resultType": "complete",
                        }}
                    return real_handle_mcp_request(request)

                with patch("wps_ai_agent_cli.mcp_smoke.handle_mcp_request", side_effect=response):
                    ok, result, errors = run_mcp_server_smoke(expected_min_tools=1)

                self.assertTrue(ok, errors)
                self.assertEqual(result["checks"][1]["details"]["invalid_tool_count"], 0)

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
