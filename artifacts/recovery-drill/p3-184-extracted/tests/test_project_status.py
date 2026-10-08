import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from wps_ai_agent_cli.project_status import _sha256, build_project_status


class ProjectStatusTests(unittest.TestCase):
    def test_build_project_status_reports_local_only_state(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "artifacts" / "cloud-sync").mkdir(parents=True)
            package = workspace / "artifacts" / "cloud-sync" / "wps-ai-agent-cli-phase3-sync-cli.zip"
            package.write_text("zip", encoding="utf-8")

            status = build_project_status(workspace)

        self.assertEqual(status["phase"], "phase3")
        self.assertFalse(status["remote_git_required"])
        self.assertGreaterEqual(status["mcp_tool_count"], 40)
        self.assertGreaterEqual(len(status["next_tasks"]), 1)
        self.assertTrue(status["cleanup"]["read_only"])
        self.assertFalse(status["cleanup"]["deletion_performed"])
        self.assertTrue(status["sync_package"]["exists"])
        self.assertEqual(len(status["sync_package"]["sha256"]), 64)

    def test_sha256_returns_none_when_file_is_unreadable(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "locked.zip"
            path.write_text("zip", encoding="utf-8")
            with patch.object(Path, "open", side_effect=PermissionError("locked")):
                digest = _sha256(path)

        self.assertIsNone(digest)


if __name__ == "__main__":
    unittest.main()
