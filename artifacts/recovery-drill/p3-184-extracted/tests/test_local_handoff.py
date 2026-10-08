import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.local_handoff import build_local_handoff_summary


def _artifact(profile: str, passed: int, failed: int) -> dict:
    return {
        "data": {
            "regression": {
                "profile": profile,
                "include_wps": profile == "wps",
                "scenario_count": passed + failed,
                "passed_count": passed,
                "failed_count": failed,
                "results": [{"id": f"{profile}-scenario", "ok": failed == 0}],
            }
        }
    }


class LocalHandoffSummaryTests(unittest.TestCase):
    def test_build_local_handoff_summary_reports_passed_state(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "artifacts" / "cloud-sync").mkdir(parents=True)
            (workspace / "artifacts" / "regression" / "safe").mkdir(parents=True)
            (workspace / "artifacts" / "regression" / "wps").mkdir(parents=True)
            (workspace / "artifacts" / "cloud-sync" / "wps-ai-agent-cli-phase3-sync-cli.zip").write_text("zip", encoding="utf-8")
            (workspace / "artifacts" / "regression" / "safe" / "regression-run-safe.json").write_text(
                json.dumps(_artifact("safe", 8, 0)),
                encoding="utf-8",
            )
            (workspace / "artifacts" / "regression" / "wps" / "regression-run-wps.json").write_text(
                json.dumps(_artifact("wps", 4, 0)),
                encoding="utf-8",
            )

            ok, summary, errors = build_local_handoff_summary(workspace)

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(summary["handoff_status"], "passed")
        self.assertFalse(summary["remote_git_required"])
        self.assertTrue(summary["sync_package"]["exists"])
        self.assertEqual(summary["regression_evidence"]["evidence_status"], "passed")
        self.assertEqual(summary["mcp_catalog_drift"]["drift_count"], 0)


if __name__ == "__main__":
    unittest.main()
