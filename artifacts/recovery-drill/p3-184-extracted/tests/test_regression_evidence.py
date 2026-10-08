import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.regression_evidence import build_regression_evidence


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


class RegressionEvidenceTests(unittest.TestCase):
    def test_build_regression_evidence_summarizes_latest_artifacts(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            safe_dir = workspace / "artifacts" / "regression" / "safe"
            wps_dir = workspace / "artifacts" / "regression" / "wps"
            safe_dir.mkdir(parents=True)
            wps_dir.mkdir(parents=True)
            (safe_dir / "regression-run-safe.json").write_text(json.dumps(_artifact("safe", 7, 0)), encoding="utf-8")
            (wps_dir / "regression-run-wps.json").write_text(json.dumps(_artifact("wps", 4, 0)), encoding="utf-8")

            ok, evidence, errors = build_regression_evidence(workspace)

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(evidence["evidence_status"], "passed")
        self.assertTrue(evidence["profiles"]["safe"]["passed"])
        self.assertTrue(evidence["profiles"]["wps"]["passed"])
        self.assertEqual(evidence["profiles"]["safe"]["scenario_count"], 7)
        self.assertEqual(evidence["profiles"]["wps"]["scenario_count"], 4)

    def test_build_regression_evidence_reports_missing_profile(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            safe_dir = workspace / "artifacts" / "regression" / "safe"
            safe_dir.mkdir(parents=True)
            (safe_dir / "regression-run-safe.json").write_text(json.dumps(_artifact("safe", 7, 0)), encoding="utf-8")

            ok, evidence, errors = build_regression_evidence(workspace)

        self.assertFalse(ok)
        self.assertIn("wps", evidence["missing_profiles"])
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
