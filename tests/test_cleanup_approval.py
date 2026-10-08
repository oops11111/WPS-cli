import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.cleanup_approval import build_cleanup_approval_manifest


class CleanupApprovalManifestTests(unittest.TestCase):
    def test_manifest_groups_cleanup_candidates_by_category(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "fixtures" / "phase3").mkdir(parents=True)
            probe = workspace / "fixtures" / "phase3" / "phase0_calculation_smoke_timeout_probe.xlsx"
            probe.write_text("probe", encoding="utf-8")

            manifest = build_cleanup_approval_manifest(workspace)

        categories = {item["category"]: item for item in manifest["categories"]}
        self.assertTrue(manifest["read_only"])
        self.assertFalse(manifest["deletion_performed"])
        self.assertIn("probe_fixture", categories)
        self.assertEqual(categories["probe_fixture"]["candidate_count"], 1)
        self.assertIn("批准清理 probe_fixture", categories["probe_fixture"]["approval_phrase"])


if __name__ == "__main__":
    unittest.main()
