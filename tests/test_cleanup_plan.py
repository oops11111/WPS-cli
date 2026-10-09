import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.cleanup_plan import build_cleanup_plan


class CleanupPlanTests(unittest.TestCase):
    def test_build_cleanup_plan_is_read_only_and_identifies_candidates(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "fixtures" / "phase3").mkdir(parents=True)
            (workspace / "artifacts" / "regression" / "safe").mkdir(parents=True)
            (workspace / "artifacts" / "regression" / "wps").mkdir(parents=True)
            (workspace / "artifacts" / "cloud-sync").mkdir(parents=True)
            (workspace / ".wps-agent" / "backups" / "doc_1").mkdir(parents=True)

            probe = workspace / "fixtures" / "phase3" / "phase0_calculation_smoke_timeout_probe.xlsx"
            probe.write_text("probe", encoding="utf-8")
            safe_old = workspace / "artifacts" / "regression" / "safe" / "regression-run-20261003T000000Z-old.json"
            safe_new = workspace / "artifacts" / "regression" / "safe" / "regression-run-20261003T010000Z-new.json"
            safe_old.write_text("old", encoding="utf-8")
            safe_new.write_text("new", encoding="utf-8")
            manual_zip = workspace / "artifacts" / "cloud-sync" / "wps-ai-agent-cli-phase3-sync-20261003.zip"
            manual_zip.write_text("zip", encoding="utf-8")
            backup = workspace / ".wps-agent" / "backups" / "doc_1" / "doc.20261003.docx"
            backup.write_text("backup", encoding="utf-8")

            plan = build_cleanup_plan(workspace)

            candidate_paths = {item["path"].replace("\\", "/") for item in plan["candidates"]}
            self.assertTrue(plan["read_only"])
            self.assertFalse(plan["deletion_performed"])
            self.assertTrue(plan["approval_required"])
            self.assertIn("fixtures/phase3/phase0_calculation_smoke_timeout_probe.xlsx", candidate_paths)
            self.assertIn("artifacts/regression/safe/regression-run-20261003T000000Z-old.json", candidate_paths)
            self.assertIn("artifacts/cloud-sync/wps-ai-agent-cli-phase3-sync-20261003.zip", candidate_paths)
            self.assertIn(".wps-agent/backups", candidate_paths)
            self.assertTrue(probe.exists())


if __name__ == "__main__":
    unittest.main()
