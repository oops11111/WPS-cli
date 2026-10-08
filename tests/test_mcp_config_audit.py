import json
import sys
import tempfile
import unittest
from pathlib import Path

from wps_ai_agent_cli.mcp_config_audit import audit_mcp_client_config
from wps_ai_agent_cli.mcp_schema import list_mcp_tool_schemas


class McpConfigAuditTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
