import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.workspace_health import build_workspace_health


class WorkspaceHealthTests(unittest.TestCase):
    def test_build_workspace_health_reports_passed_local_state(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "artifacts" / "cloud-sync").mkdir(parents=True)
            (workspace / "artifacts" / "regression" / "safe").mkdir(parents=True)
            package = workspace / "artifacts" / "cloud-sync" / "wps-ai-agent-cli-phase3-sync-cli.zip"
            package.write_text("zip", encoding="utf-8")
            safe_artifact = workspace / "artifacts" / "regression" / "safe" / "regression-run-20261004T000000Z-safe.json"
            safe_artifact.write_text("{}", encoding="utf-8")

            health = build_workspace_health(workspace)

        self.assertEqual(health["health_status"], "passed")
        self.assertFalse(health["remote_git_required"])
        self.assertTrue(health["sync_package"]["exists"])
        self.assertGreaterEqual(health["mcp_tool_count"], 40)
        self.assertTrue(all(check["passed"] for check in health["checks"]))


if __name__ == "__main__":
    unittest.main()
