import json
import sys
import tempfile
import unittest
from pathlib import Path

from wps_ai_agent_cli.mcp_config_audit import audit_mcp_client_config
from wps_ai_agent_cli.mcp_schema import list_mcp_tool_schemas


class McpConfigAuditTests(unittest.TestCase):
    def audit_fake_paged_server(self, pages, expected_min_tools=1):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "mcp.json"
            server_script = (
                "import json,sys; pages=json.loads(sys.argv[sys.argv.index('mcp-server')+1]); "
                "request=json.loads(sys.argv[-1]); "
                "cursor=request.get('params',{}).get('cursor'); "
                "page=pages[0] if cursor is None else pages[1]; "
                "print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':page}))"
            )
            config_path.write_text(json.dumps({
                "mcpServers": {
                    "fake-server": {
                        "command": sys.executable,
                        "args": ["-c", server_script, "mcp-server", json.dumps(pages)],
                        "cwd": str(root),
                        "env": {"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
                    }
                }
            }), encoding="utf-8")
            return audit_mcp_client_config(
                config_path=config_path,
                server_name="fake-server",
                expected_min_tools=expected_min_tools,
                timeout_seconds=10,
            )

    def test_audit_mcp_client_config_runs_configured_tools_list_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path.cwd()
            config_path = Path(tmp) / "mcp.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "wps-ai-agent-cli": {
                                "command": sys.executable,
                                "args": ["-m", "wps_ai_agent_cli", "mcp-server"],
                                "cwd": str(workspace),
                                "env": {"PYTHONPATH": "src"},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            ok, result, errors = audit_mcp_client_config(
                config_path=config_path,
                expected_min_tools=len(list_mcp_tool_schemas()),
                timeout_seconds=15,
            )

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["smoke"]["tool_count"], len(list_mcp_tool_schemas()))
            self.assertGreater(result["smoke"]["page_count"], 1)
            self.assertEqual(result["smoke"]["duplicate_tool_count"], 0)
            self.assertTrue(all(check["passed"] for check in result["checks"]))

    def test_audit_mcp_client_config_reports_missing_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "mcp.json"
            config_path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

            ok, result, errors = audit_mcp_client_config(config_path=config_path)

            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
            self.assertFalse(result["checks"][2]["passed"])

    def test_audit_rejects_duplicate_tool_names_across_pages(self):
        ok, result, errors = self.audit_fake_paged_server([
            {"resultType": "complete", "tools": [{"name": "tool_a"}], "nextCursor": "page-2"},
            {"resultType": "complete", "tools": [{"name": "tool_a"}]},
        ], expected_min_tools=2)

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
        self.assertEqual(result["smoke"]["tool_count"], 2)
        self.assertEqual(result["smoke"]["page_count"], 2)
        self.assertEqual(result["smoke"]["duplicate_tool_count"], 1)
        smoke_check = next(check for check in result["checks"] if check["name"] == "configured_tools_list_smoke")
        self.assertFalse(smoke_check["passed"])

    def test_audit_rejects_repeated_cursor_without_extra_request(self):
        ok, result, errors = self.audit_fake_paged_server([
            {"resultType": "complete", "tools": [{"name": "tool_a"}], "nextCursor": "repeat"},
            {"resultType": "complete", "tools": [{"name": "tool_b"}], "nextCursor": "repeat"},
        ])

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
        self.assertEqual(result["smoke"]["page_count"], 2)
        self.assertIn("repeated cursor", result["smoke"]["error"])

    def test_audit_rejects_empty_and_whitespace_tool_names(self):
        for name in ("", "   "):
            with self.subTest(name=repr(name)):
                ok, result, errors = self.audit_fake_paged_server([
                    {"resultType": "complete", "tools": [{"name": name}]},
                    {"resultType": "complete", "tools": []},
                ], expected_min_tools=1)

                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
                self.assertEqual(result["smoke"]["tool_count"], 1)
                self.assertEqual(result["smoke"]["invalid_tool_count"], 1)

    def test_audit_validates_mcp_tool_name_charset_and_length(self):
        for name in ("tool name", "tool/name", "naïve", "a" * 129):
            with self.subTest(name=name[:20]):
                ok, result, _ = self.audit_fake_paged_server([
                    {"resultType": "complete", "tools": [{"name": name}]},
                    {"resultType": "complete", "tools": []},
                ])
                self.assertFalse(ok)
                self.assertEqual(result["smoke"]["invalid_tool_count"], 1)

        for name in ("a", "A" * 128, "tool.name_v2-3"):
            with self.subTest(valid_name=name[:20]):
                ok, result, errors = self.audit_fake_paged_server([
                    {"resultType": "complete", "tools": [{"name": name}]},
                    {"resultType": "complete", "tools": []},
                ])
                self.assertTrue(ok, errors)
                self.assertEqual(result["smoke"]["invalid_tool_count"], 0)
                self.assertEqual(result["smoke"]["duplicate_tool_count"], 0)


if __name__ == "__main__":
    unittest.main()
