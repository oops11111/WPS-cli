from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

from wps_ai_agent_cli import regression

TEMPLATE = Path(regression.REPO_ROOT) / regression.MCP_AUDIT_TEMPLATE


class RenderedAuditConfigTests(unittest.TestCase):
    def test_server_is_launched_by_the_running_interpreter_from_the_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            rendered = regression._render_mcp_audit_config(TEMPLATE, Path(tmp))
            server = json.loads(rendered.read_text(encoding="utf-8"))["mcpServers"]["wps-ai-agent-cli"]

        self.assertEqual(server["command"], sys.executable)
        self.assertEqual(server["cwd"], str(regression.REPO_ROOT))
        self.assertEqual(server["env"], {"PYTHONPATH": str(regression.REPO_ROOT / "src")})
        self.assertEqual(server["args"], ["-m", "wps_ai_agent_cli", "mcp-server"])
        self.assertTrue(Path(server["cwd"]).is_absolute())

    def test_only_the_audit_template_is_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            command = ["mcp-config-audit", "--config", regression.MCP_AUDIT_TEMPLATE, "--server-name", "wps-ai-agent-cli"]
            rewritten = regression._scenario_command(command, Path(tmp))

        self.assertEqual(rewritten[:2], ["mcp-config-audit", "--config"])
        self.assertNotEqual(rewritten[2], regression.MCP_AUDIT_TEMPLATE)
        self.assertEqual(rewritten[3:], ["--server-name", "wps-ai-agent-cli"])

    def test_other_commands_and_configs_are_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            other_config = ["mcp-config-audit", "--config", "config/mcp_client_config.example.json"]
            other_command = ["mcp-tools"]

            self.assertEqual(regression._scenario_command(other_config, Path(tmp)), other_config)
            self.assertEqual(regression._scenario_command(other_command, Path(tmp)), other_command)

    def test_the_shipped_manifest_points_at_the_template(self):
        ok, manifest, errors = regression.load_regression_manifest()
        self.assertTrue(ok, errors)
        audit = next(s for s in manifest["scenarios"] if s["id"] == "mcp-config-audit")
        self.assertIn(regression.MCP_AUDIT_TEMPLATE, audit["command"])
        self.assertTrue(TEMPLATE.is_file())


if __name__ == "__main__":
    unittest.main()
