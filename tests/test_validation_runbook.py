import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.validation_runbook import build_validation_runbook


class ValidationRunbookTests(unittest.TestCase):
    def test_build_validation_runbook_is_read_only_and_structured(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "artifacts" / "cloud-sync").mkdir(parents=True)
            (workspace / "artifacts" / "cloud-sync" / "wps-ai-agent-cli-phase3-sync-cli.zip").write_text(
                "zip",
                encoding="utf-8",
            )

            runbook = build_validation_runbook(workspace)

        section_ids = {section["id"] for section in runbook["sections"]}

        self.assertEqual(runbook["runbook_status"], "passed")
        self.assertTrue(runbook["read_only"])
        self.assertFalse(runbook["commands_executed"])
        self.assertFalse(runbook["launches_wps"])
        self.assertFalse(runbook["creates_package"])
        self.assertFalse(runbook["deletion_performed"])
        self.assertFalse(runbook["approval_policy"]["remote_git_required"])
        self.assertIn("quick-local-checks", section_ids)
        self.assertIn("safe-regression", section_ids)
        self.assertIn("mutation-recovery", section_ids)
        self.assertIn("package-refresh", section_ids)
        self.assertIn("optional-wps-validation", section_ids)
        self.assertIn("cleanup-review", section_ids)

        wps_section = next(section for section in runbook["sections"] if section["id"] == "optional-wps-validation")
        self.assertTrue(any(step["launches_wps"] for step in wps_section["steps"]))

        safe_section = next(section for section in runbook["sections"] if section["id"] == "safe-regression")
        safe_commands = [step["command"] for step in safe_section["steps"]]
        self.assertTrue(any("--expected-min-tools" in command for command in safe_commands))
        recovery = next(section for section in runbook["sections"] if section["id"] == "mutation-recovery")
        self.assertTrue(all(not step["mutates_files"] and not step["launches_wps"] for step in recovery["steps"]))
        self.assertIn("mutation-request-inspect", recovery["steps"][0]["command"])


if __name__ == "__main__":
    unittest.main()
