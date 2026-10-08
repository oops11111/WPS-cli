import zipfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.sync_package_summary import summarize_sync_package


class SyncPackageSummaryTests(unittest.TestCase):
    def test_summarize_sync_package_groups_entries_and_artifacts(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            package = workspace / "artifacts" / "cloud-sync" / "sync.zip"
            package.parent.mkdir(parents=True)
            files = {
                "src/app.py": "print('ok')",
                "tests/test_app.py": "def test_ok(): pass",
                "config/settings.json": "{}",
                "docs/readme.md": "# docs",
                "fixtures/sample.txt": "fixture",
                "scripts/repro.ps1": "Write-Output 'ok'",
                "artifacts/regression/safe/regression-run-safe.json": "{}",
            }
            for relative, content in files.items():
                path = workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            with zipfile.ZipFile(package, "w") as archive:
                for relative in files:
                    archive.write(workspace / relative, relative)

            ok, result, errors = summarize_sync_package(workspace=workspace, package_path=package, limit=2)

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["summary_status"], "passed")
            self.assertEqual(result["entry_count"], 7)
            self.assertEqual(result["top_level_groups"]["src"]["entry_count"], 1)
            self.assertEqual(result["artifact_entry_count"], 1)
            self.assertEqual(len(result["sha256"]), 64)
            self.assertTrue(all(result["expected_root_groups"].values()))
            self.assertLessEqual(len(result["largest_entries"]), 2)
            self.assertTrue(result["read_only"])
            self.assertFalse(result["deletion_performed"])
            self.assertFalse(result["launches_wps"])
            self.assertFalse(result["remote_git_required"])

    def test_summarize_sync_package_warns_when_missing(self):
        with TemporaryDirectory() as tmp:
            ok, result, errors = summarize_sync_package(workspace=tmp, package_path="missing.zip")

            self.assertFalse(ok)
            self.assertEqual(result["summary_status"], "warning")
            self.assertFalse(result["exists"])
            self.assertEqual(errors[0]["code"], "SYNC_PACKAGE_MISSING")


if __name__ == "__main__":
    unittest.main()
