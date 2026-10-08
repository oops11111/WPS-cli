import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.regression_history import build_regression_history


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


class RegressionHistoryTests(unittest.TestCase):
    def test_build_regression_history_reports_recent_artifacts(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            safe_dir = workspace / "artifacts" / "regression" / "safe"
            wps_dir = workspace / "artifacts" / "regression" / "wps"
            safe_dir.mkdir(parents=True)
            wps_dir.mkdir(parents=True)
            (safe_dir / "regression-run-safe-1.json").write_text(json.dumps(_artifact("safe", 2, 0)), encoding="utf-8")
            (safe_dir / "regression-run-safe-2.json").write_text(json.dumps(_artifact("safe", 3, 0)), encoding="utf-8")
            (wps_dir / "regression-run-wps-1.json").write_text(json.dumps(_artifact("wps", 4, 0)), encoding="utf-8")

            history = build_regression_history(workspace, limit=2)

        self.assertEqual(history["history_status"], "passed")
        self.assertTrue(history["read_only"])
        self.assertFalse(history["launches_wps"])
        self.assertEqual(history["profiles"]["safe"]["artifact_count"], 2)
        self.assertEqual(history["profiles"]["safe"]["recent_failed_count"], 0)
        self.assertTrue(history["profiles"]["safe"]["latest"]["passed"])
        self.assertTrue(history["profiles"]["wps"]["latest"]["passed"])

    def test_build_regression_history_warns_when_profile_missing(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            safe_dir = workspace / "artifacts" / "regression" / "safe"
            safe_dir.mkdir(parents=True)
            (safe_dir / "regression-run-safe-1.json").write_text(json.dumps(_artifact("safe", 2, 0)), encoding="utf-8")

            history = build_regression_history(workspace)

        self.assertEqual(history["history_status"], "warning")
        self.assertEqual(history["profiles"]["wps"]["artifact_count"], 0)


if __name__ == "__main__":
    unittest.main()
