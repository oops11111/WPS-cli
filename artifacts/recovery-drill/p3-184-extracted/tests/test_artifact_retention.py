import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.artifact_retention import build_artifact_retention_summary


def _artifact(profile: str) -> dict:
    return {
        "data": {
            "regression": {
                "profile": profile,
                "scenario_count": 1,
                "passed_count": 1,
                "failed_count": 0,
                "results": [{"id": f"{profile}-scenario", "ok": True}],
            }
        }
    }


class ArtifactRetentionSummaryTests(unittest.TestCase):
    def test_build_artifact_retention_summary_is_read_only(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "artifacts" / "cloud-sync").mkdir(parents=True)
            (workspace / "artifacts" / "regression" / "safe").mkdir(parents=True)
            (workspace / "artifacts" / "regression" / "wps").mkdir(parents=True)
            (workspace / ".wps-agent" / "backups" / "doc").mkdir(parents=True)
            (workspace / "artifacts" / "cloud-sync" / "wps-ai-agent-cli-phase3-sync-cli.zip").write_text(
                "zip",
                encoding="utf-8",
            )
            (workspace / "artifacts" / "cloud-sync" / "old-sync.zip").write_text("old", encoding="utf-8")
            (workspace / "artifacts" / "regression" / "safe" / "regression-run-old.json").write_text(
                json.dumps(_artifact("safe")),
                encoding="utf-8",
            )
            (workspace / "artifacts" / "regression" / "safe" / "regression-run-new.json").write_text(
                json.dumps(_artifact("safe")),
                encoding="utf-8",
            )
            (workspace / "artifacts" / "regression" / "wps" / "regression-run-new.json").write_text(
                json.dumps(_artifact("wps")),
                encoding="utf-8",
            )
            (workspace / ".wps-agent" / "backups" / "doc" / "backup.docx").write_text("backup", encoding="utf-8")

            summary = build_artifact_retention_summary(workspace)

        self.assertEqual(summary["retention_status"], "passed")
        self.assertTrue(summary["read_only"])
        self.assertFalse(summary["deletion_performed"])
        self.assertFalse(summary["remote_git_required"])
        self.assertTrue(summary["review_required"])
        self.assertTrue(summary["current_sync_package"]["exists"])
        self.assertEqual(len(summary["preserved_evidence"]), 2)
        self.assertGreaterEqual(summary["candidate_summary"]["candidate_count"], 2)
        self.assertIn(
            "superseded_sync_package",
            {category["category"] for category in summary["candidate_summary"]["categories"]},
        )
        self.assertFalse(summary["approval_policy"]["deletion_allowed_without_user_approval"])


if __name__ == "__main__":
    unittest.main()
